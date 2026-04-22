"""
API REST v1 — RESTful, JSON, JWT/API key.
- Recursos: auth, incidents, categories, comments, votes, alert-subscriptions,
  notifications, plans, dashboard.
- Mezcla ORM (CRUD) + raw SQL (operaciones avanzadas / vistas / SP).
"""
import hashlib
import secrets
from datetime import datetime
from flask import Blueprint, request, jsonify, g, current_app
from werkzeug.security import check_password_hash, generate_password_hash
from sqlalchemy import text

from ..extensions import db
from ..models import (
    User, Role, Plan, Subscription, Incident, IncidentCategory,
    IncidentVote, IncidentComment, AlertSubscription, Notification, ApiKey,
)
from ..security import (
    valid_email, valid_username, valid_password, jwt_encode, jwt_required,
    api_role_required,
)

bp = Blueprint("api", __name__, url_prefix="/api/v1")


# ----------------------------- helpers ------------------------------------
def err(msg, code=400):
    return jsonify({"error": msg}), code

def ok(data, code=200):
    return jsonify(data), code

def paginate():
    try:
        page  = max(int(request.args.get("page", 1)), 1)
        limit = min(max(int(request.args.get("limit", 50)), 1),
                    current_app.config["API_MAX_LIMIT"])
    except ValueError:
        page, limit = 1, 50
    return page, limit, (page - 1) * limit


def ensure_default_role():
    role = Role.query.filter_by(name="user").first()
    if role:
        return role
    role = Role(name="user", description="Usuario ciudadano")
    db.session.add(role)
    db.session.flush()
    return role


def ensure_free_plan():
    plan = Plan.query.filter_by(name="Free").first()
    if plan:
        return plan
    plan = Plan(
        name="Free",
        price_monthly_usd=0,
        max_alerts_per_day=10,
        max_geo_fences=1,
        api_access=False,
        priority_support=False,
        features_json=["Mapa en tiempo real", "10 reportes por dia", "1 zona de alerta", "Validacion IA basica"],
    )
    db.session.add(plan)
    db.session.flush()
    return plan


# ============================== AUTH =====================================
@bp.post("/auth/login")
def api_login():
    body = request.get_json(silent=True) or {}
    email = (body.get("email") or "").lower()
    pw    = body.get("password") or ""
    if not valid_email(email) or not pw:
        return err("Credenciales requeridas")
    u = User.query.filter_by(email=email).first()
    if not u or not check_password_hash(u.password_hash, pw):
        return err("Credenciales invalidas", 401)
    return ok({
        "token": jwt_encode(u),
        "expires_in": current_app.config["JWT_EXP_MINUTES"] * 60,
        "user": {"id": u.id, "username": u.username, "role": u.role_name()},
    })

@bp.post("/auth/register")
def api_register():
    b = request.get_json(silent=True) or {}
    if not all([b.get("username"), b.get("email"), b.get("password"), b.get("full_name")]):
        return err("Campos faltantes")
    if not valid_username(b["username"]): return err("Username invalido")
    if not valid_email(b["email"]):       return err("Email invalido")
    if not valid_password(b["password"]): return err("Password debil")
    if User.query.filter((User.email == b["email"]) | (User.username == b["username"])).first():
        return err("Usuario existente", 409)
    role = ensure_default_role()
    u = User(
        username=b["username"], email=b["email"].lower(),
        password_hash=generate_password_hash(b["password"]),
        full_name=b["full_name"], role_id=role.id,
    )
    db.session.add(u)
    db.session.flush()
    free = ensure_free_plan()
    db.session.add(Subscription(user_id=u.id, plan_id=free.id, status="active"))
    db.session.commit()
    return ok({"id": u.id}, 201)


@bp.post("/auth/api-keys")
@jwt_required
def create_api_key():
    name = (request.get_json(silent=True) or {}).get("name", "default")
    raw  = secrets.token_urlsafe(32)
    h    = hashlib.sha256(raw.encode()).hexdigest()
    db.session.add(ApiKey(user_id=g.current_user_id, name=name, key_hash=h))
    db.session.commit()
    return ok({"api_key": raw, "name": name,
               "warning": "Guardalo: no se mostrara de nuevo"}, 201)


# ============================== INCIDENTS (CRUD) =========================
@bp.get("/incidents")
@jwt_required
def list_incidents():
    """Lista paginada via vista v_incidents_full + filtros."""
    page, limit, off = paginate()
    where, params = ["1=1"], {}
    if (cat := request.args.get("category_id")):
        where.append("category_id = :cat"); params["cat"] = cat
    if (st := request.args.get("status")):
        where.append("status = :st");      params["st"] = st
    if (dist := request.args.get("district_id")):
        where.append("district_id = :d");  params["d"] = dist
    if (sev := request.args.get("min_severity")):
        where.append("severity >= :sev");  params["sev"] = sev
    sql = f"""
        SELECT * FROM v_incidents_full
        WHERE {' AND '.join(where)}
        ORDER BY created_at DESC LIMIT :lim OFFSET :off
    """
    params.update(lim=limit, off=off)
    rows = [dict(r) for r in db.session.execute(text(sql), params).mappings()]
    total = db.session.execute(
        text(f"SELECT COUNT(*) c FROM v_incidents_full WHERE {' AND '.join(where)}"),
        {k: v for k, v in params.items() if k not in ('lim', 'off')}
    ).scalar()
    for r in rows:
        for k, v in list(r.items()):
            if hasattr(v, "isoformat"): r[k] = v.isoformat()
            elif hasattr(v, "__float__") and not isinstance(v, (int, bool)): r[k] = float(v)
    return ok({"data": rows, "page": page, "limit": limit, "total": total})


@bp.get("/incidents/<int:iid>")
@jwt_required
def get_incident(iid):
    row = db.session.execute(
        text("SELECT * FROM v_incidents_full WHERE incident_id = :id"),
        {"id": iid}
    ).mappings().first()
    if not row:
        return err("No encontrado", 404)
    d = {k: (v.isoformat() if hasattr(v, "isoformat")
             else (float(v) if hasattr(v, "__float__") and not isinstance(v, (int, bool)) else v))
         for k, v in dict(row).items()}
    return ok(d)


@bp.post("/incidents")
@jwt_required
def create_incident():
    """Crea via stored procedure (valida cuota plan + notifica suscriptores)."""
    b = request.get_json(silent=True) or {}
    required = ["category_id", "title", "description", "lat", "lng"]
    if not all(b.get(k) is not None for k in required):
        return err("Campos requeridos: " + ",".join(required))
    try:
        lat, lng = float(b["lat"]), float(b["lng"])
        if not (-90 <= lat <= 90 and -180 <= lng <= 180):
            return err("Coordenadas fuera de rango")
    except (TypeError, ValueError):
        return err("Coordenadas invalidas")
    if len(b["description"]) > 1000 or len(b["title"]) > 160:
        return err("Texto excede longitud")

    severity = int(b.get("severity") or 3)
    severity = max(1, min(5, severity))

    # Llamada al SP — devuelve el id por OUT param
    conn = db.session.connection()
    conn.exec_driver_sql("SET @new_id = 0")
    conn.exec_driver_sql(
        "CALL sp_create_incident(%s,%s,%s,%s,%s,%s,%s,%s,@new_id)",
        (g.current_user_id, b["category_id"], b.get("district_id"),
         b["title"], b["description"], lat, lng, severity)
    )
    new_id = conn.exec_driver_sql("SELECT @new_id").scalar()
    db.session.commit()
    return ok({"id": int(new_id)}, 201)


@bp.put("/incidents/<int:iid>")
@jwt_required
def update_incident(iid):
    inc = Incident.query.get(iid)
    if not inc:
        return err("No encontrado", 404)
    if inc.user_id != g.current_user_id and g.current_role not in ("admin", "moderator"):
        return err("No autorizado", 403)
    b = request.get_json(silent=True) or {}
    for f in ("title", "description", "category_id", "district_id"):
        if f in b: setattr(inc, f, b[f])
    if "lat" in b and "lng" in b:
        try:
            inc.lat, inc.lng = float(b["lat"]), float(b["lng"])
        except ValueError:
            return err("Coordenadas invalidas")
    if "severity" in b:
        inc.severity = max(1, min(5, int(b["severity"])))
    db.session.commit()
    return ok(inc.to_dict())


@bp.delete("/incidents/<int:iid>")
@jwt_required
def delete_incident(iid):
    inc = Incident.query.get(iid)
    if not inc:
        return err("No encontrado", 404)
    if inc.user_id != g.current_user_id and g.current_role != "admin":
        return err("No autorizado", 403)
    db.session.delete(inc)
    db.session.commit()
    return ok({"deleted": True})


@bp.post("/incidents/<int:iid>/verify")
@jwt_required
@api_role_required("moderator", "admin")
def verify_incident(iid):
    new_status = (request.get_json(silent=True) or {}).get("status", "verified")
    try:
        db.session.execute(
            text("CALL sp_verify_incident(:m, :i, :s)"),
            {"m": g.current_user_id, "i": iid, "s": new_status}
        )
        db.session.commit()
        return ok({"id": iid, "status": new_status})
    except Exception as e:
        db.session.rollback()
        return err(str(e), 400)


# ----------------------------- nearby (raw + SP) -------------------------
@bp.get("/incidents/nearby")
@jwt_required
def nearby():
    try:
        lat = float(request.args["lat"]); lng = float(request.args["lng"])
        radius = float(request.args.get("radius_km", 5))
        limit  = min(int(request.args.get("limit", 50)), 200)
    except (KeyError, ValueError):
        return err("lat, lng, radius_km requeridos")
    rows = db.session.execute(
        text("CALL sp_nearby_incidents(:la,:ln,:r,:l)"),
        {"la": lat, "ln": lng, "r": radius, "l": limit}
    ).mappings().all()
    out = []
    for r in rows:
        d = dict(r)
        for k, v in d.items():
            if hasattr(v, "isoformat"): d[k] = v.isoformat()
            elif hasattr(v, "__float__") and not isinstance(v, (int, bool)): d[k] = float(v)
        out.append(d)
    return ok({"data": out, "count": len(out)})


# ============================== VOTES ====================================
@bp.post("/incidents/<int:iid>/vote")
@jwt_required
def vote(iid):
    v = (request.get_json(silent=True) or {}).get("vote")
    if v not in (1, -1):
        return err("vote debe ser 1 o -1")
    existing = IncidentVote.query.filter_by(incident_id=iid, user_id=g.current_user_id).first()
    if existing:
        existing.vote = v
    else:
        db.session.add(IncidentVote(incident_id=iid, user_id=g.current_user_id, vote=v))
    db.session.commit()
    return ok({"voted": v})


# ============================== COMMENTS =================================
@bp.get("/incidents/<int:iid>/comments")
@jwt_required
def list_comments(iid):
    rows = db.session.execute(text("""
        SELECT c.id, c.body, c.created_at, u.username
          FROM incident_comments c JOIN users u ON u.id=c.user_id
         WHERE c.incident_id = :i ORDER BY c.created_at DESC LIMIT 200
    """), {"i": iid}).mappings().all()
    return ok([{**dict(r), "created_at": r["created_at"].isoformat()} for r in rows])

@bp.post("/incidents/<int:iid>/comments")
@jwt_required
def add_comment(iid):
    body = (request.get_json(silent=True) or {}).get("body", "").strip()
    if not body or len(body) > 1000:
        return err("Comentario invalido")
    c = IncidentComment(incident_id=iid, user_id=g.current_user_id, body=body)
    db.session.add(c); db.session.commit()
    return ok({"id": c.id}, 201)


# ============================== ALERT SUBSCRIPTIONS (geo-fence premium) ==
@bp.get("/alert-subscriptions")
@jwt_required
def list_alert_subs():
    rows = AlertSubscription.query.filter_by(user_id=g.current_user_id, active=True).all()
    return ok([{
        "id": r.id, "category_id": r.category_id,
        "lat": float(r.center_lat), "lng": float(r.center_lng),
        "radius_km": float(r.radius_km), "min_severity": r.min_severity,
    } for r in rows])

@bp.post("/alert-subscriptions")
@jwt_required
def create_alert_sub():
    b = request.get_json(silent=True) or {}
    # Verifica cuota del plan
    cap = db.session.execute(text("""
        SELECT COALESCE(pl.max_geo_fences,1) cap
          FROM users u
          LEFT JOIN subscriptions s ON s.user_id=u.id AND s.status='active'
          LEFT JOIN plans pl ON pl.id=s.plan_id
         WHERE u.id=:uid
    """), {"uid": g.current_user_id}).scalar() or 1
    used = AlertSubscription.query.filter_by(user_id=g.current_user_id, active=True).count()
    if used >= cap:
        return err(f"Alcanzaste el limite de {cap} geo-fences. Actualiza tu plan.", 402)

    sub = AlertSubscription(
        user_id=g.current_user_id,
        category_id=b.get("category_id"),
        center_lat=float(b["lat"]), center_lng=float(b["lng"]),
        radius_km=float(b.get("radius_km", 5)),
        min_severity=int(b.get("min_severity", 1)),
    )
    db.session.add(sub); db.session.commit()
    return ok({"id": sub.id}, 201)

@bp.delete("/alert-subscriptions/<int:sid>")
@jwt_required
def delete_alert_sub(sid):
    sub = AlertSubscription.query.get(sid)
    if not sub or sub.user_id != g.current_user_id:
        return err("No encontrado", 404)
    sub.active = False
    db.session.commit()
    return ok({"deleted": True})


# ============================== NOTIFICATIONS ============================
@bp.get("/notifications")
@jwt_required
def list_notifs():
    rows = (Notification.query
            .filter_by(user_id=g.current_user_id)
            .order_by(Notification.created_at.desc()).limit(100).all())
    return ok([{
        "id": n.id, "type": n.type, "message": n.message,
        "is_read": n.is_read, "incident_id": n.incident_id,
        "created_at": n.created_at.isoformat()
    } for n in rows])

@bp.post("/notifications/<int:nid>/read")
@jwt_required
def read_notif(nid):
    n = Notification.query.get(nid)
    if not n or n.user_id != g.current_user_id:
        return err("No encontrado", 404)
    n.is_read = True; db.session.commit()
    return ok({"ok": True})


# ============================== CATÁLOGOS / PLANES =======================
@bp.get("/categories")
def categories():
    rows = IncidentCategory.query.all()
    return ok([{"id": c.id, "name": c.name, "icon": c.icon,
                "color": c.color_hex, "default_severity": c.default_severity} for c in rows])

@bp.get("/plans")
def plans():
    return ok([{
        "id": p.id, "name": p.name, "price_usd": float(p.price_monthly_usd),
        "max_alerts_per_day": p.max_alerts_per_day,
        "max_geo_fences": p.max_geo_fences, "api_access": bool(p.api_access),
        "priority_support": bool(p.priority_support), "features": p.features_json,
    } for p in Plan.query.all()])

@bp.post("/plans/upgrade")
@jwt_required
def upgrade_plan():
    b = request.get_json(silent=True) or {}
    db.session.execute(text("CALL sp_upgrade_plan(:u,:p,:m)"),
                       {"u": g.current_user_id, "p": b["plan_id"], "m": int(b.get("months", 1))})
    db.session.commit()
    return ok({"upgraded": True})


# ============================== DASHBOARD / ANALÍTICA ====================
@bp.get("/dashboard/summary")
@jwt_required
def dashboard_summary():
    """Métricas agregadas con raw SQL — alimenta el panel y Power BI."""
    sql = text("""
        SELECT
          (SELECT COUNT(*) FROM incidents) AS total_incidents,
          (SELECT COUNT(*) FROM incidents WHERE status='verified') AS verified,
          (SELECT COUNT(*) FROM incidents WHERE created_at >= NOW() - INTERVAL 24 HOUR) AS last_24h,
          (SELECT COUNT(*) FROM users) AS total_users,
          (SELECT COUNT(*) FROM subscriptions WHERE status='active' AND plan_id>1) AS paying_users
    """)
    row = db.session.execute(sql).mappings().first()
    by_cat = db.session.execute(text("""
        SELECT c.name AS category, COUNT(i.id) AS total
          FROM incident_categories c
          LEFT JOIN incidents i ON i.category_id=c.id
            AND i.created_at >= NOW() - INTERVAL 30 DAY
         GROUP BY c.name ORDER BY total DESC
    """)).mappings().all()
    hotspots = db.session.execute(text("SELECT * FROM v_hotspots ORDER BY incidents_30d DESC LIMIT 20")).mappings().all()
    return ok({
        "kpis": dict(row),
        "by_category_30d": [dict(r) for r in by_cat],
        "hotspots": [{k: (float(v) if hasattr(v, "__float__") and not isinstance(v, int) else
                          (v.isoformat() if hasattr(v, "isoformat") else v))
                      for k, v in dict(r).items()} for r in hotspots],
    })


@bp.get("/dashboard/daily")
@jwt_required
def dashboard_daily():
    rows = db.session.execute(text("""
        SELECT * FROM v_incidents_daily_stats
        WHERE day >= CURDATE() - INTERVAL 30 DAY
        ORDER BY day DESC
    """)).mappings().all()
    out = []
    for r in rows:
        d = dict(r)
        d["day"] = d["day"].isoformat() if d.get("day") else None
        for k, v in d.items():
            if hasattr(v, "__float__") and not isinstance(v, (int, bool)):
                d[k] = float(v)
        out.append(d)
    return ok(out)


# ============================== HEALTH ===================================
@bp.get("/health")
def health():
    try:
        db.session.execute(text("SELECT 1"))
        return ok({"status": "ok", "db": "up", "time": datetime.utcnow().isoformat()})
    except Exception as e:
        return err(f"DB down: {e}", 503)

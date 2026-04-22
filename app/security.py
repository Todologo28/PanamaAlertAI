"""Helpers de seguridad: CSRF, cabeceras, rate limit, TOTP, JWT."""
import os
import re
import time
import secrets
import hashlib
import functools
import threading
from collections import defaultdict, deque
from datetime import datetime, timedelta
from pathlib import Path

import jwt
import pyotp
from sqlalchemy import text
from flask import g, request, session, jsonify, redirect, url_for, flash, current_app, render_template
from cryptography.fernet import Fernet, InvalidToken

from .extensions import db
from .models import AuthAttempt, User, ApiKey, ActiveSession


# ----------------------------- validaciones -------------------------------
EMAIL_RE = re.compile(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$')
USERNAME_RE = re.compile(r'^[a-zA-Z0-9_.-]{3,20}$')
_REQUEST_LOCK = threading.Lock()
_REQUEST_WINDOWS = defaultdict(lambda: {"burst": deque(), "minute": deque()})
_BLOCKED_IPS = {}
_SESSION_SENDER_BLOCKED = {}

def valid_email(v): return bool(v and EMAIL_RE.match(v))
def valid_username(v): return bool(v and USERNAME_RE.match(v))
def valid_password(v):
    return bool(v and len(v) >= 8 and re.search(r"[A-Z]", v)
                and re.search(r"[a-z]", v) and re.search(r"\d", v))

def hash_password(password):
    """Hashea contraseña con Werkzeug."""
    from werkzeug.security import generate_password_hash
    return generate_password_hash(password)

def verify_password(password, hash):
    """Verifica contraseña contra hash."""
    from werkzeug.security import check_password_hash
    return check_password_hash(hash, password)

def hash_api_key(key):
    """Hashea API key con SHA-256."""
    return hashlib.sha256(key.encode()).hexdigest()


# ----------------------------- TOTP ---------------------------------------
def _fernet():
    key = current_app.config.get("TOTP_ENC_KEY")
    if not key:
        return None
    try:
        return Fernet(key)
    except (ValueError, TypeError):
        return None

def encrypt_totp(secret: str) -> str:
    f = _fernet()
    if not f:
        return secret
    return "enc:" + f.encrypt(secret.encode()).decode()

def decrypt_totp(value: str) -> str | None:
    if not value:
        return None
    if value.startswith("enc:"):
        f = _fernet()
        if not f:
            return None
        try:
            return f.decrypt(value[4:].encode()).decode()
        except InvalidToken:
            return None
    return value

def new_totp_secret() -> str:
    return pyotp.random_base32()

def verify_totp(secret: str, code: str) -> bool:
    code = re.sub(r"\D", "", code or "")
    if len(code) != 6:
        return False
    return pyotp.TOTP(secret).verify(code, valid_window=2)


# ----------------------------- CSRF ---------------------------------------
def get_csrf_token():
    token = session.get("_csrf")
    if not token:
        token = secrets.token_urlsafe(32)
        session["_csrf"] = token
    return token


def reset_session_state(**entries):
    session.clear()
    session["_sid"] = secrets.token_urlsafe(24)
    session["_issued_at"] = int(time.time())
    session["_csrf"] = secrets.token_urlsafe(32)
    for key, value in entries.items():
        session[key] = value
    return session

def _has_api_auth_header():
    auth = request.headers.get("Authorization", "")
    return auth.startswith("Bearer ") or bool(request.headers.get("X-API-Key"))

def _same_origin_request():
    origin = request.headers.get("Origin")
    referer = request.headers.get("Referer")
    host_url = request.host_url.rstrip("/")
    if origin:
        return origin.rstrip("/") == host_url
    if referer:
        return referer.startswith(host_url + "/") or referer == host_url
    return not request.path.startswith("/api/")

def csrf_protect():
    if request.method not in ("POST", "PUT", "DELETE"):
        return None
    is_api_style = request.path.startswith("/api/") or request.is_json or request.headers.get("X-Requested-With") == "XMLHttpRequest"
    if request.path.startswith("/api/") and _has_api_auth_header():
        return None
    if is_api_style and not _same_origin_request():
        if is_api_style:
            return jsonify({"error": "Origen no permitido"}), 403
        flash("Origen no permitido.", "danger")
        return redirect(request.url)
    token = (request.headers.get("X-CSRF-Token")
             or (request.form.get("csrf_token") if request.form else None))
    if not token and request.is_json:
        token = (request.get_json(silent=True) or {}).get("csrf_token")
    if not token or token != session.get("_csrf"):
        # API-style requests get JSON; web forms get a flash + redirect
        if request.is_json or request.headers.get("X-Requested-With") == "XMLHttpRequest":
            return jsonify({"error": "CSRF token invalido"}), 400
        flash("Sesion expirada. Intenta de nuevo.", "danger")
        return redirect(request.url)
    return None


# ----------------------------- cabeceras / CSP ----------------------------
def set_context():
    g.csp_nonce = secrets.token_urlsafe(16)

def apply_headers(response):
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("X-Frame-Options", "DENY")
    response.headers.setdefault("Referrer-Policy", "no-referrer")
    response.headers.setdefault("Permissions-Policy", "geolocation=(self), camera=(), microphone=(), payment=()")
    nonce = getattr(g, "csp_nonce", "")
    connect_src = [
        "'self'",
        "https://cdnjs.cloudflare.com",
        "https://cdn.jsdelivr.net",
        "https://unpkg.com",
        "https://nominatim.openstreetmap.org",
        "https://*.basemaps.cartocdn.com",
    ]
    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; base-uri 'self'; object-src 'none'; "
        "frame-ancestors 'none'; img-src 'self' data: https:; "
        "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com "
        "https://cdn.jsdelivr.net https://unpkg.com https://cdnjs.cloudflare.com; "
        "font-src 'self' https://fonts.gstatic.com; "
        f"script-src 'self' 'nonce-{nonce}' https://cdn.jsdelivr.net "
        "https://unpkg.com https://cdnjs.cloudflare.com; "
        f"connect-src {' '.join(connect_src)}; worker-src 'self';"
    )
    is_secure_origin = (
        request.is_secure
        or request.headers.get("X-Forwarded-Proto", "").startswith("https")
        or request.host.split(":")[0] in {"localhost", "127.0.0.1"}
    )
    response.headers.setdefault("Cross-Origin-Resource-Policy", "same-origin")
    response.headers.setdefault("X-Permitted-Cross-Domain-Policies", "none")
    if is_secure_origin:
        response.headers.setdefault("Cross-Origin-Opener-Policy", "same-origin")
        response.headers.setdefault("Origin-Agent-Cluster", "?1")
        response.headers.setdefault(
            "Strict-Transport-Security",
            "max-age=63072000; includeSubDomains; preload")
    if request.path.startswith(("/login", "/token", "/registro", "/setup-2fa", "/recuperar-acceso")):
        response.headers["Cache-Control"] = "no-store, max-age=0"
        response.headers["Pragma"] = "no-cache"
    return response


# ----------------------------- rate limit (DB) ----------------------------
def client_ip():
    fwd = request.headers.get("X-Forwarded-For", "")
    if fwd:
        return fwd.split(",")[0].strip()
    return request.remote_addr or "unknown"


def _security_events_file():
    return Path(current_app.config["SECURITY_EVENTS_FILE"])


def _load_security_events():
    path = _security_events_file()
    if not path.exists():
        return []
    try:
        import json
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return []


def _save_security_events(events):
    path = _security_events_file()
    path.parent.mkdir(parents=True, exist_ok=True)
    import json
    path.write_text(
        json.dumps(events[-current_app.config.get("SECURITY_MAX_EVENTS", 1000):], ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def record_security_event(reason: str, **meta):
    events = _load_security_events()
    event = {
        "created_at": datetime.utcnow().isoformat(),
        "ip": meta.get("ip") or client_ip(),
        "path": meta.get("path") or request.path,
        "method": meta.get("method") or request.method,
        "reason": reason,
        "user_agent": (meta.get("user_agent") or request.headers.get("User-Agent", ""))[:512],
        "meta": {k: v for k, v in meta.items() if k not in {"ip", "path", "method", "user_agent"}},
    }
    events.append(event)
    _save_security_events(events)
    return event


def list_security_events(limit=100):
    events = _load_security_events()
    return list(reversed(events[-max(1, min(int(limit), 500)):]))


def ensure_active_session_table():
    db.session.execute(text("""
        CREATE TABLE IF NOT EXISTS active_sessions (
            id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
            session_id VARCHAR(96) NOT NULL UNIQUE,
            user_id INT UNSIGNED NOT NULL,
            ip VARCHAR(64) NULL,
            user_agent VARCHAR(512) NULL,
            created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
            last_seen_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
            expires_at DATETIME NOT NULL,
            CONSTRAINT fk_active_session_user FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
            INDEX idx_active_session_user (user_id),
            INDEX idx_active_session_expires (expires_at),
            INDEX idx_active_session_last_seen (last_seen_at)
        ) ENGINE=InnoDB;
    """))
    db.session.commit()


def _active_session_expiry():
    idle_minutes = int(current_app.config.get("ACTIVE_SESSION_IDLE_MINUTES", 60))
    return datetime.utcnow() + timedelta(minutes=max(1, idle_minutes))


def prune_expired_active_sessions():
    now = datetime.utcnow()
    (db.session.query(ActiveSession)
     .filter((ActiveSession.expires_at <= now) | (ActiveSession.last_seen_at <= now - timedelta(minutes=max(1, int(current_app.config.get("ACTIVE_SESSION_IDLE_MINUTES", 60))))))
     .delete(synchronize_session=False))
    db.session.commit()


def count_active_sessions():
    prune_expired_active_sessions()
    return db.session.query(ActiveSession).count()


def can_open_new_session():
    return count_active_sessions() < int(current_app.config.get("MAX_ACTIVE_SESSIONS", 5000))


def register_active_session(user_id: int):
    sid = session.get("_sid")
    if not sid or not user_id:
        return None
    expires_at = _active_session_expiry()
    existing = ActiveSession.query.filter_by(session_id=sid).first()
    if existing:
        existing.user_id = user_id
        existing.ip = client_ip()
        existing.user_agent = (request.headers.get("User-Agent", "") or "")[:512]
        existing.last_seen_at = datetime.utcnow()
        existing.expires_at = expires_at
    else:
        db.session.add(ActiveSession(
            session_id=sid,
            user_id=user_id,
            ip=client_ip(),
            user_agent=(request.headers.get("User-Agent", "") or "")[:512],
            expires_at=expires_at,
        ))
    db.session.commit()
    return sid


def touch_active_session():
    sid = session.get("_sid")
    if not sid or "user_id" not in session:
        return False
    row = ActiveSession.query.filter_by(session_id=sid, user_id=session.get("user_id")).first()
    if not row:
        return False
    row.last_seen_at = datetime.utcnow()
    row.expires_at = _active_session_expiry()
    db.session.commit()
    return True


def release_active_session(session_id=None):
    sid = session_id or session.get("_sid")
    if not sid:
        return
    ActiveSession.query.filter_by(session_id=sid).delete(synchronize_session=False)
    db.session.commit()


def sync_active_session():
    if "user_id" not in session:
        return None
    if touch_active_session():
        return None
    reset_session_state()
    if request.path.startswith("/api/"):
        return jsonify({"error": "Sesion expirada o no activa"}), 401
    flash("Tu sesion expiro o ya no esta activa. Vuelve a iniciar sesion.", "danger")
    return redirect(url_for("auth.login"))


def count_session_creation_attempts(identifier=None, window_seconds=None):
    window = int(window_seconds or current_app.config.get("SESSION_CREATION_WINDOW_SECONDS", 24 * 60 * 60))
    ident = identifier or f"ip:{client_ip()}"
    since = datetime.utcnow() - timedelta(seconds=max(60, window))
    return (db.session.query(AuthAttempt)
            .filter_by(kind="session_open", identifier=ident)
            .filter(AuthAttempt.created_at >= since)
            .count())


def record_session_creation_attempt(success=False):
    ident = f"ip:{client_ip()}"
    db.session.add(AuthAttempt(
        kind="session_open",
        identifier=ident,
        ip=client_ip(),
        success=success,
    ))
    db.session.commit()
    return count_session_creation_attempts(ident)


def _session_sender_block_response(attempts=None, retry_after_seconds=None):
    limit = int(current_app.config.get("SESSION_CREATION_LIMIT", 5000))
    attempts = int(attempts or count_session_creation_attempts())
    retry_after = max(60, int(retry_after_seconds or current_app.config.get("SESSION_CREATION_BLOCK_MINUTES", 180) * 60))
    if request.path.startswith("/api/"):
        resp = jsonify({
            "error": "Tu origen fue bloqueado temporalmente por abuso de sesiones.",
            "attempts": attempts,
            "max_attempts": limit,
            "retry_after": retry_after,
        })
        resp.status_code = 429
        resp.headers["Retry-After"] = str(retry_after)
        return resp
    return render_template(
        "session_blocked.html",
        attempts=attempts,
        max_attempts=limit,
        retry_after_minutes=max(1, retry_after // 60),
    ), 429


def block_session_sender(attempts=None):
    ip = client_ip()
    ident = f"ip:{ip}"
    block_minutes = int(current_app.config.get("SESSION_CREATION_BLOCK_MINUTES", 180))
    blocked_until = datetime.utcnow() + timedelta(minutes=max(1, block_minutes))
    _SESSION_SENDER_BLOCKED[ident] = blocked_until
    record_security_event(
        "session_creation_block",
        ip=ip,
        attempts=attempts or count_session_creation_attempts(ident),
        max_attempts=int(current_app.config.get("SESSION_CREATION_LIMIT", 5000)),
        blocked_until=blocked_until.isoformat(),
    )
    retry_after = max(60, int((blocked_until - datetime.utcnow()).total_seconds()))
    return _session_sender_block_response(attempts=attempts, retry_after_seconds=retry_after)


def guard_session_creation_abuse():
    ident = f"ip:{client_ip()}"
    now = datetime.utcnow()
    blocked_until = _SESSION_SENDER_BLOCKED.get(ident)
    if blocked_until and blocked_until > now:
        retry_after = max(60, int((blocked_until - now).total_seconds()))
        return _session_sender_block_response(retry_after_seconds=retry_after)
    if blocked_until and blocked_until <= now:
        _SESSION_SENDER_BLOCKED.pop(ident, None)

    attempts = count_session_creation_attempts(ident)
    limit = int(current_app.config.get("SESSION_CREATION_LIMIT", 5000))
    if attempts > limit:
        return block_session_sender(attempts=attempts)
    return None


def _prune_window(queue_obj, now_ts, seconds):
    while queue_obj and (now_ts - queue_obj[0]) > seconds:
        queue_obj.popleft()


def guard_request_abuse():
    if request.endpoint == "static":
        return None

    ip = client_ip()
    now_ts = time.time()
    block_seconds = current_app.config.get("BLOCK_SECONDS", 900)
    burst_limit = current_app.config.get("REQUESTS_PER_10S", 45)
    minute_limit = current_app.config.get("REQUESTS_PER_MINUTE", 180)

    with _REQUEST_LOCK:
        blocked_until = _BLOCKED_IPS.get(ip)
        if blocked_until and blocked_until > now_ts:
            retry_after = max(1, int(blocked_until - now_ts))
            record_security_event(
                "blocked_ip_request",
                ip=ip,
                retry_after=retry_after,
                endpoint=request.endpoint,
            )
            resp = jsonify({
                "error": "Demasiadas solicitudes. IP bloqueada temporalmente.",
                "ip": ip,
                "retry_after": retry_after,
            })
            resp.status_code = 429
            resp.headers["Retry-After"] = str(retry_after)
            return resp
        if blocked_until and blocked_until <= now_ts:
            _BLOCKED_IPS.pop(ip, None)

        windows = _REQUEST_WINDOWS[ip]
        _prune_window(windows["burst"], now_ts, 10)
        _prune_window(windows["minute"], now_ts, 60)
        windows["burst"].append(now_ts)
        windows["minute"].append(now_ts)

        if len(windows["burst"]) > burst_limit or len(windows["minute"]) > minute_limit:
            blocked_until = now_ts + block_seconds
            _BLOCKED_IPS[ip] = blocked_until
            record_security_event(
                "rate_limit_block",
                ip=ip,
                endpoint=request.endpoint,
                burst_count=len(windows["burst"]),
                minute_count=len(windows["minute"]),
                blocked_until=datetime.utcfromtimestamp(blocked_until).isoformat(),
            )
            resp = jsonify({
                "error": "Actividad sospechosa detectada. IP bloqueada temporalmente.",
                "ip": ip,
                "retry_after": block_seconds,
            })
            resp.status_code = 429
            resp.headers["Retry-After"] = str(block_seconds)
            return resp
    return None

def rate_limited(kind: str, identifier: str, max_attempts: int, window_seconds: int) -> bool:
    since = datetime.utcnow() - timedelta(seconds=window_seconds)
    n = (db.session.query(AuthAttempt)
         .filter_by(kind=kind, identifier=identifier, success=False)
         .filter(AuthAttempt.created_at >= since).count())
    return n >= max_attempts

def record_attempt(kind: str, identifier: str, success: bool):
    db.session.add(AuthAttempt(
        kind=kind, identifier=identifier, ip=client_ip(), success=success,
    ))
    db.session.commit()


# ----------------------------- sesión web ---------------------------------
def login_required(fn):
    @functools.wraps(fn)
    def wrapper(*a, **kw):
        if "user_id" not in session:
            if request.path.startswith("/api/"):
                return jsonify({"error": "Autenticacion requerida"}), 401
            flash("Inicia sesión", "danger")
            return redirect(url_for("auth.login"))
        return fn(*a, **kw)
    return wrapper


def role_required(*roles):
    def deco(fn):
        @functools.wraps(fn)
        def wrapper(*a, **kw):
            if session.get("role") not in roles:
                return jsonify({"error": "No autorizado"}), 403
            return fn(*a, **kw)
        return wrapper
    return deco


# ----------------------------- JWT para API -------------------------------
def jwt_encode(user: User) -> str:
    payload = {
        "sub": user.id,
        "username": user.username,
        "role": user.role_name(),
        "iat": int(time.time()),
        "exp": int(time.time()) + current_app.config["JWT_EXP_MINUTES"] * 60,
    }
    return jwt.encode(payload, current_app.config["JWT_SECRET"], algorithm="HS256")

def jwt_decode(token: str) -> dict | None:
    try:
        return jwt.decode(token, current_app.config["JWT_SECRET"], algorithms=["HS256"])
    except jwt.PyJWTError:
        return None

def _api_key_lookup(raw: str) -> User | None:
    h = hashlib.sha256(raw.encode()).hexdigest()
    k = ApiKey.query.filter_by(key_hash=h, revoked_at=None).first()
    if not k:
        return None
    k.last_used_at = datetime.utcnow()
    db.session.commit()
    return User.query.get(k.user_id)

def jwt_required(fn):
    @functools.wraps(fn)
    def wrapper(*a, **kw):
        auth = request.headers.get("Authorization", "")
        if auth.startswith("Bearer "):
            payload = jwt_decode(auth[7:])
            if not payload:
                return jsonify({"error": "Token invalido"}), 401
            g.current_user_id = payload["sub"]
            g.current_role = payload.get("role", "user")
            return fn(*a, **kw)
        api_key = request.headers.get("X-API-Key")
        if api_key:
            user = _api_key_lookup(api_key)
            if not user:
                return jsonify({"error": "API key invalida"}), 401
            g.current_user_id = user.id
            g.current_role = user.role_name()
            return fn(*a, **kw)
        return jsonify({"error": "Autenticacion requerida"}), 401
    return wrapper


def api_role_required(*roles):
    def deco(fn):
        @functools.wraps(fn)
        def wrapper(*a, **kw):
            if getattr(g, "current_role", None) not in roles:
                return jsonify({"error": "No autorizado"}), 403
            return fn(*a, **kw)
        return wrapper
    return deco

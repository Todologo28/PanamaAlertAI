"""Rutas web de autenticación: registro, login, 2FA TOTP."""
from datetime import datetime
from flask import Blueprint, render_template, request, redirect, url_for, session, flash, current_app
from sqlalchemy.exc import IntegrityError
from werkzeug.security import generate_password_hash, check_password_hash
import pyotp

from ..extensions import db
from ..models import User, Role, Subscription, Plan
from ..security import (
    valid_email, valid_username, valid_password,
    encrypt_totp, decrypt_totp, new_totp_secret, verify_totp,
    rate_limited, record_attempt, client_ip, login_required, reset_session_state,
    can_open_new_session, register_active_session, release_active_session, prune_expired_active_sessions,
    count_active_sessions, record_session_creation_attempt, block_session_sender,
)

bp = Blueprint("auth", __name__)


def _render_capacity_blocked():
    max_sessions = int(current_app.config.get("MAX_ACTIVE_SESSIONS", 5000))
    active_sessions = count_active_sessions()
    return render_template(
        "session_capacity.html",
        active_sessions=active_sessions,
        max_sessions=max_sessions,
    ), 503


def _ensure_default_role():
    role = Role.query.filter_by(name="user").first()
    if role:
        return role
    role = Role(name="user", description="Usuario ciudadano")
    db.session.add(role)
    db.session.flush()
    return role


def _ensure_free_plan():
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


@bp.route("/registro", methods=["GET", "POST"])
def registro():
    if request.method == "POST":
        f = request.form
        username = f.get("username", "").strip()
        email    = f.get("correo", "").strip().lower()
        password = f.get("contrasena", "")
        confirm  = f.get("confirmar_contrasena", "")
        full     = " ".join([f.get("nombre", ""), f.get("apellido", "")]).strip()
        accepted_terms = f.get("terms") in ("on", "true", "1", "yes")

        if not all([username, email, password, confirm, full]):
            flash("Todos los campos obligatorios", "danger")
            return redirect(url_for("auth.registro"))
        if not accepted_terms:
            flash("Debes aceptar los terminos de servicio", "danger")
            return redirect(url_for("auth.registro"))
        if not valid_username(username):
            flash("Usuario inválido (3-20 caracteres)", "danger")
            return redirect(url_for("auth.registro"))
        if not valid_email(email):
            flash("Correo inválido", "danger")
            return redirect(url_for("auth.registro"))
        if password != confirm:
            flash("Las contraseñas no coinciden", "danger")
            return redirect(url_for("auth.registro"))
        if not valid_password(password):
            flash("Contraseña débil: 8+, mayus, minus, numero", "danger")
            return redirect(url_for("auth.registro"))

        if User.query.filter((User.email == email) | (User.username == username)).first():
            flash("Usuario o correo ya registrado", "danger")
            return redirect(url_for("auth.registro"))

        try:
            role = _ensure_default_role()
            free = _ensure_free_plan()
            secret = new_totp_secret()
            u = User(
                username=username, email=email,
                password_hash=generate_password_hash(password),
                full_name=full, role_id=role.id,
                cedula=(f.get("cedula") or "").strip() or None,
                phone=(f.get("telefono") or "").strip() or None,
                totp_secret_enc=encrypt_totp(secret),
            )
            db.session.add(u)
            db.session.flush()
            db.session.add(Subscription(user_id=u.id, plan_id=free.id, status="active"))
            db.session.commit()
        except IntegrityError:
            db.session.rollback()
            flash("El usuario o correo ya existe. Prueba con otros datos.", "danger")
            return redirect(url_for("auth.registro"))
        except Exception:
            db.session.rollback()
            flash("No se pudo completar el registro en este momento.", "danger")
            return redirect(url_for("auth.registro"))

        reset_session_state(pending_user_id=u.id, setup_email=email)
        flash("Registro ok. Configura tu token 2FA.", "success")
        return redirect(url_for("auth.setup_2fa"))

    return render_template("registro.html")


@bp.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        identifier = (request.form.get("usuario") or "").strip().lower()
        password = request.form.get("contrasena") or ""
        ip = client_ip()

        if not identifier or not password:
            flash("Datos inválidos", "danger")
            return redirect(url_for("auth.login"))

        if rate_limited("login", f"ip:{ip}", 10, 900) or rate_limited("login", f"user:{identifier}", 5, 900):
            flash("Demasiados intentos. Espera unos minutos.", "danger")
            return redirect(url_for("auth.login"))

        # Accept username or email
        u = User.query.filter(
            (User.email == identifier) | (User.username == identifier)
        ).first()
        if not u or not check_password_hash(u.password_hash, password) or not u.is_active:
            record_attempt("login", f"ip:{ip}", False)
            record_attempt("login", f"user:{identifier}", False)
            flash("Credenciales incorrectas", "danger")
            return redirect(url_for("auth.login"))

        record_attempt("login", f"user:{identifier}", True)
        reset_session_state(pending_user_id=u.id, pending_email=u.email)
        if not u.totp_enabled or not u.totp_secret_enc:
            session["setup_email"] = u.email
            return redirect(url_for("auth.setup_2fa"))
        return redirect(url_for("auth.token"))

    return render_template("login.html")


@bp.route("/recuperar-acceso", methods=["GET", "POST"])
def recover_access():
    if request.method == "POST":
        identifier = (request.form.get("identifier") or "").strip().lower()
        code = (request.form.get("token") or "").strip()
        password = request.form.get("password") or ""
        confirm = request.form.get("confirm_password") or ""

        if not all([identifier, code, password, confirm]):
            flash("Completa todos los campos para recuperar el acceso", "danger")
            return redirect(url_for("auth.recover_access"))

        user = User.query.filter(
            (User.email == identifier) | (User.username == identifier)
        ).first()
        if not user or not user.is_active:
            flash("No encontre una cuenta activa con esos datos", "danger")
            return redirect(url_for("auth.recover_access"))

        if password != confirm:
            flash("Las contraseñas no coinciden", "danger")
            return redirect(url_for("auth.recover_access"))

        if not valid_password(password):
            flash("Contraseña débil: 8+, mayus, minus, numero", "danger")
            return redirect(url_for("auth.recover_access"))

        secret = decrypt_totp(user.totp_secret_enc)
        if not secret or not verify_totp(secret, code):
            record_attempt("reset", f"user:{user.email}", False)
            flash("Token 2FA inválido", "danger")
            return redirect(url_for("auth.recover_access"))

        user.password_hash = generate_password_hash(password)
        user.last_login_at = datetime.utcnow()
        db.session.commit()
        record_attempt("reset", f"user:{user.email}", True)

        reset_session_state(pending_user_id=user.id, pending_email=user.email)
        flash("Contraseña actualizada. Verifica tu token para entrar.", "success")
        return redirect(url_for("auth.token"))

    return render_template("recover_access.html")


@bp.route("/setup-2fa")
def setup_2fa():
    email = session.get("setup_email")
    if not email:
        return redirect(url_for("auth.login"))
    u = User.query.filter_by(email=email).first()
    if not u:
        return redirect(url_for("auth.login"))
    secret = decrypt_totp(u.totp_secret_enc)
    if not secret:
        secret = new_totp_secret()
        u.totp_secret_enc = encrypt_totp(secret)
        db.session.commit()
    otpauth = pyotp.TOTP(secret).provisioning_uri(name=email, issuer_name="PanamaAlert")
    return render_template("setup_2fa.html", secret=secret, otpauth=otpauth)


@bp.route("/token", methods=["GET", "POST"])
def token():
    pending = session.get("pending_user_id")
    if not pending:
        return redirect(url_for("auth.login"))
    u = User.query.get(pending)
    if not u:
        reset_session_state()
        return redirect(url_for("auth.login"))

    if request.method == "POST":
        session_attempts = record_session_creation_attempt(success=False)
        max_session_attempts = int(current_app.config.get("SESSION_CREATION_LIMIT", 5000))
        if session_attempts > max_session_attempts:
            return block_session_sender(attempts=session_attempts)

        code = request.form.get("token", "")
        ip = client_ip()
        if rate_limited("token", f"user:{u.email}", 5, 600):
            flash("Demasiados intentos. Espera.", "danger")
            return redirect(url_for("auth.token"))
        secret = decrypt_totp(u.totp_secret_enc)
        if not secret or not verify_totp(secret, code):
            record_attempt("token", f"user:{u.email}", False)
            flash("Token inválido", "danger")
            return redirect(url_for("auth.token"))

        record_attempt("token", f"user:{u.email}", True)
        if not u.totp_enabled:
            u.totp_enabled = True
        u.last_login_at = datetime.utcnow()
        db.session.commit()

        prune_expired_active_sessions()
        if not can_open_new_session():
            return _render_capacity_blocked()

        reset_session_state(user_id=u.id, username=u.username, role=u.role_name())
        session.permanent = True
        register_active_session(u.id)

        # Cargar plan de suscripción
        sub = Subscription.query.filter_by(user_id=u.id).first()
        if sub:
            plan = Plan.query.get(sub.plan_id)
            session["plan"] = plan.name if plan else "Libre"
        else:
            session["plan"] = "Libre"

        flash("Sesión iniciada", "success")
        return redirect(url_for("main.home"))

    return render_template("token.html")


@bp.route("/logout", methods=["POST"])
@login_required
def logout():
    release_active_session()
    reset_session_state()
    return redirect(url_for("auth.login"))


@bp.route("/reset-2fa", methods=["POST"])
def reset_2fa():
    """Permite reconfigurar el TOTP confirmando la contrasena actual."""
    pending = session.get("pending_user_id") or session.get("user_id")
    if not pending:
        return redirect(url_for("auth.login"))
    u = User.query.get(pending)
    if not u:
        reset_session_state()
        return redirect(url_for("auth.login"))

    pw = request.form.get("contrasena") or ""
    if not check_password_hash(u.password_hash, pw):
        record_attempt("reset", f"user:{u.email}", False)
        flash("Contraseña incorrecta", "danger")
        return redirect(url_for("auth.token"))

    secret = new_totp_secret()
    u.totp_secret_enc = encrypt_totp(secret)
    u.totp_enabled = False
    db.session.commit()
    session["setup_email"] = u.email
    flash("Token reiniciado. Escanea el nuevo QR.", "success")
    return redirect(url_for("auth.setup_2fa"))

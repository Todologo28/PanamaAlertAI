"""Application factory — PanamaAlert Enterprise Intelligence Platform."""
import logging
from pathlib import Path
from secrets import compare_digest

from dotenv import load_dotenv
from flask import Flask
from werkzeug.middleware.proxy_fix import ProxyFix
from .extensions import db, migrate, cors
from .security import (
    csrf_protect, set_context, apply_headers, get_csrf_token,
    guard_request_abuse, ensure_active_session_table, sync_active_session,
    guard_session_creation_abuse,
)
from .ai_service import AIService

logger = logging.getLogger(__name__)

# Singleton AI service instance — importable from other modules
BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")
from .config import Config
ai_service = AIService()


def _setup_logging(app):
    level_name = app.config.get("LOG_LEVEL", "INFO")
    level = getattr(logging, str(level_name).upper(), logging.INFO)
    logging.basicConfig(
        level=level,
        format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
    )
    app.logger.setLevel(level)


def _validate_production_config(app):
    if not app.config.get("REQUIRE_STRONG_SECRETS"):
        return

    weak_values = {
        "SECRET_KEY": {"", "dev-change-me-in-prod", "change-me-to-a-strong-random-string"},
        "JWT_SECRET": {"", "dev-change-me-in-prod", "change-me-jwt-secret"},
        "TOTP_ENC_KEY": {""},
    }
    problems = []
    for key, disallowed in weak_values.items():
        value = str(app.config.get(key) or "").strip()
        if value in disallowed:
            problems.append(f"{key} no configurado correctamente")

    if app.config.get("IS_PRODUCTION"):
        if app.config.get("DEBUG"):
            problems.append("FLASK_DEBUG debe estar en false en produccion")
        if not app.config.get("SESSION_COOKIE_SECURE"):
            problems.append("COOKIE_SECURE debe estar en true en produccion")
        if not compare_digest(app.config.get("PREFERRED_URL_SCHEME", "https"), "https"):
            problems.append("PREFERRED_URL_SCHEME debe ser https en produccion")

    if problems:
        raise RuntimeError("Configuracion insegura para produccion: " + "; ".join(problems))


def create_app(config_class=Config):
    app = Flask(__name__,
                template_folder="../template",
                static_folder="../static")
    app.config.from_object(config_class)
    _setup_logging(app)
    _validate_production_config(app)
    app.wsgi_app = ProxyFix(
        app.wsgi_app,
        x_for=app.config.get("TRUST_PROXY_COUNT", 1),
        x_proto=1,
        x_host=1,
    )
    Path(app.config["INCIDENT_MEDIA_ROOT"]).mkdir(parents=True, exist_ok=True)
    Path(app.config["USER_PREFS_ROOT"]).mkdir(parents=True, exist_ok=True)
    Path(app.config["NEWS_DATA_ROOT"]).mkdir(parents=True, exist_ok=True)
    Path(app.config["SECURITY_DATA_ROOT"]).mkdir(parents=True, exist_ok=True)

    db.init_app(app)
    migrate.init_app(app, db)
    cors_origins = app.config.get("CORS_ORIGINS") or []
    if cors_origins:
        cors.init_app(app, resources={r"/api/*": {"origins": cors_origins}})

    with app.app_context():
        ensure_active_session_table()

    # Initialize AI service
    ai_service.init_app(app)

    # Initialize AI Agents
    try:
        from .ai_agents import FakePingDetector, DataAnalystAgent, SmartModerator
        app.fake_detector = FakePingDetector(ai_service)
        app.data_analyst = DataAnalystAgent(ai_service)
        app.smart_moderator = SmartModerator(ai_service)
        logger.info("AI Agents initialized: FakePingDetector, DataAnalystAgent, SmartModerator")
    except Exception as e:
        logger.warning(f"AI Agents initialization failed (non-critical): {e}")

    # Hooks de seguridad
    app.before_request(set_context)
    app.before_request(guard_request_abuse)
    app.before_request(guard_session_creation_abuse)
    app.before_request(sync_active_session)
    app.before_request(csrf_protect)
    app.after_request(apply_headers)

    @app.context_processor
    def _ctx():
        from flask import g
        return {"csrf_token": get_csrf_token(),
                "csp_nonce": getattr(g, "csp_nonce", "")}

    # Blueprints
    from .auth import bp as auth_bp
    from .main import bp as main_bp
    from .api  import bp as api_bp
    app.register_blueprint(auth_bp)
    app.register_blueprint(main_bp)
    app.register_blueprint(api_bp)

    return app

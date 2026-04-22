import os
from datetime import timedelta
from pathlib import Path


class Config:
    BASE_DIR = Path(__file__).resolve().parent.parent
    APP_ENV = os.getenv("APP_ENV", os.getenv("FLASK_ENV", "development")).strip().lower()
    IS_PRODUCTION = APP_ENV == "production"
    APP_NAME = os.getenv("APP_NAME", "PanamaAlert")
    SECRET_KEY = os.getenv("SECRET_KEY", "dev-change-me-in-prod")
    DEBUG = os.getenv("FLASK_DEBUG", "false").lower() == "true"
    TESTING = False
    PREFERRED_URL_SCHEME = os.getenv("PREFERRED_URL_SCHEME", "https" if IS_PRODUCTION else "http")
    SERVER_NAME = os.getenv("SERVER_NAME", "").strip() or None
    LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
    REQUIRE_STRONG_SECRETS = os.getenv("REQUIRE_STRONG_SECRETS", "true" if IS_PRODUCTION else "false").lower() == "true"

    # MariaDB connection
    DB_USER = os.getenv("DB_USER", "panama_alert")
    DB_PASS = os.getenv("DB_PASS", "panama_alert")
    DB_HOST = os.getenv("DB_HOST", "127.0.0.1")
    DB_PORT = os.getenv("DB_PORT", "3306")
    DB_NAME = os.getenv("DB_NAME", "panama_alert")
    SQLALCHEMY_DATABASE_URI = (
        f"mysql+pymysql://{DB_USER}:{DB_PASS}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
        "?charset=utf8mb4"
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # UTF-8: No escapar caracteres especiales en JSON (ñ, tildes, etc.)
    JSON_AS_ASCII = False
    SQLALCHEMY_ENGINE_OPTIONS = {
        "pool_pre_ping": True,
        "pool_recycle": 280,
        "pool_size": 10,
        "max_overflow": 20,
    }

    # Sesiones
    SESSION_COOKIE_NAME = os.getenv("SESSION_COOKIE_NAME", "panamaalert_session")
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = os.getenv("COOKIE_SAMESITE", "Lax")
    SESSION_COOKIE_SECURE = os.getenv("COOKIE_SECURE", "true" if IS_PRODUCTION else "false").lower() == "true"
    SESSION_COOKIE_PATH = "/"
    SESSION_REFRESH_EACH_REQUEST = False
    PERMANENT_SESSION_LIFETIME = timedelta(minutes=int(os.getenv("SESSION_MINUTES", "60")))
    MAX_ACTIVE_SESSIONS = int(os.getenv("MAX_ACTIVE_SESSIONS", "5000"))
    ACTIVE_SESSION_IDLE_MINUTES = int(os.getenv("ACTIVE_SESSION_IDLE_MINUTES", os.getenv("SESSION_MINUTES", "60")))
    SESSION_CREATION_LIMIT = int(os.getenv("SESSION_CREATION_LIMIT", "5000"))
    SESSION_CREATION_WINDOW_SECONDS = int(os.getenv("SESSION_CREATION_WINDOW_SECONDS", str(24 * 60 * 60)))
    SESSION_CREATION_BLOCK_MINUTES = int(os.getenv("SESSION_CREATION_BLOCK_MINUTES", "180"))

    # JWT API
    JWT_SECRET = os.getenv("JWT_SECRET", SECRET_KEY)
    JWT_EXP_MINUTES = int(os.getenv("JWT_EXP_MINUTES", "60"))

    # TOTP
    TOTP_ISSUER = os.getenv("TOTP_ISSUER", "PanamaAlert")
    TOTP_ENC_KEY = os.getenv("TOTP_ENC_KEY", "")

    # Rate limits (seg / intentos)
    LOGIN_MAX = int(os.getenv("LOGIN_MAX", "5"))
    LOGIN_WINDOW = int(os.getenv("LOGIN_WINDOW", "900"))

    # Paginación
    API_DEFAULT_LIMIT = 50
    API_MAX_LIMIT = 500

    # OpenAI
    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
    MAIL_ENABLED = os.getenv("MAIL_ENABLED", "false").lower() == "true"
    MAIL_HOST = os.getenv("MAIL_HOST", "")
    MAIL_PORT = int(os.getenv("MAIL_PORT", "587"))
    MAIL_USERNAME = os.getenv("MAIL_USERNAME", "")
    MAIL_PASSWORD = os.getenv("MAIL_PASSWORD", "")
    MAIL_USE_TLS = os.getenv("MAIL_USE_TLS", "true").lower() == "true"
    MAIL_USE_SSL = os.getenv("MAIL_USE_SSL", "false").lower() == "true"
    MAIL_FROM = os.getenv("MAIL_FROM", MAIL_USERNAME or "no-reply@panamaalert.local")
    MAIL_FROM_NAME = os.getenv("MAIL_FROM_NAME", "PanamaAlert")
    EMAIL_SUMMARY_HOURS = int(os.getenv("EMAIL_SUMMARY_HOURS", "24"))
    EMAIL_SUMMARY_MAX_ITEMS = int(os.getenv("EMAIL_SUMMARY_MAX_ITEMS", "8"))
    CORS_ORIGINS = [
        origin.strip()
        for origin in os.getenv("CORS_ORIGINS", "").split(",")
        if origin.strip()
    ]

    MEDIA_ROOT = Path(os.getenv("MEDIA_ROOT", BASE_DIR / "static" / "uploads"))
    INCIDENT_MEDIA_ROOT = MEDIA_ROOT / "incidents"
    USER_PREFS_ROOT = Path(os.getenv("USER_PREFS_ROOT", BASE_DIR / "app_data" / "preferences"))
    NEWS_DATA_ROOT = Path(os.getenv("NEWS_DATA_ROOT", BASE_DIR / "app_data" / "news"))
    SECURITY_DATA_ROOT = Path(os.getenv("SECURITY_DATA_ROOT", BASE_DIR / "app_data" / "security"))
    NEWS_SOURCES_FILE = NEWS_DATA_ROOT / "sources.json"
    NEWS_MANIFEST_FILE = NEWS_DATA_ROOT / "manifest.json"
    NEWS_SYNC_STATE_FILE = NEWS_DATA_ROOT / "sync_state.json"
    SECURITY_EVENTS_FILE = SECURITY_DATA_ROOT / "events.json"
    NEWS_SYNC_MINUTES = int(os.getenv("NEWS_SYNC_MINUTES", "20"))
    REQUESTS_PER_MINUTE = int(os.getenv("REQUESTS_PER_MINUTE", "180"))
    REQUESTS_PER_10S = int(os.getenv("REQUESTS_PER_10S", "45"))
    BLOCK_SECONDS = int(os.getenv("BLOCK_SECONDS", "900"))
    SECURITY_MAX_EVENTS = int(os.getenv("SECURITY_MAX_EVENTS", "1000"))
    TRUST_PROXY_COUNT = int(os.getenv("TRUST_PROXY_COUNT", "1"))
    MAX_CONTENT_LENGTH = int(os.getenv("MAX_CONTENT_LENGTH", str(20 * 1024 * 1024)))
    MAX_FORM_MEMORY_SIZE = int(os.getenv("MAX_FORM_MEMORY_SIZE", str(2 * 1024 * 1024)))
    INCIDENT_MEDIA_MAX_FILES = int(os.getenv("INCIDENT_MEDIA_MAX_FILES", "4"))
    INCIDENT_MEDIA_MAX_BYTES = int(os.getenv("INCIDENT_MEDIA_MAX_BYTES", str(12 * 1024 * 1024)))
    INCIDENT_MEDIA_ALLOWED_EXTENSIONS = {
        "jpg", "jpeg", "png", "webp", "gif", "mp4", "webm", "mov"
    }

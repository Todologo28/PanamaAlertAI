"""
ORM SQLAlchemy reflejando el schema 3FN.
Diseño coincide 1:1 con sql/01_schema.sql para que la verdad viva en la DB.
"""
from datetime import datetime
from .extensions import db


class Province(db.Model):
    __tablename__ = "provinces"
    id   = db.Column(db.SmallInteger, primary_key=True)
    code = db.Column(db.String(8), unique=True, nullable=False)
    name = db.Column(db.String(80), unique=True, nullable=False)
    districts = db.relationship("District", backref="province", lazy="select")


class District(db.Model):
    __tablename__ = "districts"
    id          = db.Column(db.SmallInteger, primary_key=True)
    province_id = db.Column(db.SmallInteger, db.ForeignKey("provinces.id"), nullable=False)
    name        = db.Column(db.String(120), nullable=False)


class Role(db.Model):
    __tablename__ = "roles"
    id   = db.Column(db.SmallInteger, primary_key=True)
    name = db.Column(db.String(32), unique=True, nullable=False)
    description = db.Column(db.String(255))


class Plan(db.Model):
    __tablename__ = "plans"
    id                  = db.Column(db.SmallInteger, primary_key=True)
    name                = db.Column(db.String(32), unique=True, nullable=False)
    price_monthly_usd   = db.Column(db.Numeric(8, 2), nullable=False, default=0)
    max_alerts_per_day  = db.Column(db.SmallInteger, nullable=False, default=10)
    max_geo_fences      = db.Column(db.SmallInteger, nullable=False, default=1)
    api_access          = db.Column(db.Boolean, nullable=False, default=False)
    priority_support    = db.Column(db.Boolean, nullable=False, default=False)
    features_json       = db.Column(db.JSON)


class User(db.Model):
    __tablename__ = "users"
    id              = db.Column(db.Integer, primary_key=True)
    username        = db.Column(db.String(32),  unique=True, nullable=False)
    email           = db.Column(db.String(190), unique=True, nullable=False)
    password_hash   = db.Column(db.String(255), nullable=False)
    totp_secret_enc = db.Column(db.String(255))
    totp_enabled    = db.Column(db.Boolean, default=False, nullable=False)
    full_name       = db.Column(db.String(120), nullable=False)
    cedula          = db.Column(db.String(32))
    phone           = db.Column(db.String(32))
    district_id     = db.Column(db.SmallInteger, db.ForeignKey("districts.id"))
    role_id         = db.Column(db.SmallInteger, db.ForeignKey("roles.id"), nullable=False)
    is_active       = db.Column(db.Boolean, default=True, nullable=False)
    email_verified  = db.Column(db.Boolean, default=False, nullable=False)
    created_at      = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    last_login_at   = db.Column(db.DateTime)

    role     = db.relationship("Role")
    district = db.relationship("District")

    def role_name(self):
        return self.role.name if self.role else "user"


class Subscription(db.Model):
    __tablename__ = "subscriptions"
    id         = db.Column(db.Integer, primary_key=True)
    user_id    = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    plan_id    = db.Column(db.SmallInteger, db.ForeignKey("plans.id"), nullable=False)
    started_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    expires_at = db.Column(db.DateTime)
    status     = db.Column(db.Enum("active", "cancelled", "expired", "trial"), default="active")
    plan       = db.relationship("Plan")


class IncidentCategory(db.Model):
    __tablename__ = "incident_categories"
    id               = db.Column(db.SmallInteger, primary_key=True)
    name             = db.Column(db.String(64), unique=True, nullable=False)
    icon             = db.Column(db.String(32))
    color_hex        = db.Column(db.String(7))
    default_severity = db.Column(db.SmallInteger, default=3)


class Incident(db.Model):
    __tablename__ = "incidents"
    id          = db.Column(db.BigInteger, primary_key=True)
    user_id     = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    category_id = db.Column(db.SmallInteger, db.ForeignKey("incident_categories.id"), nullable=False)
    district_id = db.Column(db.SmallInteger, db.ForeignKey("districts.id"))
    title       = db.Column(db.String(160), nullable=False)
    description = db.Column(db.String(1000), nullable=False)
    lat         = db.Column(db.Numeric(10, 7), nullable=False)
    lng         = db.Column(db.Numeric(10, 7), nullable=False)
    severity    = db.Column(db.SmallInteger, default=3, nullable=False)
    status      = db.Column(db.Enum("pending", "verified", "resolved", "dismissed"),
                            default="pending", nullable=False)
    verified_by = db.Column(db.Integer, db.ForeignKey("users.id"))
    verified_at = db.Column(db.DateTime)
    created_at  = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at  = db.Column(db.DateTime, default=datetime.utcnow,
                            onupdate=datetime.utcnow, nullable=False)
    expires_at  = db.Column(db.DateTime)

    user     = db.relationship("User", foreign_keys=[user_id])
    category = db.relationship("IncidentCategory")
    district = db.relationship("District")

    def to_dict(self):
        return {
            "id": self.id,
            "user_id": self.user_id,
            "username": self.user.username if self.user else None,
            "category_id": self.category_id,
            "category": self.category.name if self.category else None,
            "category_icon": self.category.icon if self.category else None,
            "category_color": self.category.color_hex if self.category else None,
            "district_id": self.district_id,
            "title": self.title,
            "description": self.description,
            "lat": float(self.lat),
            "lng": float(self.lng),
            "severity": self.severity,
            "status": self.status,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "verified_at": self.verified_at.isoformat() if self.verified_at else None,
        }


class IncidentVote(db.Model):
    __tablename__ = "incident_votes"
    incident_id = db.Column(db.BigInteger, db.ForeignKey("incidents.id"), primary_key=True)
    user_id     = db.Column(db.Integer, db.ForeignKey("users.id"), primary_key=True)
    vote        = db.Column(db.SmallInteger, nullable=False)
    created_at  = db.Column(db.DateTime, default=datetime.utcnow)


class IncidentComment(db.Model):
    __tablename__ = "incident_comments"
    id          = db.Column(db.BigInteger, primary_key=True)
    incident_id = db.Column(db.BigInteger, db.ForeignKey("incidents.id"), nullable=False)
    user_id     = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    body        = db.Column(db.String(1000), nullable=False)
    created_at  = db.Column(db.DateTime, default=datetime.utcnow)
    user        = db.relationship("User")


class AlertSubscription(db.Model):
    __tablename__ = "alert_subscriptions"
    id           = db.Column(db.Integer, primary_key=True)
    user_id      = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    category_id  = db.Column(db.SmallInteger, db.ForeignKey("incident_categories.id"))
    center_lat   = db.Column(db.Numeric(10, 7), nullable=False)
    center_lng   = db.Column(db.Numeric(10, 7), nullable=False)
    radius_km    = db.Column(db.Numeric(6, 2), nullable=False, default=5)
    min_severity = db.Column(db.SmallInteger, nullable=False, default=1)
    active       = db.Column(db.Boolean, nullable=False, default=True)
    created_at   = db.Column(db.DateTime, default=datetime.utcnow)


class Notification(db.Model):
    __tablename__ = "notifications"
    id          = db.Column(db.BigInteger, primary_key=True)
    user_id     = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    incident_id = db.Column(db.BigInteger, db.ForeignKey("incidents.id"))
    type        = db.Column(db.String(32), nullable=False)
    message     = db.Column(db.String(500), nullable=False)
    is_read     = db.Column(db.Boolean, default=False)
    created_at  = db.Column(db.DateTime, default=datetime.utcnow)


class AuthAttempt(db.Model):
    __tablename__ = "auth_attempts"
    id         = db.Column(db.BigInteger, primary_key=True)
    kind       = db.Column(db.Enum("login", "token", "reset", "session_open"), nullable=False)
    identifier = db.Column(db.String(190), nullable=False)
    ip         = db.Column(db.String(64), nullable=False)
    success    = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class ActiveSession(db.Model):
    __tablename__ = "active_sessions"
    id            = db.Column(db.BigInteger, primary_key=True)
    session_id    = db.Column(db.String(96), unique=True, nullable=False)
    user_id       = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    ip            = db.Column(db.String(64))
    user_agent    = db.Column(db.String(512))
    created_at    = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    last_seen_at  = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    expires_at    = db.Column(db.DateTime, nullable=False)

    user = db.relationship("User")


class AuditLog(db.Model):
    __tablename__ = "audit_log"
    id         = db.Column(db.BigInteger, primary_key=True)
    user_id    = db.Column(db.Integer)
    action     = db.Column(db.String(64), nullable=False)
    entity     = db.Column(db.String(64), nullable=False)
    entity_id  = db.Column(db.String(64))
    ip         = db.Column(db.String(64))
    user_agent = db.Column(db.String(512))
    meta_json  = db.Column(db.JSON)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class ApiKey(db.Model):
    __tablename__ = "api_keys"
    id           = db.Column(db.Integer, primary_key=True)
    user_id      = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    name         = db.Column(db.String(64), nullable=False)
    key_hash     = db.Column(db.String(64), unique=True, nullable=False)
    created_at   = db.Column(db.DateTime, default=datetime.utcnow)
    last_used_at = db.Column(db.DateTime)
    revoked_at   = db.Column(db.DateTime)


class PaymentMethod(db.Model):
    __tablename__ = "payment_methods"
    id          = db.Column(db.Integer, primary_key=True)
    user_id     = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, unique=True)
    card_last4  = db.Column(db.String(4), nullable=False)
    card_brand  = db.Column(db.String(20), default="unknown")
    card_name   = db.Column(db.String(60), nullable=False)
    card_expiry = db.Column(db.String(5), nullable=False)
    created_at  = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at  = db.Column(db.DateTime)

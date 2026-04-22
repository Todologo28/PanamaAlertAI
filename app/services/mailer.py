"""SMTP email delivery helpers for PanamaAlert."""
from __future__ import annotations

import logging
import smtplib
import ssl
from email.message import EmailMessage

from flask import current_app


logger = logging.getLogger(__name__)


def mail_is_configured() -> bool:
    return bool(
        current_app.config.get("MAIL_ENABLED")
        and current_app.config.get("MAIL_HOST")
        and current_app.config.get("MAIL_FROM")
    )


def send_email(to_email: str, subject: str, text_body: str, html_body: str | None = None) -> bool:
    to_email = str(to_email or "").strip()
    if not to_email:
        return False
    if not mail_is_configured():
        logger.info("Email skipped because MAIL is not configured for recipient %s", to_email)
        return False

    message = EmailMessage()
    from_name = current_app.config.get("MAIL_FROM_NAME", "PanamaAlert")
    from_email = current_app.config.get("MAIL_FROM")
    message["Subject"] = subject
    message["From"] = f"{from_name} <{from_email}>"
    message["To"] = to_email
    message.set_content(text_body or "")
    if html_body:
        message.add_alternative(html_body, subtype="html")

    host = current_app.config.get("MAIL_HOST")
    port = int(current_app.config.get("MAIL_PORT", 587))
    username = current_app.config.get("MAIL_USERNAME")
    password = current_app.config.get("MAIL_PASSWORD")
    use_ssl = bool(current_app.config.get("MAIL_USE_SSL"))
    use_tls = bool(current_app.config.get("MAIL_USE_TLS"))
    context = ssl.create_default_context()

    try:
        if use_ssl:
            with smtplib.SMTP_SSL(host, port, context=context, timeout=20) as server:
                if username:
                    server.login(username, password)
                server.send_message(message)
        else:
            with smtplib.SMTP(host, port, timeout=20) as server:
                server.ehlo()
                if use_tls:
                    server.starttls(context=context)
                    server.ehlo()
                if username:
                    server.login(username, password)
                server.send_message(message)
        return True
    except Exception:
        logger.exception("Email delivery failed for %s", to_email)
        return False


def send_geofence_alert_email(*, to_email: str, full_name: str | None, incident_title: str, incident_message: str,
                              severity: int | None = None, distance_km: float | None = None) -> bool:
    app_name = current_app.config.get("APP_NAME", "PanamaAlert")
    receiver = full_name or "usuario"
    distance_label = f"{distance_km:.1f} km" if distance_km is not None else "tu zona"
    severity_label = f"Severidad {severity}" if severity else "Severidad sin clasificar"
    subject = f"[{app_name}] Nueva alerta cerca de tu zona"
    text_body = (
        f"Hola {receiver},\n\n"
        f"Se detectó un incidente relevante cerca de {distance_label}.\n\n"
        f"Título: {incident_title}\n"
        f"Detalle: {incident_message}\n"
        f"{severity_label}\n\n"
        "Ingresa a PanamaAlert para revisar el mapa y los detalles completos.\n"
    )
    html_body = f"""
    <html>
      <body style="font-family:Segoe UI,Arial,sans-serif;background:#f8fafc;padding:24px;color:#0f172a;">
        <div style="max-width:640px;margin:0 auto;background:#ffffff;border:1px solid #e2e8f0;border-radius:18px;padding:28px;">
          <div style="font-size:12px;font-weight:800;letter-spacing:.04em;text-transform:uppercase;color:#ea580c;">Alerta PanamaAlert</div>
          <h1 style="margin:14px 0 8px;font-size:28px;line-height:1.1;">Nueva alerta cerca de tu zona</h1>
          <p style="color:#475569;line-height:1.7;">Hola {receiver}, detectamos un incidente relevante cerca de <strong>{distance_label}</strong>.</p>
          <div style="margin-top:18px;padding:18px;border-radius:14px;background:#fff7ed;border:1px solid #fed7aa;">
            <div style="font-size:18px;font-weight:800;margin-bottom:8px;">{incident_title}</div>
            <div style="color:#7c2d12;font-weight:700;margin-bottom:10px;">{severity_label}</div>
            <div style="color:#475569;line-height:1.6;">{incident_message}</div>
          </div>
          <p style="margin-top:20px;color:#64748b;line-height:1.7;">Entra a PanamaAlert para revisar el mapa, verificar el incidente y tomar acción.</p>
        </div>
      </body>
    </html>
    """
    return send_email(to_email=to_email, subject=subject, text_body=text_body, html_body=html_body)

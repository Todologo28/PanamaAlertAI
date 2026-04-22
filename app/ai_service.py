"""
AI Service Module for PanamaAlert2
Uses OpenAI API for incident moderation, alert generation, and trend analysis.
Designed with graceful fallback if OpenAI is unavailable.
"""

import os
import json
import time
import logging
from datetime import datetime, timedelta
from functools import wraps

logger = logging.getLogger(__name__)

# Rate limiting state
_rate_limit_calls = []
RATE_LIMIT_PER_MINUTE = 30

try:
    import openai
    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False
    logger.warning("openai package not installed. AI features will use fallback defaults.")


def _check_rate_limit():
    """Enforce rate limiting: max RATE_LIMIT_PER_MINUTE calls per 60 seconds."""
    now = time.time()
    cutoff = now - 60
    _rate_limit_calls[:] = [t for t in _rate_limit_calls if t > cutoff]
    if len(_rate_limit_calls) >= RATE_LIMIT_PER_MINUTE:
        return False
    _rate_limit_calls.append(now)
    return True


class AIService:
    """
    Modular AI service for PanamaAlert2.
    - Incident moderation (approve/review/reject)
    - Alert message generation
    - Zone trend analysis
    - Spam/duplicate detection

    Uses gpt-4o-mini for cost control.
    Falls back to safe defaults if OpenAI is unavailable.
    """

    DEFAULT_MODEL = "gpt-4o-mini"
    MAX_RETRIES = 2
    RETRY_DELAY = 1.0  # seconds

    def __init__(self, app=None):
        self.app = app
        self.client = None
        self.api_key = None
        self._total_tokens_used = 0

        if app is not None:
            self.init_app(app)

    def init_app(self, app):
        """Initialize with Flask app context."""
        self.app = app
        self.api_key = os.environ.get("OPENAI_API_KEY")

        if not self.api_key:
            logger.warning("OPENAI_API_KEY not set. AI service will use fallback mode.")
            return

        if not OPENAI_AVAILABLE:
            logger.warning("openai package not installed. AI service will use fallback mode.")
            return

        try:
            self.client = openai.OpenAI(api_key=self.api_key)
            logger.info("AIService initialized with OpenAI client.")
        except Exception as e:
            logger.error(f"Failed to initialize OpenAI client: {e}")
            self.client = None

    # -------------------------------------------------------------------------
    # Internal: call OpenAI with retries, error handling, and logging
    # -------------------------------------------------------------------------

    def _call_openai(self, messages, model=None, temperature=0.3, max_tokens=512):
        """
        Internal method to call OpenAI Chat Completions.
        Handles errors, retries, rate limiting, and fallback.

        Returns:
            dict with keys: success (bool), content (str), tokens_used (int), latency_ms (int)
        """
        model = model or self.DEFAULT_MODEL

        # Check prerequisites
        if not OPENAI_AVAILABLE or self.client is None:
            return {
                "success": False,
                "content": "",
                "tokens_used": 0,
                "latency_ms": 0,
                "error": "OpenAI not available"
            }

        # Rate limiting
        if not _check_rate_limit():
            logger.warning("AI rate limit reached. Returning fallback.")
            return {
                "success": False,
                "content": "",
                "tokens_used": 0,
                "latency_ms": 0,
                "error": "Rate limit exceeded"
            }

        last_error = None
        for attempt in range(self.MAX_RETRIES + 1):
            try:
                start_time = time.time()
                response = self.client.chat.completions.create(
                    model=model,
                    messages=messages,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    response_format={"type": "json_object"}
                )
                latency_ms = int((time.time() - start_time) * 1000)

                content = response.choices[0].message.content
                tokens_used = response.usage.total_tokens if response.usage else 0
                self._total_tokens_used += tokens_used

                # Log to database if possible
                self._log_ai_call(model, tokens_used, latency_ms)

                return {
                    "success": True,
                    "content": content,
                    "tokens_used": tokens_used,
                    "latency_ms": latency_ms,
                    "error": None
                }

            except openai.RateLimitError as e:
                last_error = str(e)
                logger.warning(f"OpenAI rate limit hit (attempt {attempt + 1}): {e}")
                time.sleep(self.RETRY_DELAY * (attempt + 1))

            except openai.APIConnectionError as e:
                last_error = str(e)
                logger.error(f"OpenAI connection error (attempt {attempt + 1}): {e}")
                time.sleep(self.RETRY_DELAY)

            except openai.APIError as e:
                last_error = str(e)
                logger.error(f"OpenAI API error (attempt {attempt + 1}): {e}")
                if attempt < self.MAX_RETRIES:
                    time.sleep(self.RETRY_DELAY)

            except Exception as e:
                last_error = str(e)
                logger.error(f"Unexpected error calling OpenAI: {e}")
                break

        return {
            "success": False,
            "content": "",
            "tokens_used": 0,
            "latency_ms": 0,
            "error": last_error
        }

    def _log_ai_call(self, model, tokens_used, latency_ms):
        """Log AI API call to the database for cost tracking."""
        try:
            if self.app:
                from app.extensions import db
                db.session.execute(
                    db.text(
                        "INSERT INTO ai_analyses (incident_id, model_used, tokens_used, latency_ms) "
                        "VALUES (:iid, :model, :tokens, :latency)"
                    ),
                    {"iid": 0, "model": model, "tokens": tokens_used, "latency": latency_ms}
                )
                db.session.commit()
        except Exception as e:
            logger.debug(f"Could not log AI call to database: {e}")

    # -------------------------------------------------------------------------
    # Public: Incident Moderation
    # -------------------------------------------------------------------------

    def moderate_incident(self, title, description, category, lat=None, lng=None):
        """
        Classify an incident report as approved, review, or rejected.

        Returns:
            dict with keys: decision, confidence, reason, flags, alert_level
        """
        fallback = {
            "decision": "review",
            "confidence": 0.50,
            "reason": "Moderacion automatica no disponible, enviado a revision manual.",
            "flags": [],
            "alert_level": "none"
        }

        system_prompt = (
            "Eres un moderador de contenido para PanamaAlert, una aplicacion de alertas "
            "ciudadanas en Panama. Tu trabajo es clasificar reportes de incidentes.\n\n"
            "Debes responder UNICAMENTE con un JSON valido con estas claves:\n"
            "- decision: 'approved' (legitimo), 'review' (necesita revision humana), o 'rejected' (spam/ofensivo)\n"
            "- confidence: numero entre 0.0 y 1.0 indicando tu confianza\n"
            "- reason: explicacion breve en espanol\n"
            "- flags: lista de flags detectados (ej: 'spam', 'offensive', 'duplicate', 'low_quality', 'fake')\n"
            "- alert_level: 'none', 'low', 'medium', 'high', o 'critical' segun la severidad del incidente\n\n"
            "Criterios:\n"
            "- Aprueba reportes claros y descriptivos sobre seguridad, transito, clima, infraestructura.\n"
            "- Envia a revision si el contenido es ambiguo o poco claro.\n"
            "- Rechaza spam, contenido ofensivo, informacion falsa obvia, o contenido irrelevante.\n"
            "- Asigna alert_level segun el peligro: critical para amenazas a la vida, high para riesgos "
            "significativos, medium para precaucion, low para informativo, none si no es alerta."
        )

        location_info = ""
        if lat and lng:
            location_info = f"\nUbicacion: lat={lat}, lng={lng}"

        user_message = (
            f"Titulo: {title}\n"
            f"Descripcion: {description}\n"
            f"Categoria: {category}"
            f"{location_info}"
        )

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message}
        ]

        result = self._call_openai(messages, temperature=0.1, max_tokens=300)

        if not result["success"]:
            logger.info(f"Moderation fallback used. Error: {result['error']}")
            return fallback

        try:
            parsed = json.loads(result["content"])
            return {
                "decision": parsed.get("decision", "review"),
                "confidence": float(parsed.get("confidence", 0.5)),
                "reason": parsed.get("reason", "Sin razon proporcionada."),
                "flags": parsed.get("flags", []),
                "alert_level": parsed.get("alert_level", "none"),
                "tokens_used": result["tokens_used"],
                "latency_ms": result["latency_ms"],
                "model_used": self.DEFAULT_MODEL
            }
        except (json.JSONDecodeError, ValueError, KeyError) as e:
            logger.error(f"Failed to parse moderation response: {e}")
            return fallback

    # -------------------------------------------------------------------------
    # Public: Alert Message Generation
    # -------------------------------------------------------------------------

    def generate_alert_message(self, incident_data, user_distance_km=None, context=None):
        """
        Generate a user-facing alert message for a given incident.

        Args:
            incident_data: dict with title, description, category, alert_level
            user_distance_km: float, distance from user to incident in km
            context: dict with optional extra context (time_of_day, user_preferences, etc.)

        Returns:
            dict with keys: message, urgency, emoji
        """
        fallback = {
            "message": f"Alerta: {incident_data.get('title', 'Incidente reportado')} cerca de tu zona.",
            "urgency": "medium",
            "emoji": "⚠️"
        }

        distance_text = ""
        if user_distance_km is not None:
            distance_text = f"\nDistancia al usuario: {user_distance_km:.1f} km"

        context_text = ""
        if context:
            context_text = f"\nContexto adicional: {json.dumps(context, ensure_ascii=False)}"

        system_prompt = (
            "Eres el sistema de alertas de PanamaAlert. Genera mensajes claros, concisos "
            "y utiles para notificar a los ciudadanos sobre incidentes cercanos.\n\n"
            "Responde UNICAMENTE con un JSON valido con estas claves:\n"
            "- message: mensaje de alerta en espanol, maximo 200 caracteres, claro y directo\n"
            "- urgency: 'low', 'medium', 'high', o 'critical'\n"
            "- emoji: un emoji apropiado para el tipo de alerta\n\n"
            "El mensaje debe ser informativo sin causar panico innecesario. "
            "Usa lenguaje apropiado para Panama."
        )

        user_message = (
            f"Incidente:\n"
            f"- Titulo: {incident_data.get('title', '')}\n"
            f"- Descripcion: {incident_data.get('description', '')}\n"
            f"- Categoria: {incident_data.get('category', '')}\n"
            f"- Nivel de alerta: {incident_data.get('alert_level', 'medium')}"
            f"{distance_text}"
            f"{context_text}"
        )

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message}
        ]

        result = self._call_openai(messages, temperature=0.5, max_tokens=200)

        if not result["success"]:
            return fallback

        try:
            parsed = json.loads(result["content"])
            return {
                "message": parsed.get("message", fallback["message"]),
                "urgency": parsed.get("urgency", "medium"),
                "emoji": parsed.get("emoji", "⚠️")
            }
        except (json.JSONDecodeError, ValueError) as e:
            logger.error(f"Failed to parse alert message response: {e}")
            return fallback

    # -------------------------------------------------------------------------
    # Public: Zone Trend Analysis
    # -------------------------------------------------------------------------

    def analyze_zone_trends(self, incidents_in_zone, timeframe_hours=24):
        """
        Analyze incident trends within a geographic zone.

        Args:
            incidents_in_zone: list of dicts with title, category, created_at, alert_level
            timeframe_hours: int, analysis window in hours

        Returns:
            dict with keys: trend, summary, risk_level
        """
        fallback = {
            "trend": "stable",
            "summary": "No se pudo realizar el analisis de tendencias automaticamente.",
            "risk_level": "low"
        }

        if not incidents_in_zone:
            return {
                "trend": "stable",
                "summary": "No se han reportado incidentes en esta zona recientemente.",
                "risk_level": "low"
            }

        # Prepare incident summary for the prompt
        incident_summaries = []
        for inc in incidents_in_zone[:20]:  # Limit to 20 to control token usage
            incident_summaries.append(
                f"- [{inc.get('category', 'N/A')}] {inc.get('title', 'Sin titulo')} "
                f"(nivel: {inc.get('alert_level', 'none')}, fecha: {inc.get('created_at', 'N/A')})"
            )

        incidents_text = "\n".join(incident_summaries)

        system_prompt = (
            "Eres un analista de seguridad para PanamaAlert. Analiza los incidentes "
            "reportados en una zona y determina la tendencia.\n\n"
            "Responde UNICAMENTE con un JSON valido con estas claves:\n"
            "- trend: 'increasing' (los incidentes van en aumento), 'stable' (se mantienen), "
            "o 'decreasing' (estan disminuyendo)\n"
            "- summary: resumen breve en espanol de la situacion (maximo 300 caracteres)\n"
            "- risk_level: 'low', 'medium', o 'high' segun el riesgo actual de la zona\n\n"
            "Considera la frecuencia, severidad y tipos de incidentes."
        )

        user_message = (
            f"Zona con {len(incidents_in_zone)} incidentes en las ultimas {timeframe_hours} horas:\n\n"
            f"{incidents_text}"
        )

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message}
        ]

        result = self._call_openai(messages, temperature=0.2, max_tokens=300)

        if not result["success"]:
            return fallback

        try:
            parsed = json.loads(result["content"])
            return {
                "trend": parsed.get("trend", "stable"),
                "summary": parsed.get("summary", fallback["summary"]),
                "risk_level": parsed.get("risk_level", "low")
            }
        except (json.JSONDecodeError, ValueError) as e:
            logger.error(f"Failed to parse trend analysis response: {e}")
            return fallback

    def summarize_incidents_digest(self, incidents, timeframe_hours=24, recipient_name=None):
        """
        Build a short digest summary for email delivery based on recent incidents.

        Returns:
            dict with keys: headline, summary, bullets
        """
        recipient = recipient_name or "usuario"
        if not incidents:
            return {
                "headline": "Sin alertas nuevas",
                "summary": f"Hola {recipient}, no encontramos alertas nuevas en las últimas {timeframe_hours} horas.",
                "bullets": [],
            }

        recent = incidents[:8]
        fallback_bullets = []
        for inc in recent:
            category = inc.get("category_name") or inc.get("category") or "Alerta"
            zone = inc.get("location_label") or inc.get("zone") or "ubicación reportada"
            fallback_bullets.append(
                f"{category}: {inc.get('title', 'Incidente sin título')} en {zone}"
            )

        fallback = {
            "headline": f"Resumen de {len(recent)} alertas recientes",
            "summary": (
                f"Hola {recipient}, registramos {len(incidents)} alertas en las últimas "
                f"{timeframe_hours} horas. Revisa las más relevantes en PanamaAlert."
            ),
            "bullets": fallback_bullets[:5],
        }

        incident_summaries = []
        for inc in recent:
            created_at = inc.get("created_at")
            if hasattr(created_at, "isoformat"):
                created_at = created_at.isoformat()
            incident_summaries.append(
                json.dumps({
                    "title": inc.get("title", ""),
                    "category": inc.get("category_name") or inc.get("category"),
                    "severity": inc.get("severity"),
                    "zone": inc.get("location_label") or inc.get("zone"),
                    "source": inc.get("source_name") or inc.get("reporter_username") or "usuario",
                    "created_at": created_at,
                }, ensure_ascii=False)
            )

        messages = [
            {
                "role": "system",
                "content": (
                    "Eres un analista de seguridad urbana para PanamaAlert. "
                    "Redacta un resumen breve por correo basado en alertas recientes. "
                    "Responde UNICAMENTE con JSON válido usando estas claves: "
                    "headline (max 70 chars), summary (max 320 chars) y bullets "
                    "(lista de 3 a 5 bullets breves en español)."
                ),
            },
            {
                "role": "user",
                "content": (
                    f"Usuario: {recipient}\n"
                    f"Ventana: {timeframe_hours} horas\n"
                    f"Incidentes:\n" + "\n".join(incident_summaries)
                ),
            },
        ]

        result = self._call_openai(messages, temperature=0.2, max_tokens=350)
        if not result["success"]:
            return fallback

        try:
            parsed = json.loads(result["content"])
            bullets = parsed.get("bullets") or []
            bullets = [str(item).strip() for item in bullets if str(item).strip()][:5]
            if not bullets:
                return fallback
            return {
                "headline": str(parsed.get("headline") or fallback["headline"])[:70],
                "summary": str(parsed.get("summary") or fallback["summary"])[:320],
                "bullets": bullets,
            }
        except (json.JSONDecodeError, ValueError, TypeError) as e:
            logger.error(f"Failed to parse digest summary response: {e}")
            return fallback

    # -------------------------------------------------------------------------
    # Public: Spam / Duplicate Detection
    # -------------------------------------------------------------------------

    def detect_spam_or_duplicate(self, new_incident, recent_incidents):
        """
        Check if a new incident is spam or a duplicate of recent reports.

        Args:
            new_incident: dict with title, description, category, lat, lng
            recent_incidents: list of recent incident dicts in the same area

        Returns:
            dict with keys: is_spam (bool), is_duplicate (bool),
                            duplicate_of (int|None), confidence (float), reason (str)
        """
        fallback = {
            "is_spam": False,
            "is_duplicate": False,
            "duplicate_of": None,
            "confidence": 0.0,
            "reason": "Deteccion automatica no disponible."
        }

        if not recent_incidents:
            return {
                "is_spam": False,
                "is_duplicate": False,
                "duplicate_of": None,
                "confidence": 0.9,
                "reason": "No hay incidentes recientes similares en la zona."
            }

        recent_text = ""
        for i, inc in enumerate(recent_incidents[:10]):
            recent_text += (
                f"\nIncidente #{inc.get('id', i)}: "
                f"[{inc.get('category', '')}] {inc.get('title', '')} - {inc.get('description', '')[:100]}"
            )

        system_prompt = (
            "Eres un detector de spam y duplicados para PanamaAlert.\n\n"
            "Compara el nuevo incidente con los recientes y determina si es spam o duplicado.\n\n"
            "Responde UNICAMENTE con un JSON valido con estas claves:\n"
            "- is_spam: true o false\n"
            "- is_duplicate: true o false\n"
            "- duplicate_of: ID del incidente duplicado (numero) o null\n"
            "- confidence: numero entre 0.0 y 1.0\n"
            "- reason: explicacion breve en espanol\n\n"
            "Un reporte es duplicado si describe el mismo evento en la misma ubicacion. "
            "Es spam si es publicidad, contenido sin sentido, o claramente falso."
        )

        user_message = (
            f"NUEVO INCIDENTE:\n"
            f"Titulo: {new_incident.get('title', '')}\n"
            f"Descripcion: {new_incident.get('description', '')}\n"
            f"Categoria: {new_incident.get('category', '')}\n"
            f"Ubicacion: ({new_incident.get('lat', '')}, {new_incident.get('lng', '')})\n\n"
            f"INCIDENTES RECIENTES EN LA ZONA:{recent_text}"
        )

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message}
        ]

        result = self._call_openai(messages, temperature=0.1, max_tokens=200)

        if not result["success"]:
            return fallback

        try:
            parsed = json.loads(result["content"])
            return {
                "is_spam": bool(parsed.get("is_spam", False)),
                "is_duplicate": bool(parsed.get("is_duplicate", False)),
                "duplicate_of": parsed.get("duplicate_of"),
                "confidence": float(parsed.get("confidence", 0.0)),
                "reason": parsed.get("reason", "Sin razon proporcionada.")
            }
        except (json.JSONDecodeError, ValueError) as e:
            logger.error(f"Failed to parse spam detection response: {e}")
            return fallback

    # -------------------------------------------------------------------------
    # Public: Log AI analysis result to database
    # -------------------------------------------------------------------------

    def save_analysis(self, incident_id, moderation_result):
        """
        Persist an AI moderation result to the ai_analyses table.

        Args:
            incident_id: int, the incident ID
            moderation_result: dict returned by moderate_incident()
        """
        try:
            from app.extensions import db
            db.session.execute(
                db.text(
                    "INSERT INTO ai_analyses "
                    "(incident_id, decision, confidence, reason, flags, alert_level, model_used, tokens_used, latency_ms) "
                    "VALUES (:iid, :decision, :confidence, :reason, :flags, :alert_level, :model, :tokens, :latency)"
                ),
                {
                    "iid": incident_id,
                    "decision": moderation_result.get("decision", "review"),
                    "confidence": moderation_result.get("confidence", 0.5),
                    "reason": moderation_result.get("reason", ""),
                    "flags": json.dumps(moderation_result.get("flags", [])),
                    "alert_level": moderation_result.get("alert_level", "none"),
                    "model": moderation_result.get("model_used", self.DEFAULT_MODEL),
                    "tokens": moderation_result.get("tokens_used", 0),
                    "latency": moderation_result.get("latency_ms", 0),
                }
            )
            db.session.commit()
            logger.info(f"AI analysis saved for incident {incident_id}: {moderation_result.get('decision')}")
        except Exception as e:
            logger.error(f"Failed to save AI analysis for incident {incident_id}: {e}")

    # -------------------------------------------------------------------------
    # Utility
    # -------------------------------------------------------------------------

    @property
    def total_tokens_used(self):
        """Total tokens consumed in this service instance's lifetime."""
        return self._total_tokens_used

    @property
    def is_available(self):
        """Check if the AI service is fully operational."""
        return OPENAI_AVAILABLE and self.client is not None

"""
PanamaAlert AI Agents System
Enterprise-grade AI agents for intelligent incident management.

Agents:
  1. FakePingDetector  - Detects fraudulent/fake incident reports using pattern analysis
  2. DataAnalystAgent  - Provides data analysis, trends, predictions, and zone intelligence
  3. SmartModerator    - Automated content moderation with confidence scoring

Each agent operates independently with its own prompt engineering, scoring logic,
and fallback behavior when OpenAI is unavailable.
"""

import json
import math
import logging
import time
from datetime import datetime, timedelta
from collections import Counter

logger = logging.getLogger(__name__)
MAX_CHAT_HISTORY_ITEMS = 8


class FakePingDetector:
    """
    AI Agent specialized in detecting fake, fraudulent, or malicious incident reports.

    Detection signals:
      - Velocity: Too many reports from the same user in a short window
      - Geographic impossibility: Reports from distant locations in rapid succession
      - Content quality: Vague, repetitive, or nonsensical descriptions
      - Pattern matching: Known spam patterns, offensive content
      - Community signals: Vote ratios, report history
      - Temporal anomalies: Reports at unusual hours with suspicious patterns
    """

    # Thresholds
    MAX_REPORTS_PER_HOUR = 5
    MAX_REPORTS_PER_DAY = 15
    MIN_DESCRIPTION_LENGTH = 15
    VELOCITY_WINDOW_MINUTES = 30
    MAX_SPEED_KMH = 200  # Max plausible travel speed

    def __init__(self, ai_service=None):
        self.ai_service = ai_service

    def analyze(self, incident_data, user_history=None, recent_nearby=None):
        """
        Run full fake detection analysis on an incident.

        Args:
            incident_data: dict with title, description, lat, lng, category, severity, user_id
            user_history: list of recent incidents from this user
            recent_nearby: list of recent incidents in the same area

        Returns:
            dict with:
              - is_fake: bool
              - confidence: float (0-1)
              - risk_score: float (0-100)
              - signals: list of detected signals
              - recommendation: str (approve/review/reject)
              - analysis_detail: str
        """
        signals = []
        risk_score = 0.0

        # Signal 1: Content quality
        content_score = self._analyze_content_quality(incident_data)
        risk_score += content_score["penalty"]
        signals.extend(content_score["signals"])

        # Signal 2: User velocity
        if user_history:
            velocity_score = self._analyze_velocity(incident_data, user_history)
            risk_score += velocity_score["penalty"]
            signals.extend(velocity_score["signals"])

        # Signal 3: Geographic plausibility
        if user_history:
            geo_score = self._analyze_geographic_plausibility(incident_data, user_history)
            risk_score += geo_score["penalty"]
            signals.extend(geo_score["signals"])

        # Signal 4: Duplicate detection
        if recent_nearby:
            dup_score = self._analyze_duplicates(incident_data, recent_nearby)
            risk_score += dup_score["penalty"]
            signals.extend(dup_score["signals"])

        # Signal 5: Temporal anomalies
        temporal_score = self._analyze_temporal(incident_data)
        risk_score += temporal_score["penalty"]
        signals.extend(temporal_score["signals"])

        # Signal 6: Severity mismatch
        sev_score = self._analyze_severity_mismatch(incident_data)
        risk_score += sev_score["penalty"]
        signals.extend(sev_score["signals"])

        # Clamp risk score
        risk_score = min(100, max(0, risk_score))

        # AI-enhanced analysis if available
        ai_analysis = None
        if self.ai_service and self.ai_service.is_available and risk_score > 20:
            ai_analysis = self._ai_deep_analysis(incident_data, signals, risk_score)
            if ai_analysis:
                # Blend AI confidence with rule-based score
                ai_risk = ai_analysis.get("risk_adjustment", 0)
                risk_score = (risk_score * 0.6) + (ai_risk * 0.4)
                if ai_analysis.get("additional_signals"):
                    signals.extend(ai_analysis["additional_signals"])

        # Determine recommendation
        if risk_score >= 75:
            recommendation = "reject"
            is_fake = True
        elif risk_score >= 40:
            recommendation = "review"
            is_fake = False
        else:
            recommendation = "approve"
            is_fake = False

        confidence = min(0.95, risk_score / 100 + 0.3) if risk_score > 30 else max(0.6, 1 - risk_score / 100)

        return {
            "is_fake": is_fake,
            "confidence": round(confidence, 3),
            "risk_score": round(risk_score, 1),
            "signals": signals,
            "recommendation": recommendation,
            "analysis_detail": self._build_detail(signals, risk_score, recommendation),
            "ai_enhanced": ai_analysis is not None
        }

    def _analyze_content_quality(self, data):
        """Analyze text quality of title and description."""
        signals = []
        penalty = 0.0
        title = (data.get("title") or "").strip()
        desc = (data.get("description") or "").strip()

        if len(title) < 5:
            signals.append({"type": "low_quality", "detail": "Titulo muy corto", "severity": "medium"})
            penalty += 15

        if len(desc) < self.MIN_DESCRIPTION_LENGTH:
            signals.append({"type": "low_quality", "detail": "Descripcion insuficiente", "severity": "medium"})
            penalty += 15

        # Repetitive characters
        if title and len(set(title.lower())) < 4:
            signals.append({"type": "spam", "detail": "Titulo con caracteres repetitivos", "severity": "high"})
            penalty += 25

        # All caps
        if title and title == title.upper() and len(title) > 10:
            signals.append({"type": "low_quality", "detail": "Titulo en mayusculas", "severity": "low"})
            penalty += 5

        # Check for common spam patterns
        spam_patterns = ["test", "prueba", "asdf", "xxx", "aaa", "123", "hola"]
        title_lower = title.lower()
        for pattern in spam_patterns:
            if title_lower == pattern or (len(title_lower) < 10 and pattern in title_lower):
                signals.append({"type": "spam", "detail": f"Patron de prueba detectado: '{pattern}'", "severity": "high"})
                penalty += 30
                break

        # Title-description similarity (copy-paste)
        if title and desc and title.lower() == desc.lower():
            signals.append({"type": "low_quality", "detail": "Titulo y descripcion identicos", "severity": "medium"})
            penalty += 10

        return {"penalty": penalty, "signals": signals}

    def _analyze_velocity(self, data, user_history):
        """Check if user is posting too fast."""
        signals = []
        penalty = 0.0
        now = datetime.utcnow()

        recent_hour = [h for h in user_history
                       if _parse_time(h.get("created_at")) and
                       (now - _parse_time(h["created_at"])).total_seconds() < 3600]

        recent_day = [h for h in user_history
                      if _parse_time(h.get("created_at")) and
                      (now - _parse_time(h["created_at"])).total_seconds() < 86400]

        if len(recent_hour) >= self.MAX_REPORTS_PER_HOUR:
            signals.append({
                "type": "velocity",
                "detail": f"Usuario reporto {len(recent_hour)} incidentes en la ultima hora (max {self.MAX_REPORTS_PER_HOUR})",
                "severity": "high"
            })
            penalty += 35

        elif len(recent_day) >= self.MAX_REPORTS_PER_DAY:
            signals.append({
                "type": "velocity",
                "detail": f"Usuario reporto {len(recent_day)} incidentes hoy (max {self.MAX_REPORTS_PER_DAY})",
                "severity": "medium"
            })
            penalty += 20

        # Burst detection: 3+ in 10 minutes
        recent_burst = [h for h in user_history
                        if _parse_time(h.get("created_at")) and
                        (now - _parse_time(h["created_at"])).total_seconds() < 600]
        if len(recent_burst) >= 3:
            signals.append({
                "type": "velocity_burst",
                "detail": f"Rafaga: {len(recent_burst)} reportes en 10 minutos",
                "severity": "critical"
            })
            penalty += 40

        return {"penalty": penalty, "signals": signals}

    def _analyze_geographic_plausibility(self, data, user_history):
        """Check if user could physically be at reported location."""
        signals = []
        penalty = 0.0
        now = datetime.utcnow()

        lat = float(data.get("lat", 0))
        lng = float(data.get("lng", 0))

        for prev in user_history[:5]:
            prev_time = _parse_time(prev.get("created_at"))
            if not prev_time:
                continue
            time_diff_hours = max(0.01, (now - prev_time).total_seconds() / 3600)
            prev_lat = float(prev.get("lat", 0))
            prev_lng = float(prev.get("lng", 0))
            distance_km = _haversine(lat, lng, prev_lat, prev_lng)
            speed_kmh = distance_km / time_diff_hours

            if speed_kmh > self.MAX_SPEED_KMH and distance_km > 5:
                signals.append({
                    "type": "geographic_impossible",
                    "detail": f"Velocidad imposible: {distance_km:.1f}km en {time_diff_hours*60:.0f}min ({speed_kmh:.0f}km/h)",
                    "severity": "critical"
                })
                penalty += 40
                break

        # Check if location is in Panama (rough bounds)
        if not (7.0 <= lat <= 9.7 and -83.1 <= lng <= -77.1):
            signals.append({
                "type": "out_of_bounds",
                "detail": "Ubicacion fuera del territorio de Panama",
                "severity": "critical"
            })
            penalty += 50

        return {"penalty": penalty, "signals": signals}

    def _analyze_duplicates(self, data, recent_nearby):
        """Check for duplicate reports in the same area."""
        signals = []
        penalty = 0.0
        title_lower = (data.get("title") or "").lower()

        for nearby in recent_nearby:
            nearby_title = (nearby.get("title") or "").lower()
            # Simple similarity: same words
            if title_lower and nearby_title:
                words_a = set(title_lower.split())
                words_b = set(nearby_title.split())
                if len(words_a) > 2 and len(words_b) > 2:
                    overlap = len(words_a & words_b) / max(len(words_a | words_b), 1)
                    if overlap > 0.7:
                        signals.append({
                            "type": "duplicate",
                            "detail": f"Posible duplicado del incidente #{nearby.get('id', '?')} ({overlap*100:.0f}% similitud)",
                            "severity": "medium",
                            "duplicate_of": nearby.get("id")
                        })
                        penalty += 15
                        break

        return {"penalty": penalty, "signals": signals}

    def _analyze_temporal(self, data):
        """Check for temporal anomalies."""
        signals = []
        penalty = 0.0
        now = datetime.utcnow()
        hour = now.hour

        # Late night reports with high severity are suspicious
        if 1 <= hour <= 5:
            severity = int(data.get("severity", 3))
            if severity <= 2:
                signals.append({
                    "type": "temporal",
                    "detail": "Reporte de baja severidad en madrugada (posible prueba)",
                    "severity": "low"
                })
                penalty += 5

        return {"penalty": penalty, "signals": signals}

    def _analyze_severity_mismatch(self, data):
        """Check if severity matches content."""
        signals = []
        penalty = 0.0
        desc = (data.get("description") or "").lower()
        severity = int(data.get("severity", 3))

        # High severity but trivial description
        if severity >= 4 and len(desc) < 30:
            signals.append({
                "type": "severity_mismatch",
                "detail": "Severidad alta pero descripcion muy breve",
                "severity": "medium"
            })
            penalty += 10

        return {"penalty": penalty, "signals": signals}

    def _ai_deep_analysis(self, data, existing_signals, current_risk):
        """Use AI for deeper analysis when rule-based score is ambiguous."""
        if not self.ai_service:
            return None

        signals_text = "\n".join([f"- [{s['severity']}] {s['type']}: {s['detail']}" for s in existing_signals])

        messages = [
            {"role": "system", "content": (
                "Eres un agente detector de fraude para PanamaAlert. "
                "Analiza reportes de incidentes y determina si son falsos.\n\n"
                "Responde SOLO con JSON valido:\n"
                "- risk_adjustment: numero 0-100 (tu estimacion de riesgo)\n"
                "- reasoning: explicacion breve en espanol\n"
                "- additional_signals: lista de senales adicionales detectadas "
                "(cada una con type, detail, severity)\n\n"
                "Contexto: Panama, app de seguridad ciudadana."
            )},
            {"role": "user", "content": (
                f"Incidente:\n"
                f"Titulo: {data.get('title', '')}\n"
                f"Descripcion: {data.get('description', '')}\n"
                f"Categoria: {data.get('category', '')}\n"
                f"Severidad: {data.get('severity', 3)}\n"
                f"Ubicacion: ({data.get('lat', 0)}, {data.get('lng', 0)})\n\n"
                f"Senales detectadas (riesgo actual: {current_risk:.0f}/100):\n{signals_text}"
            )}
        ]

        result = self.ai_service._call_openai(messages, temperature=0.1, max_tokens=300)
        if not result["success"]:
            return None

        try:
            parsed = json.loads(result["content"])
            return {
                "risk_adjustment": float(parsed.get("risk_adjustment", current_risk)),
                "reasoning": parsed.get("reasoning", ""),
                "additional_signals": [
                    {"type": s.get("type", "ai_detected"),
                     "detail": s.get("detail", ""),
                     "severity": s.get("severity", "medium")}
                    for s in parsed.get("additional_signals", [])
                ]
            }
        except (json.JSONDecodeError, ValueError):
            return None

    def _build_detail(self, signals, risk_score, recommendation):
        """Build human-readable analysis summary."""
        if not signals:
            return "No se detectaron senales sospechosas. Reporte parece legitimo."

        reco_text = {
            "approve": "Aprobado automaticamente",
            "review": "Enviado a revision manual",
            "reject": "Rechazado por multiples senales de fraude"
        }
        lines = [f"Puntuacion de riesgo: {risk_score:.0f}/100 - {reco_text.get(recommendation, '')}"]
        for s in signals:
            icon = {"low": "~", "medium": "!", "high": "!!", "critical": "!!!"}
            lines.append(f"  [{icon.get(s['severity'], '?')}] {s['detail']}")
        return "\n".join(lines)


class DataAnalystAgent:
    """
    AI Agent specialized in data analysis, trend detection, and predictive insights.

    Capabilities:
      - Zone risk assessment with multi-factor scoring
      - Temporal trend analysis (hourly, daily, weekly patterns)
      - Category distribution analysis
      - Predictive risk scoring
      - Natural language Q&A about incident data
      - Comparative zone analysis
    """

    def __init__(self, ai_service=None):
        self.ai_service = ai_service

    def analyze_zone(self, lat, lng, incidents, radius_km=3):
        """
        Comprehensive zone analysis with statistical and AI insights.

        Returns:
            dict with risk_level, trend, statistics, insights, predictions
        """
        nearby = self._filter_nearby(incidents, lat, lng, radius_km)
        now = datetime.utcnow()

        # Time-based filtering
        last_24h = [i for i in nearby if _parse_time(i.get("created_at")) and
                    (now - _parse_time(i["created_at"])).total_seconds() < 86400]
        last_7d = [i for i in nearby if _parse_time(i.get("created_at")) and
                   (now - _parse_time(i["created_at"])).total_seconds() < 604800]
        last_30d = [i for i in nearby if _parse_time(i.get("created_at")) and
                    (now - _parse_time(i["created_at"])).total_seconds() < 2592000]

        # Statistical analysis
        stats = {
            "total_nearby": len(nearby),
            "last_24h": len(last_24h),
            "last_7d": len(last_7d),
            "last_30d": len(last_30d),
            "avg_severity": round(sum(int(i.get("severity", 3)) for i in nearby) / max(len(nearby), 1), 2),
            "max_severity": max((int(i.get("severity", 1)) for i in nearby), default=0),
        }

        # Category breakdown
        cat_counts = Counter(i.get("category_name") or i.get("category") or "Otro" for i in nearby)
        stats["categories"] = [{"name": k, "count": v} for k, v in cat_counts.most_common(10)]

        # Hourly distribution
        hour_dist = Counter()
        for i in last_30d:
            t = _parse_time(i.get("created_at"))
            if t:
                hour_dist[t.hour] += 1
        stats["peak_hours"] = [{"hour": h, "count": c} for h, c in sorted(hour_dist.items(), key=lambda x: -x[1])[:5]]

        # Trend calculation
        trend = self._calculate_trend(last_7d, last_30d)

        # Risk level
        risk_level = self._calculate_risk_level(stats, trend)

        # Predictions
        predictions = self._generate_predictions(stats, trend, hour_dist)

        # AI-enhanced insights
        insights = []
        if self.ai_service and self.ai_service.is_available and nearby:
            ai_insights = self._ai_zone_insights(lat, lng, stats, trend, nearby[:10])
            if ai_insights:
                insights = ai_insights

        return {
            "risk_level": risk_level,
            "trend": trend,
            "statistics": stats,
            "insights": insights,
            "predictions": predictions,
            "incidents_count": len(nearby),
            "nearby_incidents": [
                {
                    "id": i.get("id") or i.get("incident_id"),
                    "title": i.get("title", ""),
                    "category": i.get("category_name") or i.get("category") or "",
                    "severity": int(i.get("severity", 3)),
                    "status": i.get("status", "pending"),
                    "created_at": i.get("created_at"),
                    "distance_km": round(_haversine(lat, lng, float(i.get("lat", 0)), float(i.get("lng", 0))), 2)
                }
                for i in sorted(nearby, key=lambda x: _haversine(lat, lng, float(x.get("lat", 0)), float(x.get("lng", 0))))[:15]
            ]
        }

    def answer_question(self, question, lat, lng, incidents, context=None):
        """
        Natural language Q&A about incident data.
        Uses AI when available, falls back to statistical analysis.
        """
        context = context or {}
        radius_km = float(context.get("radius_km") or 5)
        nearby = self._filter_nearby(incidents, lat, lng, radius_km=radius_km)
        now = datetime.utcnow()

        # Build context from data
        stats_context = {
            "total": len(nearby),
            "last_24h": len([i for i in nearby if _parse_time(i.get("created_at")) and
                             (now - _parse_time(i["created_at"])).total_seconds() < 86400]),
            "categories": dict(Counter(i.get("category_name") or "Otro" for i in nearby)),
            "avg_severity": round(sum(int(i.get("severity", 3)) for i in nearby) / max(len(nearby), 1), 2),
            "statuses": dict(Counter(i.get("status", "pending") for i in nearby)),
            "place_name": context.get("place_name") or f"{lat:.4f}, {lng:.4f}",
            "radius_km": radius_km,
            "current_hour": now.hour,
        }

        if self.ai_service and self.ai_service.is_available:
            return self._ai_answer(question, lat, lng, stats_context, nearby[:15], context=context)

        # Fallback: rule-based answers
        return self._rule_based_answer(question, stats_context, nearby, context=context)

    def _filter_nearby(self, incidents, lat, lng, radius_km):
        """Filter incidents within radius."""
        return [i for i in incidents
                if _haversine(lat, lng, float(i.get("lat", 0)), float(i.get("lng", 0))) <= radius_km]

    def _calculate_trend(self, last_7d, last_30d):
        """Calculate trend direction and magnitude."""
        if len(last_30d) == 0:
            return {"direction": "stable", "magnitude": 0, "label": "Sin datos suficientes"}

        weekly_rate = len(last_7d) / 7
        monthly_rate = len(last_30d) / 30

        if monthly_rate == 0:
            ratio = 1.0
        else:
            ratio = weekly_rate / monthly_rate

        if ratio > 1.5:
            return {"direction": "increasing", "magnitude": round((ratio - 1) * 100), "label": "En aumento"}
        elif ratio < 0.5:
            return {"direction": "decreasing", "magnitude": round((1 - ratio) * 100), "label": "En descenso"}
        else:
            return {"direction": "stable", "magnitude": round(abs(ratio - 1) * 100), "label": "Estable"}

    def _calculate_risk_level(self, stats, trend):
        """Multi-factor risk scoring."""
        score = 0

        # Volume factor
        if stats["last_24h"] >= 10:
            score += 40
        elif stats["last_24h"] >= 5:
            score += 25
        elif stats["last_24h"] >= 2:
            score += 10

        # Severity factor
        score += min(30, stats["avg_severity"] * 6)

        # Trend factor
        if trend["direction"] == "increasing":
            score += 15
        elif trend["direction"] == "decreasing":
            score -= 10

        score = min(100, max(0, score))

        if score >= 70:
            return "critical"
        elif score >= 50:
            return "high"
        elif score >= 30:
            return "medium"
        else:
            return "low"

    def _generate_predictions(self, stats, trend, hour_dist):
        """Generate simple predictions based on patterns."""
        predictions = []

        # Peak hour prediction
        if hour_dist:
            peak = max(hour_dist.items(), key=lambda x: x[1])
            predictions.append({
                "type": "peak_hour",
                "message": f"Mayor actividad esperada alrededor de las {peak[0]:02d}:00",
                "confidence": 0.7
            })

        # Trend prediction
        if trend["direction"] == "increasing":
            predictions.append({
                "type": "trend",
                "message": f"Los incidentes estan aumentando un {trend['magnitude']}%. Se espera alta actividad proximas 24h.",
                "confidence": 0.6
            })
        elif trend["direction"] == "decreasing":
            predictions.append({
                "type": "trend",
                "message": f"Los incidentes disminuyen un {trend['magnitude']}%. Tendencia positiva.",
                "confidence": 0.6
            })

        # Category prediction
        if stats["categories"]:
            top_cat = stats["categories"][0]
            predictions.append({
                "type": "category",
                "message": f"Tipo mas probable: {top_cat['name']} ({top_cat['count']} casos recientes)",
                "confidence": 0.65
            })

        return predictions

    def _ai_zone_insights(self, lat, lng, stats, trend, sample_incidents):
        """Generate AI-powered zone insights."""
        incidents_text = "\n".join([
            f"- [{i.get('category_name', 'N/A')}] {i.get('title', 'Sin titulo')} (sev:{i.get('severity', '?')}, {i.get('status', '?')})"
            for i in sample_incidents
        ])

        messages = [
            {"role": "system", "content": (
                "Eres un analista de seguridad urbana para PanamaAlert. "
                "Genera insights accionables basados en datos de incidentes.\n\n"
                "Responde SOLO con JSON valido:\n"
                "- insights: lista de objetos con {title, description, type, priority}\n"
                "  types: 'safety_tip', 'trend_alert', 'pattern', 'recommendation'\n"
                "  priority: 'low', 'medium', 'high'\n\n"
                "Maximo 4 insights. Sé conciso y util. Idioma: espanol."
            )},
            {"role": "user", "content": (
                f"Zona: lat={lat:.4f}, lng={lng:.4f}\n"
                f"Estadisticas: {json.dumps(stats, ensure_ascii=False)}\n"
                f"Tendencia: {json.dumps(trend, ensure_ascii=False)}\n\n"
                f"Incidentes recientes:\n{incidents_text}"
            )}
        ]

        result = self.ai_service._call_openai(messages, temperature=0.4, max_tokens=500)
        if not result["success"]:
            return []

        try:
            parsed = json.loads(result["content"])
            return parsed.get("insights", [])
        except (json.JSONDecodeError, ValueError):
            return []

    def _ai_answer(self, question, lat, lng, stats_context, sample_incidents, context=None):
        """AI-powered Q&A about zone data."""
        context = context or {}
        history = context.get("history") or []
        history_lines = []
        for item in history[-MAX_CHAT_HISTORY_ITEMS:]:
            role = "Usuario" if item.get("role") == "user" else "Asistente"
            content = (item.get("content") or "").strip()
            if content:
                history_lines.append(f"{role}: {content}")

        incidents_text = "\n".join([
            f"- [{i.get('category_name', 'N/A')}] {i.get('title', 'Sin titulo')} "
            f"(sev:{i.get('severity', '?')}, status:{i.get('status', '?')}, {i.get('created_at', '')})"
            for i in sample_incidents
        ])
        place_name = stats_context.get("place_name") or context.get("place_name") or f"{lat:.4f}, {lng:.4f}"
        radius_km = stats_context.get("radius_km") or context.get("radius_km") or 5
        history_block = "\n".join(history_lines) if history_lines else "Sin historial previo."

        messages = [
            {"role": "system", "content": (
                "Eres el Asistente de Analisis de PanamaAlert, una app de seguridad ciudadana en Panama. "
                "Respondes preguntas sobre incidentes y seguridad en zonas especificas.\n"
                "Debes responder directamente a la ultima pregunta del usuario, usando el historial reciente como contexto "
                "y sin reciclar un mensaje generico.\n\n"
                "Tu respuesta debe sentirse operativa y aterrizada a la zona consultada. "
                "Explica rapidamente el nivel de riesgo, el patron mas relevante y la accion inmediata recomendada.\n\n"
                "Responde SOLO con JSON valido:\n"
                "- response: tu respuesta en espanol (max 520 caracteres, clara, concreta y accionable)\n"
                "- risk_level: 'low', 'medium', 'high'\n"
                "- trend: 'increasing', 'stable', 'decreasing'\n"
                "- action_items: lista de recomendaciones breves (max 3)\n\n"
                "Sé profesional, conciso, y basado en datos. No causes panico."
            )},
            {"role": "user", "content": (
                f"Ultima pregunta del usuario: {question}\n\n"
                f"Lugar de referencia: {place_name}\n"
                f"Zona: lat={lat:.4f}, lng={lng:.4f}\n"
                f"Estadisticas zona (radio {radius_km}km): {json.dumps(stats_context, ensure_ascii=False)}\n\n"
                f"Historial reciente:\n{history_block}\n\n"
                f"Incidentes recientes:\n{incidents_text}"
            )}
        ]

        result = self.ai_service._call_openai(messages, temperature=0.5, max_tokens=400)
        if not result["success"]:
            return self._rule_based_answer(question, stats_context, sample_incidents, context=context)

        try:
            parsed = json.loads(result["content"])
            return {
                "response": parsed.get("response", "No pude analizar esta zona."),
                "risk_level": parsed.get("risk_level", "medium"),
                "trend": parsed.get("trend", "stable"),
                "action_items": parsed.get("action_items", []),
                "incidents_count": stats_context["total"],
                "place_name": place_name,
                "nearby_incidents": [
                    {
                        "title": i.get("title", ""),
                        "category": i.get("category_name") or "",
                        "severity": int(i.get("severity", 3))
                    }
                    for i in sample_incidents[:5]
                ],
                "ai_powered": True,
                "source_label": "Respuesta por IA",
                "source_mode": "ai",
                "signals_used": [
                    f"{stats_context['total']} incidentes en el radio analizado",
                    f"{stats_context['last_24h']} incidentes en las ultimas 24 horas",
                    f"Severidad promedio {stats_context['avg_severity']:.1f}/5",
                ],
                "analysis_basis": "Historial reciente del chat + estadisticas de la zona + incidentes cercanos",
            }
        except (json.JSONDecodeError, ValueError):
            return self._rule_based_answer(question, stats_context, sample_incidents, context=context)

    def _rule_based_answer(self, question, stats, incidents, context=None):
        """Fallback rule-based answers when AI is unavailable, but still conversational."""
        context = context or {}
        total = stats["total"]
        cats = stats.get("categories", {})
        top_cat = max(cats.items(), key=lambda x: x[1])[0] if cats else "N/A"
        place_name = stats.get("place_name") or context.get("place_name") or "esta zona"
        radius_km = stats.get("radius_km") or context.get("radius_km") or 5
        q = (question or "").lower()

        risk = "low"
        if stats["last_24h"] > 5 or stats["avg_severity"] > 3.5 or total >= 12:
            risk = "high"
        elif stats["last_24h"] > 2 or stats["avg_severity"] > 2.5 or total >= 5:
            risk = "medium"

        trend = "stable"
        if total >= 10 and stats["last_24h"] >= 4:
            trend = "increasing"
        elif total <= 2 and stats["last_24h"] == 0:
            trend = "decreasing"

        trend_labels = {
            "increasing": "en aumento",
            "stable": "estable",
            "decreasing": "a la baja"
        }

        incident_preview = []
        for i in incidents[:5]:
            created = _parse_time(i.get("created_at"))
            when = created.strftime("%d/%m %H:%M") if created else "sin hora"
            incident_preview.append({
                "title": i.get("title", ""),
                "category": i.get("category_name") or i.get("category") or "",
                "severity": int(i.get("severity", 3)),
                "created_at": when
            })

        action_items = [
            "Mantente atento a nuevas alertas de la zona",
            "Evita rutas solitarias si te desplazas de noche",
            "Reporta cualquier incidente relevante para mejorar el contexto"
        ]
        if top_cat and top_cat != "N/A":
            action_items[0] = f"Prioriza precaucion frente a reportes de {top_cat.lower()} en la zona"
        if risk == "high":
            action_items[1] = "Si te movilizas ahora, usa rutas principales y evita paradas innecesarias"
        elif risk == "medium":
            action_items[1] = "Si vas a pasar por la zona, revisa primero los reportes mas recientes"

        if "tipo" in q or "predomin" in q or "categoria" in q:
            response = (
                f"En {place_name}, dentro de {radius_km} km, predominan los incidentes de tipo '{top_cat}'. "
                f"Hay {total} casos cercanos y {stats['last_24h']} ocurrieron en las últimas 24 horas."
            )
        elif "tendencia" in q or "aumento" in q or "disminu" in q:
            response = (
                f"La tendencia en {place_name} se ve {trend_labels[trend]}. "
                f"Ahora mismo hay {total} incidentes de referencia y una severidad promedio de {stats['avg_severity']:.1f}/5."
            )
        elif "segura" in q or "seguridad" in q or "riesgo" in q:
            response = (
                f"Para {place_name}, el riesgo actual es {risk}. "
                f"Estoy viendo {stats['last_24h']} incidentes en las últimas 24 horas y {total} en el radio de {radius_km} km."
            )
        elif "noche" in q or "ahora" in q or "pasar" in q or "ir" in q:
            if risk == "high":
                response = (
                    f"Yo tomaría precaución alta en {place_name}, sobre todo de noche. "
                    f"La actividad reciente y la severidad media sugieren evitar rutas poco transitadas."
                )
            elif risk == "medium":
                response = (
                    f"Se puede transitar por {place_name}, pero con atención. "
                    f"No es la zona más crítica ahora, aunque sí conviene moverse por áreas iluminadas y activas."
                )
            else:
                response = (
                    f"No veo señales fuertes de riesgo inmediato en {place_name}. "
                    f"Aun así, conserva precauciones normales y revisa alertas nuevas antes de salir."
                )
        elif "recomend" in q or "hacer" in q or "mover" in q:
            response = (
                f"Para moverte con más seguridad en {place_name}, te recomiendo priorizar vías principales, "
                f"evitar puntos aislados y revisar si el tipo dominante de incidente es '{top_cat}'."
            )
        else:
            response = (
                f"En {place_name} encontré {total} incidentes dentro de {radius_km} km, con {stats['last_24h']} en las últimas 24 horas. "
                f"La categoría más frecuente es '{top_cat}' y el panorama general se ve {trend_labels[trend]}."
            )

        if risk == "high":
            action_items = [
                "Evita pasar solo por la zona en horarios de baja circulación",
                "Prefiere rutas principales y comparte tu trayecto",
                "Si detectas algo inusual, repórtalo de inmediato"
            ]
        elif risk == "medium":
            action_items = [
                "Mantén atención a movimientos inusuales",
                "Usa rutas transitadas e iluminadas",
                "Consulta nuevas alertas antes de moverte"
            ]

        return {
            "response": response,
            "risk_level": risk,
            "trend": trend,
            "action_items": action_items,
            "incidents_count": total,
            "nearby_incidents": incident_preview,
            "ai_powered": False,
            "place_name": place_name,
            "source_label": "Respuesta por reglas",
            "source_mode": "rules",
            "signals_used": [
                f"{total} incidentes cercanos en {radius_km} km",
                f"{stats['last_24h']} incidentes en 24h",
                f"Categoria dominante: {top_cat}",
            ],
            "analysis_basis": "Heuristicas de riesgo basadas en volumen, severidad y tendencia",
        }


class SmartModerator:
    """
    AI Agent for intelligent content moderation with learning capabilities.

    Features:
      - Multi-layered moderation pipeline
      - Confidence-based auto-approve/reject
      - Escalation to human moderators
      - Pattern learning from moderator decisions
    """

    AUTO_APPROVE_THRESHOLD = 0.85
    AUTO_REJECT_THRESHOLD = 0.90
    REVIEW_THRESHOLD = 0.50

    def __init__(self, ai_service=None, fake_detector=None):
        self.ai_service = ai_service
        self.fake_detector = fake_detector or FakePingDetector(ai_service)

    def moderate(self, incident_data, user_history=None, recent_nearby=None):
        """
        Full moderation pipeline combining fake detection + content moderation + AI analysis.

        Returns:
            dict with decision, confidence, actions, fake_analysis, moderation_detail
        """
        # Step 1: Fake ping detection
        fake_result = self.fake_detector.analyze(incident_data, user_history, recent_nearby)

        # If clearly fake, reject immediately
        if fake_result["is_fake"] and fake_result["confidence"] > self.AUTO_REJECT_THRESHOLD:
            return {
                "decision": "rejected",
                "confidence": fake_result["confidence"],
                "reason": "Detectado como reporte fraudulento",
                "actions": ["auto_rejected", "flagged_for_review"],
                "fake_analysis": fake_result,
                "alert_level": "none",
                "flags": [s["type"] for s in fake_result["signals"]]
            }

        # Step 2: Content moderation via AI
        if self.ai_service and self.ai_service.is_available:
            ai_mod = self.ai_service.moderate_incident(
                incident_data.get("title", ""),
                incident_data.get("description", ""),
                incident_data.get("category", ""),
                incident_data.get("lat"),
                incident_data.get("lng")
            )
        else:
            ai_mod = {
                "decision": "review",
                "confidence": 0.5,
                "reason": "Moderacion IA no disponible",
                "flags": [],
                "alert_level": "none"
            }

        # Step 3: Combine signals
        combined_confidence = (fake_result["confidence"] * 0.4 + ai_mod.get("confidence", 0.5) * 0.6)

        if fake_result["risk_score"] > 40:
            # High fake risk overrides AI approval
            if ai_mod["decision"] == "approved":
                final_decision = "review"
            else:
                final_decision = ai_mod["decision"]
        else:
            final_decision = ai_mod["decision"]

        # Auto-approve if both agents agree and confidence is high
        if (final_decision == "approved" and
                combined_confidence > self.AUTO_APPROVE_THRESHOLD and
                fake_result["risk_score"] < 20):
            actions = ["auto_approved"]
        elif final_decision == "rejected":
            actions = ["auto_rejected", "notify_admins"]
        else:
            actions = ["queued_for_review"]

        return {
            "decision": final_decision,
            "confidence": round(combined_confidence, 3),
            "reason": ai_mod.get("reason", fake_result["analysis_detail"]),
            "actions": actions,
            "fake_analysis": {
                "risk_score": fake_result["risk_score"],
                "is_fake": fake_result["is_fake"],
                "signals_count": len(fake_result["signals"]),
                "top_signals": fake_result["signals"][:3]
            },
            "alert_level": ai_mod.get("alert_level", "none"),
            "flags": list(set(
                [s["type"] for s in fake_result["signals"]] +
                ai_mod.get("flags", [])
            ))
        }


# ============================================================================
# Utility functions
# ============================================================================

def _haversine(lat1, lng1, lat2, lng2):
    """Calculate distance in km between two coordinates."""
    R = 6371
    dlat = math.radians(float(lat2) - float(lat1))
    dlng = math.radians(float(lng2) - float(lng1))
    a = (math.sin(dlat / 2) ** 2 +
         math.cos(math.radians(float(lat1))) * math.cos(math.radians(float(lat2))) *
         math.sin(dlng / 2) ** 2)
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def _parse_time(val):
    """Parse a datetime string or return None."""
    if val is None:
        return None
    if isinstance(val, datetime):
        return val
    try:
        return datetime.fromisoformat(str(val).replace("Z", "+00:00").replace("+00:00", ""))
    except (ValueError, TypeError):
        return None

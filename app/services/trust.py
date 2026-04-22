"""Reporter trust scoring and AI explainability helpers."""
from __future__ import annotations

from collections import defaultdict


def _clamp(value, minimum=0, maximum=100):
    return max(minimum, min(maximum, int(round(value))))


def _score_band(score):
    if score >= 80:
        return "high"
    if score >= 55:
        return "medium"
    return "low"


def _score_label(score):
    band = _score_band(score)
    return {
        "high": "Credibilidad alta",
        "medium": "Credibilidad media",
        "low": "Credibilidad en observacion",
    }[band]


def build_reporter_profiles(db_session, user_ids):
    from sqlalchemy import text

    ids = [int(uid) for uid in set(user_ids or []) if uid is not None]
    if not ids:
        return {}

    placeholders = ",".join(str(uid) for uid in ids)
    incident_rows = db_session.execute(text(f"""
        SELECT
            i.user_id,
            COUNT(*) AS total_reports,
            SUM(CASE WHEN i.status = 'verified' THEN 1 ELSE 0 END) AS verified_reports,
            SUM(CASE WHEN i.status = 'resolved' THEN 1 ELSE 0 END) AS resolved_reports,
            SUM(CASE WHEN i.status = 'dismissed' THEN 1 ELSE 0 END) AS dismissed_reports,
            AVG(i.severity) AS avg_severity
        FROM incidents i
        WHERE i.user_id IN ({placeholders})
        GROUP BY i.user_id
    """)).mappings().all()

    vote_rows = db_session.execute(text(f"""
        SELECT
            i.user_id,
            SUM(CASE WHEN v.vote = 1 THEN 1 ELSE 0 END) AS up_votes,
            SUM(CASE WHEN v.vote = -1 THEN 1 ELSE 0 END) AS down_votes
        FROM incidents i
        LEFT JOIN incident_votes v ON v.incident_id = i.id
        WHERE i.user_id IN ({placeholders})
        GROUP BY i.user_id
    """)).mappings().all()

    ai_rows = db_session.execute(text(f"""
        SELECT
            i.user_id,
            SUM(CASE WHEN a.decision = 'approved' THEN 1 ELSE 0 END) AS ai_approved,
            SUM(CASE WHEN a.decision = 'review' THEN 1 ELSE 0 END) AS ai_review,
            SUM(CASE WHEN a.decision = 'rejected' THEN 1 ELSE 0 END) AS ai_rejected
        FROM incidents i
        LEFT JOIN (
            SELECT aa.incident_id, aa.decision
            FROM ai_analyses aa
            INNER JOIN (
                SELECT incident_id, MAX(id) AS last_id
                FROM ai_analyses
                GROUP BY incident_id
            ) latest ON latest.last_id = aa.id
        ) a ON a.incident_id = i.id
        WHERE i.user_id IN ({placeholders})
        GROUP BY i.user_id
    """)).mappings().all()

    base = defaultdict(dict)
    for row in incident_rows:
        base[int(row["user_id"])].update({
            "total_reports": int(row["total_reports"] or 0),
            "verified_reports": int(row["verified_reports"] or 0),
            "resolved_reports": int(row["resolved_reports"] or 0),
            "dismissed_reports": int(row["dismissed_reports"] or 0),
            "avg_severity": float(row["avg_severity"] or 0),
        })
    for row in vote_rows:
        base[int(row["user_id"])].update({
            "up_votes": int(row["up_votes"] or 0),
            "down_votes": int(row["down_votes"] or 0),
        })
    for row in ai_rows:
        base[int(row["user_id"])].update({
            "ai_approved": int(row["ai_approved"] or 0),
            "ai_review": int(row["ai_review"] or 0),
            "ai_rejected": int(row["ai_rejected"] or 0),
        })

    profiles = {}
    for uid in ids:
        stats = base[uid]
        total_reports = int(stats.get("total_reports", 0))
        verified_reports = int(stats.get("verified_reports", 0))
        resolved_reports = int(stats.get("resolved_reports", 0))
        dismissed_reports = int(stats.get("dismissed_reports", 0))
        up_votes = int(stats.get("up_votes", 0))
        down_votes = int(stats.get("down_votes", 0))
        ai_approved = int(stats.get("ai_approved", 0))
        ai_review = int(stats.get("ai_review", 0))
        ai_rejected = int(stats.get("ai_rejected", 0))
        positive_outcomes = verified_reports + resolved_reports
        verified_ratio = positive_outcomes / max(total_reports, 1)
        dismissed_ratio = dismissed_reports / max(total_reports, 1)
        community_ratio = up_votes / max(up_votes + down_votes, 1)
        ai_ratio = ai_approved / max(ai_approved + ai_review + ai_rejected, 1)

        score = 45
        score += verified_ratio * 30
        score += community_ratio * 15
        score += ai_ratio * 10
        score -= dismissed_ratio * 35
        if total_reports >= 5:
            score += 5
        elif total_reports == 0:
            score -= 5

        credibility_score = _clamp(score)
        trust_signals = []
        if total_reports:
            trust_signals.append(f"{total_reports} reportes historicos")
        if positive_outcomes:
            trust_signals.append(f"{positive_outcomes} reportes validados o resueltos")
        if dismissed_reports:
            trust_signals.append(f"{dismissed_reports} reportes descartados")
        if up_votes or down_votes:
            trust_signals.append(f"Comunidad: +{up_votes} / -{down_votes}")
        if ai_approved or ai_review or ai_rejected:
            trust_signals.append(f"IA: {ai_approved} aprobados, {ai_review} revision, {ai_rejected} rechazados")

        profiles[uid] = {
            "credibility_score": credibility_score,
            "credibility_band": _score_band(credibility_score),
            "credibility_label": _score_label(credibility_score),
            "total_reports": total_reports,
            "verified_reports": verified_reports,
            "resolved_reports": resolved_reports,
            "dismissed_reports": dismissed_reports,
            "up_votes": up_votes,
            "down_votes": down_votes,
            "avg_severity": round(float(stats.get("avg_severity", 0)), 2),
            "ai_approved": ai_approved,
            "ai_review": ai_review,
            "ai_rejected": ai_rejected,
            "trust_signals": trust_signals[:4],
        }

    return profiles


def explain_analysis(incident, ai_analysis=None, reporter_profile=None):
    reporter_profile = reporter_profile or {}
    ai_analysis = ai_analysis or {}
    source_mode = "ai" if ai_analysis else "rules"
    flags = ai_analysis.get("flags") or []
    signal_labels = []
    for flag in flags[:4]:
        if isinstance(flag, dict):
            signal_labels.append(flag.get("detail") or flag.get("type") or "senal")
        else:
            signal_labels.append(str(flag))

    trust_summary = []
    if reporter_profile.get("credibility_label"):
        trust_summary.append(reporter_profile["credibility_label"])
    if reporter_profile.get("total_reports"):
        trust_summary.append(f"{reporter_profile['total_reports']} reportes historicos")
    if incident.get("status"):
        trust_summary.append(f"Estado actual: {incident['status']}")

    return {
        "source_mode": source_mode,
        "source_label": "Respuesta por IA" if source_mode == "ai" else "Respuesta por reglas",
        "confidence_percent": int(round((ai_analysis.get("confidence") or 0) * 100)) if ai_analysis else None,
        "trust_summary": trust_summary,
        "signals_used": signal_labels,
        "decision": ai_analysis.get("decision") if ai_analysis else None,
        "reason": ai_analysis.get("reason") or "",
    }

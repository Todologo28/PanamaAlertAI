"""Lightweight user notification preferences storage."""
from __future__ import annotations

import json
from pathlib import Path


DEFAULT_PREFS = {
    "push_enabled": True,
    "email_enabled": False,
    "browser_notifications": False,
    "min_alert_level": "medium",
    "incident_types": [],
    "last_summary_sent_at": None,
}


def _prefs_path(root: Path, user_id: int) -> Path:
    return Path(root) / f"user_{int(user_id)}.json"


def load_preferences(root: Path, user_id: int):
    path = _prefs_path(root, user_id)
    if not path.exists():
        return dict(DEFAULT_PREFS)
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return dict(DEFAULT_PREFS)
    merged = dict(DEFAULT_PREFS)
    merged.update({k: v for k, v in data.items() if k in DEFAULT_PREFS})
    if not isinstance(merged.get("incident_types"), list):
        merged["incident_types"] = []
    return merged


def save_preferences(root: Path, user_id: int, payload):
    data = dict(DEFAULT_PREFS)
    data.update({
        "push_enabled": bool(payload.get("push_enabled", DEFAULT_PREFS["push_enabled"])),
        "email_enabled": bool(payload.get("email_enabled", DEFAULT_PREFS["email_enabled"])),
        "browser_notifications": bool(payload.get("browser_notifications", DEFAULT_PREFS["browser_notifications"])),
        "min_alert_level": str(payload.get("min_alert_level") or DEFAULT_PREFS["min_alert_level"]),
        "incident_types": [
            str(item).strip() for item in (payload.get("incident_types") or [])
            if str(item).strip()
        ],
        "last_summary_sent_at": payload.get("last_summary_sent_at", DEFAULT_PREFS["last_summary_sent_at"]),
    })
    root = Path(root)
    root.mkdir(parents=True, exist_ok=True)
    _prefs_path(root, user_id).write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    return data


def should_notify(preferences, incident):
    preferences = preferences or DEFAULT_PREFS
    severity = int(incident.get("severity") or 1)
    min_level = str(preferences.get("min_alert_level") or "medium").lower()
    severity_threshold = {
        "low": 1,
        "medium": 2,
        "high": 4,
        "critical": 5,
    }.get(min_level, 2)
    if severity < severity_threshold:
        return False

    allowed_types = preferences.get("incident_types") or []
    category = str(incident.get("category") or incident.get("category_name") or "").strip()
    if allowed_types and category and category not in allowed_types:
        return False
    return True

"""Filesystem-backed evidence storage for incidents."""
from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path
from uuid import uuid4

IMAGE_EXTENSIONS = {"jpg", "jpeg", "png", "webp", "gif"}
VIDEO_EXTENSIONS = {"mp4", "webm", "mov"}
ALLOWED_SIGNATURES = {
    "jpg": [b"\xff\xd8\xff"],
    "jpeg": [b"\xff\xd8\xff"],
    "png": [b"\x89PNG\r\n\x1a\n"],
    "gif": [b"GIF87a", b"GIF89a"],
    "webp": [b"RIFF"],
    "mp4": [b"ftyp"],
    "mov": [b"ftyp"],
    "webm": [b"\x1a\x45\xdf\xa3"],
}
ALLOWED_MIME_PREFIXES = {
    "jpg": ("image/jpeg",),
    "jpeg": ("image/jpeg",),
    "png": ("image/png",),
    "gif": ("image/gif",),
    "webp": ("image/webp",),
    "mp4": ("video/mp4",),
    "mov": ("video/quicktime", "video/mp4"),
    "webm": ("video/webm",),
}


def _manifest_path(root: Path, incident_id: int) -> Path:
    return Path(root) / str(int(incident_id)) / "manifest.json"


def _incident_dir(root: Path, incident_id: int) -> Path:
    return Path(root) / str(int(incident_id))


def _load_manifest(root: Path, incident_id: int):
    manifest_path = _manifest_path(root, incident_id)
    if not manifest_path.exists():
        return []
    try:
        return json.loads(manifest_path.read_text(encoding="utf-8"))
    except Exception:
        return []


def _save_manifest(root: Path, incident_id: int, entries):
    incident_dir = _incident_dir(root, incident_id)
    incident_dir.mkdir(parents=True, exist_ok=True)
    _manifest_path(root, incident_id).write_text(
        json.dumps(entries, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def _ext(filename: str):
    parts = str(filename or "").rsplit(".", 1)
    return parts[-1].lower() if len(parts) == 2 else ""


def _safe_filename(filename: str):
    cleaned = re.sub(r"[^A-Za-z0-9._-]+", "_", str(filename or "")).strip("._")
    return cleaned or f"archivo_{uuid4().hex[:8]}"


def _media_kind(extension: str):
    if extension in IMAGE_EXTENSIONS:
        return "image"
    if extension in VIDEO_EXTENSIONS:
        return "video"
    return "file"


def _sniff_signature(file_storage, extension: str):
    stream = file_storage.stream
    stream.seek(0)
    head = stream.read(64)
    stream.seek(0)
    signatures = ALLOWED_SIGNATURES.get(extension, [])
    if extension in {"mp4", "mov"}:
        return any(sig in head[:32] for sig in signatures)
    if extension == "webp":
        return head.startswith(b"RIFF") and b"WEBP" in head[:16]
    return any(head.startswith(sig) for sig in signatures)


def _validate_mimetype(file_storage, extension: str):
    mime_type = (getattr(file_storage, "mimetype", "") or "").lower().strip()
    allowed = ALLOWED_MIME_PREFIXES.get(extension, ())
    return bool(mime_type and any(mime_type.startswith(prefix) for prefix in allowed))


def list_incident_evidence(root: Path, incident_id: int):
    return _load_manifest(root, incident_id)


def save_incident_evidence(
    file_storage,
    incident_id: int,
    user_id: int,
    root: Path,
    max_bytes: int,
    allowed_extensions,
    max_files: int,
):
    entries = _load_manifest(root, incident_id)
    if len(entries) >= max_files:
        raise ValueError(f"Solo se permiten {max_files} evidencias por incidente")

    filename = _safe_filename(getattr(file_storage, "filename", "") or "")
    extension = _ext(filename)
    if not extension or extension not in set(allowed_extensions or []):
        raise ValueError("Formato de archivo no permitido")
    if not _validate_mimetype(file_storage, extension):
        raise ValueError("El tipo MIME del archivo no coincide con la extension permitida")
    if not _sniff_signature(file_storage, extension):
        raise ValueError("El contenido del archivo no coincide con el formato esperado")

    file_storage.stream.seek(0, 2)
    size = file_storage.stream.tell()
    file_storage.stream.seek(0)
    if size <= 0:
        raise ValueError("El archivo esta vacio")
    if size > max_bytes:
        raise ValueError("El archivo excede el tamano permitido")

    incident_dir = _incident_dir(root, incident_id)
    incident_dir.mkdir(parents=True, exist_ok=True)
    stored_name = f"{datetime.utcnow().strftime('%Y%m%d%H%M%S')}_{uuid4().hex[:10]}.{extension}"
    file_path = incident_dir / stored_name
    file_storage.save(file_path)

    item = {
        "id": uuid4().hex,
        "filename": filename,
        "stored_name": stored_name,
        "url": f"/static/uploads/incidents/{int(incident_id)}/{stored_name}",
        "kind": _media_kind(extension),
        "mime_type": file_storage.mimetype or "",
        "size_bytes": int(size),
        "uploaded_by": int(user_id),
        "uploaded_at": datetime.utcnow().isoformat(),
    }
    entries.append(item)
    _save_manifest(root, incident_id, entries)
    return item

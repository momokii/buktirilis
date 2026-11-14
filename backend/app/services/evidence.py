"""Protected local artifact storage and evidence payloads."""

from __future__ import annotations

import hashlib
import mimetypes
import re
import uuid
from pathlib import Path

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.config import get_settings
from app.models import Artifact, Evidence, Project
from app.services.redaction import redact_headers, redact_payload, redact_text, truncate

_SAFE_NAME = re.compile(r"[^A-Za-z0-9._-]+")


def artifact_root() -> Path:
    root = Path(get_settings().artifact_root).expanduser().resolve()
    root.mkdir(parents=True, exist_ok=True)
    return root


def safe_filename(name: str) -> str:
    cleaned = _SAFE_NAME.sub("_", Path(name or "artifact").name)[:120].strip("._")
    return cleaned or "artifact"


def save_bytes(
    db: Session,
    *,
    project: Project,
    content: bytes,
    filename: str,
    content_type: str,
    created_by: uuid.UUID | None = None,
    max_bytes: int | None = None,
) -> Artifact:
    settings = get_settings()
    limit = max_bytes or settings.max_artifact_bytes
    if len(content) == 0:
        raise HTTPException(status_code=422, detail="Attachment is empty")
    if len(content) > limit:
        raise HTTPException(
            status_code=413, detail=f"Attachment exceeds the {limit} byte limit for this upload"
        )
    digest = hashlib.sha256(content).hexdigest()
    artifact_id = uuid.uuid4()
    storage_key = f"{project.id}/{artifact_id}"
    directory = artifact_root() / str(project.id)
    directory.mkdir(parents=True, exist_ok=True)
    target = directory / str(artifact_id)
    resolved = target.resolve()
    if not str(resolved).startswith(str(artifact_root())):
        raise HTTPException(status_code=500, detail="Artifact storage path rejected")
    resolved.write_bytes(content)
    artifact = Artifact(
        id=artifact_id,
        project_id=project.id,
        storage_key=storage_key,
        filename=safe_filename(filename),
        content_type=content_type or "application/octet-stream",
        size_bytes=len(content),
        sha256=digest,
        created_by=created_by,
    )
    db.add(artifact)
    db.flush()
    return artifact


def read_bytes(artifact: Artifact) -> bytes:
    root = artifact_root()
    path = (root / str(artifact.project_id) / str(artifact.id)).resolve()
    if not str(path).startswith(str(root)):
        raise HTTPException(status_code=400, detail="Artifact path rejected")
    if not path.is_file():
        raise HTTPException(status_code=404, detail="Artifact content is unavailable")
    return path.read_bytes()


def validate_attachment(content: bytes, filename: str, declared_type: str | None) -> str:
    """Sniff image types; reject executable or mismatched declarations."""
    settings = get_settings()
    guessed, _ = mimetypes.guess_type(filename)
    content_type = (declared_type or guessed or "").lower()
    is_png = content.startswith(b"\x89PNG\r\n\x1a\n")
    is_jpeg = content.startswith(b"\xff\xd8\xff")
    if content_type == "image/png" and not is_png:
        raise HTTPException(status_code=422, detail="File content does not match image/png")
    if content_type in {"image/jpeg", "image/jpg"}:
        if not is_jpeg:
            raise HTTPException(status_code=422, detail="File content does not match image/jpeg")
        content_type = "image/jpeg"
    if content_type == "image/png" and not is_png:
        raise HTTPException(status_code=422, detail="File content does not match image/png")
    if content_type == "application/json":
        try:
            import json

            json.loads(content.decode("utf-8"))
        except (UnicodeDecodeError, ValueError) as exc:
            raise HTTPException(status_code=422, detail="Attachment is not valid JSON") from exc
    if content_type not in settings.allowed_attachment_types:
        raise HTTPException(
            status_code=415,
            detail="Only PNG, JPEG, JSON, and plain-text attachments are accepted",
        )
    return content_type


def http_exchange_payload(
    *,
    request_method: str,
    request_url: str,
    request_headers: dict[str, str] | None,
    request_body: str | None,
    response_status: int | None,
    response_headers: dict[str, str] | None,
    response_body: str | None,
    elapsed_ms: int | None,
    actor_label: str,
    notes: str = "",
    source_note: str = "",
) -> dict:
    return {
        "request": {
            "method": request_method.upper(),
            "url": redact_text(request_url),
            "headers": redact_headers(request_headers),
            "body": truncate(redact_text(request_body or "")),
        },
        "response": {
            "status": response_status,
            "headers": redact_headers(response_headers),
            "body": truncate(redact_text(response_body or "")),
        },
        "elapsed_ms": elapsed_ms,
        "actor": actor_label,
        "notes": redact_text(notes),
        "source_note": source_note,
    }


def create_evidence(
    db: Session,
    *,
    project: Project,
    finding_id: uuid.UUID | None,
    run_id: uuid.UUID | None,
    attempt_id: uuid.UUID | None,
    build_id: uuid.UUID | None,
    kind: str,
    attribution: str,
    summary: str,
    payload: dict,
    highlight: list[str] | None = None,
    artifact_id: uuid.UUID | None = None,
    actor_label: str = "",
    method: str = "",
    endpoint: str = "",
    created_by: uuid.UUID | None = None,
) -> Evidence:
    evidence = Evidence(
        project_id=project.id,
        finding_id=finding_id,
        run_id=run_id,
        attempt_id=attempt_id,
        build_id=build_id,
        kind=kind,
        attribution=attribution,
        summary=summary[:400],
        payload=redact_payload(payload),
        highlight=[redact_text(h) for h in (highlight or [])],
        artifact_id=artifact_id,
        actor_label=actor_label,
        method=method,
        endpoint=redact_text(endpoint)[:400],
        created_by=created_by,
    )
    db.add(evidence)
    db.flush()
    return evidence

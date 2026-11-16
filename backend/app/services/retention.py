"""Evidence retention: bounded raw artifacts, retained metadata and frozen exports."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Artifact, AuditEvent, Evidence


def _artifact_path(artifact: Artifact):
    from app.services.evidence import artifact_root

    root = artifact_root()
    path = (root / str(artifact.project_id) / str(artifact.id)).resolve()
    if not str(path).startswith(str(root)):
        raise RuntimeError("artifact path rejected")
    return path


def prune_evidence(
    db: Session,
    *,
    days: int,
    dry_run: bool = False,
    actor_id: uuid.UUID | None = None,
    actor_label: str = "retention",
) -> dict[str, Any]:
    """Remove raw evidence payloads/artifacts older than ``days``.

    Observations, verdicts, finding records, and frozen export bytes are retained. The
    evidence row remains with a pruned marker so missing proof is explicit rather than
    silently disappearing.
    """
    if days < 1:
        raise ValueError("retention days must be at least 1")
    cutoff = datetime.now(UTC) - timedelta(days=days)
    rows = list(
        db.execute(
            select(Evidence).where(Evidence.created_at < cutoff, Evidence.pruned_at.is_(None))
        ).scalars()
    )
    if dry_run:
        return {
            "dry_run": True,
            "days": days,
            "cutoff": cutoff.isoformat(),
            "candidates": len(rows),
            "pruned": 0,
            "artifacts_removed": 0,
        }

    artifacts_removed = 0
    for evidence in rows:
        if evidence.artifact_id is not None:
            artifact = db.get(Artifact, evidence.artifact_id)
            if artifact is not None:
                path = _artifact_path(artifact)
                if path.is_file():
                    path.unlink()
                    artifacts_removed += 1
                db.delete(artifact)
            evidence.artifact_id = None
        evidence.pruned_at = datetime.now(UTC)
        evidence.payload = {
            "pruned": True,
            "reason": f"Raw evidence exceeded the {days}-day retention window.",
        }
        evidence.highlight = []
    if rows:
        db.add(
            AuditEvent(
                actor_id=actor_id,
                actor_label=actor_label,
                action="evidence.pruned",
                target_type="evidence",
                target_id=f"{len(rows)} record(s)",
                metadata_json={
                    "days": days,
                    "cutoff": cutoff.isoformat(),
                    "evidence": len(rows),
                    "artifacts": artifacts_removed,
                },
            )
        )
    db.flush()
    return {
        "dry_run": False,
        "days": days,
        "cutoff": cutoff.isoformat(),
        "candidates": len(rows),
        "pruned": len(rows),
        "artifacts_removed": artifacts_removed,
    }

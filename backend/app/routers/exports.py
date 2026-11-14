"""Frozen report exports: create, list, and download."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db
from app.deps import Principal, ProjectAccess, require_project
from app.domain import AuditAction, Role
from app.models import Artifact, AuditEvent, ExportSnapshot, Run
from app.routers.deps import csrf_protected
from app.services.evidence import read_bytes
from app.services.exports import EXPORT_FORMATS, create_export, export_row

ROUTER = APIRouter(prefix="/projects/{project_id}", tags=["exports"])


class ExportRequest(BaseModel):
    format: str = Field(pattern="^(pdf|csv|json)$")
    scope: str = Field(default="full", pattern="^(full|filtered)$")
    filters: dict = {}
    note: str = Field(default="", max_length=300)


def _run_or_404(db: Session, access: ProjectAccess, run_id: uuid.UUID) -> Run:
    run = db.get(Run, run_id)
    if run is None or run.project_id != access.project.id:
        raise HTTPException(status_code=404, detail="Run not found")
    return run


@ROUTER.post("/runs/{run_id}/exports", status_code=201)
def create_report_export(
    run_id: uuid.UUID,
    payload: ExportRequest,
    access: ProjectAccess = Depends(require_project(Role.VIEWER)),
    db: Session = Depends(get_db),
    principal: Principal = Depends(csrf_protected),
) -> dict:
    run = _run_or_404(db, access, run_id)
    if payload.format not in EXPORT_FORMATS:
        raise HTTPException(status_code=422, detail="Unsupported export format")
    if run.completed_at is None:
        raise HTTPException(
            status_code=409,
            detail="This run has not finished. Exports require a recorded snapshot.",
        )
    snapshots = create_export(
        db,
        project=access.project,
        run=run,
        fmt=payload.format,
        actor=principal.user,
        scope=payload.scope,
        scope_detail=payload.filters,
    )
    db.add(
        AuditEvent(
            actor_id=principal.user.id,
            actor_label=principal.label,
            project_id=access.project.id,
            action=AuditAction.EXPORT_CREATED.value,
            target_type="run",
            target_id=str(run.id),
            metadata_json={
                "format": payload.format,
                "scope": payload.scope,
                "exports": [str(snapshot.id) for snapshot in snapshots],
            },
        )
    )
    db.commit()
    return {
        "exports": [export_row(snapshot) for snapshot in snapshots],
        "message": f"{payload.format.upper()} snapshot generated from the recorded run state.",
    }


@ROUTER.get("/runs/{run_id}/exports")
def list_report_exports(
    run_id: uuid.UUID,
    access: ProjectAccess = Depends(require_project(Role.VIEWER)),
    db: Session = Depends(get_db),
) -> dict:
    run = _run_or_404(db, access, run_id)
    snapshots = list(
        db.execute(
            select(ExportSnapshot)
            .where(ExportSnapshot.run_id == run.id)
            .order_by(ExportSnapshot.created_at.desc())
        ).scalars()
    )
    return {"items": [export_row(snapshot) for snapshot in snapshots]}


@ROUTER.get("/exports/{export_id}")
def read_export(
    export_id: uuid.UUID,
    access: ProjectAccess = Depends(require_project(Role.VIEWER)),
    db: Session = Depends(get_db),
) -> dict:
    snapshot = db.get(ExportSnapshot, export_id)
    if snapshot is None or snapshot.project_id != access.project.id:
        raise HTTPException(status_code=404, detail="Export not found")
    return {
        **export_row(snapshot),
        "snapshot_at": snapshot.payload.get("snapshot_at"),
        "run_id": str(snapshot.run_id),
    }


@ROUTER.get("/exports/{export_id}/download")
def download_export(
    export_id: uuid.UUID,
    access: ProjectAccess = Depends(require_project(Role.VIEWER)),
    db: Session = Depends(get_db),
) -> object:
    from fastapi.responses import Response

    snapshot = db.get(ExportSnapshot, export_id)
    if snapshot is None or snapshot.project_id != access.project.id:
        raise HTTPException(status_code=404, detail="Export not found")
    artifact = db.get(Artifact, snapshot.artifact_id) if snapshot.artifact_id else None
    if artifact is None:
        raise HTTPException(status_code=410, detail="The frozen export content is unavailable")
    try:
        content = read_bytes(artifact)
    except HTTPException as exc:
        raise HTTPException(
            status_code=410,
            detail="The frozen export content is unavailable; generate a new snapshot.",
        ) from exc
    return Response(
        content=content,
        media_type=artifact.content_type,
        headers={
            "Content-Disposition": f'attachment; filename="{artifact.filename}"',
            "X-Content-Type-Options": "nosniff",
            "Cache-Control": "no-store",
        },
    )

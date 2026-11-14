"""Finding detail, evidence, replay recipes, automatic and guided retests, reviews."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db import get_db
from app.deps import Principal, ProjectAccess, require_project
from app.domain import AuditAction, EvidenceStatus, Role
from app.models import (
    Artifact,
    AuditEvent,
    Build,
    Evidence,
    Finding,
    Job,
    Recipe,
    RecipeRevision,
    RetestAttempt,
    Run,
    User,
)
from app.routers.deps import csrf_protected
from app.security import decrypt_secret
from app.serializers import finding_detail_row, iso
from app.services.evidence import read_bytes, save_bytes, validate_attachment
from app.services.policy import PolicyError
from app.services.recipes import (
    approve_revision,
    create_recipe_revision,
    guided_package,
    recipe_for_finding,
    recipe_preview,
)
from app.services.retests import (
    attempt_row,
    evidence_row,
    execute_attempt,
    mark_ready,
    queue_automatic_attempt,
    review_attempt,
    set_disposition,
    submit_guided,
    validate_evidence,
)
from app.services.runs import run_policy

ROUTER = APIRouter(prefix="/projects/{project_id}", tags=["findings"])


class ReadyRequest(BaseModel):
    build_id: uuid.UUID


class DispositionRequest(BaseModel):
    disposition: str = Field(pattern="^(open|false_positive|duplicate)$")
    reason: str = Field(default="", max_length=2000)


class EvidenceStatusRequest(BaseModel):
    status: str = Field(pattern="^(supported|needs_validation)$")
    note: str = Field(default="", max_length=2000)


class RetestRequest(BaseModel):
    build_id: uuid.UUID


class GuidedSubmit(BaseModel):
    build_id: uuid.UUID
    outcome: str = Field(pattern="^(fix_verified|still_reproducible|inconclusive)$")
    notes: str = Field(min_length=4, max_length=8000)
    artifact_id: uuid.UUID | None = None
    evidence_link: str = Field(default="", max_length=500)
    steps_revision: int = Field(default=1, ge=1)


class ReviewRequest(BaseModel):
    decision: str = Field(pattern="^(accepted|changes_requested)$")
    reason: str = Field(default="", max_length=2000)


class RecipeRequest(BaseModel):
    method: str = Field(pattern="^(GET|HEAD)$")
    path_template: str = Field(min_length=1, max_length=300)
    fixture_refs: list[dict] = []
    identity_refs: dict = {}
    expected_authorized: dict = {}
    expected_unauthorized: dict = {}
    assertion: dict = {}
    preconditions: list[str] = []
    approve: bool = False


def _finding_or_404(db: Session, access: ProjectAccess, finding_id: uuid.UUID) -> Finding:
    finding = db.get(Finding, finding_id)
    if finding is None or finding.project_id != access.project.id:
        raise HTTPException(status_code=404, detail="Finding not found")
    return finding


def _build_or_404(db: Session, access: ProjectAccess, build_id: uuid.UUID) -> Build:
    build = db.get(Build, build_id)
    if build is None or build.project_id != access.project.id:
        raise HTTPException(status_code=404, detail="Build not found in this project")
    return build


@ROUTER.get("/findings")
def list_findings(
    severity: list[str] = Query(default=[]),
    disposition: str | None = None,
    access: ProjectAccess = Depends(require_project(Role.VIEWER)),
    db: Session = Depends(get_db),
) -> dict:
    stmt = select(Finding).where(Finding.project_id == access.project.id)
    if severity:
        stmt = stmt.where(Finding.severity.in_(severity))
    if disposition:
        stmt = stmt.where(Finding.disposition == disposition)
    findings = list(db.execute(stmt.order_by(Finding.public_id)).scalars())
    return {
        "items": [
            {
                "id": str(finding.id),
                "public_id": finding.public_id,
                "title": finding.title,
                "severity": finding.severity,
                "issue_class": finding.issue_class,
                "evidence_status": finding.evidence_status,
                "disposition": finding.disposition,
                "scope_summary": finding.scope_summary,
            }
            for finding in findings
        ]
    }


@ROUTER.get("/findings/{finding_id}")
def read_finding(
    finding_id: uuid.UUID,
    run_id: uuid.UUID | None = None,
    build_id: uuid.UUID | None = None,
    access: ProjectAccess = Depends(require_project(Role.VIEWER)),
    db: Session = Depends(get_db),
) -> dict:
    finding = _finding_or_404(db, access, finding_id)
    build = _build_or_404(db, access, build_id) if build_id else None
    run = None
    if run_id:
        run = db.get(Run, run_id)
        if run is None or run.project_id != access.project.id:
            raise HTTPException(status_code=404, detail="Run not found")
        if build is None:
            build = db.get(Build, run.build_id)
    payload = finding_detail_row(db, project=access.project, finding=finding, build=build, run=run)
    payload["capabilities"] = {
        "can_operate": access.can(Role.OPERATOR),
        "can_retest": access.can(Role.DEVELOPER),
        "can_export": access.can(Role.VIEWER),
    }
    return payload


@ROUTER.post("/findings/{finding_id}/ready")
def mark_ready_for_retest(
    finding_id: uuid.UUID,
    payload: ReadyRequest,
    access: ProjectAccess = Depends(require_project(Role.OPERATOR)),
    db: Session = Depends(get_db),
    principal: Principal = Depends(csrf_protected),
) -> dict:
    finding = _finding_or_404(db, access, finding_id)
    build = _build_or_404(db, access, payload.build_id)
    marker = mark_ready(
        db, project=access.project, finding=finding, build=build, actor=principal.user
    )
    db.add(
        AuditEvent(
            actor_id=principal.user.id,
            actor_label=principal.label,
            project_id=access.project.id,
            action=AuditAction.READY_FOR_RETEST.value,
            target_type="finding",
            target_id=str(finding.id),
            metadata_json={"build_id": str(build.id), "build_label": build.label},
        )
    )
    db.commit()
    return {
        "marked_at": iso(marker.marked_at),
        "finding_id": str(finding.id),
        "build_id": str(build.id),
        "note": "This marker schedules work; it does not change the verification outcome.",
    }


@ROUTER.patch("/findings/{finding_id}")
def change_disposition(
    finding_id: uuid.UUID,
    payload: DispositionRequest,
    access: ProjectAccess = Depends(require_project(Role.OPERATOR)),
    db: Session = Depends(get_db),
    principal: Principal = Depends(csrf_protected),
) -> dict:
    finding = _finding_or_404(db, access, finding_id)
    set_disposition(db, finding=finding, disposition=payload.disposition, reason=payload.reason)
    db.add(
        AuditEvent(
            actor_id=principal.user.id,
            actor_label=principal.label,
            project_id=access.project.id,
            action=AuditAction.DISPOSITION_CHANGED.value,
            target_type="finding",
            target_id=str(finding.id),
            metadata_json={"disposition": payload.disposition, "reason": payload.reason[:300]},
        )
    )
    db.commit()
    return {"id": str(finding.id), "disposition": finding.disposition}


@ROUTER.post("/findings/{finding_id}/evidence-status")
def set_evidence_status(
    finding_id: uuid.UUID,
    payload: EvidenceStatusRequest,
    access: ProjectAccess = Depends(require_project(Role.OPERATOR)),
    db: Session = Depends(get_db),
    principal: Principal = Depends(csrf_protected),
) -> dict:
    finding = _finding_or_404(db, access, finding_id)
    validate_evidence(
        db, finding=finding, actor=principal.user, status=payload.status, note=payload.note
    )
    db.add(
        AuditEvent(
            actor_id=principal.user.id,
            actor_label=principal.label,
            project_id=access.project.id,
            action=AuditAction.EVIDENCE_VALIDATED.value,
            target_type="finding",
            target_id=str(finding.id),
            metadata_json={"status": payload.status, "note": payload.note[:300]},
        )
    )
    db.commit()
    return {
        "id": str(finding.id),
        "evidence_status": finding.evidence_status,
        "retest_method": finding.retest_method,
    }


@ROUTER.get("/findings/{finding_id}/guided")
def guided(
    finding_id: uuid.UUID,
    build_id: uuid.UUID | None = None,
    access: ProjectAccess = Depends(require_project(Role.VIEWER)),
    db: Session = Depends(get_db),
) -> dict:
    finding = _finding_or_404(db, access, finding_id)
    build = (
        _build_or_404(db, access, build_id)
        if build_id
        else db.execute(
            select(Build)
            .where(Build.project_id == access.project.id)
            .order_by(Build.created_at.desc())
            .limit(1)
        ).scalar_one_or_none()
    )
    if build is None:
        raise HTTPException(status_code=409, detail="Register a build before preparing a retest")
    return guided_package(
        db,
        project=access.project,
        finding=finding,
        build=build,
        can_submit=access.can(Role.DEVELOPER),
    )


@ROUTER.get("/findings/{finding_id}/recipe")
def read_recipe(
    finding_id: uuid.UUID,
    access: ProjectAccess = Depends(require_project(Role.VIEWER)),
    db: Session = Depends(get_db),
) -> dict:
    finding = _finding_or_404(db, access, finding_id)
    return {"recipe": recipe_for_finding(db, finding.id)}


@ROUTER.post("/findings/{finding_id}/recipes", status_code=201)
def create_recipe(
    finding_id: uuid.UUID,
    payload: RecipeRequest,
    access: ProjectAccess = Depends(require_project(Role.OPERATOR)),
    db: Session = Depends(get_db),
    principal: Principal = Depends(csrf_protected),
) -> dict:
    finding = _finding_or_404(db, access, finding_id)
    recipe, revision = create_recipe_revision(
        db,
        project=access.project,
        finding=finding,
        payload=payload.model_dump(),
        actor=principal.user,
        approve=payload.approve,
    )
    db.add(
        AuditEvent(
            actor_id=principal.user.id,
            actor_label=principal.label,
            project_id=access.project.id,
            action=AuditAction.RECIPE_APPROVED.value
            if payload.approve
            else "retest.recipe_created",
            target_type="recipe_revision",
            target_id=str(revision.id),
            metadata_json={"revision": revision.revision, "approved": payload.approve},
        )
    )
    db.commit()
    return {
        "recipe_id": str(recipe.id),
        "revision_id": str(revision.id),
        "revision": revision.revision,
        "approved": revision.approved_at is not None,
    }


@ROUTER.post("/recipes/{recipe_id}/revisions/{revision_id}/approve")
def approve_recipe(
    recipe_id: uuid.UUID,
    revision_id: uuid.UUID,
    access: ProjectAccess = Depends(require_project(Role.OPERATOR)),
    db: Session = Depends(get_db),
    principal: Principal = Depends(csrf_protected),
) -> dict:
    recipe = db.get(Recipe, recipe_id)
    revision = db.get(RecipeRevision, revision_id)
    if recipe is None or recipe.project_id != access.project.id or revision is None:
        raise HTTPException(status_code=404, detail="Recipe revision not found")
    approve_revision(db, recipe=recipe, revision=revision, actor=principal.user)
    db.add(
        AuditEvent(
            actor_id=principal.user.id,
            actor_label=principal.label,
            project_id=access.project.id,
            action=AuditAction.RECIPE_APPROVED.value,
            target_type="recipe_revision",
            target_id=str(revision.id),
            metadata_json={"revision": revision.revision},
        )
    )
    db.commit()
    return {"recipe_id": str(recipe.id), "revision": revision.revision, "approved": True}


@ROUTER.get("/findings/{finding_id}/recipes/{revision_id}/preview")
def preview_recipe(
    finding_id: uuid.UUID,
    revision_id: uuid.UUID,
    build_id: uuid.UUID,
    access: ProjectAccess = Depends(require_project(Role.OPERATOR)),
    db: Session = Depends(get_db),
) -> dict:
    finding = _finding_or_404(db, access, finding_id)
    revision = db.get(RecipeRevision, revision_id)
    if revision is None:
        raise HTTPException(status_code=404, detail="Recipe revision not found")
    recipe = db.get(Recipe, revision.recipe_id)
    if recipe is None or recipe.finding_id != finding.id:
        raise HTTPException(status_code=404, detail="Recipe revision not found for this finding")
    build = _build_or_404(db, access, build_id)
    return recipe_preview(
        db, project=access.project, finding=finding, build=build, revision=revision
    )


@ROUTER.post("/findings/{finding_id}/retests", status_code=202)
def start_automatic_retest(
    finding_id: uuid.UUID,
    payload: RetestRequest,
    access: ProjectAccess = Depends(require_project(Role.DEVELOPER)),
    db: Session = Depends(get_db),
    principal: Principal = Depends(csrf_protected),
) -> dict:
    finding = _finding_or_404(db, access, finding_id)
    build = _build_or_404(db, access, payload.build_id)
    attempt = queue_automatic_attempt(
        db,
        project=access.project,
        finding=finding,
        build=build,
        actor=principal.user,
        mode=(get_settings().demo_enabled and "demo") or "live",
        settings=get_settings(),
    )
    db.add(
        AuditEvent(
            actor_id=principal.user.id,
            actor_label=principal.label,
            project_id=access.project.id,
            action=AuditAction.RETEST_REQUESTED.value,
            target_type="retest_attempt",
            target_id=str(attempt.id),
            metadata_json={"finding": finding.public_id, "build_id": str(build.id)},
        )
    )
    db.commit()
    return {
        "attempt": attempt_row(db, attempt),
        "message": (
            "Retest queued. The worker executes the approved read-only recipe and records "
            "the evidence here."
        ),
    }


@ROUTER.post("/findings/{finding_id}/guided-attempts", status_code=201)
def create_guided_attempt(
    finding_id: uuid.UUID,
    payload: GuidedSubmit,
    access: ProjectAccess = Depends(require_project(Role.DEVELOPER)),
    db: Session = Depends(get_db),
    principal: Principal = Depends(csrf_protected),
) -> dict:
    finding = _finding_or_404(db, access, finding_id)
    build = _build_or_404(db, access, payload.build_id)
    attempt = submit_guided(
        db,
        project=access.project,
        finding=finding,
        build=build,
        actor=principal.user,
        outcome=payload.outcome,
        notes=payload.notes,
        evidence_artifact_id=payload.artifact_id,
        evidence_link=payload.evidence_link,
        steps_revision=payload.steps_revision,
        mode="demo" if get_settings().demo_enabled else "live",
    )
    db.add(
        AuditEvent(
            actor_id=principal.user.id,
            actor_label=principal.label,
            project_id=access.project.id,
            action=AuditAction.GUIDED_SUBMITTED.value,
            target_type="retest_attempt",
            target_id=str(attempt.id),
            metadata_json={
                "finding": finding.public_id,
                "outcome": payload.outcome,
                "build_id": str(build.id),
            },
        )
    )
    db.commit()
    return {
        "attempt": attempt_row(db, attempt),
        "message": "Submitted for reviewer acceptance. The build verdict is unchanged until accepted.",
    }


@ROUTER.get("/attempts")
def list_attempts(
    finding_id: uuid.UUID | None = None,
    run_id: uuid.UUID | None = None,
    access: ProjectAccess = Depends(require_project(Role.VIEWER)),
    db: Session = Depends(get_db),
) -> dict:
    stmt = (
        select(RetestAttempt)
        .where(RetestAttempt.project_id == access.project.id)
        .order_by(RetestAttempt.requested_at.desc())
        .limit(100)
    )
    if finding_id:
        stmt = stmt.where(RetestAttempt.finding_id == finding_id)
    if run_id:
        stmt = stmt.where(RetestAttempt.run_id == run_id)
    attempts = list(db.execute(stmt).scalars())
    return {"items": [attempt_row(db, attempt, include_evidence=False) for attempt in attempts]}


@ROUTER.get("/attempts/{attempt_id}")
def read_attempt(
    attempt_id: uuid.UUID,
    access: ProjectAccess = Depends(require_project(Role.VIEWER)),
    db: Session = Depends(get_db),
) -> dict:
    attempt = db.get(RetestAttempt, attempt_id)
    if attempt is None or attempt.project_id != access.project.id:
        raise HTTPException(status_code=404, detail="Attempt not found")
    return attempt_row(db, attempt)


@ROUTER.post("/attempts/{attempt_id}/review")
def review(
    attempt_id: uuid.UUID,
    payload: ReviewRequest,
    access: ProjectAccess = Depends(require_project(Role.OPERATOR)),
    db: Session = Depends(get_db),
    principal: Principal = Depends(csrf_protected),
) -> dict:
    attempt = db.get(RetestAttempt, attempt_id)
    if attempt is None or attempt.project_id != access.project.id:
        raise HTTPException(status_code=404, detail="Attempt not found")
    result = review_attempt(
        db,
        attempt=attempt,
        reviewer=principal.user,
        decision=payload.decision,
        reason=payload.reason,
    )
    db.add(
        AuditEvent(
            actor_id=principal.user.id,
            actor_label=principal.label,
            project_id=access.project.id,
            action=(
                AuditAction.REVIEW_ACCEPTED.value
                if payload.decision == "accepted"
                else AuditAction.REVIEW_CHANGES_REQUESTED.value
            ),
            target_type="retest_attempt",
            target_id=str(attempt.id),
            metadata_json={"decision": payload.decision, "reason": payload.reason[:300]},
        )
    )
    db.commit()
    return result


@ROUTER.get("/evidence/{evidence_id}")
def read_evidence(
    evidence_id: uuid.UUID,
    access: ProjectAccess = Depends(require_project(Role.VIEWER)),
    db: Session = Depends(get_db),
) -> dict:
    evidence = db.get(Evidence, evidence_id)
    if evidence is None or evidence.project_id != access.project.id:
        raise HTTPException(status_code=404, detail="Evidence not found")
    artifact = db.get(Artifact, evidence.artifact_id) if evidence.artifact_id else None
    return {
        **evidence_row(evidence),
        "build_id": str(evidence.build_id) if evidence.build_id else None,
        "run_id": str(evidence.run_id) if evidence.run_id else None,
        "artifact": (
            {
                "id": str(artifact.id),
                "filename": artifact.filename,
                "content_type": artifact.content_type,
                "size_bytes": artifact.size_bytes,
                "download_url": f"/api/projects/{access.project.id}/artifacts/{artifact.id}/download",
            }
            if artifact
            else None
        ),
    }


@ROUTER.post("/artifacts", status_code=201)
async def upload_artifact(
    file: UploadFile = File(...),
    note: str = Form(default=""),
    access: ProjectAccess = Depends(require_project(Role.DEVELOPER)),
    db: Session = Depends(get_db),
    principal: Principal = Depends(csrf_protected),
) -> dict:
    settings = get_settings()
    raw = await file.read(settings.max_upload_bytes + 1)
    if len(raw) > settings.max_upload_bytes:
        raise HTTPException(
            status_code=413, detail=f"Upload exceeds the {settings.max_upload_bytes} byte limit"
        )
    content_type = validate_attachment(raw, file.filename or "attachment", file.content_type)
    artifact = save_bytes(
        db,
        project=access.project,
        content=raw,
        filename=file.filename or "attachment",
        content_type=content_type,
        created_by=principal.user.id,
        max_bytes=settings.max_upload_bytes,
    )
    db.add(
        AuditEvent(
            actor_id=principal.user.id,
            actor_label=principal.label,
            project_id=access.project.id,
            action=AuditAction.EVIDENCE_UPLOADED.value,
            target_type="artifact",
            target_id=str(artifact.id),
            metadata_json={"content_type": content_type, "size_bytes": artifact.size_bytes},
        )
    )
    db.commit()
    return {
        "id": str(artifact.id),
        "filename": artifact.filename,
        "content_type": artifact.content_type,
        "size_bytes": artifact.size_bytes,
        "sha256": artifact.sha256,
        "note": note[:300],
        "download_url": f"/api/projects/{access.project.id}/artifacts/{artifact.id}/download",
    }


@ROUTER.get("/artifacts/{artifact_id}/download")
def download_artifact(
    artifact_id: uuid.UUID,
    access: ProjectAccess = Depends(require_project(Role.VIEWER)),
    db: Session = Depends(get_db),
) -> object:
    from fastapi.responses import Response

    artifact = db.get(Artifact, artifact_id)
    if artifact is None or artifact.project_id != access.project.id:
        raise HTTPException(status_code=404, detail="Artifact not found")
    content = read_bytes(artifact)
    return Response(
        content=content,
        media_type=artifact.content_type,
        headers={
            "Content-Disposition": f'attachment; filename="{artifact.filename}"',
            "X-Content-Type-Options": "nosniff",
            "Cache-Control": "no-store",
        },
    )


_ = (
    EvidenceStatus,
    Job,
    PolicyError,
    User,
    decrypt_secret,
    execute_attempt,
    evidence_row,
    run_policy,
)

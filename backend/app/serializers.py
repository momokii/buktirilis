"""API serializers shared by routers."""

from __future__ import annotations

import uuid
from datetime import datetime
from pathlib import Path
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.domain import SEVERITY_ORDER, Severity
from app.models import (
    Artifact,
    Build,
    Evidence,
    EvidenceDecision,
    Finding,
    Observation,
    OpenApiDocument,
    Project,
    ProjectMember,
    ReadyMarker,
    Recipe,
    RetestAttempt,
    Run,
    TargetConfig,
    TestAccount,
    User,
)
from app.services.evidence import artifact_root
from app.services.findings import (
    duplicate_candidates,
    eligibility,
    latest_observation,
    state_for_build,
)
from app.services.retests import attempt_row, evidence_row


def iso(value: datetime | None) -> str | None:
    return value.isoformat().replace("+00:00", "Z") if value else None


def user_row(user: User) -> dict[str, Any]:
    return {
        "id": str(user.id),
        "email": user.email,
        "display_name": user.display_name,
        "is_admin": user.is_admin,
        "is_active": user.is_active,
        "created_at": iso(user.created_at),
    }


def project_row(db: Session, project: Project, role: str | None) -> dict[str, Any]:
    config = db.execute(
        select(TargetConfig)
        .where(TargetConfig.project_id == project.id)
        .order_by(TargetConfig.revision.desc())
        .limit(1)
    ).scalar_one_or_none()
    builds = db.execute(
        select(func.count()).select_from(Build).where(Build.project_id == project.id)
    ).scalar_one()
    runs = db.execute(
        select(func.count()).select_from(Run).where(Run.project_id == project.id)
    ).scalar_one()
    open_findings = db.execute(
        select(func.count())
        .select_from(Finding)
        .where(Finding.project_id == project.id, Finding.disposition == "open")
    ).scalar_one()
    last_run = db.execute(
        select(Run).where(Run.project_id == project.id).order_by(Run.created_at.desc()).limit(1)
    ).scalar_one_or_none()
    return {
        "id": str(project.id),
        "slug": project.slug,
        "name": project.name,
        "description": project.description,
        "role": role,
        "counts": {"builds": builds, "runs": runs, "open_findings": open_findings},
        "target": target_row(config) if config else None,
        "last_run": (
            {
                "id": str(last_run.id),
                "status": last_run.status,
                "kind": last_run.kind,
                "mode": last_run.mode,
                "created_at": iso(last_run.created_at),
            }
            if last_run
            else None
        ),
    }


def target_row(config: TargetConfig) -> dict[str, Any]:
    return {
        "id": str(config.id),
        "revision": config.revision,
        "base_url": config.base_url,
        "allowed_origins": config.allowed_origins,
        "path_prefixes": config.path_prefixes,
        "environment_label": config.environment_label,
        "scope_owner": config.scope_owner,
        "authorization_reference": config.authorization_reference,
        "run_limits": config.run_limits,
        "created_at": iso(config.created_at),
    }


def member_row(db: Session, member: ProjectMember) -> dict[str, Any]:
    user = db.get(User, member.user_id)
    return {
        "user_id": str(member.user_id),
        "email": user.email if user else "",
        "display_name": user.display_name if user else "",
        "role": member.role,
        "added_at": iso(member.created_at),
    }


def build_row(db: Session, build: Build, *, include_openapi: bool = True) -> dict[str, Any]:
    document = (
        db.get(OpenApiDocument, build.openapi_document_id) if build.openapi_document_id else None
    )
    run_count = db.execute(
        select(func.count()).select_from(Run).where(Run.build_id == build.id)
    ).scalar_one()
    payload = {
        "id": str(build.id),
        "label": build.label,
        "target_url": build.target_url,
        "commit_sha": build.commit_sha,
        "build_metadata": build.build_metadata,
        "identity": {
            "expected": build.expected_identity,
            "observed": build.identity_observed,
            "attested": build.identity_attested_by is not None,
            "source": (
                "operator_attested"
                if build.identity_attested_by is not None and not build.identity_observed
                else "observed"
                if build.identity_observed
                else "unrecorded"
            ),
        },
        "target_config_id": str(build.target_config_id),
        "created_at": iso(build.created_at),
        "run_count": run_count,
    }
    if include_openapi:
        payload["openapi"] = (
            {
                "id": str(document.id),
                "filename": document.filename,
                "sha256": document.sha256,
                "operations": len(document.operations or []),
                "declared_server_url": document.declared_server_url,
            }
            if document
            else None
        )
    return payload


def account_row(account: TestAccount) -> dict[str, Any]:
    return {
        "id": str(account.id),
        "name": account.name,
        "role": account.role_label,
        "tenant": account.tenant_label,
        "identity_check_path": account.identity_check_path,
        "credential_kind": account.credential_kind,
        "has_credential": bool(account.credential_ciphertext),
        "created_at": iso(account.created_at),
    }


def run_row(db: Session, run: Run, *, include_counts: bool = True) -> dict[str, Any]:
    build = db.get(Build, run.build_id)
    payload = {
        "id": str(run.id),
        "project_id": str(run.project_id),
        "build": {"id": str(build.id), "label": build.label} if build else None,
        "baseline_run_id": str(run.baseline_run_id) if run.baseline_run_id else None,
        "kind": run.kind,
        "mode": run.mode,
        "depth": run.depth,
        "status": run.status,
        "profile": {"code": run.profile_code, "version": run.profile_version},
        "engine": run.engine,
        "engine_version": run.engine_version,
        "requested_by": run.requested_by_label,
        "created_at": iso(run.created_at),
        "started_at": iso(run.started_at),
        "completed_at": iso(run.completed_at),
        "coverage_complete": run.coverage_complete,
        "ingest_state": run.ingest_state,
        "summary": run.summary,
        "failure_reason": run.failure_reason,
        "budget": run.budget,
        "limitations": run.limitations,
    }
    if include_counts:
        from app.services.findings import build_run_view, severity_counts

        rows = build_run_view(db, run)
        payload["counts"] = {
            "records": len(rows),
            "severity": severity_counts(rows),
        }
    return payload


def finding_summary_row(db: Session, finding: Finding, build_id: uuid.UUID) -> dict[str, Any]:
    state = state_for_build(db, finding.id, build_id)
    evidence_count = db.execute(
        select(func.count()).select_from(Evidence).where(Evidence.finding_id == finding.id)
    ).scalar_one()
    marked_ready = (
        db.execute(
            select(ReadyMarker.id).where(
                ReadyMarker.finding_id == finding.id, ReadyMarker.build_id == build_id
            )
        ).scalar_one_or_none()
        is not None
    )
    return {
        "id": str(finding.id),
        "public_id": finding.public_id,
        "title": finding.title,
        "severity": finding.severity,
        "issue_class": finding.issue_class,
        "scope_summary": finding.scope_summary,
        "actors_summary": finding.actors_summary,
        "evidence_status": finding.evidence_status,
        "retest_method": eligibility(finding),
        "disposition": finding.disposition,
        "marked_ready": marked_ready,
        "verification": {
            "outcome": state.outcome.value,
            "source": state.source,
            "observed_at": iso(state.observed_at),
            "reason_code": state.reason_code,
            "reason": state.reason_text,
            "stale": state.stale,
        },
        "evidence_count": evidence_count,
    }


def finding_detail_row(
    db: Session, *, project: Project, finding: Finding, build: Build | None, run: Run | None
) -> dict[str, Any]:
    target_build = build or (
        db.execute(
            select(Build)
            .where(Build.project_id == project.id)
            .order_by(Build.created_at.desc())
            .limit(1)
        ).scalar_one_or_none()
    )
    state = state_for_build(db, finding.id, target_build.id) if target_build is not None else None
    evidence_rows = list(
        db.execute(
            select(Evidence)
            .where(Evidence.finding_id == finding.id)
            .order_by(Evidence.created_at.desc())
        ).scalars()
    )
    attempts = list(
        db.execute(
            select(RetestAttempt)
            .where(RetestAttempt.finding_id == finding.id)
            .order_by(RetestAttempt.requested_at.desc())
        ).scalars()
    )
    observations = list(
        db.execute(
            select(Observation)
            .where(Observation.finding_id == finding.id)
            .order_by(Observation.observed_at.desc())
        ).scalars()
    )
    decisions = list(
        db.execute(
            select(EvidenceDecision)
            .where(EvidenceDecision.finding_id == finding.id)
            .order_by(EvidenceDecision.created_at)
        ).scalars()
    )
    recipe = db.execute(select(Recipe).where(Recipe.finding_id == finding.id)).scalar_one_or_none()
    marked_ready = None
    if target_build is not None:
        marker = db.execute(
            select(ReadyMarker).where(
                ReadyMarker.finding_id == finding.id, ReadyMarker.build_id == target_build.id
            )
        ).scalar_one_or_none()
        marked_ready = iso(marker.marked_at) if marker else None
    build_labels = {
        str(build_id): label
        for build_id, label in db.execute(
            select(Build.id, Build.label).where(Build.project_id == project.id)
        ).all()
    }
    run_links = {
        str(run_id): {"id": str(run_id), "kind": kind, "created_at": iso(created_at)}
        for run_id, kind, created_at in db.execute(
            select(Run.id, Run.kind, Run.created_at).where(Run.project_id == project.id)
        ).all()
    }
    latest = (
        latest_observation(db, finding.id, target_build.id) if target_build is not None else None
    )
    return {
        "id": str(finding.id),
        "public_id": finding.public_id,
        "project_id": str(project.id),
        "title": finding.title,
        "severity": finding.severity,
        "issue_class": finding.issue_class,
        "scope_summary": finding.scope_summary,
        "actors_summary": finding.actors_summary,
        "impact": finding.impact,
        "expected_behavior": finding.expected_behavior,
        "observed_behavior": finding.observed_behavior,
        "remediation": finding.remediation,
        "prerequisites": finding.prerequisites,
        "reproduction_steps": finding.reproduction_steps,
        "root_cause_hypothesis": finding.root_cause_hypothesis,
        "evidence_status": finding.evidence_status,
        "retest_method": eligibility(finding),
        "evidence_decisions": [
            {
                "status": decision.status,
                "reason": decision.reason,
                "actor": decision.actor_label,
                "at": iso(decision.created_at),
            }
            for decision in decisions
        ],
        "disposition": finding.disposition,
        "disposition_reason": finding.disposition_reason,
        "fingerprint": finding.fingerprint,
        "first_run_id": str(finding.first_run_id) if finding.first_run_id else None,
        "created_at": iso(finding.created_at),
        "build": (
            {
                "id": str(target_build.id),
                "label": target_build.label,
                "target_url": target_build.target_url,
                "commit_sha": target_build.commit_sha,
                "identity": {
                    "expected": target_build.expected_identity,
                    "observed": target_build.identity_observed,
                },
            }
            if target_build
            else None
        ),
        "run": (
            {
                "id": str(run.id),
                "kind": run.kind,
                "mode": run.mode,
                "completed_at": iso(run.completed_at),
            }
            if run is not None
            else None
        ),
        "verification": (
            {
                "outcome": state.outcome.value,
                "source": state.source,
                "observed_at": iso(state.observed_at),
                "reason_code": state.reason_code,
                "reason": state.reason_text,
                "stale": state.stale,
                "stale_note": state.stale_note,
            }
            if state
            else None
        ),
        "latest_observation": (
            {
                "id": str(latest.id),
                "outcome": latest.outcome,
                "source": latest.source,
                "observed_at": iso(latest.observed_at),
                "stale": bool((latest.detail or {}).get("stale")),
            }
            if latest
            else None
        ),
        "marked_ready_at": marked_ready,
        "recipe": ({"id": str(recipe.id), "state": recipe.state} if recipe else None),
        "evidence": [
            {
                **evidence_row(row),
                "artifact": _artifact_meta(db, row.artifact_id),
                "build_id": str(row.build_id) if row.build_id else None,
                "build_label": build_labels.get(str(row.build_id), "") if row.build_id else "",
                "run": run_links.get(str(row.run_id)) if row.run_id else None,
            }
            for row in evidence_rows
        ],
        "evidence_missing": [
            _missing_evidence_note(row)
            for row in evidence_rows
            if not _artifact_available(db, row.artifact_id)
        ],
        "attempts": [attempt_row(db, attempt) for attempt in attempts],
        "observations": [
            {
                "id": str(observation.id),
                "outcome": observation.outcome,
                "source": observation.source,
                "observed_at": iso(observation.observed_at),
                "recorded_at": iso(observation.recorded_at),
                "accepted": observation.accepted,
                "build_id": str(observation.build_id),
                "build_label": build_labels.get(str(observation.build_id), ""),
                "stale": bool((observation.detail or {}).get("stale")),
                "reason": observation.detail,
                "run": run_links.get(str(observation.run_id)) if observation.run_id else None,
            }
            for observation in observations
        ],
        "duplicate_candidates": duplicate_candidates(db, finding),
    }


def _artifact_meta(db: Session, artifact_id: uuid.UUID | None) -> dict[str, Any] | None:
    if artifact_id is None:
        return None
    artifact = db.get(Artifact, artifact_id)
    if artifact is None:
        return {"id": str(artifact_id), "available": False, "reason": "artifact record is missing"}
    available = _artifact_available(db, artifact_id)
    return {
        "id": str(artifact.id),
        "filename": artifact.filename,
        "content_type": artifact.content_type,
        "size_bytes": artifact.size_bytes,
        "sha256": artifact.sha256,
        "available": available,
        "reason": ""
        if available
        else "stored content is unavailable; the evidence cannot be shown",
        "download_url": f"/api/projects/{artifact.project_id}/artifacts/{artifact.id}/download",
    }


def _artifact_available(db: Session, artifact_id: uuid.UUID | None) -> bool:
    if artifact_id is None:
        return True
    artifact = db.get(Artifact, artifact_id)
    if artifact is None:
        return False
    root = artifact_root()
    path = (root / str(artifact.project_id) / str(artifact.id)).resolve()
    return str(path).startswith(str(root)) and path.is_file()


def _missing_evidence_note(evidence: Evidence) -> dict[str, Any]:
    return {
        "evidence_id": str(evidence.id),
        "summary": evidence.summary,
        "reason": "The attachment is referenced but its stored content is unavailable.",
    }


def severity_rank(value: str) -> int:
    try:
        return SEVERITY_ORDER[Severity(value)]
    except ValueError:
        return 5


def evidence_download_path(project: Project, evidence: Evidence) -> str:
    return f"/api/projects/{project.id}/evidence/{evidence.id}"


_ = (Path, attempt_row)

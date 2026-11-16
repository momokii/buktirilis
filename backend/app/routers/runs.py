"""Runs, live progress, report tabs, and build comparison."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db import get_db
from app.deps import Principal, ProjectAccess, get_principal, require_project
from app.domain import CONCLUSIVE_OUTCOMES, Role, RunKind, RunStatus, Severity
from app.models import Build, Finding, Run, RunCheck, Surface, TargetConfig
from app.routers.deps import csrf_protected
from app.serializers import iso, run_row
from app.services.findings import (
    bucket_counts,
    build_run_view,
    compare_scope,
    comparison_findings,
    coverage_counts,
    eligibility,
    finding_row,
    latest_verification_panel,
    severity_counts,
)
from app.services.profiles import (
    ACCESS_CONTROL_CODE,
    ACCESS_CONTROL_VERSION,
    depth_config,
    get_profile,
    profile_as_json,
)
from app.services.runs import cancel_run, create_run, preflight, run_progress

ROUTER = APIRouter(prefix="/projects/{project_id}", tags=["runs"])


class RunRequest(BaseModel):
    build_id: uuid.UUID
    kind: RunKind = RunKind.BASELINE
    depth: str = Field(default="quick", pattern="^(quick|standard)$")
    profile_code: str = ACCESS_CONTROL_CODE
    profile_version: int = ACCESS_CONTROL_VERSION
    account_ids: list[uuid.UUID] = []
    unauthenticated: bool = False
    baseline_run_id: uuid.UUID | None = None
    accept_reduced_scope: bool = False


class PreflightRequest(BaseModel):
    build_id: uuid.UUID
    kind: RunKind = RunKind.BASELINE
    depth: str = Field(default="quick", pattern="^(quick|standard)$")
    profile_code: str = ACCESS_CONTROL_CODE
    profile_version: int = ACCESS_CONTROL_VERSION
    account_ids: list[uuid.UUID] = []
    unauthenticated: bool = False
    baseline_run_id: uuid.UUID | None = None


def _run_or_404(db: Session, access: ProjectAccess, run_id: uuid.UUID) -> Run:
    run = db.get(Run, run_id)
    if run is None or run.project_id != access.project.id:
        raise HTTPException(status_code=404, detail="Run not found")
    return run


@ROUTER.get("/runs")
def list_runs(
    kind: str | None = Query(default=None),
    status: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    access: ProjectAccess = Depends(require_project(Role.VIEWER)),
    db: Session = Depends(get_db),
) -> dict:
    stmt = (
        select(Run)
        .where(Run.project_id == access.project.id)
        .order_by(Run.created_at.desc())
        .limit(limit)
    )
    if kind:
        stmt = stmt.where(Run.kind == kind)
    if status:
        stmt = stmt.where(Run.status == status)
    runs = list(db.execute(stmt).scalars())
    builds = {
        build.id: build.label
        for build in db.execute(
            select(Build).where(Build.project_id == access.project.id)
        ).scalars()
    }
    return {
        "items": [
            {
                **run_row(db, run),
                "build": {"id": str(run.build_id), "label": builds.get(run.build_id, "")},
            }
            for run in runs
        ]
    }


@ROUTER.post("/runs/preflight")
def preview_preflight(
    payload: PreflightRequest,
    access: ProjectAccess = Depends(require_project(Role.OPERATOR)),
    db: Session = Depends(get_db),
) -> dict:
    build = db.get(Build, payload.build_id)
    if build is None or build.project_id != access.project.id:
        raise HTTPException(status_code=404, detail="Build not found in this project")
    settings = get_settings()
    result = preflight(
        db,
        settings=settings,
        project=access.project,
        build=build,
        kind=payload.kind.value,
        depth=payload.depth,
        profile_code=payload.profile_code,
        profile_version=payload.profile_version,
        account_ids=payload.account_ids,
        unauthenticated=payload.unauthenticated,
        baseline_run_id=payload.baseline_run_id,
    )
    try:
        profile = get_profile(payload.profile_code, payload.profile_version)
    except KeyError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    limits = depth_config(payload.depth)
    return {
        "preflight": result.as_dict(),
        "profile": profile_as_json(profile),
        "depth": {
            "name": payload.depth,
            "limits": limits,
            "note": "Engine spend is an estimate and can overshoot the configured budget.",
        },
        "expected_checks": _expected_checks(build, profile, payload.depth),
    }


def _expected_checks(build: Build, profile, depth: str) -> list[dict]:
    rows = []
    for scenario in profile.scenarios:
        if not scenario.surfaces:
            continue
        rows.append(
            {
                "scenario_code": scenario.code,
                "title": scenario.title,
                "owasp_refs": list(scenario.owasp_refs),
                "automatic": scenario.automatic_eligible,
                "method_note": scenario.method_note,
            }
        )
    return rows


@ROUTER.post("/runs", status_code=201)
def request_run(
    payload: RunRequest,
    access: ProjectAccess = Depends(require_project(Role.OPERATOR)),
    db: Session = Depends(get_db),
    principal: Principal = Depends(csrf_protected),
) -> dict:
    build = db.get(Build, payload.build_id)
    if build is None or build.project_id != access.project.id:
        raise HTTPException(status_code=404, detail="Build not found in this project")
    if payload.baseline_run_id:
        baseline = db.get(Run, payload.baseline_run_id)
        if baseline is None or baseline.project_id != access.project.id:
            raise HTTPException(status_code=404, detail="Baseline run not found in this project")
    try:
        profile = get_profile(payload.profile_code, payload.profile_version)
    except KeyError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    run, created = create_run(
        db,
        settings=get_settings(),
        project=access.project,
        build=build,
        kind=payload.kind.value,
        depth=payload.depth,
        profile_code=profile.code,
        profile_version=profile.version,
        account_ids=payload.account_ids,
        unauthenticated=payload.unauthenticated,
        baseline_run_id=payload.baseline_run_id,
        actor=principal.user,
        accept_reduced_scope=payload.accept_reduced_scope,
    )
    db.commit()
    return {
        "run": run_row(db, run),
        "created": created,
        "message": (
            "Run queued."
            if created
            else "An identical run is already queued or running; returning that run."
        ),
    }


@ROUTER.get("/runs/{run_id}")
def read_run(
    run_id: uuid.UUID,
    access: ProjectAccess = Depends(require_project(Role.VIEWER)),
    db: Session = Depends(get_db),
) -> dict:
    run = _run_or_404(db, access, run_id)
    build = db.get(Build, run.build_id)
    rows = build_run_view(db, run)
    counts = coverage_counts(db, run)
    baseline = db.get(Run, run.baseline_run_id) if run.baseline_run_id else None
    return {
        **run_row(db, run),
        "build": {
            "id": str(build.id),
            "label": build.label,
            "target_url": build.target_url,
            "commit_sha": build.commit_sha,
            "identity": {
                "expected": build.expected_identity,
                "observed": build.identity_observed,
            },
            "openapi_document_id": str(build.openapi_document_id)
            if build.openapi_document_id
            else None,
        }
        if build
        else None,
        "baseline": (
            {
                "id": str(baseline.id),
                "build_id": str(baseline.build_id),
                "kind": baseline.kind,
                "mode": baseline.mode,
                "completed_at": iso(baseline.completed_at),
            }
            if baseline
            else None
        ),
        "progress": run_progress(db, run),
        "counts": {
            "records": len(rows),
            "severity": severity_counts(rows),
            "coverage": counts,
        },
        "scope": {
            "base_url": (run.scope_snapshot or {}).get("base_url"),
            "allowed_origins": (run.scope_snapshot or {}).get("allowed_origins", []),
            "path_prefixes": (run.scope_snapshot or {}).get("path_prefixes", []),
            "accounts": (run.scope_snapshot or {}).get("accounts", []),
            "unauthenticated": (run.scope_snapshot or {}).get("unauthenticated", False),
            "build_identity": (run.scope_snapshot or {}).get("build_identity"),
        },
    }


@ROUTER.get("/runs/{run_id}/progress")
def read_progress(
    run_id: uuid.UUID,
    access: ProjectAccess = Depends(require_project(Role.VIEWER)),
    db: Session = Depends(get_db),
) -> dict:
    run = _run_or_404(db, access, run_id)
    return run_progress(db, run)


@ROUTER.post("/runs/{run_id}/cancel")
def cancel(
    run_id: uuid.UUID,
    access: ProjectAccess = Depends(require_project(Role.OPERATOR)),
    db: Session = Depends(get_db),
    principal: Principal = Depends(csrf_protected),
) -> dict:
    run = _run_or_404(db, access, run_id)
    cancel_run(db, run=run, actor=principal.user)
    db.commit()
    return {
        "run_id": str(run.id),
        "status": run.status,
        "message": "Cancellation requested. The worker stops at the next stage boundary.",
    }


def _filtered_rows(
    db: Session,
    run: Run,
    *,
    severity: list[str] | None = None,
    outcome: list[str] | None = None,
    method: list[str] | None = None,
    surface: str | None = None,
    query: str | None = None,
    sort: str = "severity",
) -> list[dict]:
    items = build_run_view(db, run)
    baseline = db.get(Run, run.baseline_run_id) if run.baseline_run_id else None
    comparison_map = (
        {row["id"]: row for row in comparison_findings(db, baseline, run)} if baseline else {}
    )
    rows: list[dict] = []
    for item in items:
        row = finding_row(item, run=run)
        if comparison_map.get(row["id"]):
            row["bucket"] = comparison_map[row["id"]]["bucket"]
            row["bucket_reason"] = comparison_map[row["id"]]["bucket_reason"]
        if severity and row["severity"] not in severity:
            continue
        if outcome and row["verification"]["outcome"] not in outcome:
            continue
        if method and row["retest_method"] not in method:
            continue
        if (
            surface
            and surface.lower() not in (row["scope_summary"] + " " + row["actors_summary"]).lower()
        ):
            continue
        if (
            query
            and query.lower() not in row["title"].lower()
            and query.lower() not in row["public_id"].lower()
        ):
            continue
        rows.append(row)
    severity_order = {severity.value: index for index, severity in enumerate(Severity)}
    if sort == "severity":
        rows.sort(key=lambda row: (severity_order.get(row["severity"], 9), row["public_id"]))
    elif sort == "title":
        rows.sort(key=lambda row: row["title"].lower())
    elif sort == "last_attempt":
        rows.sort(key=lambda row: (row["last_attempt_at"] or "", row["public_id"]), reverse=True)
    elif sort == "outcome":
        rows.sort(key=lambda row: (row["verification"]["outcome"], row["public_id"]))
    return rows


@ROUTER.get("/runs/{run_id}/report/findings")
def report_findings(
    run_id: uuid.UUID,
    severity: list[str] = Query(default=[]),
    outcome: list[str] = Query(default=[]),
    method: list[str] = Query(default=[]),
    surface: str | None = Query(default=None),
    q: str | None = Query(default=None),
    sort: str = Query(default="severity"),
    access: ProjectAccess = Depends(require_project(Role.VIEWER)),
    db: Session = Depends(get_db),
) -> dict:
    run = _run_or_404(db, access, run_id)
    rows = _filtered_rows(
        db,
        run,
        severity=severity,
        outcome=outcome,
        method=method,
        surface=surface,
        query=q,
        sort=sort,
    )
    all_rows = _filtered_rows(db, run)
    return {
        "run_id": str(run.id),
        "build_id": str(run.build_id),
        "items": rows,
        "total": len(all_rows),
        "filtered": len(rows),
        "filters": {
            "severity": severity,
            "outcome": outcome,
            "method": method,
            "surface": surface or "",
            "q": q or "",
            "sort": sort,
        },
        "facets": {
            "severity": sorted({row["severity"] for row in all_rows}),
            "outcome": sorted({row["verification"]["outcome"] for row in all_rows}),
            "method": sorted({row["retest_method"] for row in all_rows}),
        },
    }


@ROUTER.get("/runs/{run_id}/report/overview")
def report_overview(
    run_id: uuid.UUID,
    access: ProjectAccess = Depends(require_project(Role.VIEWER)),
    db: Session = Depends(get_db),
) -> dict:
    run = _run_or_404(db, access, run_id)
    rows = build_run_view(db, run)
    baseline = db.get(Run, run.baseline_run_id) if run.baseline_run_id else None
    comparison = comparison_findings(db, baseline, run) if baseline else []
    coverage = coverage_counts(db, run)
    severity = severity_counts(rows)
    open_rows = [row for row in rows if row.finding.disposition == "open"]
    awaiting = sum(1 for item in rows if item.state.outcome == "awaiting_retest")
    needs_validation = sum(1 for item in rows if item.finding.evidence_status == "needs_validation")
    guided_pending = sum(
        1 for item in rows if eligibility(item.finding) in {"guided", "pending_evidence_review"}
    )
    build = db.get(Build, run.build_id)
    zero_message = ""
    if not open_rows:
        zero_message = (
            "No open findings were recorded. "
            f"{coverage['counts'].get('tested_no_finding', 0)} planned check(s) were tested "
            "without a finding inside the recorded scope."
            if run.coverage_complete
            else "No open findings were recorded, but coverage is incomplete, so this is not a "
            "clean result for the whole application."
        )
    return {
        "run": run_row(db, run),
        "build": {"id": str(build.id), "label": build.label} if build else None,
        "severity": severity,
        "counts": {
            "total": len(rows),
            "open": len(open_rows),
            "awaiting_verification": awaiting,
            "needs_validation": needs_validation,
            "guided_pending": guided_pending,
        },
        "comparison": (
            {
                "bucket_counts": bucket_counts(comparison),
                "baseline_run_id": str(baseline.id),
                "baseline_build_id": str(baseline.build_id),
                "scope": compare_scope(baseline, run),
            }
            if baseline
            else None
        ),
        "coverage": coverage,
        "limitations": run.limitations,
        "zero_findings_message": zero_message,
        "summary": run.summary,
        "engine": {"name": run.engine, "version": run.engine_version},
        "mode": run.mode,
        "latest_verification": latest_verification_panel(
            db,
            run,
            [
                {
                    "id": str(item.finding.id),
                    "public_id": item.finding.public_id,
                    "title": item.finding.title,
                }
                for item in rows
            ],
        ),
    }


@ROUTER.get("/runs/{run_id}/report/coverage")
def report_coverage(
    run_id: uuid.UUID,
    access: ProjectAccess = Depends(require_project(Role.VIEWER)),
    db: Session = Depends(get_db),
) -> dict:
    run = _run_or_404(db, access, run_id)
    checks = list(
        db.execute(
            select(RunCheck)
            .where(RunCheck.run_id == run.id)
            .order_by(RunCheck.stage, RunCheck.scenario_code)
        ).scalars()
    )
    findings = {
        finding.id: finding.public_id
        for finding in db.execute(
            select(Finding).where(Finding.project_id == access.project.id)
        ).scalars()
    }
    surfaces = list(
        db.execute(
            select(Surface).where(Surface.run_id == run.id).order_by(Surface.route)
        ).scalars()
    )
    profile = get_profile(run.profile_code, run.profile_version)
    snapshot = run.scope_snapshot or {}
    return {
        "run_id": str(run.id),
        "coverage": coverage_counts(db, run),
        "planned": snapshot.get("planned_checks", []),
        "checks": [
            {
                "id": str(check.id),
                "stage": check.stage,
                "scenario_code": check.scenario_code,
                "scenario_title": check.scenario_title,
                "surface": check.surface,
                "method": check.method,
                "actor": check.actor_label,
                "approach": check.approach,
                "source": check.coverage_source,
                "result": check.result,
                "result_detail": check.result_detail,
                "owasp_refs": check.owasp_refs,
                "finding_id": str(check.finding_id) if check.finding_id else None,
                "finding_public_id": findings.get(check.finding_id) if check.finding_id else None,
            }
            for check in checks
        ],
        "surfaces": [
            {
                "route": surface.route,
                "methods": surface.methods,
                "source": surface.source,
                "tested": surface.tested,
            }
            for surface in surfaces
        ],
        "methodology": {
            "profile": profile_as_json(profile),
            "depth": run.depth,
            "depth_limits": depth_config(run.depth),
            "limits": snapshot.get("limits", {}),
            "scope": {
                "base_url": snapshot.get("base_url"),
                "allowed_origins": snapshot.get("allowed_origins", []),
                "path_prefixes": snapshot.get("path_prefixes", []),
                "environment_label": snapshot.get("environment_label"),
                "accounts": snapshot.get("accounts", []),
                "unauthenticated": snapshot.get("unauthenticated", False),
                "approval": snapshot.get("approval", {}),
                "build_identity": snapshot.get("build_identity"),
                "build_identity_source": snapshot.get("build_identity_source"),
            },
            "release_plan": snapshot.get("release_plan"),
            "identity_checks": snapshot.get("identity_checks", []),
            "prerequisite_probe": snapshot.get("prerequisite_probe"),
        },
        "limitations": run.limitations,
        "coverage_complete": run.coverage_complete,
    }


@ROUTER.get("/compare")
def compare_builds(
    baseline_run_id: uuid.UUID | None = Query(default=None),
    current_run_id: uuid.UUID | None = Query(default=None),
    access: ProjectAccess = Depends(require_project(Role.VIEWER)),
    db: Session = Depends(get_db),
) -> dict:
    project_runs = list(
        db.execute(
            select(Run).where(Run.project_id == access.project.id).order_by(Run.created_at.desc())
        ).scalars()
    )
    completed = [
        run for run in project_runs if run.status == RunStatus.COMPLETED.value and run.completed_at
    ]
    current = (
        db.get(Run, current_run_id) if current_run_id else (completed[0] if completed else None)
    )
    if current is None or current.project_id != access.project.id:
        raise HTTPException(status_code=404, detail="Current run not found in this project")
    if baseline_run_id:
        baseline = db.get(Run, baseline_run_id)
        if baseline is None or baseline.project_id != access.project.id:
            raise HTTPException(status_code=404, detail="Baseline run not found in this project")
    else:
        earlier = [
            run
            for run in completed
            if run.id != current.id
            and run.mode == current.mode
            and run.created_at < current.created_at
        ]
        baseline = earlier[0] if earlier else None
    if baseline is not None and baseline.id == current.id:
        raise HTTPException(status_code=422, detail="Select two different runs to compare")
    if baseline is None:
        return {
            "comparable": False,
            "incomparable_reason": (
                "No earlier completed run is available in this mode. The project's first "
                "assessment is the baseline."
            ),
            "current": run_row(db, current),
            "baseline": None,
            "rows": [],
            "bucket_counts": {},
            "scope": {},
        }
    scope = compare_scope(baseline, current)
    # Demo and live evidence never produce a verdict against each other; return no rows
    # rather than labelling buckets that are not comparable.
    rows = comparison_findings(db, baseline, current) if scope["comparable"] else []
    return {
        "comparable": scope["comparable"],
        "incomparable_reason": scope["incomparable_reason"],
        "baseline": run_row(db, baseline),
        "current": run_row(db, current),
        "rows": rows,
        "bucket_counts": bucket_counts(rows),
        "scope": scope,
        "coverage": {
            "baseline": coverage_counts(db, baseline),
            "current": coverage_counts(db, current),
        },
        "latest_verification": latest_verification_panel(db, current, rows),
        "selectors": [
            {
                "id": str(run.id),
                "build_id": str(run.build_id),
                "label": f"{run.kind.replace('_', ' ')} · {run.mode} · {iso(run.completed_at) or run.status}",
                "status": run.status,
                "mode": run.mode,
                "created_at": iso(run.created_at),
            }
            for run in project_runs
        ],
    }


_ = (Principal, get_principal, TargetConfig, CONCLUSIVE_OUTCOMES)

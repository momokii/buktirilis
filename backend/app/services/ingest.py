"""Normalise Strix artifacts and any available partial output into application records.

Parsing is tolerant of optional fields and explicit about unavailable data. An evidence
ID is only presented as captured proof when the referenced observation resolves.
"""

from __future__ import annotations

import re
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.domain import (
    CoverageResult,
    EvidenceAttribution,
    EvidenceSource,
    EvidenceStatus,
    ObservationOutcome,
    RetestMethod,
    Severity,
    VerificationOutcome,
)
from app.models import (
    Build,
    Evidence,
    Finding,
    Project,
    Run,
    RunCheck,
    Surface,
    utcnow,
)
from app.services.evidence import create_evidence
from app.services.findings import (
    compute_fingerprint,
    coverage_counts,
    normalise_scope,
    run_findings,
    upsert_finding,
)
from app.services.profiles import (
    depth_config,
    get_profile,
    plan_coverage,
    surface_matches,
)
from app.services.redaction import redact_text, truncate

SEVERITY_ALIASES = {
    "critical": Severity.CRITICAL,
    "high": Severity.HIGH,
    "medium": Severity.MEDIUM,
    "moderate": Severity.MEDIUM,
    "low": Severity.LOW,
    "info": Severity.INFO,
    "informational": Severity.INFO,
}

_DYNAMIC_ISSUE_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"export|download", re.I), "cross-tenant-export"),
    (re.compile(r"approv|workflow|sign-?off", re.I), "two-actor-approval"),
    (
        re.compile(r"role|admin(?:istrative)? (?:function|endpoint)|privileg", re.I),
        "role-restricted-function",
    ),
    (
        re.compile(r"bola|idor|object level|tenant|account.*(?:read|access)", re.I),
        "broken-object-authorization",
    ),
    (re.compile(r"rate.?limit|log(?:ging)?|audit trail|weak evidence", re.I), "evidence-review"),
]

_ID_SEGMENT = re.compile(
    r"/(?:[0-9a-f]{8}-[0-9a-f-]{27,}|\d+|INV-[A-Za-z0-9-]+|inv_[A-Za-z0-9]+)(?=/|$)"
)


class IngestError(RuntimeError):
    def __init__(self, message: str, *, code: str = "ingest_failed") -> None:
        super().__init__(message)
        self.code = code


@dataclass
class ArtifactBundle:
    run_record: dict[str, Any] | None = None
    vulnerabilities: list[dict[str, Any]] = field(default_factory=list)
    coverage: dict[str, Any] | None = None
    sarif: dict[str, Any] | None = None
    http_exchanges: dict[str, Any] = field(default_factory=dict)
    missing: list[str] = field(default_factory=list)
    unparsed: list[str] = field(default_factory=list)

    @property
    def status(self) -> str:
        if not self.run_record and not self.vulnerabilities and not self.coverage:
            return "missing"
        if self.missing or self.unparsed:
            return "partial"
        return "complete"


def load_artifact_bundle(run_dir: Path) -> ArtifactBundle:
    import json

    bundle = ArtifactBundle()
    run_json = run_dir / "run.json"
    if run_json.is_file():
        try:
            bundle.run_record = json.loads(run_json.read_text("utf-8"))
        except (ValueError, OSError):
            bundle.unparsed.append("run.json")
    else:
        bundle.missing.append("run.json")

    vuln_json = run_dir / "vulnerabilities.json"
    if vuln_json.is_file():
        try:
            payload = json.loads(vuln_json.read_text("utf-8"))
            if isinstance(payload, list):
                bundle.vulnerabilities = [item for item in payload if isinstance(item, dict)]
            else:
                bundle.unparsed.append("vulnerabilities.json")
        except (ValueError, OSError):
            bundle.unparsed.append("vulnerabilities.json")
    else:
        bundle.missing.append("vulnerabilities.json")

    coverage_json = run_dir / "coverage.json"
    if coverage_json.is_file():
        try:
            payload = json.loads(coverage_json.read_text("utf-8"))
            if isinstance(payload, dict):
                bundle.coverage = payload
            else:
                bundle.unparsed.append("coverage.json")
        except (ValueError, OSError):
            bundle.unparsed.append("coverage.json")
    else:
        bundle.missing.append("coverage.json")

    sarif = run_dir / "findings.sarif"
    if sarif.is_file():
        try:
            bundle.sarif = json.loads(sarif.read_text("utf-8"))
            if isinstance(bundle.sarif, dict) and not _sarif_has_findings(bundle.sarif):
                # Strix 1.7.1 only writes vulnerabilities.json when a report exists.
                # A SARIF document containing only coverage results is a clean run,
                # not a missing findings index.
                bundle.missing = [name for name in bundle.missing if name != "vulnerabilities.json"]
        except (ValueError, OSError):
            bundle.unparsed.append("findings.sarif")

    exchanges = run_dir / "http_exchanges.json"
    if exchanges.is_file():
        try:
            payload = json.loads(exchanges.read_text("utf-8"))
            if isinstance(payload, list):
                for exchange in payload:
                    if isinstance(exchange, dict) and exchange.get("id"):
                        bundle.http_exchanges[str(exchange["id"])] = exchange
            elif isinstance(payload, dict):
                bundle.http_exchanges = {
                    str(key): value for key, value in payload.items() if isinstance(value, dict)
                }
        except (ValueError, OSError):
            bundle.unparsed.append("http_exchanges.json")
    return bundle


def _sarif_has_findings(document: dict[str, Any]) -> bool:
    for run in document.get("runs") or []:
        if not isinstance(run, dict):
            continue
        for result in run.get("results") or []:
            if not isinstance(result, dict):
                continue
            if not str(result.get("ruleId") or "").startswith("strix-coverage/"):
                return True
    return False


def normalise_severity(value: Any) -> str:
    text = str(value or "").strip().lower()
    return SEVERITY_ALIASES.get(text, Severity.MEDIUM).value


def normalise_endpoint(record: dict[str, Any]) -> str:
    endpoint = str(record.get("endpoint") or "").strip()
    if not endpoint:
        target = str(record.get("target") or "").strip()
        if "://" in target:
            from urllib.parse import urlsplit

            endpoint = urlsplit(target).path or "/"
    if endpoint and "://" in endpoint:
        from urllib.parse import urlsplit

        endpoint = urlsplit(endpoint).path or "/"
    endpoint = _ID_SEGMENT.sub("/{id}", endpoint)
    return endpoint or "/"


def infer_issue_class(record: dict[str, Any]) -> str:
    explicit = str(record.get("issue_class") or "").strip()
    if explicit:
        return explicit
    haystack = " ".join(
        str(record.get(key) or "")
        for key in ("title", "description", "endpoint", "cwe", "technical_analysis")
    )
    for pattern, issue_class in _DYNAMIC_ISSUE_PATTERNS:
        if pattern.search(haystack):
            return issue_class
    return "dynamic-web-issue"


def _evidence_supported(record: dict[str, Any]) -> bool:
    confidence = str(record.get("confidence") or "").strip().lower()
    if confidence in {"low", "tentative", "weak"}:
        return False
    if record.get("evidence_strength") == "weak":
        return False
    evidence = str(record.get("evidence") or record.get("poc_description") or "").strip()
    return bool(evidence)


def _reproduction_steps(record: dict[str, Any]) -> list[str]:
    steps = record.get("reproduction_steps")
    if isinstance(steps, list) and steps:
        return [str(step)[:400] for step in steps]
    poc = str(record.get("poc_description") or "").strip()
    if poc:
        lines = [line.strip(" -*\t") for line in poc.splitlines() if line.strip()]
        return lines[:12]
    return []


def _record_timestamp(record: dict[str, Any], fallback: datetime) -> datetime:
    raw = str(record.get("timestamp") or "").strip()
    if not raw:
        return fallback
    for pattern in ("%Y-%m-%d %H:%M:%S UTC", "%Y-%m-%dT%H:%M:%S%z", "%Y-%m-%dT%H:%M:%SZ"):
        try:
            parsed = datetime.strptime(raw, pattern)
            return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)
        except ValueError:
            continue
    return fallback


def ingest_run(
    db: Session,
    *,
    run: Run,
    project: Project,
    build: Build,
    bundle: ArtifactBundle,
    limitations: list[str] | None = None,
) -> dict[str, Any]:
    run_limitations: list[str] = list(limitations or [])
    if bundle.status == "missing":
        run.ingest_state = "missing"
        run_limitations.append(
            "No engine artifacts were available for this run. Nothing was ingested, so the "
            "report cannot claim any tested surface."
        )
        run.limitations = run_limitations
        run.summary = (
            "No engine artifacts were available; this run produced no verifiable evidence."
        )
        db.flush()
        return {"imported": 0, "missing": bundle.missing}

    for name in bundle.missing:
        if name == "coverage.json":
            run_limitations.append(
                "The engine produced no coverage record, so untested scope is unknown rather "
                "than clean."
            )
        elif name == "run.json":
            run_limitations.append(
                "Engine run metadata was unavailable; status and spend are unconfirmed."
            )
        elif name == "vulnerabilities.json":
            run_limitations.append(
                "The engine findings index was unavailable. Absence of findings is not evidence "
                "of absence."
            )
    for name in bundle.unparsed:
        run_limitations.append(f"Artifact {name} could not be parsed and was not ingested.")

    run_record = bundle.run_record or {}
    engine_status = str(run_record.get("status") or "unknown")
    usage = run_record.get("llm_usage") or {}
    spend = 0.0
    if isinstance(usage, dict):
        for key in ("cost", "total_cost_usd", "cost_usd"):
            value = usage.get(key)
            if isinstance(value, int | float):
                spend = float(value)
                break
    run.budget = {
        **(run.budget or {}),
        "engine_status": engine_status,
        "estimated_cost_usd": round(spend, 4),
        "engine_max_budget_usd": (run.budget or {}).get("engine_budget_usd"),
        "spend_note": "Engine spend is a best-effort estimate and may overshoot the cap.",
    }
    if engine_status == "stopped":
        run_limitations.append(
            "The engine stopped at its budget or turn ceiling before finishing; coverage "
            "reflects only completed work."
        )
    elif engine_status in {"failed", "interrupted"}:
        run_limitations.append(
            f"The engine ended with status {engine_status!r}; results are partial."
        )

    fallback_time = run.completed_at or utcnow()
    imported = 0
    finding_by_engine_id: dict[str, Finding] = {}
    for record in bundle.vulnerabilities:
        engine_id = str(record.get("id") or "").strip()
        title = str(record.get("title") or "Unstructured engine finding").strip()[:300]
        issue_class = infer_issue_class(record)
        endpoint = normalise_endpoint(record)
        method = str(record.get("method") or "").upper()[:10]
        scope_summary = f"{method} {endpoint}".strip() if method else endpoint
        actors = str(record.get("actors_summary") or "").strip()
        condition = str(record.get("condition") or record.get("cwe") or issue_class).strip()
        fingerprint = compute_fingerprint(
            issue_class=issue_class,
            scope=scope_summary,
            actor_boundary=actors,
            condition=condition,
        )
        supported = _evidence_supported(record)
        payload = {
            "title": title,
            "severity": normalise_severity(record.get("severity")),
            "issue_class": issue_class,
            "scope_summary": scope_summary,
            "actors_summary": actors,
            "impact": str(record.get("impact") or "").strip(),
            "expected_behavior": str(record.get("expected_behavior") or "").strip(),
            "observed_behavior": str(
                record.get("observed_behavior") or record.get("technical_analysis") or ""
            ).strip(),
            "remediation": str(
                record.get("remediation_steps") or record.get("remediation") or ""
            ).strip(),
            "prerequisites": [str(p)[:300] for p in (record.get("prerequisites") or [])],
            "reproduction_steps": _reproduction_steps(record),
            "root_cause_hypothesis": record.get("root_cause_hypothesis"),
            "fingerprint": fingerprint,
            "evidence_status": (
                EvidenceStatus.SUPPORTED.value
                if supported
                else EvidenceStatus.NEEDS_VALIDATION.value
            ),
            "retest_method": (
                RetestMethod.GUIDED.value
                if supported
                else RetestMethod.PENDING_EVIDENCE_REVIEW.value
            ),
        }
        finding = upsert_finding(db, project=project, run=run, payload=payload)
        if not supported:
            finding.evidence_status = EvidenceStatus.NEEDS_VALIDATION.value
        if engine_id:
            finding_by_engine_id[engine_id] = finding

        observed_at = _record_timestamp(record, fallback_time)
        if not _observation_exists(db, run.id, finding.id):
            db.add(
                ObservationRecord(
                    project_id=project.id,
                    finding_id=finding.id,
                    build_id=build.id,
                    run_id=run.id,
                    source=EvidenceSource.ENGINE.value,
                    outcome=ObservationOutcome.OBSERVED.value,
                    accepted=True,
                    observed_at=observed_at,
                    detail={
                        "engine_id": engine_id,
                        "engine_status": engine_status,
                        "evidence_supported": supported,
                        "confidence": record.get("confidence"),
                    },
                ).model()
            )
        imported += 1

        if not _engine_evidence_exists(db, run.id, engine_id):
            create_evidence(
                db,
                project=project,
                finding_id=finding.id,
                run_id=run.id,
                attempt_id=None,
                build_id=build.id,
                kind="engine_report",
                attribution=EvidenceAttribution.ENGINE_REPORT,
                summary=f"Engine report for {title}",
                payload={
                    "engine_id": engine_id,
                    "engine": "strix",
                    "title": title,
                    "description": truncate(
                        redact_text(str(record.get("description") or "")), 6000
                    ),
                    "technical_analysis": truncate(
                        redact_text(str(record.get("technical_analysis") or "")), 6000
                    ),
                    "evidence": truncate(redact_text(str(record.get("evidence") or "")), 6000),
                    "poc_description": truncate(
                        redact_text(str(record.get("poc_description") or "")), 4000
                    ),
                    "assumptions": str(record.get("assumptions") or "")[:1000],
                    "counterevidence": str(record.get("counterevidence") or "")[:1000],
                    "confidence": record.get("confidence"),
                    "cvss": record.get("cvss"),
                    "cwe": record.get("cwe"),
                    "target": str(record.get("target") or ""),
                    "agent": str(record.get("agent_name") or ""),
                },
                actor_label="strix engine",
                method=method,
                endpoint=endpoint,
            )

        exchange_ids = [str(i) for i in (record.get("http_exchange_ids") or [])]
        for exchange_id in exchange_ids:
            exchange = bundle.http_exchanges.get(exchange_id)
            if exchange is None:
                run_limitations.append(
                    f"Linked HTTP evidence {exchange_id} referenced by {engine_id} was not "
                    "available in the artifact set; it is not presented as captured proof."
                )
                continue
            if _exchange_evidence_exists(db, run.id, exchange_id):
                continue
            request = exchange.get("request") or {}
            response = exchange.get("response") or {}
            create_evidence(
                db,
                project=project,
                finding_id=finding.id,
                run_id=run.id,
                attempt_id=None,
                build_id=build.id,
                kind="http_exchange",
                attribution=EvidenceAttribution.ENGINE_REPORT,
                summary=str(exchange.get("summary") or "Linked HTTP evidence")[:400],
                payload={
                    "request": {
                        "method": str(request.get("method") or ""),
                        "url": str(request.get("url") or ""),
                        "headers": request.get("headers") or {},
                        "body": truncate(str(request.get("body") or ""), 4000),
                    },
                    "response": {
                        "status": response.get("status"),
                        "headers": response.get("headers") or {},
                        "body": truncate(str(response.get("body") or ""), 6000),
                    },
                    "actor": str(exchange.get("actor") or ""),
                    "engine_id": engine_id,
                    "source_note": "resolved from the engine artifact set",
                },
                highlight=[str(h) for h in (exchange.get("highlight") or [])],
                actor_label=str(exchange.get("actor") or ""),
                method=str(request.get("method") or ""),
                endpoint=str(request.get("url") or "")[:400],
            )

    checks = _import_coverage(
        db, run=run, project=project, bundle=bundle, findings=finding_by_engine_id
    )
    surfaces = _import_surfaces(db, run=run, project=project, bundle=bundle)
    _ensure_planned_checks(db, run=run, project=project, build=build, checks=checks)

    run.ingest_state = bundle.status
    run.limitations = _dedupe(run_limitations)
    run.coverage_complete = _coverage_complete(run, bundle, checks)
    if not run.coverage_complete and not any(
        "complete" in limitation.lower() for limitation in run.limitations
    ):
        run.limitations = _dedupe(
            [
                *run.limitations,
                "Coverage is incomplete: the report describes only checks with a recorded result.",
            ]
        )
    run.summary = build_summary(db, run=run)
    db.flush()
    return {
        "imported": imported,
        "checks": len(checks),
        "surfaces": len(surfaces),
        "ingest_state": run.ingest_state,
        "coverage_complete": run.coverage_complete,
    }


@dataclass
class ObservationRecord:
    """Small factory so ingest never imports the ORM name ambiguously."""

    project_id: uuid.UUID
    finding_id: uuid.UUID
    build_id: uuid.UUID
    run_id: uuid.UUID
    source: str
    outcome: str
    accepted: bool
    observed_at: datetime
    detail: dict[str, Any]

    def model(self):
        from app.models import Observation

        return Observation(
            project_id=self.project_id,
            finding_id=self.finding_id,
            build_id=self.build_id,
            run_id=self.run_id,
            source=self.source,
            outcome=self.outcome,
            accepted=self.accepted,
            observed_at=self.observed_at,
            detail=self.detail,
        )


def _observation_exists(db: Session, run_id: uuid.UUID, finding_id: uuid.UUID) -> bool:
    from app.models import Observation

    return (
        db.execute(
            select(Observation.id).where(
                Observation.run_id == run_id,
                Observation.finding_id == finding_id,
                Observation.source == EvidenceSource.ENGINE.value,
            )
        ).scalar_one_or_none()
        is not None
    )


def _engine_evidence_exists(db: Session, run_id: uuid.UUID, engine_id: str) -> bool:
    if not engine_id:
        return False
    rows = db.execute(
        select(Evidence).where(Evidence.run_id == run_id, Evidence.kind == "engine_report")
    ).scalars()
    return any(str((row.payload or {}).get("engine_id")) == engine_id for row in rows)


def _exchange_evidence_exists(db: Session, run_id: uuid.UUID, exchange_id: str) -> bool:
    rows = db.execute(
        select(Evidence).where(Evidence.run_id == run_id, Evidence.kind == "http_exchange")
    ).scalars()
    return any(str((row.payload or {}).get("exchange_id")) == exchange_id for row in rows)


_ENGINE_RESULT_MAP = {
    "reported": CoverageResult.FINDING_OBSERVED,
    "no_issue_found": CoverageResult.TESTED_NO_FINDING,
    "ruled_out": CoverageResult.TESTED_NO_FINDING,
    "not_applicable": CoverageResult.NOT_APPLICABLE,
    "needs_follow_up": CoverageResult.NEEDS_REVIEW,
}


def _import_coverage(
    db: Session,
    *,
    run: Run,
    project: Project,
    bundle: ArtifactBundle,
    findings: dict[str, Finding],
) -> list[RunCheck]:
    checks: list[RunCheck] = []
    coverage = bundle.coverage or {}
    entries: list[Any] = list(coverage.get("entries") or [])
    for index, entry in enumerate(entries):
        if not isinstance(entry, dict):
            continue
        surface = str(entry.get("surface") or "").strip()
        risk_area = str(entry.get("risk_area") or "").strip()
        outcome = str(entry.get("outcome") or "").strip()
        mapped = _ENGINE_RESULT_MAP.get(outcome, CoverageResult.NEEDS_REVIEW)
        check_key = f"engine:{index}:{surface}:{risk_area}"[:160]
        existing = db.execute(
            select(RunCheck).where(RunCheck.run_id == run.id, RunCheck.check_key == check_key)
        ).scalar_one_or_none()
        finding_id = None
        if mapped == CoverageResult.FINDING_OBSERVED:
            for finding in findings.values():
                if finding.scope_summary and _route_matches(finding.scope_summary, surface):
                    finding_id = finding.id
                    break
        if existing is not None:
            checks.append(existing)
            continue
        check = RunCheck(
            project_id=project.id,
            run_id=run.id,
            finding_id=finding_id,
            check_key=check_key,
            stage="discovery",
            scenario_code=risk_area[:80] or "agent-reported",
            scenario_title=(risk_area or "Engine-reported check")[:200],
            surface=surface[:300],
            method="",
            actor_label=str(entry.get("recorded_by") or "")[:120],
            approach=str(entry.get("evidence") or "")[:400],
            coverage_source="agent_reported",
            result=mapped.value,
            result_detail=str(entry.get("outcome_label") or outcome)[:400],
            owasp_refs=[],
        )
        db.add(check)
        checks.append(check)
    gaps: list[Any] = list(coverage.get("gaps") or [])
    for index, gap in enumerate(gaps):
        surface = str(gap.get("surface") or "") if isinstance(gap, dict) else str(gap)
        check_key = f"engine-gap:{index}:{surface}"[:160]
        existing = db.execute(
            select(RunCheck).where(RunCheck.run_id == run.id, RunCheck.check_key == check_key)
        ).scalar_one_or_none()
        if existing is not None:
            checks.append(existing)
            continue
        check = RunCheck(
            project_id=project.id,
            run_id=run.id,
            check_key=check_key,
            stage="discovery",
            scenario_code="coverage-gap",
            scenario_title="Coverage gap reported by the engine",
            surface=surface[:300],
            approach=str(gap.get("reason") or "")[:400] if isinstance(gap, dict) else "",
            coverage_source="machine_observed",
            result=CoverageResult.NOT_RUN.value,
            result_detail=str(gap.get("reason") or "The engine reported an unverified gap")[:400],
        )
        db.add(check)
        checks.append(check)
    db.flush()
    return checks


def _route_matches(scope_summary: str, surface: str) -> bool:
    route = normalise_scope(surface)
    if not route:
        return False
    scope = normalise_scope(scope_summary)
    if route in scope:
        return True
    normalized_surface = _ID_SEGMENT.sub(
        "/{id}", surface if surface.startswith("/") else "/" + surface
    )
    return normalise_scope(normalized_surface) in scope or surface_matches(
        normalized_surface, normalise_scope(surface)
    )


def _import_surfaces(
    db: Session, *, run: Run, project: Project, bundle: ArtifactBundle
) -> list[Surface]:
    routes: dict[str, set[str]] = {}
    coverage = bundle.coverage or {}
    for entry in coverage.get("entries") or []:
        if isinstance(entry, dict) and entry.get("surface"):
            routes.setdefault(str(entry["surface"]), set()).add("recon")
    for gap in coverage.get("gaps") or []:
        if isinstance(gap, dict) and gap.get("surface"):
            routes.setdefault(str(gap["surface"]), set()).add("recon")
    for record in bundle.vulnerabilities:
        endpoint = normalise_endpoint(record)
        if endpoint:
            routes.setdefault(endpoint, set()).add("recon")
    build = db.get(Build, run.build_id)
    if build is not None and build.openapi_document_id:
        from app.models import OpenApiDocument

        document = db.get(OpenApiDocument, build.openapi_document_id)
        for operation in (document.operations if document else []) or []:
            routes.setdefault(operation["path"], set()).add("openapi")
    surfaces: list[Surface] = []
    for route, sources in routes.items():
        existing = db.execute(
            select(Surface).where(Surface.run_id == run.id, Surface.route == route)
        ).scalar_one_or_none()
        if existing is not None:
            surfaces.append(existing)
            continue
        tested = any(
            _route_matches(check.surface, route)
            for check in db.execute(
                select(RunCheck).where(
                    RunCheck.run_id == run.id,
                    RunCheck.result.in_(
                        [
                            CoverageResult.TESTED_NO_FINDING.value,
                            CoverageResult.FINDING_OBSERVED.value,
                        ]
                    ),
                )
            ).scalars()
        )
        surface = Surface(
            project_id=project.id,
            run_id=run.id,
            route=route[:300],
            methods=["GET"],
            source="openapi" if "openapi" in sources else "recon",
            tested=tested,
        )
        db.add(surface)
        surfaces.append(surface)
    db.flush()
    return surfaces


def _ensure_planned_checks(
    db: Session,
    *,
    run: Run,
    project: Project,
    build: Build,
    checks: list[RunCheck],
) -> None:
    """Add an explicit NOT_RUN row for every planned check with no recorded result."""
    from app.models import OpenApiDocument

    profile = get_profile(run.profile_code, run.profile_version)
    surfaces: list[dict[str, Any]] = []
    for surface in db.execute(select(Surface).where(Surface.run_id == run.id)).scalars():
        surfaces.append(
            {"route": surface.route, "methods": surface.methods, "source": surface.source}
        )
    if not surfaces and build.openapi_document_id:
        document = db.get(OpenApiDocument, build.openapi_document_id)
        for operation in (document.operations if document else []) or []:
            surfaces.append(
                {"route": operation["path"], "methods": [operation["method"]], "source": "openapi"}
            )
    planned = plan_coverage(profile, surfaces=surfaces, depth=run.depth)
    for plan in planned:
        matched = [
            check
            for check in checks
            if surface_matches(plan["surface"], check.surface) or check.surface == plan["surface"]
        ]
        if matched:
            continue
        check_key = f"planned:{plan['check_key']}"[:160]
        existing = db.execute(
            select(RunCheck).where(RunCheck.run_id == run.id, RunCheck.check_key == check_key)
        ).scalar_one_or_none()
        if existing is not None:
            continue
        db.add(
            RunCheck(
                project_id=project.id,
                run_id=run.id,
                check_key=check_key,
                stage="verify_known"
                if plan["scenario_code"] != "role-restricted-function"
                else "discovery",
                scenario_code=plan["scenario_code"],
                scenario_title=plan["scenario_title"],
                surface=plan["surface"],
                method=plan["method"],
                actor_label="",
                approach=plan["approach"],
                coverage_source="buktirilis-plan",
                result=CoverageResult.NOT_RUN.value,
                result_detail=(
                    "No recorded check for this planned scenario. Unknown coverage is not a pass."
                ),
                owasp_refs=plan["owasp_refs"],
            )
        )
    db.flush()


def _coverage_complete(run: Run, bundle: ArtifactBundle, checks: list[RunCheck]) -> bool:
    completeness = (bundle.coverage or {}).get("completeness") or {}
    engine_complete = bool(completeness.get("complete")) if completeness else False
    has_gap = any(
        check.result in {CoverageResult.NOT_RUN.value, CoverageResult.NEEDS_REVIEW.value}
        for check in checks
    )
    return engine_complete and not has_gap


def build_summary(db: Session, *, run: Run) -> str:
    findings = run_findings(db, run)
    open_findings = [finding for finding in findings if finding.disposition == "open"]
    counts: dict[str, int] = {}
    for finding in open_findings:
        counts[finding.severity] = counts.get(finding.severity, 0) + 1
    coverage = coverage_counts(db, run)
    if open_findings:
        severity_bits = ", ".join(
            f"{counts[severity]} {severity}" for severity in Severity if counts.get(severity)
        )
        finding_clause = f"{len(open_findings)} open finding(s): {severity_bits}"
    else:
        finding_clause = "No open findings were recorded in the tested scope"
    tested = coverage["counts"].get(CoverageResult.TESTED_NO_FINDING.value, 0) + coverage[
        "counts"
    ].get(CoverageResult.FINDING_OBSERVED.value, 0)
    coverage_clause = (
        f"{tested} of {coverage['denominator']} planned checks have a recorded result"
        if coverage["denominator"]
        else "No planned checks were defined for this run"
    )
    incomplete = " Coverage is incomplete." if not run.coverage_complete else ""
    return f"{finding_clause}. {coverage_clause}.{incomplete}"


def _dedupe(values: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        if value and value not in seen:
            seen.add(value)
            result.append(value)
    return result


def sample_run_status(run: Run, bundle: ArtifactBundle) -> str:
    status = str((bundle.run_record or {}).get("status") or "")
    if status in {"failed", "interrupted"}:
        return "failed"
    if run.budget.get("engine_status") == "stopped":
        return "completed"
    return "completed"


_ = (depth_config, VerificationOutcome)

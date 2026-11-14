"""Deterministic demo artifacts and the single reproducible lab scenario.

These fixtures are intentionally synthetic and labelled as such in run metadata and
reports. They exercise the same normalisation path as live Strix artifacts; automatic
retests still execute real HTTP requests against the bundled lab.
"""

from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from app.domain import Depth

BUILD_VULNERABLE = "2024.10.1"
BUILD_PATCHED = "2024.10.2"
BUILD_REGRESSED = "2024.10.3"

DEMO_BUILDS = (BUILD_VULNERABLE, BUILD_PATCHED, BUILD_REGRESSED)

_BASE_ENTRIES = {
    "invoices": {
        "surface": "/api/invoices/{invoice_id}",
        "risk_area": "Broken object level authorization",
        "evidence": "Cross-tenant GET executed with the tenant B identity.",
    },
    "invoice_list": {
        "surface": "/api/invoices",
        "risk_area": "Broken object level authorization",
        "evidence": "Tenant-scoped listing checked with both identities.",
    },
    "export": {
        "surface": "/api/exports/{invoice_id}/pdf",
        "risk_area": "Broken object level authorization",
        "evidence": "Export document requested with the tenant B identity.",
    },
    "approval": {
        "surface": "/api/approvals/{invoice_id}",
        "risk_area": "Broken function level authorization",
        "evidence": "Two-actor approval transition attempted across tenants.",
    },
    "rate_limit": {
        "surface": "/api/invoices",
        "risk_area": "Authentication and rate limiting",
        "evidence": "Repeated unauthenticated listing requests observed.",
    },
}


def _vuln(
    *,
    engine_id: str,
    title: str,
    severity: str,
    issue_class: str,
    endpoint: str,
    actors: str,
    condition: str,
    description: str,
    impact: str,
    expected: str,
    observed: str,
    prereqs: list[str],
    steps: list[str],
    remediation: str,
    evidence: str,
    confidence: str = "high",
    evidence_strength: str = "supported",
) -> dict[str, Any]:
    return {
        "id": engine_id,
        "title": title,
        "severity": severity,
        "description": description,
        "impact": impact,
        "expected_behavior": expected,
        "observed_behavior": observed,
        "prerequisites": prereqs,
        "reproduction_steps": steps,
        "remediation_steps": remediation,
        "evidence": evidence,
        "confidence": confidence,
        "evidence_strength": evidence_strength,
        "issue_class": issue_class,
        "actors_summary": actors,
        "condition": condition,
        "endpoint": endpoint,
        "method": "GET",
        "target": f"http://lab.invalid{endpoint}",
        "technical_analysis": (
            "The handler resolves the object by identifier before it checks whether the "
            "caller belongs to the owning tenant."
        ),
        "poc_description": "\n".join(steps),
        "cwe": condition,
        "finding_class": "dynamic",
        "agent_name": "demo-fixture",
    }


BOLA_VULN = _vuln(
    engine_id="vuln-1",
    title="Cross-tenant invoice read via object identifier",
    severity="high",
    issue_class="broken-object-authorization",
    endpoint="/api/invoices/{invoice_id}",
    actors="tenant-b developer → tenant-a invoice object",
    condition="response body tenant_id differs from the acting identity tenant",
    description=(
        "A developer identity from tenant B can read an invoice owned by tenant A by "
        "requesting its identifier directly."
    ),
    impact=(
        "Any authenticated tenant can read another tenant's invoice totals, line items, "
        "and billing contact details, which is a cross-tenant data disclosure."
    ),
    expected="The API denies a request for an object outside the caller's tenant.",
    observed=(
        "GET /api/invoices/INV-A-1001 with a tenant B token returns HTTP 200 and the "
        "full tenant A invoice body."
    ),
    prereqs=[
        "Two active test identities in different tenants",
        "A known invoice identifier owned by tenant A (fixture invoice-a-1001)",
    ],
    steps=[
        "Sign in as the tenant B developer and capture the bearer token.",
        "Request GET /api/invoices/INV-A-1001.",
        "Observe HTTP 200 with tenant_id set to tenant-a.",
        "Repeat as the tenant A owner and confirm the same object remains reachable.",
    ],
    remediation=(
        "Authorize the object at the query boundary (tenant filter in the SQL predicate) "
        "and add a regression test covering cross-tenant identifiers."
    ),
    evidence=(
        "HTTP/1.1 200 OK\nContent-Type: application/json\n\n"
        '{"invoice_id":"INV-A-1001","tenant_id":"tenant-a","total_cents":184000}'
    ),
)

EXPORT_VULN = _vuln(
    engine_id="vuln-1",
    title="Cross-tenant invoice export returns tenant A document",
    severity="critical",
    issue_class="cross-tenant-export",
    endpoint="/api/exports/{invoice_id}/pdf",
    actors="tenant-b developer → tenant-a invoice export",
    condition="export document contains the owning tenant marker for a different tenant",
    description=(
        "The export endpoint resolves the invoice identifier and renders the document "
        "without verifying that the caller belongs to the owning tenant."
    ),
    impact=(
        "A tenant B user can download a PDF that contains tenant A's invoice data, "
        "including amounts and billing identity."
    ),
    expected="The export endpoint denies cross-tenant document requests.",
    observed=(
        "GET /api/exports/INV-A-1001/pdf with a tenant B token returns a PDF containing "
        "INV-A-1001 and tenant-a."
    ),
    prereqs=[
        "Two active test identities in different tenants",
        "A known invoice identifier owned by tenant A (fixture invoice-a-1001)",
    ],
    steps=[
        "Sign in as the tenant B developer.",
        "Request GET /api/exports/INV-A-1001/pdf.",
        "Inspect the returned document for the tenant A invoice marker.",
        "Repeat as the tenant A owner to confirm the export remains available to its owner.",
    ],
    remediation=(
        "Apply the same tenant authorization predicate used by the invoice read path "
        "before rendering an export document."
    ),
    evidence=(
        "HTTP/1.1 200 OK\nContent-Type: application/pdf\n\n"
        "%PDF-1.4 ... (INV-A-1001, tenant-a, total 184000) ..."
    ),
)

APPROVAL_VULN = _vuln(
    engine_id="vuln-1",
    title="Two-actor invoice approval can be completed by the wrong tenant",
    severity="high",
    issue_class="two-actor-approval",
    endpoint="/api/approvals/{invoice_id}",
    actors="tenant-b submitter + tenant-a approver → tenant-a approval request",
    condition="approval state transition accepted across tenant boundaries",
    description=(
        "An approval request created for tenant A can be approved by a tenant B identity "
        "that does not own the request, which completes an irreversible state transition."
    ),
    impact=(
        "A tenant can approve another tenant's invoice, changing billing state that is "
        "not reversible through the product UI."
    ),
    expected=(
        "Only an approver in the owning tenant can approve the request, and the approval "
        "is recorded once."
    ),
    observed=(
        "The tenant B approver receives approval confirmation for a tenant A request; the "
        "owner approval control also succeeds."
    ),
    prereqs=[
        "Two identities with submitter and approver roles",
        "A pending approval request for invoice-a-1001",
    ],
    steps=[
        "As the tenant A submitter, create an approval request for INV-A-1001.",
        "As the tenant B approver, open the approval page and approve the request.",
        "Confirm the state transition and record the response.",
        "As the tenant A approver, verify the legitimate approval path still works.",
    ],
    remediation=(
        "Authorize both the submitter and approver against the owning tenant and make the "
        "approval transition idempotent per request."
    ),
    evidence=(
        "Submitted approval req-8841 for tenant-a invoice INV-A-1001.\n"
        'Approved as tenant-b-approver: HTTP 200 {"status":"approved"}.'
    ),
)

RATE_LIMIT_VULN = _vuln(
    engine_id="vuln-1",
    title="Unbounded unauthenticated invoice listing requests",
    severity="medium",
    issue_class="evidence-review",
    endpoint="/api/invoices",
    actors="anonymous client → invoice listing",
    condition="repeated anonymous requests are served without throttling",
    description=(
        "Anonymous listing requests appear to be served without rate limiting, but the "
        "captured evidence is a single request without timing."
    ),
    impact=(
        "If confirmed, unlimited anonymous listing requests could be used to enumerate "
        "tenant activity."
    ),
    expected="Anonymous listing requests are rejected or throttled.",
    observed="A single anonymous request returned 401; no throttling was observed.",
    prereqs=["Target reachable from the worker"],
    steps=["Send 20 anonymous listing requests and record status and timing."],
    remediation="Reject anonymous listing requests and add a shared rate-limit bucket.",
    evidence="One request only; no timing series captured.",
    confidence="low",
    evidence_strength="weak",
)


def fixture_payload(
    build_label: str, *, depth: str, base_url: str, run_id: str
) -> tuple[dict[str, Any], list[dict[str, Any]], dict[str, Any]]:
    started = datetime(2024, 10, 1, 9, 0, tzinfo=UTC)
    if build_label.endswith("10.2"):
        started = datetime(2024, 10, 8, 9, 0, tzinfo=UTC)
    elif build_label.endswith("10.3"):
        started = datetime(2024, 10, 15, 9, 0, tzinfo=UTC)
    completed = started + timedelta(minutes=6 if depth == Depth.QUICK else 18)

    if build_label in {BUILD_VULNERABLE, BUILD_REGRESSED}:
        vulnerabilities = [BOLA_VULN, RATE_LIMIT_VULN, APPROVAL_VULN]
        entries = [
            {
                **_BASE_ENTRIES["invoices"],
                "outcome": "reported",
                "outcome_label": "Finding reported",
                "recorded_by": "demo-agent",
                "recorded_at": started.isoformat(),
            },
            {
                **_BASE_ENTRIES["invoice_list"],
                "outcome": "no_issue_found",
                "outcome_label": "No issue identified",
                "recorded_by": "demo-agent",
                "recorded_at": started.isoformat(),
            },
            {
                **_BASE_ENTRIES["approval"],
                "outcome": "reported",
                "outcome_label": "Finding reported",
                "recorded_by": "demo-agent",
                "recorded_at": started.isoformat(),
            },
            {
                **_BASE_ENTRIES["rate_limit"],
                "outcome": "needs_follow_up",
                "outcome_label": "Requires further review",
                "recorded_by": "demo-agent",
                "recorded_at": started.isoformat(),
            },
        ]
        gaps = [
            {
                "surface": "/api/exports/{invoice_id}/pdf",
                "reason": "Export routes were not reached before the quick scan ended.",
                "kind": "unreviewed_surface",
            }
        ]
        completeness = {
            "complete": False,
            "scan_status": "completed",
            "exit_reason": "finished_by_tool",
            "caveats": [
                "The export surface was inventoried but not tested, so its coverage is unknown."
            ],
        }
    elif build_label == BUILD_PATCHED:
        vulnerabilities = [EXPORT_VULN, APPROVAL_VULN, RATE_LIMIT_VULN]
        entries = [
            {
                **_BASE_ENTRIES["invoices"],
                "outcome": "no_issue_found",
                "outcome_label": "No issue identified",
                "recorded_by": "demo-agent",
                "recorded_at": started.isoformat(),
            },
            {
                **_BASE_ENTRIES["invoice_list"],
                "outcome": "no_issue_found",
                "outcome_label": "No issue identified",
                "recorded_by": "demo-agent",
                "recorded_at": started.isoformat(),
            },
            {
                **_BASE_ENTRIES["export"],
                "outcome": "reported",
                "outcome_label": "Finding reported",
                "recorded_by": "demo-agent",
                "recorded_at": started.isoformat(),
            },
            {
                **_BASE_ENTRIES["approval"],
                "outcome": "reported",
                "outcome_label": "Finding reported",
                "recorded_by": "demo-agent",
                "recorded_at": started.isoformat(),
            },
            {
                **_BASE_ENTRIES["rate_limit"],
                "outcome": "needs_follow_up",
                "outcome_label": "Requires further review",
                "recorded_by": "demo-agent",
                "recorded_at": started.isoformat(),
            },
        ]
        gaps = []
        completeness = {
            "complete": True,
            "scan_status": "completed",
            "exit_reason": "finished_by_tool",
            "caveats": [],
        }
    else:
        vulnerabilities = [BOLA_VULN, EXPORT_VULN, APPROVAL_VULN]
        entries = [
            {
                **_BASE_ENTRIES["invoices"],
                "outcome": "reported",
                "outcome_label": "Finding reported",
                "recorded_by": "demo-agent",
                "recorded_at": started.isoformat(),
            },
            {
                **_BASE_ENTRIES["invoice_list"],
                "outcome": "no_issue_found",
                "outcome_label": "No issue identified",
                "recorded_by": "demo-agent",
                "recorded_at": started.isoformat(),
            },
            {
                **_BASE_ENTRIES["export"],
                "outcome": "reported",
                "outcome_label": "Finding reported",
                "recorded_by": "demo-agent",
                "recorded_at": started.isoformat(),
            },
            {
                **_BASE_ENTRIES["approval"],
                "outcome": "needs_follow_up",
                "outcome_label": "Requires further review",
                "recorded_by": "demo-agent",
                "recorded_at": started.isoformat(),
            },
        ]
        gaps = [
            {
                "surface": "/api/invoices",
                "reason": "The budget ceiling stopped discovery before the listing scenario finished.",
                "kind": "budget_stopped",
            }
        ]
        completeness = {
            "complete": False,
            "scan_status": "stopped",
            "exit_reason": "budget_exceeded",
            "caveats": ["The scan stopped at its budget ceiling; remaining scope was not reached."],
        }

    for record in vulnerabilities:
        record = dict(record)
        record["timestamp"] = (started + timedelta(minutes=3)).strftime("%Y-%m-%d %H:%M:%S UTC")
    run_record = {
        "run_id": run_id,
        "run_name": f"demo-{build_label.replace('.', '-')}",
        "start_time": started.isoformat(),
        "end_time": completed.isoformat(),
        "status": "completed" if completeness["complete"] else "stopped",
        "auth_mode": "demo",
        "scan_mode": depth,
        "targets_info": [{"target": base_url, "type": "web"}],
        "instruction": "Demo fixture scan of the illustrative invoice API.",
        "llm_usage": {"requests": 0, "input_tokens": 0, "output_tokens": 0, "cost": 0.0},
        "non_interactive": True,
        "scope_mode": "full",
    }
    coverage = {
        "schema_version": 1,
        "generated_at": completed.strftime("%Y-%m-%d %H:%M:%S UTC"),
        "run_id": run_id,
        "run_name": run_record["run_name"],
        "scope": {
            "targets": run_record["targets_info"],
            "scan_mode": depth,
            "instruction": run_record["instruction"],
        },
        "summary": {
            "surfaces_reviewed": len(entries),
            "findings_filed": len(vulnerabilities),
            "gaps": len(gaps),
        },
        "machine_observed": {
            "agents": [
                {
                    "agent_name": "demo-agent",
                    "status": "finished",
                    "skills": ["broken_object_level_authorization"],
                }
            ],
            "skills_exercised": ["broken_object_level_authorization"],
        },
        "completeness": completeness,
        "entries": [
            {
                **entry,
                "source": "agent_reported",
                "previous_outcomes": [],
            }
            for entry in entries
        ],
        "gaps": gaps,
    }
    return run_record, vulnerabilities, coverage


def write_demo_artifacts(
    run_dir: Path, *, build_label: str, depth: str, base_url: str, run_id: str
) -> Path:
    run_record, vulnerabilities, coverage = fixture_payload(
        build_label, depth=depth, base_url=base_url, run_id=run_id
    )
    target = run_dir / "strix_runs" / run_record["run_name"]
    target.mkdir(parents=True, exist_ok=True)
    (target / "run.json").write_text(json.dumps(run_record, indent=2), encoding="utf-8")
    (target / "vulnerabilities.json").write_text(
        json.dumps(vulnerabilities, indent=2), encoding="utf-8"
    )
    (target / "coverage.json").write_text(json.dumps(coverage, indent=2), encoding="utf-8")
    vuln_dir = target / "vulnerabilities"
    vuln_dir.mkdir(exist_ok=True)
    for record in vulnerabilities:
        (vuln_dir / f"{record['id']}.md").write_text(
            f"# {record['title']}\n\nSeverity: {record['severity'].upper()}\n\n"
            f"{record['description']}\n\n```\n{record['evidence']}\n```\n",
            encoding="utf-8",
        )
    (target / "penetration_test_report.md").write_text(
        "# Security Penetration Test Report\n\n"
        f"**Generated:** {run_record['end_time']}\n\n"
        "Synthetic demo artifact. It is labelled as a fixture everywhere it appears.\n",
        encoding="utf-8",
    )
    latest = run_dir / "strix_runs" / "demo-contract.json"
    latest.write_text(
        json.dumps(
            {
                "synthetic": True,
                "note": "Synthetic contract fixture, not a live Strix execution.",
                "artifacts": sorted(p.name for p in target.iterdir()),
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    return target


def scan_root(artifact_root: Path, run_id: uuid.UUID) -> Path:
    directory = artifact_root / "runs" / str(run_id)
    directory.mkdir(parents=True, exist_ok=True)
    return directory

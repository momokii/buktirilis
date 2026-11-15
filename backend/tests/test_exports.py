"""PDF/CSV/JSON snapshot exports: content, redaction, stability, and limits."""

from __future__ import annotations

import csv
import io
import json
from datetime import UTC, datetime, timedelta

from sqlalchemy import select

from app.models import Evidence, ExportSnapshot
from app.services.evidence import create_evidence
from app.services.exports import create_export, render_pdf
from tests.helpers import add_observation, make_finding, make_run

NOW = datetime(2024, 10, 20, 9, 0, tzinfo=UTC)


def _report(db, lab_project, settings):
    finding = make_finding(db, lab_project.project)
    run = make_run(db, lab_project.project, lab_project.builds["2024.10.2"], lab_project.operator)
    run.completed_at = NOW
    run.snapshot_at = NOW
    run.summary = (
        "1 open finding. 2 of 4 planned checks have a recorded result. Coverage is incomplete."
    )
    run.limitations = ["The export surface was inventoried but not tested."]
    run.coverage_complete = False
    db.flush()
    add_observation(db, finding, run.build_id, outcome="observed", observed_at=NOW, run=run)
    from app.models import RunCheck

    db.add(
        RunCheck(
            project_id=lab_project.project.id,
            run_id=run.id,
            finding_id=finding.id,
            check_key=f"engine:0:{finding.scope_summary}",
            stage="discovery",
            scenario_code="bola-object-read",
            scenario_title="Cross-tenant object read",
            surface="/api/invoices/{invoice_id}",
            method="GET",
            actor_label="tenant-b-dev",
            approach="Compared the owning tenant with the acting identity.",
            coverage_source="buktirilis-replay",
            result="finding_observed",
            result_detail="Tenant A object returned to tenant B.",
            owasp_refs=["OWASP API1:2023"],
        )
    )
    db.flush()
    create_evidence(
        db,
        project=lab_project.project,
        finding_id=finding.id,
        run_id=run.id,
        attempt_id=None,
        build_id=run.build_id,
        kind="http_exchange",
        attribution="observed_capture",
        summary="Cross-tenant request and response",
        payload={
            "request": {
                "method": "GET",
                "url": "http://127.0.0.1:18099/deployments/2024.10.2/api/invoices/INV-A-1001",
                "headers": {
                    "Authorization": "Bearer lab.tenant-b-dev",
                    "Accept": "application/json",
                },
                "body": "",
            },
            "response": {
                "status": 200,
                "headers": {"content-type": "application/json", "set-cookie": "session=secret"},
                "body": '{"invoice_id":"INV-A-1001","tenant_id":"tenant-a"}',
            },
            "actor": "tenant-b-dev",
            "notes": "unauthorized request",
        },
        highlight=["\"tenant_id\": 'tenant-a'"],
    )
    db.commit()
    return run, finding


def test_json_export_is_sanitised_and_complete(db, lab_project, settings):
    run, finding = _report(db, lab_project, settings)
    exports = create_export(
        db, project=lab_project.project, run=run, fmt="json", actor=lab_project.viewer
    )
    db.commit()
    assert len(exports) == 1
    export = exports[0]
    payload = json.loads((export.payload) and json.dumps(export.payload))
    assert payload["schema_version"] == "buktirilis.report.v1"
    assert payload["run"]["id"] == str(run.id)
    assert payload["builds"][0]["label"] == "2024.10.2"
    assert payload["snapshot_at"].startswith("2024-10-20")
    assert payload["findings"][0]["public_id"] == finding.public_id
    assert payload["limitations"]
    text = json.dumps(payload)
    assert "lab.tenant-b-dev" not in text
    assert "export surface was inventoried" in text
    assert payload["coverage"]["summary"]["denominator"] >= 0


def test_csv_exports_parse_and_neutralise_formulas(db, lab_project, settings):
    run, finding = _report(db, lab_project, settings)
    finding.title = '=HYPERLINK("http://evil.example/","click")'
    db.commit()
    exports = create_export(
        db, project=lab_project.project, run=run, fmt="csv", actor=lab_project.viewer
    )
    db.commit()
    formats = {export.format for export in exports}
    assert formats == {"csv_findings", "csv_coverage"}
    from app.services.evidence import read_bytes

    findings_bytes = read_bytes(
        db.get(__import__("app.models", fromlist=["Artifact"]).Artifact, exports[0].artifact_id)
    ).decode("utf-8")
    rows = list(csv.DictReader(io.StringIO(findings_bytes)))
    assert rows
    assert rows[0]["public_id"] == finding.public_id
    assert rows[0]["verification_outcome"] == "still_reproducible"
    assert rows[0]["title"].startswith("'=")
    coverage_bytes = read_bytes(
        db.get(__import__("app.models", fromlist=["Artifact"]).Artifact, exports[1].artifact_id)
    ).decode("utf-8")
    coverage_rows = list(csv.DictReader(io.StringIO(coverage_bytes)))
    assert coverage_rows
    assert "check_key" in coverage_rows[0]


def test_pdf_is_paginated_and_readable(db, lab_project, settings):
    run, finding = _report(db, lab_project, settings)
    exports = create_export(
        db, project=lab_project.project, run=run, fmt="pdf", actor=lab_project.viewer
    )
    db.commit()
    from pypdf import PdfReader

    from app.services.evidence import read_bytes

    artifact = db.get(
        __import__("app.models", fromlist=["Artifact"]).Artifact, exports[0].artifact_id
    )
    content = read_bytes(artifact)
    assert content.startswith(b"%PDF")
    reader = PdfReader(io.BytesIO(content))
    assert len(reader.pages) >= 2
    text = "\n".join(page.extract_text() or "" for page in reader.pages)
    assert "BuktiRilis Security Assessment Report" in text
    assert finding.public_id in text
    assert "Coverage and methodology" in text
    assert "Snapshot" in text
    assert "not a certification" in text
    assert "lab.tenant-b-dev" not in text


def test_frozen_snapshot_does_not_change_after_later_retest(db, lab_project, settings):
    run, finding = _report(db, lab_project, settings)
    exports = create_export(
        db, project=lab_project.project, run=run, fmt="pdf", actor=lab_project.viewer
    )
    db.commit()
    original = exports[0]
    original_sha = original.sha256
    original_outcome = original.payload["findings"][0]["verification"]["outcome"]
    add_observation(
        db,
        finding,
        run.build_id,
        outcome="not_observed",
        observed_at=NOW + timedelta(days=2),
        source="replay",
    )
    db.commit()
    stored = db.get(ExportSnapshot, original.id)
    assert stored.sha256 == original_sha
    assert stored.payload["findings"][0]["verification"]["outcome"] == original_outcome
    refreshed = create_export(
        db, project=lab_project.project, run=run, fmt="json", actor=lab_project.viewer
    )
    db.commit()
    # A new export of this run keeps the recorded snapshot and labels later work separately.
    assert refreshed[0].payload["findings"][0]["verification"]["outcome"] == "still_reproducible"
    assert refreshed[0].payload["latest_verification"]
    assert refreshed[0].payload["latest_verification"][0]["outcome"] == "fix_verified"


def test_filtered_export_is_labelled_as_subset(db, lab_project, settings):
    run, _ = _report(db, lab_project, settings)
    exports = create_export(
        db,
        project=lab_project.project,
        run=run,
        fmt="json",
        actor=lab_project.viewer,
        scope="filtered",
        scope_detail={"severity": ["critical"]},
    )
    db.commit()
    payload = exports[0].payload
    assert payload["scope"] == "filtered"
    assert payload["scope_detail"] == {"severity": ["critical"]}
    assert payload["findings"] == []


def test_export_payload_has_no_credential_and_evidence_is_explicit(db, lab_project, settings):
    run, _ = _report(db, lab_project, settings)
    exports = create_export(
        db, project=lab_project.project, run=run, fmt="json", actor=lab_project.viewer
    )
    db.commit()
    payload = exports[0].payload
    evidence = payload["findings"][0]["evidence"]
    assert evidence
    assert evidence[0]["attribution"] == "observed_capture"
    assert evidence[0]["payload"]["request"]["headers"]["Authorization"] == "[REDACTED]"
    assert "lab." not in json.dumps(payload)
    all_text = json.dumps(payload)
    assert "session=secret" not in all_text
    assert evidence[0]["payload"]["response"]["headers"]["set-cookie"] == "[REDACTED]"


def test_render_pdf_handles_empty_report(db, lab_project, settings):
    run = make_run(db, lab_project.project, lab_project.builds["2024.10.1"], lab_project.operator)
    run.completed_at = NOW
    run.snapshot_at = NOW
    run.summary = "No open findings were recorded."
    run.coverage_complete = True
    db.flush()
    exports = create_export(
        db, project=lab_project.project, run=run, fmt="pdf", actor=lab_project.viewer
    )
    db.commit()
    from pypdf import PdfReader

    artifact = db.get(
        __import__("app.models", fromlist=["Artifact"]).Artifact, exports[0].artifact_id
    )
    content = artifact and __import__("app.services.evidence", fromlist=["read_bytes"]).read_bytes(
        artifact
    )
    text = "\n".join(page.extract_text() or "" for page in PdfReader(io.BytesIO(content)).pages)
    assert "No findings were recorded inside the tested scope" in text


_ = (select, Evidence, render_pdf)

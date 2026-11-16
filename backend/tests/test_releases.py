"""Release Scan operation diffing and discovery-candidate derivation."""

from __future__ import annotations

import pytest
from fastapi import HTTPException

from app.models import OpenApiDocument
from app.services.releases import build_release_plan, openapi_diff
from app.services.runs import normalise_discovery_routes
from tests.helpers import make_run


def _document(db, project, operations: list[dict]) -> OpenApiDocument:
    document = OpenApiDocument(
        project_id=project.id,
        filename="spec.json",
        sha256="0" * 64,
        size_bytes=10,
        declared_server_url="http://lab:8099",
        operations=operations,
        sanitized_json={},
    )
    db.add(document)
    db.flush()
    return document


def test_openapi_diff_finds_added_changed_and_removed_operations(db, lab_project):
    baseline_ops = [
        {
            "path": "/api/invoices",
            "method": "GET",
            "operation_id": "listInvoices",
            "summary": "List invoices",
        },
        {
            "path": "/api/invoices/{invoice_id}",
            "method": "GET",
            "operation_id": "getInvoice",
            "summary": "Read an invoice",
        },
        {
            "path": "/api/old",
            "method": "GET",
            "operation_id": "old",
            "summary": "Removed",
        },
    ]
    current_ops = [
        {
            "path": "/api/invoices",
            "method": "GET",
            "operation_id": "listInvoices",
            "summary": "List invoices",
        },
        {
            "path": "/api/invoices/{invoice_id}",
            "method": "GET",
            "operation_id": "getInvoiceV2",
            "summary": "Read an invoice (v2)",
        },
        {
            "path": "/api/exports/{invoice_id}/pdf",
            "method": "GET",
            "operation_id": "exportInvoice",
            "summary": "Export an invoice",
        },
    ]
    baseline_build = lab_project.builds["2024.10.1"]
    current_build = lab_project.builds["2024.10.2"]
    baseline_build.openapi_document_id = _document(db, lab_project.project, baseline_ops).id
    current_build.openapi_document_id = _document(db, lab_project.project, current_ops).id
    db.commit()
    diff = openapi_diff(db, baseline_build, current_build)
    assert diff["available"] is True
    assert diff["added"] == ["GET /api/exports/{invoice_id}/pdf"]
    assert diff["changed"] == ["GET /api/invoices/{invoice_id}"]
    assert diff["removed"] == ["GET /api/old"]


def test_discovery_route_validation_rejects_absolute_and_injected_values():
    assert normalise_discovery_routes(["/api/ok", "/api/ok"]) == ["/api/ok"]
    for bad in [
        "https://evil.example",
        "/api/../admin",
        "/api/ok\n- injected",
        "/api/with space",
        "/" + "a" * 400,
    ]:
        with pytest.raises(HTTPException):
            normalise_discovery_routes([bad])


def test_release_plan_records_operator_selected_routes(db, lab_project):
    run = make_run(db, lab_project.project, lab_project.builds["2024.10.3"], lab_project.operator)
    run.scope_snapshot = {
        "base_url": lab_project.builds["2024.10.3"].target_url,
        "discovery_routes": ["/api/operator-selected"],
    }
    db.flush()
    plan = build_release_plan(db, run)
    assert plan["operator_routes"] == ["/api/operator-selected"]
    assert any(
        candidate["route"] == "/api/operator-selected"
        and candidate["reason"] == "operator selected"
        for candidate in plan["discovery_candidates"]
    )


def test_openapi_diff_is_unavailable_without_both_specs(db, lab_project):
    diff = openapi_diff(db, lab_project.builds["2024.10.1"], lab_project.builds["2024.10.2"])
    assert diff["available"] is False
    assert "Both builds need" in diff["reason"]

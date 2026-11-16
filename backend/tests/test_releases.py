"""Release Scan operation diffing and discovery-candidate derivation."""

from __future__ import annotations

from app.models import OpenApiDocument
from app.services.releases import openapi_diff


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


def test_openapi_diff_is_unavailable_without_both_specs(db, lab_project):
    diff = openapi_diff(db, lab_project.builds["2024.10.1"], lab_project.builds["2024.10.2"])
    assert diff["available"] is False
    assert "Both builds need" in diff["reason"]

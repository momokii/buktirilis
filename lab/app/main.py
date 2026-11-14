"""Illustrative staging API with synthetic data (BuktiRilis demo lab).

Deployments are path-prefixed (`/deployments/<label>`) so each approved build has a
distinct destination. Tokens are synthetic, documented in the lab README, and carry no
real privileges. This service is development-only and must not be exposed publicly.
"""

from __future__ import annotations

import os
from typing import Any

from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.responses import JSONResponse, Response

APP = FastAPI(title="Atlas Billing Lab", docs_url="/docs", openapi_url="/openapi.json")

LAB_DEPLOYMENTS = ("2024.10.1", "2024.10.2", "2024.10.3")
DEFAULT_DEPLOYMENT = "2024.10.1"

ACCOUNTS = {
    "tenant-c-observer": {"tenant_id": "tenant-c", "role": "viewer", "name": "Casey Lin"},
    "tenant-a-owner": {"tenant_id": "tenant-a", "role": "owner", "name": "Avery Chen"},
    "tenant-a-approver": {"tenant_id": "tenant-a", "role": "approver", "name": "Alex Rivera"},
    "tenant-b-dev": {"tenant_id": "tenant-b", "role": "developer", "name": "Blake Osei"},
    "tenant-b-approver": {"tenant_id": "tenant-b", "role": "approver", "name": "Bailey Novak"},
    "tenant-b-expired": {"tenant_id": "tenant-b", "role": "developer", "name": "Blake Osei"},
}

INVOICES = {
    "INV-A-1001": {
        "invoice_id": "INV-A-1001",
        "tenant_id": "tenant-a",
        "status": "open",
        "currency": "USD",
        "total_cents": 184000,
        "billing_contact": "ap@northwind.example",
        "line_items": [
            {"description": "Freight settlement, week 40", "amount_cents": 148000},
            {"description": "Handling", "amount_cents": 36000},
        ],
    },
    "INV-A-1002": {
        "invoice_id": "INV-A-1002",
        "tenant_id": "tenant-a",
        "status": "paid",
        "currency": "USD",
        "total_cents": 92000,
        "billing_contact": "ap@northwind.example",
        "line_items": [{"description": "Freight settlement, week 39", "amount_cents": 92000}],
    },
    "INV-B-2001": {
        "invoice_id": "INV-B-2001",
        "tenant_id": "tenant-b",
        "status": "open",
        "currency": "USD",
        "total_cents": 43000,
        "billing_contact": "finance@lumen.example",
        "line_items": [{"description": "Courier retainer", "amount_cents": 43000}],
    },
}

APPROVALS: dict[str, dict[str, Any]] = {}
APPROVAL_SEQUENCE = {"value": 8840}


def _deployment_from_request(request: Request) -> str:
    parts = [part for part in request.url.path.split("/") if part]
    if len(parts) >= 2 and parts[0] == "deployments":
        return parts[1]
    return DEFAULT_DEPLOYMENT


def _token_for(account: str) -> str:
    return f"lab.{account}"


def _account_from_header(deployment: str, authorization: str | None) -> str | None:
    if not authorization or not authorization.lower().startswith("bearer "):
        return None
    token = authorization.split(" ", 1)[1].strip()
    if not token.startswith("lab."):
        return None
    account = token[4:]
    if account.endswith("-expired"):
        return None
    return account if account in ACCOUNTS else None


def _error(status: int, code: str, message: str) -> JSONResponse:
    return JSONResponse(
        status_code=status,
        content={"error": {"code": code, "message": message}},
    )


def _require_account(request: Request, authorization: str | None) -> tuple[str, dict[str, Any]]:
    deployment = _deployment_from_request(request)
    account = _account_from_header(deployment, authorization)
    if account is None:
        raise _AuthError()
    return account, ACCOUNTS[account]


class _AuthError(Exception):
    pass


@APP.exception_handler(_AuthError)
async def _auth_error_handler(request: Request, exc: _AuthError) -> JSONResponse:
    return _error(401, "AUTH_REQUIRED", "A valid bearer token is required.")


@APP.exception_handler(HTTPException)
async def _http_error_handler(request: Request, exc: HTTPException) -> JSONResponse:
    detail = exc.detail if isinstance(exc.detail, str) else "Request rejected"
    return _error(exc.status_code, "REQUEST_REJECTED", detail)


@APP.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": "atlas-billing-lab"}


@APP.get("/")
def root() -> dict[str, Any]:
    return {
        "service": "atlas-billing-lab",
        "synthetic": True,
        "deployments": list(LAB_DEPLOYMENTS),
        "note": "Synthetic data only. Development demo target.",
    }


@APP.get("/deployments/{deployment}/api/meta")
def meta(deployment: str) -> JSONResponse:
    if deployment not in LAB_DEPLOYMENTS:
        return _error(404, "DEPLOYMENT_UNKNOWN", "Unknown deployment.")
    return JSONResponse(
        {"build": deployment, "service": "atlas-billing-lab", "synthetic": True},
        headers={"X-Build-Identity": deployment},
    )


@APP.get("/deployments/{deployment}/api/me")
def me(request: Request, authorization: str | None = Header(default=None)) -> dict[str, Any]:
    account, identity = _require_account(request, authorization)
    return {
        "account": account,
        "tenant_id": identity["tenant_id"],
        "role": identity["role"],
        "display_name": identity["name"],
        "deployment": _deployment_from_request(request),
    }


def _deployment_vulnerable(deployment: str) -> bool:
    return deployment in {"2024.10.1", "2024.10.3"}


@APP.get("/deployments/{deployment}/api/invoices")
def list_invoices(
    request: Request, authorization: str | None = Header(default=None)
) -> dict[str, Any]:
    _account, identity = _require_account(request, authorization)
    invoices = [
        invoice for invoice in INVOICES.values() if invoice["tenant_id"] == identity["tenant_id"]
    ]
    return {"items": invoices, "count": len(invoices)}


def _invoice(invoice_id: str) -> dict[str, Any]:
    invoice = INVOICES.get(invoice_id)
    if invoice is None:
        raise HTTPException(status_code=404, detail="Invoice not found.")
    return invoice


@APP.get("/deployments/{deployment}/api/invoices/{invoice_id}")
def get_invoice(
    invoice_id: str,
    request: Request,
    authorization: str | None = Header(default=None),
) -> Any:
    deployment = _deployment_from_request(request)
    _account, identity = _require_account(request, authorization)
    invoice = _invoice(invoice_id)
    if not _deployment_vulnerable(deployment) and invoice["tenant_id"] != identity["tenant_id"]:
        return _error(
            403,
            "TENANT_SCOPE_DENIED",
            "The requested invoice is outside the caller's tenant.",
        )
    if _deployment_vulnerable(deployment):
        # Deliberate demo flaw: authorization is not scoped to the owning tenant.
        return invoice
    return invoice


def _pdf(lines: list[str]) -> bytes:
    content = ["BT", "/F1 12 Tf", "72 740 Td", "16 TL"]
    for line in lines:
        safe = line.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
        content.append(f"({safe}) Tj T*")
    content.append("ET")
    stream = "\n".join(content).encode("latin-1", errors="replace")
    objects: list[bytes] = []
    objects.append(b"<< /Type /Catalog /Pages 2 0 R >>")
    objects.append(b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>")
    objects.append(
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
        b"/Resources << /Font << /F1 5 0 R >> >> /Contents 4 0 R >>"
    )
    objects.append(
        b"<< /Length " + str(len(stream)).encode() + b" >>\nstream\n" + stream + b"\nendstream"
    )
    objects.append(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>")
    payload = bytearray(b"%PDF-1.4\n")
    offsets: list[int] = []
    for index, body in enumerate(objects, start=1):
        offsets.append(len(payload))
        payload += f"{index} 0 obj\n".encode() + body + b"\nendobj\n"
    xref_start = len(payload)
    payload += f"xref\n0 {len(objects) + 1}\n".encode()
    payload += b"0000000000 65535 f \n"
    for offset in offsets:
        payload += f"{offset:010d} 00000 n \n".encode()
    payload += (
        f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{xref_start}\n%%EOF\n"
    ).encode()
    return bytes(payload)


@APP.get("/deployments/{deployment}/api/exports/{invoice_id}/pdf")
def export_invoice_pdf(
    invoice_id: str,
    request: Request,
    authorization: str | None = Header(default=None),
) -> Response:
    deployment = _deployment_from_request(request)
    _account, identity = _require_account(request, authorization)
    if deployment == "2024.10.1":
        raise HTTPException(status_code=404, detail="Export route not available in this build.")
    invoice = _invoice(invoice_id)
    # Deliberate demo flaw: the export handler resolves the identifier and renders the
    # document without scoping it to the caller's tenant.
    lines = [
        "Atlas Billing - Invoice export",
        f"Invoice: {invoice['invoice_id']}",
        f"Tenant: {invoice['tenant_id']}",
        f"Status: {invoice['status']}",
        f"Total (cents): {invoice['total_cents']}",
        f"Billing contact: {invoice['billing_contact']}",
        "Synthetic demo document.",
    ]
    return Response(content=_pdf(lines), media_type="application/pdf")


@APP.post("/deployments/{deployment}/api/approvals/{invoice_id}")
def create_approval(
    invoice_id: str,
    request: Request,
    authorization: str | None = Header(default=None),
) -> dict[str, Any]:
    deployment = _deployment_from_request(request)
    account, identity = _require_account(request, authorization)
    invoice = _invoice(invoice_id)
    APPROVAL_SEQUENCE["value"] += 1
    approval_id = f"apr-{APPROVAL_SEQUENCE['value']}"
    APPROVALS[approval_id] = {
        "approval_id": approval_id,
        "invoice_id": invoice["invoice_id"],
        "tenant_id": invoice["tenant_id"],
        "submitted_by": account,
        "status": "pending",
        "deployment": deployment,
    }
    return APPROVALS[approval_id]


@APP.post("/deployments/{deployment}/api/approvals/{approval_id}/approve")
def approve(
    approval_id: str,
    request: Request,
    authorization: str | None = Header(default=None),
) -> Any:
    account, identity = _require_account(request, authorization)
    approval = APPROVALS.get(approval_id)
    if approval is None:
        raise HTTPException(status_code=404, detail="Approval request not found.")
    if approval["status"] != "pending":
        raise HTTPException(status_code=409, detail="Approval request is already resolved.")
    if identity["role"] != "approver":
        return _error(403, "ROLE_REQUIRED", "An approver role is required.")
    # Deliberate demo flaw: the approver's tenant is not checked against the request.
    approval["status"] = "approved"
    approval["approved_by"] = account
    return approval


@APP.get("/deployments/{deployment}/api/approvals/{approval_id}")
def read_approval(
    approval_id: str,
    request: Request,
    authorization: str | None = Header(default=None),
) -> dict[str, Any]:
    _account, _identity = _require_account(request, authorization)
    approval = APPROVALS.get(approval_id)
    if approval is None:
        raise HTTPException(status_code=404, detail="Approval request not found.")
    return approval


@APP.get("/deployments/{deployment}/api/redirect-outside")
def redirect_outside(deployment: str) -> Response:
    """Synthetic out-of-scope redirect used to prove the runner fails closed."""
    from fastapi.responses import RedirectResponse

    return RedirectResponse("https://evil.example.test/collect", status_code=307)


@APP.get("/deployments/{deployment}/api/fixtures/{fixture_name}")
def fixture(
    fixture_name: str,
    request: Request,
    authorization: str | None = Header(default=None),
) -> Any:
    _account, identity = _require_account(request, authorization)
    if fixture_name == "invoice-a-1001" or fixture_name == "invoice_object_a":
        invoice = INVOICES["INV-A-1001"]
        if invoice["tenant_id"] != identity["tenant_id"]:
            return _error(403, "TENANT_SCOPE_DENIED", "Fixture is outside the caller's tenant.")
        return {"name": fixture_name, "present": True, **invoice}
    raise HTTPException(status_code=404, detail="Fixture not found.")


if __name__ == "__main__":  # pragma: no cover - manual lab launch
    import uvicorn

    uvicorn.run(
        "app.main:APP",
        host=os.environ.get("LAB_HOST", "127.0.0.1"),
        port=int(os.environ.get("LAB_PORT", "8099")),
        reload=False,
    )

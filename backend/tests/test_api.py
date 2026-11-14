"""API-level tests: authentication, CSRF, access isolation, report data, retests."""

from __future__ import annotations

import uuid
from datetime import datetime

import pytest
from fastapi.testclient import TestClient

from app.config import get_settings
from app.models import Job, Run
from app.services.pipeline import execute_run

PASSWORD = "correct horse battery staple"


def login(client: TestClient, email: str, password: str = PASSWORD) -> str:
    response = client.post("/api/auth/login", json={"email": email, "password": password})
    assert response.status_code == 200, response.text
    csrf = response.json()["csrf_token"]
    client.headers.update({"X-CSRF-Token": csrf})
    return csrf


def process_run(db, run_id: str) -> Run:
    run = db.get(Run, uuid.UUID(run_id))
    job = db.get(Job, run.job_id)
    job.state = "running"
    job.claimed_by = "api-test"
    job.attempts = 1
    job.started_at = datetime.now()
    db.flush()
    execute_run(db, run=run, job=job, settings=get_settings())
    db.commit()
    return run


def setup_project(client: TestClient, lab_base: str) -> dict:
    response = client.post(
        "/api/projects",
        json={
            "name": "API Test Atlas",
            "slug": "api-test-atlas",
            "description": "Integration project",
            "target": {
                "base_url": lab_base,
                "allowed_origins": [lab_base],
                "path_prefixes": ["/deployments"],
                "environment_label": "staging",
                "scope_owner": "QA",
                "authorization_reference": "AUTH-API-1",
                "run_limits": {"max_depth": "standard", "max_replay_checks": 6},
            },
        },
    )
    assert response.status_code == 201, response.text
    project = response.json()
    users = {}
    for role in ("operator", "developer", "viewer", "outsider"):
        response = client.post(
            "/api/admin/users",
            json={
                "email": f"{role}@api.test",
                "display_name": role.title(),
                "password": PASSWORD,
                "is_admin": False,
                "memberships": (
                    [{"project_id": project["id"], "role": role}] if role != "outsider" else []
                ),
            },
        )
        assert response.status_code == 201, response.text
        users[role] = response.json()
    build_ids = {}
    for label in ("2024.10.1", "2024.10.2"):
        response = client.post(
            f"/api/projects/{project['id']}/builds",
            json={
                "label": label,
                "target_url": f"{lab_base}/deployments/{label}",
                "expected_identity": label,
                "build_metadata": {"synthetic": True},
            },
        )
        assert response.status_code == 201, response.text
        build_ids[label] = response.json()["id"]
    account_ids = []
    for name, tenant in (("tenant-a-owner", "tenant-a"), ("tenant-b-dev", "tenant-b")):
        response = client.post(
            f"/api/projects/{project['id']}/accounts",
            json={
                "name": name,
                "role_label": "developer",
                "tenant_label": tenant,
                "credential": f"lab.{name}",
            },
        )
        assert response.status_code == 201, response.text
        account_ids.append(response.json()["id"])
    return {
        "project": project,
        "users": users,
        "builds": build_ids,
        "accounts": account_ids,
        "lab_base": lab_base,
    }


@pytest.fixture()
def api(db, admin_client, lab_server, lab_project):
    _ = lab_project
    data = setup_project(admin_client, lab_server)
    data["admin_client"] = admin_client
    return data


def test_unauthenticated_requests_are_rejected(client):
    assert client.get("/api/auth/session").status_code == 401
    assert client.get("/api/projects").status_code == 401
    assert client.get("/api/system/worker").status_code == 401


def test_csrf_is_required_for_mutations(api, client):
    operator = api["users"]["operator"]
    login(client, operator["email"])
    client.headers.pop("X-CSRF-Token", None)
    response = client.post(
        f"/api/projects/{api['project']['id']}/builds",
        json={"label": "2024.10.3", "target_url": f"{api['lab_base']}/deployments/2024.10.3"},
    )
    assert response.status_code == 403
    assert "CSRF" in response.json()["detail"]


def test_login_rate_limit(api):
    from fastapi.testclient import TestClient as FreshClient

    from app.main import app

    fresh = FreshClient(app)
    for _ in range(5):
        response = fresh.post(
            "/api/auth/login", json={"email": "operator@api.test", "password": "wrong password"}
        )
        assert response.status_code == 401
    response = fresh.post(
        "/api/auth/login", json={"email": "operator@api.test", "password": PASSWORD}
    )
    assert response.status_code == 429
    fresh.close()


def test_cross_project_isolation(api, client):
    outsider = api["users"]["outsider"]
    login(client, outsider["email"])
    project_id = api["project"]["id"]
    assert client.get(f"/api/projects/{project_id}").status_code == 404
    assert client.get(f"/api/projects/{project_id}/runs").status_code == 404
    assert client.get(f"/api/projects/{project_id}/builds").status_code == 404
    assert client.get(f"/api/projects/{project_id}/accounts").status_code == 404
    # A directly guessed finding id from the other project must not resolve either.
    assert client.get(f"/api/projects/{project_id}/findings/{uuid.uuid4()}").status_code == 404


def test_build_outside_scope_and_openapi_override_fail_closed(api, client):
    project_id = api["project"]["id"]
    response = client.post(
        f"/api/projects/{project_id}/builds",
        json={"label": "evil", "target_url": "http://169.254.169.254/latest/meta-data"},
    )
    assert response.status_code == 422, response.text
    spec = {
        "openapi": "3.0.3",
        "info": {"title": "Evil", "version": "1"},
        "servers": [{"url": api["lab_base"]}],
        "paths": {
            "/deployments/x/api/invoices": {
                "get": {
                    "servers": [{"url": "https://evil.example.test"}],
                    "responses": {"200": {"description": "ok"}},
                }
            }
        },
    }
    response = client.post(
        f"/api/projects/{project_id}/openapi",
        files={"file": ("spec.json", __import__("json").dumps(spec).encode(), "application/json")},
    )
    assert response.status_code == 422
    assert "unapproved server" in response.json()["detail"]


def test_run_preflight_and_reduced_scope_ack(api, client):
    project = api["project"]
    operator = api["users"]["operator"]
    login(client, operator["email"])
    body = {
        "build_id": api["builds"]["2024.10.1"],
        "kind": "baseline",
        "depth": "quick",
        "account_ids": [api["accounts"][0]],
        "unauthenticated": False,
    }
    preview = client.post(f"/api/projects/{project['id']}/runs/preflight", json=body)
    assert preview.status_code == 200, preview.text
    checks = preview.json()["preflight"]["checks"]
    codes = {check["code"] for check in checks}
    assert {"target_policy", "build_identity", "test_accounts", "daily_quota"} <= codes
    response = client.post(f"/api/projects/{project['id']}/runs", json=body)
    assert response.status_code == 409
    detail = response.json()["detail"]
    assert detail["requires_reduced_scope_ack"] is True
    assert detail["blocked_scenarios"]
    body["accept_reduced_scope"] = True
    created = client.post(f"/api/projects/{project['id']}/runs", json=body)
    assert created.status_code == 201, created.text
    assert created.json()["created"] is True
    duplicate = client.post(f"/api/projects/{project['id']}/runs", json=body)
    assert duplicate.status_code == 201
    assert duplicate.json()["created"] is False
    assert duplicate.json()["run"]["id"] == created.json()["run"]["id"]


def test_report_counts_match_rows_and_filters(api, client, db):
    project = api["project"]
    operator = api["users"]["operator"]
    login(client, operator["email"])
    body = {
        "build_id": api["builds"]["2024.10.1"],
        "kind": "baseline",
        "depth": "quick",
        "account_ids": api["accounts"],
        "unauthenticated": False,
        "accept_reduced_scope": True,
    }
    created = client.post(f"/api/projects/{project['id']}/runs", json=body).json()
    process_run(db, created["run"]["id"])
    run_id = created["run"]["id"]
    findings = client.get(f"/api/projects/{project['id']}/runs/{run_id}/report/findings").json()
    assert findings["items"]
    overview = client.get(f"/api/projects/{project['id']}/runs/{run_id}/report/overview").json()
    severity_total = sum(overview["severity"].values())
    assert severity_total == len([row for row in findings["items"] if row["disposition"] == "open"])
    severity = findings["items"][0]["severity"]
    filtered = client.get(
        f"/api/projects/{project['id']}/runs/{run_id}/report/findings",
        params={"severity": severity},
    ).json()
    assert filtered["items"]
    assert all(row["severity"] == severity for row in filtered["items"])
    coverage = client.get(f"/api/projects/{project['id']}/runs/{run_id}/report/coverage").json()
    assert coverage["checks"]
    assert coverage["coverage"]["denominator"] == len(coverage["checks"])
    assert coverage["coverage_complete"] is False
    assert coverage["limitations"]


def test_retest_flow_and_guided_review(api, client, db):
    project = api["project"]
    operator = api["users"]["operator"]
    login(client, operator["email"])
    body = {
        "build_id": api["builds"]["2024.10.1"],
        "kind": "baseline",
        "depth": "quick",
        "account_ids": api["accounts"],
        "unauthenticated": False,
        "accept_reduced_scope": True,
    }
    created = client.post(f"/api/projects/{project['id']}/runs", json=body).json()
    process_run(db, created["run"]["id"])
    # Approve a replay recipe as the operator.
    findings = client.get(
        f"/api/projects/{project['id']}/runs/{created['run']['id']}/report/findings"
    ).json()["items"]
    finding = next(row for row in findings if row["issue_class"] == "broken-object-authorization")
    recipe = client.post(
        f"/api/projects/{project['id']}/findings/{finding['id']}/recipes",
        json={
            "method": "GET",
            "path_template": "/api/invoices/{invoice_id}",
            "fixture_refs": [
                {
                    "name": "invoice_id",
                    "value": "INV-A-1001",
                    "check_path": "/api/invoices/INV-A-1001",
                    "expect": {"status": 200, "json_field": "tenant_id", "equals": "owner_tenant"},
                }
            ],
            "identity_refs": {"actor": "tenant-b-dev", "owner": "tenant-a-owner"},
            "expected_authorized": {
                "status": 200,
                "json_field": "tenant_id",
                "equals_identity_tenant": True,
            },
            "expected_unauthorized": {"denial_statuses": [403, 404]},
            "assertion": {
                "kind": "cross_tenant_json_object",
                "owner_field": "tenant_id",
                "highlight_fields": ["tenant_id", "invoice_id"],
            },
            "approve": True,
        },
    )
    assert recipe.status_code == 201, recipe.text
    # Viewer cannot start a retest.
    viewer = api["users"]["viewer"]
    login(client, viewer["email"])
    response = client.post(
        f"/api/projects/{project['id']}/findings/{finding['id']}/retests",
        json={"build_id": api["builds"]["2024.10.2"]},
    )
    assert response.status_code == 403
    # Developer can, and the worker records the verdict.
    developer = api["users"]["developer"]
    login(client, developer["email"])
    response = client.post(
        f"/api/projects/{project['id']}/findings/{finding['id']}/retests",
        json={"build_id": api["builds"]["2024.10.2"]},
    )
    assert response.status_code == 202, response.text
    attempt_id = response.json()["attempt"]["id"]
    job = db.query(Job).filter(Job.kind == "retest").order_by(Job.created_at.desc()).first()
    job.state = "running"
    job.claimed_by = "api-test"
    job.attempts = 1
    db.flush()
    from app.models import RetestAttempt
    from app.services.retests import execute_attempt

    attempt = db.get(RetestAttempt, uuid.UUID(attempt_id))
    execute_attempt(db, attempt=attempt, settings=get_settings())
    db.commit()
    detail = client.get(
        f"/api/projects/{project['id']}/findings/{finding['id']}",
        params={"build_id": api["builds"]["2024.10.2"]},
    ).json()
    assert detail["verification"]["outcome"] == "fix_verified"
    assert detail["attempts"][0]["outcome"] == "fix_verified"
    assert detail["attempts"][0]["positive_control"]["ok"] is True
    # A developer may mark the finding ready for retest (work scheduling only).
    ready = client.post(
        f"/api/projects/{project['id']}/findings/{finding['id']}/ready",
        json={"build_id": api["builds"]["2024.10.2"]},
    )
    assert ready.status_code == 200, ready.text
    assert "does not change the verification outcome" in ready.json()["note"]
    # Guided submission stays pending until a reviewer accepts it.
    login(client, developer["email"])
    guided = client.post(
        f"/api/projects/{project['id']}/findings/{finding['id']}/guided-attempts",
        json={
            "build_id": api["builds"]["2024.10.2"],
            "outcome": "still_reproducible",
            "notes": "Cross-tenant read still returns the object; owner control works.",
            "evidence_link": "https://evidence.internal/guided-1",
            "steps_revision": 1,
        },
    )
    assert guided.status_code == 201, guided.text
    assert guided.json()["attempt"]["pending_review"] is True
    login(client, operator["email"])
    review = client.post(
        f"/api/projects/{project['id']}/attempts/{guided.json()['attempt']['id']}/review",
        json={"decision": "changes_requested", "reason": "Attach the raw control response."},
    )
    assert review.status_code == 200
    assert review.json()["accepted"] is False


def test_export_api_download_and_isolation(api, client, db):
    project = api["project"]
    operator = api["users"]["operator"]
    login(client, operator["email"])
    body = {
        "build_id": api["builds"]["2024.10.1"],
        "kind": "baseline",
        "depth": "quick",
        "account_ids": api["accounts"],
        "unauthenticated": False,
        "accept_reduced_scope": True,
    }
    created = client.post(f"/api/projects/{project['id']}/runs", json=body).json()
    process_run(db, created["run"]["id"])
    response = client.post(
        f"/api/projects/{project['id']}/runs/{created['run']['id']}/exports",
        json={"format": "json"},
    )
    assert response.status_code == 201, response.text
    export = response.json()["exports"][0]
    download = client.get(f"/api/projects/{project['id']}/exports/{export['id']}/download")
    assert download.status_code == 200
    assert download.headers["content-type"].startswith("application/json")
    assert "lab.tenant" not in download.text
    assert "Bearer lab" not in download.text
    assert "Demo mode" in download.text
    outsider = api["users"]["outsider"]
    login(client, outsider["email"])
    assert (
        client.get(f"/api/projects/{project['id']}/exports/{export['id']}/download").status_code
        == 404
    )


def test_finding_detail_shows_evidence_and_separates_states(api, client, db):
    project = api["project"]
    operator = api["users"]["operator"]
    login(client, operator["email"])
    body = {
        "build_id": api["builds"]["2024.10.1"],
        "kind": "baseline",
        "depth": "quick",
        "account_ids": api["accounts"],
        "unauthenticated": False,
        "accept_reduced_scope": True,
    }
    created = client.post(f"/api/projects/{project['id']}/runs", json=body).json()
    process_run(db, created["run"]["id"])
    findings = client.get(
        f"/api/projects/{project['id']}/runs/{created['run']['id']}/report/findings"
    ).json()["items"]
    finding = findings[0]
    detail = client.get(
        f"/api/projects/{project['id']}/findings/{finding['id']}",
        params={"run_id": created["run"]["id"]},
    ).json()
    assert detail["evidence_status"] in {"supported", "needs_validation"}
    assert detail["verification"]["outcome"] in {
        "still_reproducible",
        "awaiting_retest",
        "fix_verified",
    }
    assert detail["retest_method"] in {"automatic", "guided", "pending_evidence_review"}
    assert detail["evidence"]
    assert detail["evidence"][0]["attribution"]
    assert "lab.tenant" not in __import__("json").dumps(detail)
    assert detail["capabilities"]["can_operate"] is True

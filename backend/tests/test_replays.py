"""Constrained replay runner tests against the real local lab over HTTP."""

from __future__ import annotations

import copy

import pytest

from app.services.policy import TargetPolicy
from app.services.replays import evaluate_recipe, resolve_path
from app.services.recipes import create_recipe_revision
from tests.helpers import BOLA_RECIPE, EXPORT_RECIPE, approve_recipe, make_finding


def _policy(settings, prefix="/deployments") -> TargetPolicy:
    return TargetPolicy(
        base_url=settings.lab_base_url,
        allowed_origins=(settings.lab_base_url,),
        path_prefixes=(prefix,),
        allow_loopback=True,
    )


def _approve(db, lab_project, recipe_payload):
    finding = make_finding(db, lab_project.project)
    approve_recipe(db, lab_project.project, finding, lab_project.operator, recipe_payload)
    revision = finding.recipe if hasattr(finding, "recipe") else None
    _ = revision
    from app.models import RecipeRevision

    revision = (
        db.query(RecipeRevision)
        .join(__import__("app.models", fromlist=["Recipe"]).Recipe)
        .filter_by(finding_id=finding.id)
        .one()
    )
    return finding, revision


def test_bola_still_reproducible_on_vulnerable_build(db, lab_project, settings):
    finding, revision = _approve(db, lab_project, BOLA_RECIPE)
    from app.services.replays import resolve_recipe_accounts

    actor, owner = resolve_recipe_accounts(db, revision)
    result = evaluate_recipe(
        db,
        settings=settings,
        project=lab_project.project,
        build=lab_project.builds["2024.10.1"],
        policy=_policy(settings),
        revision=revision,
        actor=actor,
        owner=owner,
    )
    assert result.outcome == "still_reproducible"
    assert result.build_identity_observed == "2024.10.1"
    assert result.positive_control["ok"] is True
    assert result.assertion_result["observed_owner"] == "tenant-a"
    evidence_text = str(result.evidence)
    assert "INV-A-1001" in evidence_text
    # No credential value may leak into captured evidence.
    assert "lab.tenant-b-dev" not in evidence_text
    assert "Bearer [REDACTED]" in evidence_text or "[REDACTED]" in evidence_text


def test_bola_fix_verified_when_patched_with_control(db, lab_project, settings):
    finding, revision = _approve(db, lab_project, BOLA_RECIPE)
    from app.services.replays import resolve_recipe_accounts

    actor, owner = resolve_recipe_accounts(db, revision)
    result = evaluate_recipe(
        db,
        settings=settings,
        project=lab_project.project,
        build=lab_project.builds["2024.10.2"],
        policy=_policy(settings),
        revision=revision,
        actor=actor,
        owner=owner,
    )
    assert result.outcome == "fix_verified"
    assert result.positive_control["ok"] is True
    assert result.assertion_result["status"] == 403


def test_expired_identity_is_inconclusive(db, lab_project, settings):
    payload = copy.deepcopy(BOLA_RECIPE)
    payload["identity_refs"]["actor"] = "tenant-b-expired"
    finding, revision = _approve(db, lab_project, payload)
    from app.services.replays import resolve_recipe_accounts

    actor, owner = resolve_recipe_accounts(db, revision)
    result = evaluate_recipe(
        db,
        settings=settings,
        project=lab_project.project,
        build=lab_project.builds["2024.10.2"],
        policy=_policy(settings),
        revision=revision,
        actor=actor,
        owner=owner,
    )
    assert result.outcome == "inconclusive"
    assert result.reason_code == "expired_credentials"


def test_missing_fixture_is_inconclusive(db, lab_project, settings):
    payload = copy.deepcopy(BOLA_RECIPE)
    payload["fixture_refs"][0]["value"] = "INV-Z-9999"
    payload["fixture_refs"][0]["check_path"] = "/api/invoices/INV-Z-9999"
    finding, revision = _approve(db, lab_project, payload)
    from app.services.replays import resolve_recipe_accounts

    actor, owner = resolve_recipe_accounts(db, revision)
    result = evaluate_recipe(
        db,
        settings=settings,
        project=lab_project.project,
        build=lab_project.builds["2024.10.1"],
        policy=_policy(settings),
        revision=revision,
        actor=actor,
        owner=owner,
    )
    assert result.outcome == "inconclusive"
    assert result.reason_code == "missing_fixture"


def test_failed_positive_control_never_verifies_a_fix(db, lab_project, settings):
    payload = copy.deepcopy(BOLA_RECIPE)
    payload["expected_authorized"] = {"status": 201}
    finding, revision = _approve(db, lab_project, payload)
    from app.services.replays import resolve_recipe_accounts

    actor, owner = resolve_recipe_accounts(db, revision)
    result = evaluate_recipe(
        db,
        settings=settings,
        project=lab_project.project,
        build=lab_project.builds["2024.10.2"],
        policy=_policy(settings),
        revision=revision,
        actor=actor,
        owner=owner,
    )
    assert result.outcome == "inconclusive"
    assert result.reason_code == "positive_control_failed"


def test_build_identity_mismatch_is_inconclusive(db, lab_project, settings):
    finding, revision = _approve(db, lab_project, BOLA_RECIPE)
    build = lab_project.builds["2024.10.1"]
    build.expected_identity = "2024.10.9"
    db.flush()
    from app.services.replays import resolve_recipe_accounts

    actor, owner = resolve_recipe_accounts(db, revision)
    result = evaluate_recipe(
        db,
        settings=settings,
        project=lab_project.project,
        build=build,
        policy=_policy(settings),
        revision=revision,
        actor=actor,
        owner=owner,
    )
    assert result.outcome == "inconclusive"
    assert result.reason_code == "build_identity_mismatch"
    assert result.build_identity_observed == "2024.10.1"


def test_unverified_build_identity_is_inconclusive(db, lab_project, settings):
    finding, revision = _approve(db, lab_project, BOLA_RECIPE)
    build = lab_project.builds["2024.10.1"]
    build.expected_identity = ""
    db.flush()
    from app.services.replays import resolve_recipe_accounts

    actor, owner = resolve_recipe_accounts(db, revision)
    result = evaluate_recipe(
        db,
        settings=settings,
        project=lab_project.project,
        build=build,
        policy=_policy(settings),
        revision=revision,
        actor=actor,
        owner=owner,
    )
    assert result.reason_code == "build_identity_unverified"


def test_scope_denied_when_path_restriction_excludes_recipe(db, lab_project, settings):
    finding, revision = _approve(db, lab_project, BOLA_RECIPE)
    from app.services.replays import resolve_recipe_accounts

    actor, owner = resolve_recipe_accounts(db, revision)
    result = evaluate_recipe(
        db,
        settings=settings,
        project=lab_project.project,
        build=lab_project.builds["2024.10.1"],
        policy=_policy(settings, prefix="/other"),
        revision=revision,
        actor=actor,
        owner=owner,
    )
    assert result.outcome == "inconclusive"
    assert result.reason_code == "scope_denied"


def test_export_document_vulnerability_is_reproducible(db, lab_project, settings):
    finding = make_finding(
        db,
        lab_project.project,
        title="Cross-tenant export",
        issue_class="cross-tenant-export",
        severity="critical",
        scope="GET /api/exports/{invoice_id}/pdf",
    )
    approve_recipe(
        db, lab_project.project, finding, lab_project.operator, EXPORT_RECIPE
    )
    from app.models import Recipe, RecipeRevision
    from app.services.replays import resolve_recipe_accounts

    revision = (
        db.query(RecipeRevision)
        .join(Recipe)
        .filter(Recipe.finding_id == finding.id)
        .one()
    )
    actor, owner = resolve_recipe_accounts(db, revision)
    result = evaluate_recipe(
        db,
        settings=settings,
        project=lab_project.project,
        build=lab_project.builds["2024.10.2"],
        policy=_policy(settings),
        revision=revision,
        actor=actor,
        owner=owner,
    )
    assert result.outcome == "still_reproducible"
    assert result.assertion_result["marker_present"] is True
    assert b"%PDF" in result.evidence[1]["response"]["body"].encode() or "%PDF" in str(
        result.evidence[1]["response"]["body"]
    )


def test_resolve_path_rejects_absolute_and_traversal(db, lab_project):
    with pytest.raises(Exception):  # noqa: B017 - PolicyError
        from app.services.policy import PolicyError, TargetPolicy

        policy = TargetPolicy(
            base_url="http://127.0.0.1:8099",
            allowed_origins=("http://127.0.0.1:8099",),
            path_prefixes=("/deployments",),
            allow_loopback=True,
        )
        policy.resolve("http://127.0.0.1:8099/deployments/2024.10.1", "http://evil.test/x")
    assert resolve_path("/api/invoices/{invoice_id}", [{"name": "invoice_id", "value": "INV-1"}]) == (
        "/api/invoices/INV-1"
    )

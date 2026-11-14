"""Operator-reviewed replay recipes and guided-retest packages."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.domain import RecipeState, RetestMethod
from app.models import (
    Build,
    Finding,
    Project,
    Recipe,
    RecipeRevision,
    TargetConfig,
    TestAccount,
    User,
)
from app.services.findings import approved_recipe, eligibility, latest_observation
from app.services.policy import PolicyError, TargetPolicy
from app.services.replays import ALLOWED_METHODS, resolve_path

SUPPORTED_ASSERTIONS = {"cross_tenant_json_object", "cross_tenant_document"}


def _project_policy(project: Project, db: Session, build: Build | None) -> TargetPolicy:
    from app.config import get_settings

    config = None
    if build is not None:
        config = db.get(TargetConfig, build.target_config_id)
    if config is None:
        config = db.execute(
            select(TargetConfig)
            .where(TargetConfig.project_id == project.id)
            .order_by(TargetConfig.revision.desc())
            .limit(1)
        ).scalar_one_or_none()
    if config is None:
        raise HTTPException(status_code=409, detail="Project has no approved target policy")
    return TargetPolicy.from_config(
        config, allow_loopback=bool(get_settings().allow_loopback_lab_targets)
    )


def validate_recipe_input(
    db: Session,
    *,
    project: Project,
    payload: dict[str, Any],
) -> dict[str, Any]:
    method = str(payload.get("method", "")).upper()
    if method not in ALLOWED_METHODS:
        raise HTTPException(
            status_code=422,
            detail="Approved recipes are limited to read-oriented GET/HEAD operations",
        )
    path_template = str(payload.get("path_template") or "").strip()
    if not path_template:
        raise HTTPException(status_code=422, detail="A relative path template is required")
    if "://" in path_template or path_template.startswith("//"):
        raise HTTPException(
            status_code=422,
            detail="Recipes may only contain a relative path; the build supplies the origin",
        )
    if ".." in path_template:
        raise HTTPException(status_code=422, detail="Path templates may not traverse directories")

    fixture_refs = payload.get("fixture_refs") or []
    if not isinstance(fixture_refs, list) or not fixture_refs:
        raise HTTPException(status_code=422, detail="At least one fixture reference is required")
    values: dict[str, str] = {}
    for ref in fixture_refs:
        if not isinstance(ref, dict) or not ref.get("name") or ref.get("value") is None:
            raise HTTPException(
                status_code=422, detail="Each fixture reference needs a name and value"
            )
        values[str(ref["name"])] = str(ref["value"])
        if ref.get("check_path") and ".." in str(ref["check_path"]):
            raise HTTPException(status_code=422, detail="Fixture check paths may not traverse")
    for placeholder in [part.split("}")[0] for part in path_template.split("{")[1:]]:
        if placeholder not in values:
            raise HTTPException(
                status_code=422,
                detail=f"Path placeholder {{{placeholder}}} has no fixture value",
            )

    identity_refs = payload.get("identity_refs") or {}
    if not isinstance(identity_refs, dict) or not identity_refs.get("actor"):
        raise HTTPException(status_code=422, detail="An acting test identity is required")
    if not identity_refs.get("owner"):
        raise HTTPException(
            status_code=422,
            detail="A legitimate owner identity is required for the positive control",
        )
    accounts = {
        account.name: account
        for account in db.execute(
            select(TestAccount).where(TestAccount.project_id == project.id)
        ).scalars()
    }
    for role in ("actor", "owner"):
        name = str(identity_refs.get(role) or "")
        if name not in accounts:
            raise HTTPException(status_code=422, detail=f"Unknown test identity for {role}: {name}")
    if identity_refs["actor"] == identity_refs["owner"]:
        raise HTTPException(
            status_code=422,
            detail="Actor and owner must be distinct identities for a cross-account assertion",
        )

    assertion = payload.get("assertion") or {}
    if not isinstance(assertion, dict) or assertion.get("kind") not in SUPPORTED_ASSERTIONS:
        raise HTTPException(
            status_code=422,
            detail="Assertion must be one of the supported typed assertions",
        )
    if assertion.get("kind") == "cross_tenant_json_object" and not assertion.get("owner_field"):
        raise HTTPException(status_code=422, detail="A JSON assertion needs an owner_field")

    expected_authorized = payload.get("expected_authorized") or {"status": 200}
    expected_unauthorized = payload.get("expected_unauthorized") or {
        "statuses": [200],
        "denial_statuses": [403, 404],
    }
    return {
        "method": method,
        "path_template": path_template,
        "fixture_refs": fixture_refs,
        "identity_refs": identity_refs,
        "expected_authorized": expected_authorized,
        "expected_unauthorized": expected_unauthorized,
        "assertion": assertion,
        "preconditions": payload.get("preconditions")
        or ["build_identity", "actor_identity", "fixture_present", "positive_control"],
    }


def create_recipe_revision(
    db: Session,
    *,
    project: Project,
    finding: Finding,
    payload: dict[str, Any],
    actor: User,
    approve: bool = False,
) -> tuple[Recipe, RecipeRevision]:
    validated = validate_recipe_input(db, project=project, payload=payload)
    recipe = db.execute(select(Recipe).where(Recipe.finding_id == finding.id)).scalar_one_or_none()
    if recipe is None:
        recipe = Recipe(
            project_id=project.id,
            finding_id=finding.id,
            state=RecipeState.DRAFT,
            created_by=actor.id,
        )
        db.add(recipe)
        db.flush()
    next_revision = (
        db.execute(
            select(RecipeRevision.revision)
            .where(RecipeRevision.recipe_id == recipe.id)
            .order_by(RecipeRevision.revision.desc())
            .limit(1)
        ).scalar_one_or_none()
        or 0
    ) + 1
    revision = RecipeRevision(
        recipe_id=recipe.id,
        revision=next_revision,
        method=validated["method"],
        path_template=validated["path_template"],
        fixture_refs=validated["fixture_refs"],
        identity_refs=validated["identity_refs"],
        preconditions=validated["preconditions"],
        expected_unauthorized=validated["expected_unauthorized"],
        expected_authorized=validated["expected_authorized"],
        assertion=validated["assertion"],
        created_by=actor.id,
    )
    db.add(revision)
    db.flush()
    if approve:
        revision.approved_by = actor.id
        revision.approved_at = datetime.now(UTC)
        recipe.state = RecipeState.APPROVED
        finding.retest_method = RetestMethod.AUTOMATIC.value
    db.flush()
    return recipe, revision


def approve_revision(db: Session, *, recipe: Recipe, revision: RecipeRevision, actor: User) -> None:
    if revision.recipe_id != recipe.id:
        raise HTTPException(status_code=404, detail="Recipe revision not found")
    latest = db.execute(
        select(RecipeRevision.revision)
        .where(RecipeRevision.recipe_id == recipe.id)
        .order_by(RecipeRevision.revision.desc())
        .limit(1)
    ).scalar_one()
    if revision.revision != latest:
        raise HTTPException(
            status_code=409,
            detail="Only the newest revision can be approved",
        )
    revision.approved_by = actor.id
    revision.approved_at = datetime.now(UTC)
    recipe.state = RecipeState.APPROVED
    finding = db.get(Finding, recipe.finding_id)
    if finding is not None:
        finding.retest_method = RetestMethod.AUTOMATIC.value
    db.flush()


def recipe_preview(
    db: Session,
    *,
    project: Project,
    finding: Finding,
    build: Build,
    revision: RecipeRevision,
) -> dict[str, Any]:
    policy = _project_policy(project, db, build)
    path = resolve_path(revision.path_template, list(revision.fixture_refs or []))
    resolved = ""
    error = ""
    try:
        resolved = policy.resolve(build.target_url, path).url
    except PolicyError as exc:
        error = str(exc)
    return {
        "recipe_id": str(revision.recipe_id),
        "revision": revision.revision,
        "method": revision.method,
        "path": path,
        "resolved_target": resolved,
        "target_error": error,
        "identity_refs": revision.identity_refs,
        "fixture_refs": [
            {k: v for k, v in ref.items() if k != "value"} | {"value": ref.get("value")}
            for ref in (revision.fixture_refs or [])
        ],
        "preconditions": revision.preconditions,
        "expected_authorized": revision.expected_authorized,
        "expected_unauthorized": revision.expected_unauthorized,
        "assertion": revision.assertion,
        "approved": revision.approved_at is not None,
    }


GUIDED_AUTOMATION_LIMITS = {
    "two-actor-approval": (
        "This case needs a state-changing approval transition across two authenticated "
        "sessions; automatic replay is limited to read-oriented checks."
    ),
    "broken-object-authorization": (
        "The original proofs do not include a bounded read-only recipe that passes the "
        "typed assertion contract."
    ),
    "evidence-review": (
        "The recorded evidence is incomplete, so a reviewer must complete or reject it "
        "before a retest path can be chosen."
    ),
}


def guided_package(
    db: Session,
    *,
    project: Project,
    finding: Finding,
    build: Build,
    can_submit: bool,
) -> dict[str, Any]:
    recipe_pair = approved_recipe(db, finding.id)
    scenario_hint = GUIDED_AUTOMATION_LIMITS.get(
        finding.issue_class,
        "No approved read-only replay recipe covers this case, so it requires a human retest.",
    )
    if finding.issue_class == "two-actor-approval":
        scenario_hint = GUIDED_AUTOMATION_LIMITS["two-actor-approval"]
    accounts = list(
        db.execute(
            select(TestAccount)
            .where(TestAccount.project_id == project.id)
            .order_by(TestAccount.name)
        ).scalars()
    )
    evidence_rows = list(db.execute(select(Finding.id).where(Finding.id == finding.id)).scalars())
    missing: list[str] = []
    if not finding.reproduction_steps:
        missing.append("Ordered reproduction steps are not recorded")
    if not finding.observed_behavior:
        missing.append("The observed behavior statement is missing")
    if not finding.expected_behavior:
        missing.append("The expected behavior after the fix is missing")
    if not evidence_rows:
        missing.append("No linked evidence")
    if not finding.prerequisites:
        missing.append("Prerequisites or required fixtures are not listed")
    control = None
    if recipe_pair:
        control = recipe_pair[1].expected_authorized
    else:
        control = {
            "status": 200,
            "note": "The legitimate owner must still receive the object or document.",
        }
    latest = latest_observation(db, finding.id, build.id)
    return {
        "finding_id": str(finding.id),
        "public_id": finding.public_id,
        "build_id": str(build.id),
        "build_label": build.label,
        "automation_limit": scenario_hint,
        "retest_method": eligibility(finding),
        "required_identities": [
            {"name": account.name, "role": account.role_label, "tenant": account.tenant_label}
            for account in accounts
        ],
        "required_fixtures": list(finding.prerequisites),
        "steps": list(finding.reproduction_steps),
        "expected_after_fix": finding.expected_behavior,
        "observed_behavior": finding.observed_behavior,
        "control_check": control,
        "capture_instructions": [
            "The exact request and response excerpt from the unauthorized attempt",
            "The response from the legitimate-owner control request on the same build",
            "The build identity reported by the deployment, if it exposes one",
            "A note for anything that differed from the recorded steps",
        ],
        "missing_prerequisites": missing,
        "latest_observation": (
            {
                "outcome": latest.outcome,
                "source": latest.source,
                "observed_at": latest.observed_at.isoformat().replace("+00:00", "Z"),
            }
            if latest
            else None
        ),
        "can_submit": can_submit,
        "copyable_details": {
            "method": recipe_pair[1].method if recipe_pair else "GET",
            "path_template": (
                recipe_pair[1].path_template if recipe_pair else finding.scope_summary
            ),
            "identity_refs": recipe_pair[1].identity_refs if recipe_pair else {},
            "fixture_refs": [
                {k: v for k, v in ref.items()}
                for ref in (recipe_pair[1].fixture_refs if recipe_pair else [])
            ],
        },
    }


def recipe_for_finding(db: Session, finding_id: uuid.UUID) -> dict[str, Any] | None:
    recipe = db.execute(select(Recipe).where(Recipe.finding_id == finding_id)).scalar_one_or_none()
    if recipe is None:
        return None
    revisions = list(
        db.execute(
            select(RecipeRevision)
            .where(RecipeRevision.recipe_id == recipe.id)
            .order_by(RecipeRevision.revision.desc())
        ).scalars()
    )
    return {
        "id": str(recipe.id),
        "state": recipe.state,
        "revisions": [
            {
                "id": str(rev.id),
                "revision": rev.revision,
                "method": rev.method,
                "path_template": rev.path_template,
                "approved": rev.approved_at is not None,
                "approved_at": rev.approved_at.isoformat().replace("+00:00", "Z")
                if rev.approved_at
                else None,
                "identity_refs": rev.identity_refs,
                "assertion": rev.assertion,
                "expected_authorized": rev.expected_authorized,
            }
            for rev in revisions
        ],
    }

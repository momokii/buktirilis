"""Constrained, read-oriented replay runner.

Only normalized, approved recipes execute here. Recipes carry a typed assertion; the
runner verifies identity, fixture, build identity and a legitimate positive control
before it can call anything "fixed". Imported PoCs, scripts, and response bodies are
never executed.
"""

from __future__ import annotations

import ipaddress
import socket
import time
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any
from urllib.parse import urljoin

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import Settings
from app.domain import INCONCLUSIVE_REASON_LABELS, InconclusiveReason, VerificationOutcome
from app.models import Build, Project, RecipeRevision, RetestAttempt, TestAccount
from app.security import decrypt_secret
from app.services.evidence import http_exchange_payload
from app.services.policy import Destination, PolicyError, TargetPolicy, parse_destination

ALLOWED_METHODS = frozenset({"GET", "HEAD"})
DEFAULT_TIMEOUT_SECONDS = 8.0


@dataclass
class HttpExchange:
    method: str
    url: str
    request_headers: dict[str, str]
    status: int | None
    response_headers: dict[str, str] = field(default_factory=dict)
    body: str = ""
    elapsed_ms: int = 0
    error: str | None = None
    redirect_target: str | None = None
    redirect_blocked: bool = False

    @property
    def is_json(self) -> bool:
        content_type = self.response_headers.get("content-type", "")
        return "json" in content_type.lower()

    def json(self) -> Any:
        if not self.body:
            return None
        try:
            import json

            return json.loads(self.body)
        except ValueError:
            return None


@dataclass
class AttemptResult:
    outcome: VerificationOutcome
    reason_code: str | None
    reason_text: str
    prerequisites: dict[str, Any] = field(default_factory=dict)
    positive_control: dict[str, Any] = field(default_factory=dict)
    assertion_result: dict[str, Any] = field(default_factory=dict)
    evidence: list[dict[str, Any]] = field(default_factory=list)
    build_identity_observed: str = ""

    @property
    def is_conclusive(self) -> bool:
        return self.outcome in {
            VerificationOutcome.FIX_VERIFIED,
            VerificationOutcome.STILL_REPRODUCIBLE,
        }


def _inconclusive(reason: InconclusiveReason, detail: str = "", **kwargs: Any) -> AttemptResult:
    return AttemptResult(
        outcome=VerificationOutcome.INCONCLUSIVE,
        reason_code=reason.value,
        reason_text=f"{INCONCLUSIVE_REASON_LABELS[reason]}: {detail}"
        if detail
        else INCONCLUSIVE_REASON_LABELS[reason],
        **kwargs,
    )


def check_resolution(destination: Destination, *, allow_loopback: bool) -> str | None:
    """Resolve the host and reject metadata/link-local/reserved destinations."""
    try:
        infos = socket.getaddrinfo(destination.host, destination.port, type=socket.SOCK_STREAM)
    except OSError as exc:
        return f"DNS resolution failed ({exc.__class__.__name__})"
    addresses = {info[4][0] for info in infos}
    for raw in addresses:
        try:
            address = ipaddress.ip_address(raw)
        except ValueError:
            return "Resolved address could not be parsed"
        if address.is_link_local or address.is_reserved or address.is_multicast:
            return "Resolved address is a reserved or link-local destination"
        if address.is_loopback and not allow_loopback:
            return "Resolved address is loopback and loopback targets are disabled"
    return None


def send(
    *,
    policy: TargetPolicy,
    method: str,
    url: str,
    headers: dict[str, str],
    timeout: float = DEFAULT_TIMEOUT_SECONDS,
) -> HttpExchange:
    method = method.upper()
    if method not in ALLOWED_METHODS:
        return HttpExchange(
            method=method,
            url=url,
            request_headers=headers,
            status=None,
            error="Replay runner only permits read-oriented GET/HEAD recipes",
        )
    try:
        destination = policy.check(url)
    except PolicyError as exc:
        return HttpExchange(
            method=method,
            url=url,
            request_headers=headers,
            status=None,
            error=f"scope_denied:{exc.code}",
        )
    resolution_error = check_resolution(destination, allow_loopback=policy.allow_loopback)
    if resolution_error:
        return HttpExchange(
            method=method,
            url=url,
            request_headers=headers,
            status=None,
            error=f"resolution_denied:{resolution_error}",
        )

    started = time.monotonic()
    try:
        with httpx.Client(follow_redirects=False, timeout=timeout, verify=True) as client:
            response = client.request(method, url, headers=headers)
    except httpx.HTTPError as exc:
        return HttpExchange(
            method=method,
            url=url,
            request_headers=headers,
            status=None,
            elapsed_ms=int((time.monotonic() - started) * 1000),
            error=f"transport_error:{exc.__class__.__name__}",
        )
    elapsed = int((time.monotonic() - started) * 1000)
    body = response.text if response.status_code != 204 else ""
    headers_dict = {key: value for key, value in response.headers.items()}
    exchange = HttpExchange(
        method=method,
        url=url,
        request_headers=headers,
        status=response.status_code,
        response_headers=headers_dict,
        body=body[:20000],
        elapsed_ms=elapsed,
    )
    if 300 <= response.status_code < 400:
        location = headers_dict.get("location", "")
        exchange.redirect_target = urljoin(url, location) if location else ""
        try:
            policy.check_redirect(location, from_url=url)
        except PolicyError:
            exchange.redirect_blocked = True
        if not exchange.redirect_blocked:
            # Even an in-scope redirect is not followed by this runner.
            exchange.error = "redirect_not_followed"
    return exchange


def _auth_headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}", "Accept": "application/json"}


def _account_token(account: TestAccount) -> str:
    return decrypt_secret(account.credential_ciphertext)


def _account_identity(exchange: HttpExchange) -> dict[str, Any] | None:
    payload = exchange.json()
    if not isinstance(payload, dict):
        return None
    return payload


def _identity_matches(account: TestAccount, identity: dict[str, Any]) -> bool:
    tenant = identity.get("tenant_id") or identity.get("tenant")
    if account.tenant_label and tenant:
        return str(tenant) == account.tenant_label
    name = identity.get("account") or identity.get("account_id") or identity.get("user")
    return bool(name) and str(name) == account.name


def _fixture_value(refs: list[dict], name: str) -> str | None:
    for ref in refs:
        if str(ref.get("name")) == name:
            return str(ref.get("value", ""))
    return None


def resolve_path(path_template: str, fixture_refs: list[dict]) -> str:
    resolved = path_template
    for ref in fixture_refs:
        placeholder = "{" + str(ref.get("name")) + "}"
        if placeholder in resolved:
            resolved = resolved.replace(placeholder, str(ref.get("value")))
    return resolved


def _exchange_evidence(
    *,
    exchange: HttpExchange,
    actor_label: str,
    notes: str,
    source_note: str,
) -> dict[str, Any]:
    payload = http_exchange_payload(
        request_method=exchange.method,
        request_url=exchange.url,
        request_headers=exchange.request_headers,
        request_body=None,
        response_status=exchange.status,
        response_headers=exchange.response_headers,
        response_body=exchange.body,
        elapsed_ms=exchange.elapsed_ms,
        actor_label=actor_label,
        notes=notes,
        source_note=source_note,
    )
    return payload


def _denied(assertion: dict[str, Any], *, status: int | None, body: Any) -> tuple[bool, str]:
    denial_statuses = {int(s) for s in assertion.get("denial_statuses", [403, 404])}
    if status in denial_statuses:
        return True, f"denial status {status}"
    error_field = assertion.get("denial_error_field")
    prefix = assertion.get("denial_error_prefix")
    if error_field and prefix and isinstance(body, dict):
        value: Any = body
        for part in str(error_field).split("."):
            value = value.get(part) if isinstance(value, dict) else None
        if isinstance(value, str) and value.upper().startswith(str(prefix).upper()):
            return True, f"denial code {value}"
    return False, ""


def _json_owner_field(
    body: Any, assertion: dict[str, Any]
) -> tuple[str | None, dict[str, Any] | None]:
    owner_field = str(assertion.get("owner_field") or "tenant_id")
    node: Any = body
    object_path = assertion.get("object_path")
    if object_path:
        for part in str(object_path).split("."):
            node = node.get(part) if isinstance(node, dict) else None
    if not isinstance(node, dict):
        return None, None
    value = node.get(owner_field)
    return (str(value) if value is not None else None), node


def _highlight(assertion: dict[str, Any], node: dict[str, Any] | None) -> list[str]:
    fields = [str(f) for f in assertion.get("highlight_fields", [])]
    lines: list[str] = []
    if node is None:
        return lines
    for field_name in fields:
        if field_name in node:
            lines.append(f'"{field_name}": {node[field_name]!r}')
    return lines


@dataclass
class ResolvedRecipe:
    recipe_revision: RecipeRevision
    actor: TestAccount
    owner: TestAccount
    fixture_refs: list[dict]
    path: str
    url: str

    @property
    def revision_label(self) -> str:
        return f"r{self.recipe_revision.revision}"


def resolve_recipe_accounts(
    db: Session, revision: RecipeRevision
) -> tuple[TestAccount | None, TestAccount | None]:
    identity_refs = revision.identity_refs or {}
    project_id = None
    recipe = revision.recipe_id
    from app.models import Recipe

    recipe_row = db.get(Recipe, recipe)
    if recipe_row is not None:
        project_id = recipe_row.project_id
    actor = owner = None
    if identity_refs.get("actor") and project_id:
        actor = db.execute(
            select(TestAccount).where(
                TestAccount.project_id == project_id,
                TestAccount.name == str(identity_refs["actor"]),
            )
        ).scalar_one_or_none()
    if identity_refs.get("owner") and project_id:
        owner = db.execute(
            select(TestAccount).where(
                TestAccount.project_id == project_id,
                TestAccount.name == str(identity_refs["owner"]),
            )
        ).scalar_one_or_none()
    return actor, owner


def evaluate_recipe(
    db: Session,
    *,
    settings: Settings,
    project: Project,
    build: Build,
    policy: TargetPolicy,
    revision: RecipeRevision,
    actor: TestAccount,
    owner: TestAccount,
) -> AttemptResult:
    assertion = revision.assertion or {}
    fixture_refs = list(revision.fixture_refs or [])
    prerequisites: dict[str, Any] = {}

    path = resolve_path(revision.path_template, fixture_refs)
    try:
        destination = policy.resolve(build.target_url, path)
    except PolicyError as exc:
        prerequisites["scope"] = {"ok": False, "detail": exc.code}
        return _inconclusive(InconclusiveReason.SCOPE_DENIED, exc.code, prerequisites=prerequisites)
    prerequisites["scope"] = {"ok": True, "url": destination.url}
    prerequisites["method"] = {"ok": True, "detail": revision.method}
    if revision.method.upper() not in ALLOWED_METHODS:
        prerequisites["method"] = {"ok": False, "detail": "read-only runner"}
        return _inconclusive(
            InconclusiveReason.SCOPE_DENIED,
            "approved recipes are limited to read-oriented operations",
            prerequisites=prerequisites,
        )

    # Build identity: a detected mismatch makes every affected result inconclusive.
    meta_url = urljoin(build.target_url.rstrip("/") + "/", "api/meta")
    expected_identity = build.expected_identity or ""
    identity_exchange = send(
        policy=policy, method="GET", url=meta_url, headers={"Accept": "application/json"}
    )
    observed_identity = ""
    if identity_exchange.status == 200:
        payload = identity_exchange.json()
        if isinstance(payload, dict):
            observed_identity = str(payload.get("build") or payload.get("build_identity") or "")
        if not observed_identity:
            observed_identity = str(identity_exchange.response_headers.get("x-build-identity", ""))
    prerequisites["build_identity"] = {
        "ok": bool(expected_identity)
        and bool(observed_identity)
        and observed_identity == expected_identity,
        "expected": expected_identity,
        "observed": observed_identity,
        "attested": build.identity_attested_by is not None and not build.identity_observed,
    }
    if not expected_identity:
        return _inconclusive(
            InconclusiveReason.BUILD_IDENTITY_UNVERIFIED,
            "no expected build identity is recorded; attest the deployed build first",
            prerequisites=prerequisites,
            build_identity_observed=observed_identity,
        )
    if not observed_identity:
        return _inconclusive(
            InconclusiveReason.BUILD_IDENTITY_UNVERIFIED,
            "the deployment did not expose a build identity",
            prerequisites=prerequisites,
            build_identity_observed=observed_identity,
        )
    if observed_identity != expected_identity:
        return _inconclusive(
            InconclusiveReason.BUILD_IDENTITY_MISMATCH,
            f"expected {expected_identity}, observed {observed_identity}",
            prerequisites=prerequisites,
            build_identity_observed=observed_identity,
        )

    # Actor identity: expired or wrong credentials never verify a fix.
    actor_token = _account_token(actor)
    identity_url = urljoin(build.target_url.rstrip("/") + "/", "api/me")
    actor_exchange = send(
        policy=policy, method="GET", url=identity_url, headers=_auth_headers(actor_token)
    )
    if actor_exchange.status is None:
        prerequisites["actor_identity"] = {"ok": False, "detail": actor_exchange.error}
        return _inconclusive(
            InconclusiveReason.TRANSPORT_ERROR,
            str(actor_exchange.error or ""),
            prerequisites=prerequisites,
            evidence=[
                _exchange_evidence(
                    exchange=actor_exchange,
                    actor_label=actor.name,
                    notes="identity probe",
                    source_note="replay runner",
                )
            ],
            build_identity_observed=observed_identity,
        )
    if actor_exchange.status == 401:
        prerequisites["actor_identity"] = {"ok": False, "detail": "401 from identity probe"}
        return _inconclusive(
            InconclusiveReason.EXPIRED_CREDENTIALS,
            f"{actor.name} was rejected by the identity probe",
            prerequisites=prerequisites,
            evidence=[
                _exchange_evidence(
                    exchange=actor_exchange,
                    actor_label=actor.name,
                    notes="identity probe",
                    source_note="replay runner",
                )
            ],
            build_identity_observed=observed_identity,
        )
    actor_identity = _account_identity(actor_exchange)
    if (
        actor_exchange.status != 200
        or actor_identity is None
        or not _identity_matches(actor, actor_identity)
    ):
        prerequisites["actor_identity"] = {
            "ok": False,
            "detail": f"status {actor_exchange.status}",
        }
        return _inconclusive(
            InconclusiveReason.IDENTITY_MISMATCH,
            f"the acting credential did not resolve to {actor.name}",
            prerequisites=prerequisites,
            evidence=[
                _exchange_evidence(
                    exchange=actor_exchange,
                    actor_label=actor.name,
                    notes="identity probe",
                    source_note="replay runner",
                )
            ],
            build_identity_observed=observed_identity,
        )
    actor_tenant = actor.tenant_label or str(
        actor_identity.get("tenant_id") or actor_identity.get("tenant") or ""
    )
    prerequisites["actor_identity"] = {"ok": True, "account": actor.name, "tenant": actor_tenant}

    owner_token = _account_token(owner)

    # Fixture presence: checked as the legitimate owner before any assertion.
    for ref in fixture_refs:
        check_path = ref.get("check_path")
        if not check_path:
            continue
        try:
            fixture_url = policy.check(policy.resolve(build.target_url, str(check_path)).url).url
        except PolicyError as exc:
            return _inconclusive(
                InconclusiveReason.SCOPE_DENIED,
                exc.code,
                prerequisites=prerequisites,
                build_identity_observed=observed_identity,
            )
        exchange = send(
            policy=policy, method="GET", url=fixture_url, headers=_auth_headers(owner_token)
        )
        expect = ref.get("expect") or {}
        expected_status = int(expect.get("status", 200))
        ok = exchange.status == expected_status
        detail = f"status {exchange.status}"
        payload = exchange.json()
        field_name = expect.get("json_field")
        if ok and field_name and isinstance(payload, dict):
            actual = payload.get(str(field_name))
            wanted = expect.get("equals")
            if wanted == "owner_tenant":
                wanted = owner.tenant_label
            if wanted is not None:
                ok = str(actual) == str(wanted)
                detail = f"{field_name}={actual!r}"
        if not ok:
            prerequisites["fixture_present"] = {
                "ok": False,
                "fixture": ref.get("name"),
                "detail": detail,
            }
            return _inconclusive(
                InconclusiveReason.MISSING_FIXTURE,
                f"fixture {ref.get('name')} was not available to the legitimate owner",
                prerequisites=prerequisites,
                evidence=[
                    _exchange_evidence(
                        exchange=exchange,
                        actor_label=owner.name,
                        notes="fixture check",
                        source_note="replay runner",
                    )
                ],
                build_identity_observed=observed_identity,
            )
        prerequisites[f"fixture:{ref.get('name')}"] = {"ok": True, "detail": detail}

    # Positive control: the legitimate actor must still be able to read the object.
    authorized = send(
        policy=policy,
        method=revision.method,
        url=destination.url,
        headers=_auth_headers(owner_token),
    )
    expected_authorized = revision.expected_authorized or {}
    control_ok = authorized.status == int(expected_authorized.get("status", 200))
    control_detail = f"status {authorized.status}"
    if control_ok and expected_authorized.get("contains_marker"):
        marker = _fixture_value(fixture_refs, str(expected_authorized["contains_marker"]))
        if marker and marker not in authorized.body:
            control_ok = False
            control_detail = "owner response did not contain the expected marker"
    if control_ok and expected_authorized.get("json_field"):
        payload = authorized.json()
        field_name = str(expected_authorized["json_field"])
        wanted = expected_authorized.get("equals_identity_tenant")
        actual = payload.get(field_name) if isinstance(payload, dict) else None
        if wanted is True:
            control_ok = str(actual) == owner.tenant_label
        elif wanted is not None:
            control_ok = str(actual) == str(wanted)
        control_detail = f"{field_name}={actual!r}"
    positive_control = {
        "ok": control_ok,
        "detail": control_detail,
        "actor": owner.name,
        "url": destination.url,
    }
    control_evidence = _exchange_evidence(
        exchange=authorized,
        actor_label=owner.name,
        notes="positive control: legitimate owner request",
        source_note="replay runner",
    )
    if not control_ok:
        return _inconclusive(
            InconclusiveReason.POSITIVE_CONTROL_FAILED,
            "the legitimate owner could not access the object",
            prerequisites=prerequisites,
            positive_control=positive_control,
            evidence=[control_evidence],
            build_identity_observed=observed_identity,
        )

    # The unauthorized request is the only evidence that can prove reproduction.
    unauthorized = send(
        policy=policy,
        method=revision.method,
        url=destination.url,
        headers=_auth_headers(actor_token),
    )
    if unauthorized.status is None:
        return _inconclusive(
            InconclusiveReason.TRANSPORT_ERROR,
            str(unauthorized.error or ""),
            prerequisites=prerequisites,
            positive_control=positive_control,
            evidence=[control_evidence],
            build_identity_observed=observed_identity,
        )
    if unauthorized.redirect_blocked:
        return _inconclusive(
            InconclusiveReason.REDIRECT_BLOCKED,
            "the unauthorized request redirected outside the approved scope",
            prerequisites=prerequisites,
            positive_control=positive_control,
            evidence=[control_evidence],
            build_identity_observed=observed_identity,
        )
    if unauthorized.status == 401:
        return _inconclusive(
            InconclusiveReason.EXPIRED_CREDENTIALS,
            "the acting account was rejected mid-attempt",
            prerequisites=prerequisites,
            positive_control=positive_control,
            evidence=[control_evidence],
            build_identity_observed=observed_identity,
        )
    if unauthorized.status >= 500:
        return _inconclusive(
            InconclusiveReason.TRANSPORT_ERROR,
            f"target returned {unauthorized.status}",
            prerequisites=prerequisites,
            positive_control=positive_control,
            evidence=[control_evidence],
            build_identity_observed=observed_identity,
        )

    body = unauthorized.json()
    denied, denial_detail = _denied(assertion, status=unauthorized.status, body=body)
    unauthorized_evidence = _exchange_evidence(
        exchange=unauthorized,
        actor_label=actor.name,
        notes="unauthorized request from a differently-scoped identity",
        source_note="replay runner",
    )
    kind = str(assertion.get("kind") or "")

    if kind == "cross_tenant_json_object":
        owner_field_value, node = _json_owner_field(body, assertion)
        assertion_result = {
            "kind": kind,
            "owner_field": assertion.get("owner_field", "tenant_id"),
            "observed_owner": owner_field_value,
            "actor_tenant": actor_tenant,
            "status": unauthorized.status,
        }
        if denied:
            assertion_result["denial"] = denial_detail
            return AttemptResult(
                outcome=VerificationOutcome.FIX_VERIFIED,
                reason_code=None,
                reason_text=(
                    f"The original cross-tenant read is prevented ({denial_detail}) and the "
                    "legitimate owner still receives the object."
                ),
                prerequisites=prerequisites,
                positive_control=positive_control,
                assertion_result=assertion_result,
                evidence=[
                    control_evidence,
                    {**unauthorized_evidence, "highlight": [denial_detail]},
                ],
                build_identity_observed=observed_identity,
            )
        if (
            unauthorized.status == 200
            and owner_field_value is not None
            and owner_field_value != actor_tenant
        ):
            highlight = _highlight(assertion, node)
            return AttemptResult(
                outcome=VerificationOutcome.STILL_REPRODUCIBLE,
                reason_code=None,
                reason_text=(
                    f"The API returned an object owned by {owner_field_value!r} to "
                    f"{actor.name} ({actor_tenant!r})."
                ),
                prerequisites=prerequisites,
                positive_control=positive_control,
                assertion_result=assertion_result,
                evidence=[
                    control_evidence,
                    {**unauthorized_evidence, "highlight": highlight},
                ],
                build_identity_observed=observed_identity,
            )
        return _inconclusive(
            InconclusiveReason.UNRECOGNIZED_RESPONSE,
            "the response did not expose an owning-tenant field",
            prerequisites=prerequisites,
            positive_control=positive_control,
            assertion_result=assertion_result,
            evidence=[control_evidence, unauthorized_evidence],
            build_identity_observed=observed_identity,
        )

    if kind == "cross_tenant_document":
        marker_name = str(assertion.get("owner_marker_fixture") or "invoice_id")
        marker = _fixture_value(fixture_refs, marker_name) or ""
        content_type_expected = str(assertion.get("content_type") or "application/pdf")
        actual_content_type = unauthorized.response_headers.get("content-type", "")
        body_has_marker = bool(marker) and marker in unauthorized.body
        body_has_tenant = bool(owner.tenant_label) and owner.tenant_label in unauthorized.body
        assertion_result = {
            "kind": kind,
            "status": unauthorized.status,
            "content_type": actual_content_type,
            "marker_present": body_has_marker,
            "owner_tenant_present": body_has_tenant,
        }
        if denied:
            assertion_result["denial"] = denial_detail
            return AttemptResult(
                outcome=VerificationOutcome.FIX_VERIFIED,
                reason_code=None,
                reason_text=(
                    f"The cross-tenant export is prevented ({denial_detail}) and the "
                    "legitimate owner still receives the document."
                ),
                prerequisites=prerequisites,
                positive_control=positive_control,
                assertion_result=assertion_result,
                evidence=[
                    control_evidence,
                    {**unauthorized_evidence, "highlight": [denial_detail]},
                ],
                build_identity_observed=observed_identity,
            )
        if (
            unauthorized.status == 200
            and content_type_expected.lower() in actual_content_type.lower()
            and body_has_marker
            and body_has_tenant
        ):
            return AttemptResult(
                outcome=VerificationOutcome.STILL_REPRODUCIBLE,
                reason_code=None,
                reason_text=(
                    f"The export returned {owner.tenant_label!r} document content to "
                    f"{actor.name} ({actor_tenant!r})."
                ),
                prerequisites=prerequisites,
                positive_control=positive_control,
                assertion_result=assertion_result,
                evidence=[
                    control_evidence,
                    {
                        **unauthorized_evidence,
                        "highlight": [
                            f"document contains {marker}",
                            f"tenant {owner.tenant_label}",
                        ],
                    },
                ],
                build_identity_observed=observed_identity,
            )
        return _inconclusive(
            InconclusiveReason.UNRECOGNIZED_RESPONSE,
            "the export response did not match the expected document shape",
            prerequisites=prerequisites,
            positive_control=positive_control,
            assertion_result=assertion_result,
            evidence=[control_evidence, unauthorized_evidence],
            build_identity_observed=observed_identity,
        )

    return _inconclusive(
        InconclusiveReason.UNRECOGNIZED_RESPONSE,
        f"unsupported assertion kind {kind!r}",
        prerequisites=prerequisites,
        positive_control=positive_control,
        evidence=[control_evidence, unauthorized_evidence],
        build_identity_observed=observed_identity,
    )


def utc_stamp() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


__all__ = [
    "AttemptResult",
    "HttpExchange",
    "ResolvedRecipe",
    "check_resolution",
    "evaluate_recipe",
    "resolve_path",
    "resolve_recipe_accounts",
    "send",
    "utc_stamp",
]

# ``RetestAttempt`` and ``parse_destination`` are imported for type/utility completeness.
_ = (RetestAttempt, parse_destination)

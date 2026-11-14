"""Versioned testing profiles.

A profile is a reviewable code registry, not a database dump: version bumps are code
review, and runs store the exact ``code+version`` they used. Selection states testing
intention; coverage records state what actually happened.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

ACCESS_CONTROL_CODE = "web-api-access-control"
ACCESS_CONTROL_VERSION = 1

DEPTHS: dict[str, dict[str, Any]] = {
    "quick": {
        "label": "Quick",
        "description": "Focused replay and a bounded surface pass. Minutes, not hours.",
        "max_checks": 12,
        "time_budget_seconds": 600,
        "strix_budget_usd": 1.0,
        "strix_max_turns": 20,
        "discovery_share": 0.5,
    },
    "standard": {
        "label": "Standard",
        "description": "Full profile coverage across the recorded surface with bounded discovery.",
        "max_checks": 40,
        "time_budget_seconds": 1800,
        "strix_budget_usd": 3.0,
        "strix_max_turns": 60,
        "discovery_share": 0.6,
    },
}


@dataclass(frozen=True)
class Scenario:
    code: str
    title: str
    description: str
    owasp_refs: tuple[str, ...]
    required_identities: int
    required_fixtures: tuple[str, ...]
    automatic_eligible: bool
    method_note: str
    approach: str
    surfaces: tuple[str, ...] = field(default=())


@dataclass(frozen=True)
class ProfileDefinition:
    code: str
    version: int
    name: str
    description: str
    reference_links: tuple[str, ...]
    scenarios: tuple[Scenario, ...]

    def scenario(self, code: str) -> Scenario | None:
        return next((s for s in self.scenarios if s.code == code), None)

    @property
    def required_identities(self) -> int:
        return max((s.required_identities for s in self.scenarios), default=0)


WEB_API_ACCESS_CONTROL_V1 = ProfileDefinition(
    code=ACCESS_CONTROL_CODE,
    version=ACCESS_CONTROL_VERSION,
    name="Web & API Access Control",
    description=(
        "Focused authorization assessment for private staging APIs. Covers cross-account "
        "and cross-tenant object access, role-restricted functions, authentication "
        "prerequisites, and typed replay verification of previously reported issues."
    ),
    reference_links=(
        "https://owasp.org/API-Security/editions/2023/en/0x11-t10/",
        "https://owasp.org/www-project-web-security-testing-guide/v42/4-Web_Application_Security_Testing/"
        "05-Authorization_Testing/",
        "https://cheatsheetseries.owasp.org/cheatsheets/Authorization_Regression_Testing_Cheat_Sheet.html",
    ),
    scenarios=(
        Scenario(
            code="bola-object-read",
            title="Cross-tenant object read",
            description=(
                "A tenant B identity requests an object owned by tenant A and the API "
                "returns the object instead of denying access."
            ),
            owasp_refs=(
                "OWASP API1:2023 Broken Object Level Authorization",
                "OWASP WSTG v4.2 ATHZ-01/ATHZ-02",
            ),
            required_identities=2,
            required_fixtures=("invoice-object-a",),
            automatic_eligible=True,
            method_note=(
                "Bounded read-only replay: one unauthorized GET plus a legitimate-owner "
                "positive control."
            ),
            approach=(
                "Compare the response body's owning tenant with the acting identity, and "
                "confirm the owner still receives the object."
            ),
            surfaces=("/api/invoices/{invoice_id}",),
        ),
        Scenario(
            code="role-restricted-function",
            title="Role-restricted function access",
            description=(
                "An identity without the required role invokes an administrative or "
                "role-restricted operation."
            ),
            owasp_refs=(
                "OWASP API5:2023 Broken Function Level Authorization",
                "OWASP WSTG v4.2 ATHZ-01",
            ),
            required_identities=2,
            required_fixtures=("invoice-object-a",),
            automatic_eligible=True,
            method_note="Bounded replay of one denied function call with a control call.",
            approach="Verify the denial is authorization-specific, not an expired session.",
            surfaces=("/api/admin/settings",),
        ),
        Scenario(
            code="authentication-prerequisite",
            title="Authentication prerequisite",
            description=(
                "Requests without a valid session must be rejected, and expired test "
                "credentials must not be mistaken for a fixed authorization check."
            ),
            owasp_refs=("OWASP WSTG v4.2 ATHN-01/ATHN-04", "OWASP API2:2023 Broken Authentication"),
            required_identities=1,
            required_fixtures=(),
            automatic_eligible=False,
            method_note="Requires a deliberately unauthenticated run selected by an operator.",
            approach="Compare anonymous responses against authenticated expectations.",
            surfaces=("/api/invoices",),
        ),
        Scenario(
            code="cross-tenant-export",
            title="Cross-tenant data export",
            description=(
                "An export endpoint returns another tenant's document bytes to a caller "
                "who does not own the record."
            ),
            owasp_refs=(
                "OWASP API1:2023 Broken Object Level Authorization",
                "OWASP WSTG v4.2 ATHZ-02",
            ),
            required_identities=2,
            required_fixtures=("invoice-object-a",),
            automatic_eligible=True,
            method_note="Bounded read-only replay with a document-shape assertion.",
            approach=(
                "Assert the export body names the other tenant's record and the owner "
                "still receives it."
            ),
            surfaces=("/api/exports/{invoice_id}/pdf",),
        ),
        Scenario(
            code="two-actor-approval",
            title="Two-actor approval transition",
            description=(
                "A state-changing approval requires one actor to submit and a different "
                "authorized actor to approve. Automating this needs browser state and two "
                "live sessions, so it is a guided retest."
            ),
            owasp_refs=(
                "OWASP API5:2023 Broken Function Level Authorization",
                "OWASP WSTG v4.2 BUSL-01",
            ),
            required_identities=2,
            required_fixtures=("invoice-object-a", "approval-request"),
            automatic_eligible=False,
            method_note=(
                "Not automatable in this release: irreversible state transition across two "
                "authenticated sessions."
            ),
            approach="Record both actor steps, the denial on the wrong tenant, and the owner control.",
            surfaces=("/api/approvals/{invoice_id}",),
        ),
        Scenario(
            code="evidence-review",
            title="Evidence completeness review",
            description=(
                "An observation exists but the reproduction procedure or captured excerpt "
                "is incomplete, so the finding cannot yet be treated as supported."
            ),
            owasp_refs=("OWASP WSTG v4.2 reporting guidance",),
            required_identities=0,
            required_fixtures=(),
            automatic_eligible=False,
            method_note="Requires a reviewer to complete or reject the evidence.",
            approach="Review the observation, document the gap, and record a decision.",
            surfaces=(),
        ),
    ),
)

REGISTRY: dict[tuple[str, int], ProfileDefinition] = {
    (WEB_API_ACCESS_CONTROL_V1.code, WEB_API_ACCESS_CONTROL_V1.version): WEB_API_ACCESS_CONTROL_V1
}


def get_profile(code: str, version: int) -> ProfileDefinition:
    try:
        return REGISTRY[(code, version)]
    except KeyError as exc:
        raise KeyError(f"unknown profile {code} v{version}") from exc


def latest_profile(code: str = ACCESS_CONTROL_CODE) -> ProfileDefinition:
    versions = [v for (c, v) in REGISTRY if c == code]
    if not versions:
        raise KeyError(f"unknown profile {code}")
    return REGISTRY[(code, max(versions))]


def list_profiles() -> list[ProfileDefinition]:
    return sorted(REGISTRY.values(), key=lambda p: (p.code, p.version))


def depth_config(depth: str) -> dict[str, Any]:
    if depth not in DEPTHS:
        raise KeyError(f"unknown depth {depth}")
    return DEPTHS[depth]


def profile_as_json(profile: ProfileDefinition) -> dict[str, Any]:
    return {
        "code": profile.code,
        "version": profile.version,
        "name": profile.name,
        "description": profile.description,
        "reference_links": list(profile.reference_links),
        "scenarios": [
            {
                "code": s.code,
                "title": s.title,
                "description": s.description,
                "owasp_refs": list(s.owasp_refs),
                "required_identities": s.required_identities,
                "required_fixtures": list(s.required_fixtures),
                "automatic_eligible": s.automatic_eligible,
                "method_note": s.method_note,
                "approach": s.approach,
                "surfaces": list(s.surfaces),
            }
            for s in profile.scenarios
        ],
    }


def plan_coverage(
    profile: ProfileDefinition,
    *,
    surfaces: list[dict[str, Any]],
    depth: str,
) -> list[dict[str, Any]]:
    """Build the planned-check denominator.

    Only scenarios with a concrete surface the run intended to test are counted; the
    returned rows are what coverage later reports against.
    """
    config = depth_config(depth)
    explicit_routes = [s for s in surfaces if s.get("route")]
    planned: list[dict[str, Any]] = []
    limit = config["max_checks"]
    for scenario in profile.scenarios:
        if scenario.code == "evidence-review" or not scenario.surfaces:
            continue
        candidates = [
            surface
            for surface in explicit_routes
            if any(
                _surface_matches(surface.get("route", ""), pattern) for pattern in scenario.surfaces
            )
        ]
        if not candidates:
            continue
        for surface in candidates:
            if len(planned) >= limit:
                return planned
            planned.append(
                {
                    "check_key": f"{scenario.code}:{surface['route']}",
                    "scenario_code": scenario.code,
                    "scenario_title": scenario.title,
                    "surface": surface["route"],
                    "method": (surface.get("methods") or ["GET"])[0],
                    "owasp_refs": list(scenario.owasp_refs),
                    "approach": scenario.approach,
                    "source": surface.get("source", "recon"),
                }
            )
    return planned


def _surface_matches(route: str, pattern: str) -> bool:
    route_segments = route.strip("/").split("/")
    pattern_segments = pattern.strip("/").split("/")
    if len(route_segments) != len(pattern_segments):
        return False
    for actual, expected in zip(route_segments, pattern_segments, strict=True):
        if expected.startswith("{") and expected.endswith("}"):
            continue
        if actual != expected:
            return False
    return True


surface_matches = _surface_matches

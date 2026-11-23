"""Domain constants shared by models, services, and routers.

Kept free of framework imports so every layer can import it safely.
"""

from __future__ import annotations

from enum import StrEnum


class Role(StrEnum):
    """Project-scoped capability set."""

    OPERATOR = "operator"
    DEVELOPER = "developer"
    VIEWER = "viewer"


class RunKind(StrEnum):
    BASELINE = "baseline"
    RELEASE_SCAN = "release_scan"


class RunMode(StrEnum):
    DEMO = "demo"
    LIVE = "live"


class Depth(StrEnum):
    QUICK = "quick"
    STANDARD = "standard"


class RunStatus(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    CANCEL_REQUESTED = "cancel_requested"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELED = "canceled"
    INTERRUPTED = "interrupted"


TERMINAL_RUN_STATES = frozenset(
    {RunStatus.COMPLETED, RunStatus.FAILED, RunStatus.CANCELED, RunStatus.INTERRUPTED}
)


class JobState(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    CANCEL_REQUESTED = "cancel_requested"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELED = "canceled"
    INTERRUPTED = "interrupted"


class StageCode(StrEnum):
    PREFLIGHT = "preflight"
    VERIFY_KNOWN = "verify_known"
    DISCOVERY = "discovery"
    INGEST = "ingest"
    FINALIZE = "finalize"


class StageState(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    DONE = "done"
    FAILED = "failed"
    SKIPPED = "skipped"
    CANCELED = "canceled"


class Severity(StrEnum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"


SEVERITY_ORDER = {
    Severity.CRITICAL: 0,
    Severity.HIGH: 1,
    Severity.MEDIUM: 2,
    Severity.LOW: 3,
    Severity.INFO: 4,
}


class EvidenceStatus(StrEnum):
    """Independently tracked strength of the proof for a finding."""

    SUPPORTED = "supported"
    NEEDS_VALIDATION = "needs_validation"


class RetestMethod(StrEnum):
    AUTOMATIC = "automatic"
    GUIDED = "guided"
    PENDING_EVIDENCE_REVIEW = "pending_evidence_review"


class VerificationOutcome(StrEnum):
    """Outcome of one attempt/build; ``awaiting_retest`` is a workflow state."""

    FIX_VERIFIED = "fix_verified"
    STILL_REPRODUCIBLE = "still_reproducible"
    INCONCLUSIVE = "inconclusive"
    AWAITING_RETEST = "awaiting_retest"


CONCLUSIVE_OUTCOMES = frozenset(
    {VerificationOutcome.FIX_VERIFIED, VerificationOutcome.STILL_REPRODUCIBLE}
)


class ComparisonBucket(StrEnum):
    FIX_VERIFIED = "fix_verified"
    STILL_REPRODUCIBLE = "still_reproducible"
    NEWLY_OBSERVED = "newly_observed"
    REGRESSED = "regressed"
    AWAITING_VERIFICATION = "awaiting_verification"
    NEEDS_VALIDATION = "needs_validation"
    INCOMPARABLE = "incomparable"


class ObservationOutcome(StrEnum):
    """What an observation says about the finding on its build."""

    OBSERVED = "observed"
    NOT_OBSERVED = "not_observed"
    INCONCLUSIVE = "inconclusive"


OBSERVATION_CONCLUSIVE = frozenset({ObservationOutcome.OBSERVED, ObservationOutcome.NOT_OBSERVED})

OBSERVATION_TO_VERIFICATION = {
    ObservationOutcome.OBSERVED: VerificationOutcome.STILL_REPRODUCIBLE,
    ObservationOutcome.NOT_OBSERVED: VerificationOutcome.FIX_VERIFIED,
}


class EvidenceSource(StrEnum):
    ENGINE = "engine"
    REPLAY = "replay"
    REVIEWER = "reviewer"
    GUIDED = "guided"


class EvidenceAttribution(StrEnum):
    ENGINE_REPORT = "engine_report"
    OBSERVED_CAPTURE = "observed_capture"
    REVIEWER_SUBMISSION = "reviewer_submission"


class AttemptKind(StrEnum):
    AUTOMATIC = "automatic"
    GUIDED = "guided"


class AttemptState(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    CANCELED = "canceled"


class ReviewDecision(StrEnum):
    ACCEPTED = "accepted"
    CHANGES_REQUESTED = "changes_requested"


class RecipeState(StrEnum):
    DRAFT = "draft"
    APPROVED = "approved"
    RETIRED = "retired"


class Disposition(StrEnum):
    OPEN = "open"
    FALSE_POSITIVE = "false_positive"
    DUPLICATE = "duplicate"


class CoverageResult(StrEnum):
    """One row per planned or observed check."""

    PLANNED = "planned"
    TESTED_NO_FINDING = "tested_no_finding"
    FINDING_OBSERVED = "finding_observed"
    BLOCKED = "blocked"
    NOT_RUN = "not_run"
    NOT_APPLICABLE = "not_applicable"
    NEEDS_REVIEW = "needs_review"


class InconclusiveReason(StrEnum):
    AUTHORIZATION_REVOKED = "authorization_revoked"
    EXPIRED_CREDENTIALS = "expired_credentials"
    IDENTITY_MISMATCH = "identity_mismatch"
    MISSING_FIXTURE = "missing_fixture"
    POSITIVE_CONTROL_FAILED = "positive_control_failed"
    BUILD_IDENTITY_MISMATCH = "build_identity_mismatch"
    BUILD_IDENTITY_UNVERIFIED = "build_identity_unverified"
    SCOPE_DENIED = "scope_denied"
    TRANSPORT_ERROR = "transport_error"
    REDIRECT_BLOCKED = "redirect_blocked"
    UNRECOGNIZED_RESPONSE = "unrecognized_response"
    RECIPE_SUPERSEDED = "recipe_superseded"


INCONCLUSIVE_REASON_LABELS = {
    InconclusiveReason.AUTHORIZATION_REVOKED: (
        "Inconclusive — the requester or target is no longer authorized"
    ),
    InconclusiveReason.EXPIRED_CREDENTIALS: "Inconclusive — test account expired",
    InconclusiveReason.IDENTITY_MISMATCH: "Inconclusive — identity did not match the declared account",
    InconclusiveReason.MISSING_FIXTURE: "Inconclusive — required fixture missing",
    InconclusiveReason.POSITIVE_CONTROL_FAILED: (
        "Inconclusive — legitimate control request failed"
    ),
    InconclusiveReason.BUILD_IDENTITY_MISMATCH: (
        "Inconclusive — deployed build identity does not match the approved build"
    ),
    InconclusiveReason.BUILD_IDENTITY_UNVERIFIED: (
        "Inconclusive — deployed build identity could not be observed"
    ),
    InconclusiveReason.SCOPE_DENIED: "Inconclusive — destination is outside the approved scope",
    InconclusiveReason.TRANSPORT_ERROR: "Inconclusive — target could not be reached",
    InconclusiveReason.REDIRECT_BLOCKED: (
        "Inconclusive — target redirected outside the approved scope"
    ),
    InconclusiveReason.UNRECOGNIZED_RESPONSE: (
        "Inconclusive — response did not match the expected evidence shape"
    ),
    InconclusiveReason.RECIPE_SUPERSEDED: (
        "Inconclusive — an approved recipe revision changed after this attempt started"
    ),
}


class ComparisonLimit(StrEnum):
    SAME_MODE = "same_mode"
    SAME_PROJECT = "same_project"


class AuditAction(StrEnum):
    LOGIN_SUCCEEDED = "auth.login_succeeded"
    LOGIN_FAILED = "auth.login_failed"
    LOGOUT = "auth.logout"
    PASSWORD_CHANGED = "auth.password_changed"
    USER_CREATED = "admin.user_created"
    USER_UPDATED = "admin.user_updated"
    MEMBER_ADDED = "project.member_added"
    MEMBER_REMOVED = "project.member_removed"
    PROJECT_CREATED = "project.created"
    TARGET_CONFIG_CREATED = "project.target_config_created"
    BUILD_CREATED = "build.created"
    BUILD_IDENTITY_ATTESTED = "build.identity_attested"
    ACCOUNT_CREATED = "project.test_account_created"
    RUN_REQUESTED = "run.requested"
    RUN_STARTED = "run.started"
    RUN_CANCEL_REQUESTED = "run.cancel_requested"
    RUN_COMPLETED = "run.completed"
    RUN_FAILED = "run.failed"
    RUN_INTERRUPTED = "run.interrupted"
    READY_FOR_RETEST = "finding.ready_for_retest"
    RECIPE_APPROVED = "retest.recipe_approved"
    RETEST_REQUESTED = "retest.requested"
    RETEST_COMPLETED = "retest.completed"
    GUIDED_SUBMITTED = "retest.guided_submitted"
    REVIEW_ACCEPTED = "review.verdict_accepted"
    REVIEW_CHANGES_REQUESTED = "review.changes_requested"
    EVIDENCE_VALIDATED = "evidence.validated"
    EVIDENCE_UPLOADED = "evidence.uploaded"
    DISPOSITION_CHANGED = "finding.disposition_changed"
    EXPORT_CREATED = "export.created"
    OPENAPI_UPLOADED = "project.openapi_uploaded"
    ACCESS_DENIED = "security.access_denied"

# Architecture decisions

Short records of choices that shape the implementation. Each is reversible only with a
migration or a deliberate product change.

## ADR-001 — Greenfield stack: React/TypeScript + FastAPI + PostgreSQL + Compose

**Decision.** Use the spec's preferred greenfield stack: React 19 + TypeScript + Vite,
Python 3.12 + FastAPI + SQLAlchemy 2 + Alembic, PostgreSQL 16, Docker Compose for a single
Linux host. The worker is a separate process using a database-backed queue.

**Why.** The repository contained only agent infrastructure (no product code or stack), so
the default from the brief applies. A relational schema with explicit ownership edges is the
right fit for evidence, review decisions, and frozen snapshots. A separate worker keeps
runtime control off the web process.

**Consequences.** Three processes plus a database; development needs Docker for PostgreSQL.
Alembic's initial migration was reordered to handle the `jobs ↔ runs` cycle with deferred
foreign keys.

## ADR-002 — Verification is derived, never stored as a status flag

**Decision.** Store observations (finding + build + source + outcome + observed time) and
attempts; derive current verification, historical snapshots, and comparison buckets from
them. An attempt only becomes an observation when it is conclusive and accepted.

**Why.** The brief's hardest requirements are chronological: a newer accepted reproduction
supersedes an earlier fix on the same build, a late older-build result cannot change a newer
build, and a historical report must stay stable. A mutable `finding.status` cannot express
those without losing history. Deriving state also makes "absent is not fixed" the default.

**Consequences.** Queries are more involved and indexed by `(finding, build)` and time.
Snapshot queries pass an `as_of` timestamp. Comparisons assign exactly one primary bucket
per current finding, with needs-validation and incomparable cases separated.

## ADR-002a — Evidence decisions are append-only

**Decision.** Store each evidence assessment in `evidence_decisions`; derive the status as of a
run snapshot from the entries at that time. The mutable `findings.evidence_status` remains the
current value for the detail screen. The table is append-only after the one-time backfill;
subsequent corrective migrations only relabel the synthetic migration entries.

**Why.** A review after a run must not rewrite a historical comparison. Exports freeze the same
snapshot. The pre-migration backfill is explicitly marked as migration-time data, not a
historical decision.

**Consequences.** Pre-migration findings have no review timeline; comparisons before the
migration fall back to current state and are labelled only by that limitation.

## ADR-003 — One reproducible demo scenario with real HTTP replays

**Decision.** Build a synthetic Atlas Billing lab with three build deployments. Demo scans
use deterministic, clearly labelled Strix-shaped artifact fixtures; automatic retests send
real HTTP requests to the lab through the constrained runner.

**Why.** The brief requires a usable demo without paid model access while insisting that
buttons must imply genuine execution. Fixtures alone would make "Fix verified" a mock.
Real replays through the same code as live retests keep the trust path honest, while
fixtures give deterministic coverage/finding shapes.

**Consequences.** Demo requires the lab process. Demo records are excluded from live
comparisons. The lab contains deliberate vulnerabilities and must stay loopback-only.

## ADR-004 — Frozen exports: payload + rendered bytes stored together

**Decision.** An export row stores the canonical snapshot JSON, the generated artifact, its
hash and size. Downloads return the stored bytes, not a re-render.

**Why.** PDF generation can embed timestamps, and later retests or reviews must not rewrite
an already delivered snapshot. The brief requires historical stability and consistent
values across PDF/CSV/JSON.

**Consequences.** Storage grows with each export; retention is an operational setting.
A new export must be generated to include later evidence.

## ADR-005 — Hand-built accessible primitives; system font stacks

**Decision.** Implement buttons, tabs (roving tabindex), native `<dialog>` modals, toasts,
and badges directly, with a single design-token stylesheet. Use system sans/monospace font
fallbacks; no CDN and no large component library.

**Why.** The brief asks for a restrained, professional light workspace with local fonts and
accessible controls. The component surface is small, and native `<dialog>` gives focus
containment and Escape handling without a dependency. Hand-rolling keeps the dependency
tree minimal and auditable.

**Consequences.** We own keyboard behaviour and must test it. Playwright covers arrow-key
tabs, axe-core scans, 390 px layouts, and evidence scroll containers.

## ADR-006 — Database queue with a lease; no silent redispatch

**Decision.** Jobs are claimed with `FOR UPDATE SKIP LOCKED` and a lease renewed by a
heartbeat thread. An expired lease is marked `interrupted`, never re-queued automatically.
The requester, project access, and current target policy are re-checked before dispatch.

**Why.** The brief requires duplicate-submission idempotency, cancellation, interruption
handling, and revocation to prevent queued work from running. Automatic retry would risk
two engines scanning the same target.

**Consequences.** Idempotency is enforced only while a job is queued/running: resubmitting an
identical configuration after a terminal run creates a new run, which is the intended retry path.
A restarted worker does not resume old jobs; an operator must explicitly request a new run.
Interrupted runs keep partial artifacts with an incomplete label.

## ADR-007 — Loopback is a policy-controlled exception

**Decision.** Reject metadata/link-local/reserved destinations always. Allow loopback only
when `ALLOW_LOOPBACK_LAB_TARGETS=true` (development/demo), and still require the destination
to match the project's exact origin allowlist and path restrictions.

**Why.** The demo lab is loopback, while the security standard says private/reserved
targets must fail closed. An explicit deployment switch is safer than a special case in the
runner, and production defaults to false.

**Consequences.** Enabling the lab in a shared environment requires an explicit config
change. DNS is resolved and checked before a request, but connections are not pinned; the
deployment guide requires an enforcing gateway for rebinding-sensitive targets.

## ADR-008 — Conservative project-level fingerprinting with duplicate review

**Decision.** Match findings across runs by a SHA-256 fingerprint of normalized issue class,
scope, actor boundary, and impact condition. Keep engine IDs as run-level provenance. Surface
same-surface/different-fingerprint findings as duplicate candidates for a reviewer.

**Why.** Over-merging silently rewrites evidence; under-merging creates duplicates. A
conservative fingerprint plus explicit review is the honest middle, as the brief requests.

**Consequences.** A changed scope template or actor description can create a new finding
that a reviewer later marks duplicate. The original observation is preserved.

## ADR-009 — ReportLab for PDF; CSV formula-injection neutralization

**Decision.** Generate PDFs with ReportLab Platypus (Helvetica/Courier), with a summary-first
structure and a technical section. CSV cells beginning with `= + - @`, tab, or carriage
return are apostrophe-prefixed.

**Why.** ReportLab is maintained, pure-Python, produces real paginated PDFs, and avoids
system-native dependencies. CSV exports are attacker-influenced and spreadsheets execute
formulas (CWE-1236).

**Consequences.** PDF styling is code; adding fonts or a design change means editing
`services/exports.py`. PDF text is verified in tests with pypdf.

## ADR-010 — Cookie session + header CSRF; Argon2id; encrypted test credentials

**Decision.** Issue a random session token in an HttpOnly, SameSite=Lax cookie (Secure
outside development). Store only its SHA-256 hash server-side, alongside a per-session CSRF
token that mutations must send as `X-CSRF-Token`. Hash passwords with Argon2id. Encrypt test
credentials with Fernet using a key derived from the deployment secret.

**Why.** The brief requires protected session cookies, CSRF protection, login rate limits,
and library-provided password hashing. Header-based CSRF with JSON-only endpoints avoids
form-based cross-site requests without extra state.

**Consequences.** Rotating the deployment key invalidates sessions and stored credential
ciphertexts. Login attempts are retained for rate limiting and audit hashes, not raw IPs.

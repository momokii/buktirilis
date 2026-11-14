# Decisions Log

Record approved significant decisions and new patterns with rationale and security
impact. General templates remain conditional until real project facts are known.

---
**Decision:** Root CLAUDE.md imports exactly four compact context files; deeper docs load on demand.
**Date:** 2026-11-14
**Context:** A blank project needs consistent startup context without manual re-briefing.
**Rationale:** Claude Code auto-loads the root entry point and expands plain-text imports; rules, coding/security standards, and current state are relevant every session.
**Alternatives Rejected:** A README-only entry point is not auto-loaded; importing every file wastes context; machine-local auto-memory does not share team knowledge.
**Security Implications:** Security Gate is always in context; instruction text remains guidance rather than enforced permissions.
**Impact:** Keep imported files concise and specialize them as the stack emerges; history/templates remain on demand.
---
**Decision:** Adopt the requested security-first shared permission baseline with additional explicit secret-file/key write denies and common force-push variants.
**Date:** 2026-11-14
**Context:** No stack exists, but secret exposure and destructive commands need immediate controls.
**Rationale:** Documented deny/ask/allow syntax supports explicit file rules and narrow command prefixes. Keep the user's permission mode unchanged; require approval for future stack command grants.
**Alternatives Rejected:** Blanket Bash allow; broad .env.* Read/Edit deny blocking .env.example; automatic sandbox enablement; settings.local.json edits; instructions presented as enforcement.
**Security Implications:** Deny beats ask/allow. Includes local/test env variants, key stores, sudo, world-writable chmod, and force-with-lease forms. Shell matching and indirect-file-reader gaps remain; recommend sandbox evaluation with confirmation.
**Impact:** All rule shapes checked against current official docs; interactive /permissions check remains for the user's Claude Code session. Batch protected-path writes; never bypass refusal.
---
**Decision:** Document the Compose v2 base + automatic development override + explicit production override pattern conditionally.
**Date:** 2026-11-14
**Context:** Environment discipline is needed before the stack or containerization is chosen.
**Rationale:** compose.yaml stays environment-agnostic; compose.override.yaml contains development-only settings; explicit compose.prod.yaml selection excludes automatic development overrides.
**Alternatives Rejected:** Obsolete docker-compose/version syntax; production depending on dev override removal; creating runtime infrastructure before stack confirmation.
**Security Implications:** Ask for any Compose command not clearly dev; prefix allows cannot prove target safety. Agents never execute production commands/credentials; approved production plans go to operators. Test release config locally with fake secrets.
**Impact:** No Compose files created. Replace examples with verified commands only if containerization is approved during TASK-001.
---

## Cross-tool portability
---
**Decision:** Keep .claude policy/state canonical and add AGENTS.md, portable skills, native OpenCode/Codex controls, and a Pi context/approval extension.
**Date:** 2026-11-14
**Context:** The user requested the same setup across Claude, OpenAI/Codex, OpenCode, Pi, and other clients, independent of model/provider.
**Rationale:** Native discovery mechanisms differ. AGENTS.md specifies mandatory reads; OpenCode loads explicit paths; Pi injects the five required files while preserving its system prompt; small skills reuse the existing procedures. Native controls complement shared instructions.
**Alternatives Rejected:** Assuming Claude @imports/permissions work in every host; duplicating policy per tool; changing models/global config; automatically installing dependencies; claiming raw API clients read repository files.
**Security Implications:** Original Claude settings preserved. OpenCode defaults shell/mutations to approval with secret-path denies. Codex uses workspace-write/on-request, shell network off, and prefix rules with documented coverage limits. Pi blocks direct secret paths and fails closed on missing context/approval UI; approved indirect shell reads and arbitrary extension code still need OS isolation.
**Impact:** Restart/review/trust resources in each host and check effective controls. Native diagnostics, configuration schemas, and Pi tests pass locally; interactive UI/model behavior remains unverified. No application stack selected.
---

## BuktiRilis application stack and trust model
---
**Decision:** Implement the brief's greenfield stack (React/TS, FastAPI, PostgreSQL, Compose)
with derived verification state, a database queue lease, a synthetic lab for demo retests,
and frozen server-generated exports. Details and alternatives: `docs/decisions.md` (ADR-001
to ADR-010).
**Date:** 2026-11-14
**Context:** The task specification supplied product requirements, stack preferences, and
explicit authorization for Git initialization; no product code existed.
**Rationale:** Derived state preserves historical evidence; real lab replays keep demo
buttons genuine; frozen snapshots keep exports stable; server-side scope checks and worker
re-validations make revocation effective.
**Alternatives Rejected:** Mutable finding status flags; fixture-only retests; re-rendering
exports on download; adding a large UI kit or CDN fonts; automatically retrying interrupted
jobs; implicit loopback access.
**Security Implications:** Cookies are HttpOnly/CSRF-protected; credentials encrypted and
never returned; evidence redacted; destination allowlists and loopback opt-in; console web
service has no Docker socket; live mode stays off until isolation is proven.
**Impact:** Enables the verified demo and an implementation of the live adapter. Live
execution and sandbox isolation remain unverified (TASK-003).
---

## New decision template
---
**Decision:** [What was decided]
**Date:** [YYYY-MM-DD]
**Context:** [Why it was needed]
**Rationale:** [Why this option]
**Alternatives Rejected:** [Other options and why not]
**Security Implications:** [Any security impact]
**Impact:** [What it affects downstream]
---

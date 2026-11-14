# BuktiRilis

**See what was tested. Verify what changed.**

BuktiRilis is a self-hosted security testing workspace for internal engineering teams. It
runs focused assessments against authorized staging web apps and REST APIs with
[Strix OSS](https://github.com/usestrix/strix) as the assessment engine, and owns the parts
an audit trail needs: project scope, builds, runs, evidence, retests, release comparison,
and frozen exports.

This repository contains the first usable internal release: a React/TypeScript browser
interface, a FastAPI API, a PostgreSQL-backed worker, and a synthetic staging lab.

> **Pilot status.** The demo path below is verified end to end in a real browser, including
> real HTTP retests against the bundled lab. The live Strix adapter is implemented and
> contract-tested but **live execution was not observed** in this environment (no model
> credentials, no pinned Strix image). See [docs/strix-contract.md](docs/strix-contract.md)
> and [docs/progress.md](docs/progress.md).

## What it does

- **Approved scope, then builds.** An administrator records the staging origin, path
  restrictions, environment, owner, authorization reference, and run limits as an
  immutable configuration revision. Builds bind a label, destination, optional OpenAPI
  revision, and expected deployment identity.
- **Assessment runs.** Operators queue baseline or release-scan runs at Quick or Standard
  depth using the versioned *Web & API Access Control* profile. Preflight validates the
  target policy, build identity, identities, quotas, and comparison baseline before
  submission.
- **Evidence, not claims.** Findings carry expected vs observed behavior, ordered steps,
  attribution, and sanitized HTTP evidence. Verification is derived from accepted
  observations scoped to a build — never from a mutable status flag.
- **Two retest paths.** Approved read-only replay recipes execute through a constrained
  runner with an owner positive control. Cases that need browser steps, two actors, or a
  state change use a guided package and reviewer acceptance.
- **Release comparison.** Baseline and current runs compare through their recorded
  completion snapshots: fix verified, still reproducible, newly observed, regressed,
  awaiting verification, needs validation, incomparable. Later evidence appears in a
  separately labelled **latest verification** panel.
- **Frozen exports.** PDF (paginated, summary + technical), separate CSV findings/coverage
  files, and versioned JSON. Every export freezes its payload and bytes in the database and
  artifact volume.
- **Safe self-hosted operation.** Server-side role checks, CSRF-protected cookie sessions,
  Argon2id passwords, encrypted test credentials, redaction on the way in, target allowlists,
  redirect re-validation, and a worker lease that never silently re-runs uncertain work.

## Architecture

```
Browser (React + Vite, 1440 and 390 verified)
        │  cookie session + CSRF header
        ▼
FastAPI API ── PostgreSQL (records, queue, snapshots, audit)
        │             ▲
        │ enqueue     │ claim with lease
        ▼             │
Worker ───────────────┘
  ├─ demo: deterministic Strix artifact fixtures + real constrained replays
  └─ live: pinned Strix CLI subprocess in a dedicated per-run directory
        │
        ├─ evidence/artifact volume (protected, bounded)
        └─ synthetic lab (demo) or authorized staging (live)
```

Key boundaries:

- The browser never receives credentials, provider keys, or raw unsanitized captures.
- The web process has no Docker daemon access; runtime control belongs to the worker.
- A spec-supplied host can never authorize a destination; target policy is server-side.
- A queued job is re-authorized (requester, project access, current target policy) before
  dispatch, so revoked access or narrowed scope prevents execution.
- Replay recipes are limited to `GET`/`HEAD` with typed assertions. Imported scripts and
  response bodies are treated as data and never executed.

## Quick start (fresh checkout)

Prerequisites: Python 3.12, Node.js 22, Docker (for the local PostgreSQL container), and
`make`.

```bash
git clone <this repo> buktirilis && cd buktirilis
cp .env.example .env
# Generate a deployment key and paste it into .env as BUKTIRILIS_SECRET_KEY:
python3 -c "import secrets; print(secrets.token_urlsafe(48))"
# For the demo, set APP_ENV=development, DEMO_SEED_ENABLED=true,
# ALLOW_LOOPBACK_LAB_TARGETS=true, and LAB_BASE_URL=http://127.0.0.1:8099.

make install         # uv sync (backend) + npm ci (web)
make db              # local PostgreSQL 16 container on 127.0.0.1:55432
make migrate         # Alembic migrations
make dev             # lab :8099, API :8000, worker, Vite :5173
```

In a second terminal, create the reproducible demo dataset (the lab must be running):

```bash
make demo           # migrate + seed; prints the credentials file path
```

Then open <http://127.0.0.1:5173>, sign in with the `operator` account from
`var/demo-credentials.txt` (generated locally, mode 600, gitignored), and open **Atlas
Billing → Runs → Open report**.

If port 8000 is already in use, run the API on another port and point Vite at it:

```bash
cd backend && .venv/bin/python -m uvicorn app.main:app --port 8100
cd web && VITE_API_TARGET=http://127.0.0.1:8100 npm run dev
```

The seed is idempotent: an existing demo project is reported and left untouched. To start
over, use a separate database or drop and recreate it (development only, your data).

### Demo scenario

One synthetic scenario runs across three builds of the *Atlas Billing* lab:

| Build | Baseline / release scan | What it demonstrates |
|---|---|---|
| `2024.10.1` | baseline | Cross-tenant invoice read (BOLA) reproduced; two-actor approval needs a guided retest; a weak rate-limit claim needs validation |
| `2024.10.2` | release scan | BOLA replay verifies the fix with an owner control; a new cross-tenant export route is discovered; guided/weak items stay pending |
| `2024.10.3` | release scan | BOLA reproduces again → **Regressed** vs `2024.10.2`; export remains reproducible; `2024.10.2` still records its verified fix |

Additional fixtures to try from the UI:

- **Identity mismatch:** build `2024.10.1-hotfix` points at the `2024.10.1` deployment but
  declares a different expected identity. A run or retest on it is inconclusive and never
  verifies a fix.
- **Expired auth:** rotate the `tenant-b-dev` credential to `lab.tenant-b-expired` in project
  settings, run a retest, observe `Inconclusive — test account expired`, then rotate back.
- **Failed positive control:** rotate the `tenant-a-owner` credential to
  `lab.tenant-c-observer` and retest; the owner control fails, so the attempt is inconclusive.
- **Weak evidence:** `BR-2` stays in **Needs validation** until an operator accepts the
  evidence; the retest path is chosen independently.

Demo records are labelled **Demo** in the UI, reports, exports, and comparison; demo and
live runs are never compared with each other. The lab is synthetic and development-only.

## Retest semantics in one screen

Independent state is kept for three questions:

1. **Evidence status** — `supported` or `needs_validation`. A weak observation is not
   rewritten by a later retest.
2. **Retest method** — `automatic` (approved read-only recipe), `guided` (human steps), or
   `pending_evidence_review`.
3. **Verification outcome** — per attempt: `fix_verified`, `still_reproducible`,
   `inconclusive`, plus the workflow state `awaiting_retest`.

Rules enforced in code and tests:

- An `inconclusive` attempt never verifies a fix; it records a reason and a next action.
- A conclusive retest requires identity, fixture, build-identity, and positive-control checks.
- `Fix verified` requires a denial/controlled behavior **and** a working legitimate control.
- HTTP status alone is insufficient: assertions read object ownership or document content.
- Only an accepted, conclusive observation changes a build's verified outcome.
- The newest accepted conclusive observation for the same build supersedes an earlier one;
  a late result on an older build cannot change a newer build.
- A finding absent from a scan is **Awaiting verification**, never inferred fixed.
- Regressions are derived by comparing a current reproduction with a baseline snapshot that
  recorded a verified fix under comparable conditions.

## Live Strix configuration

Live mode is deliberately off until the worker is provisioned. The adapter:

- pins the contract to **Strix v1.7.1** and requires an explicit `STRIX_MODEL`;
- invokes a structured argv array (`-n`, `--target`, `--scan-mode`, `--max-budget`,
  `--max-turns`, `--instruction-file`, optional sanitized spec), never a shell string;
- runs in a dedicated per-run directory with a restricted environment;
- normalises exit `0/1/2`, distinguishes `stopped` from `completed`, collects partial
  artifacts, terminates the **process group** on cancel/timeout, and records unconfirmed
  cleanup so the job cannot be redispatched blindly;
- reports likely budget exhaustion, auth failure, provider refusal, parse failure, and
  coverage gaps in user-readable form.

To enable live execution (see [docs/deployment.md](docs/deployment.md) for the isolation
topology):

```dotenv
APP_ENV=production
LIVE_EXECUTION_ENABLED=true
DEMO_SEED_ENABLED=false
ALLOW_LOOPBACK_LAB_TARGETS=false
STRIX_MODEL=<approved provider/model on the worker>
STRIX_BINARY=/opt/strix/bin/strix
```

Do not enable live mode on a host where deny-by-default egress, the child sandbox network,
and path-level enforcement are not proven. The web service must not hold the Docker socket.

## Development checks

```bash
make lint         # ruff check + format check (backend)
make typecheck    # mypy (backend)
make test         # pytest (backend, real HTTP against the lab)
cd web && npm run typecheck && npm run build
cd web && npx playwright test        # needs lab/api/worker + seeded demo
cd web && npx playwright install chromium
```

Verified in this environment (see [docs/progress.md](docs/progress.md) for exact output):

- Backend: **80 tests** covering policy/OpenAPI overrides, redaction, replay assertions,
  retest/review semantics, verdict derivation, comparison buckets, pipeline, cancellation,
  revoked access, worker lease reconciliation, exports, API/CSRF/isolation, and the Strix
  subprocess contract.
- Frontend: TypeScript build and **8 Playwright tests** at 1440 px and 390 px, including
  keyboard tab navigation, both retest paths, frozen export download, comparison, and an
  axe-core scan with no serious/critical violations.
- PDF export: 6 pages for the demo release-scan snapshot; CSV and JSON parse and agree.
- Fresh database: migrate + seed creates 4 users, 1 project, 3 runs, 4 findings, and
  5 frozen exports without a model provider.

## Repository map

| Path | Contents |
|---|---|
| `backend/app/services/` | Policy/OpenAPI, replay runner, recipes, retests, findings/comparison, ingest, releases, runs/queue, pipeline, exports, Strix adapter, demo seed |
| `backend/app/routers/` | Auth, admin, projects/builds, runs/reports, findings/retests, exports |
| `backend/migrations/` | Alembic schema (ordered, cycle-safe initial migration + follow-up) |
| `backend/tests/` | 80 tests, including a real local HTTP lab fixture |
| `lab/` | Synthetic Atlas Billing staging API with three deployments |
| `web/src/` | React app, accessible UI primitives, report/finding/compare screens |
| `web/e2e/` | Playwright browser and accessibility tests |
| `docs/` | Contract, deployment, decisions, progress, screenshots |
| `compose.yaml` | Single-host deployment (db, api, worker, web, demo lab profile) |

## Known limits

- **Live Strix execution was not observed.** The adapter, normalization, cancellation, and
  artifact contract are tested with a fake CLI; the real pinned binary needs a provisioned
  worker and an approved model.
- **Network isolation is documented, not demonstrated** on this host. The application
  enforces its own target policy and refuses loopback unless explicitly enabled, but the
  sandbox network contract must be proven on the deployment host before live use.
- DNS is resolved and checked before a replay, but connections are not pinned to that
  address; pair the runner with the enforcing egress gateway described in the deployment
  guide for DNS-rebinding-sensitive targets.
- SARIF is kept as an engine artifact; only PDF/CSV/JSON exports are first-class.
- Deep depth is intentionally not offered. Certification, public scanning, billing, and
  additional engines are out of scope for this pilot.

## Agent entry points

This repository also carries cross-tool agent policy and state. Claude Code enters through
`CLAUDE.md`; OpenAI Codex, OpenCode, and Pi enter through `AGENTS.md`. Read
[`.agents/README.md`](.agents/README.md) for discovery, native controls, and trust
requirements, and [`docs/progress.md`](docs/progress.md) for current status and next action.

# BuktiRilis — Implementation Progress

Product: self-hosted security testing workspace. Engine: Strix OSS (pinned adapter).
Browser UI: React/TypeScript. Backend/worker: Python/FastAPI. DB: PostgreSQL.

## Milestones

| # | Milestone | Status |
|---|---|---|
| M1 | Inspection, contract, and foundation (Git, stack, schema, auth, shell) | IN PROGRESS |
| M2 | Browser vertical slice: project/build/run/report/finding over persistent records | PLANNED |
| M3 | Evidence, automatic + guided retest, review | PLANNED |
| M4 | Exports (PDF/CSV/JSON) with frozen snapshots | PLANNED |
| M5 | Worker + live Strix adapter + local lab + isolation preflight | PLANNED |
| M6 | Release Scan, build comparison, final verification | PLANNED |

## Baseline inspection (2026-11-14)
- Assigned directory was not a Git repository; initialised `main` per spec §7.
- Existing content: agent infrastructure only (`.claude/`, `.agents/`, `AGENTS.md`, `.env.example`, `README.md`). No product code, so the greenfield stack from spec §6 applies.
- Host runtime: Python 3.12.3, Node 22.23.4, Docker 29.3.1 + Compose v5.1.1, `uv` 0.9.30, network reachable.
- Strix reference checked: CLI docs (`--target`, `--scan-mode quick|standard|deep`, `-n/--non-interactive`, `--fail-on`, `--max-budget`, `--max-turns`, exit codes 0/1/2), artifact contract (`run.json`, `vulnerabilities.json`, `vulnerabilities/*.md`, `coverage.json` with `source` provenance + `complete`, `findings.sarif`). Pinned contract target: `v1.7.1`.
- Live Strix execution not yet observed: no model credentials and no Strix image in this environment. Demo + fixture contract is the verified path; live mode is wired but unverified until provisioned.

## Verification log
See "Commands" section as milestones land.

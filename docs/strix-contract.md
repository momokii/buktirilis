# Strix adapter contract

Pinned reference: **Strix OSS `v1.7.1`** (`https://github.com/usestrix/strix`).
Verified against the official CLI reference and the tagged source for `v1.7.1`:
`strix/report/writer.py`, `strix/report/state.py`, `strix/report/coverage.py`, and the
`penetration-testing-with-strix` skill. Sources:

- <https://docs.strix.ai/usage/cli.md>
- <https://github.com/usestrix/strix/releases/tag/v1.7.1>
- <https://github.com/usestrix/strix/blob/v1.7.1/skills/penetration-testing-with-strix/SKILL.md>
- <https://github.com/usestrix/strix/blob/v1.7.1/strix/report/coverage.py>

Live execution was **not observed** in the implementation environment. The adapter and its
normalization are covered by a subprocess contract test with a fake CLI; see
`backend/tests/test_strix_adapter.py`.

## CLI invocation

The adapter builds a structured argv array and runs it in a dedicated per-run directory:

```
strix -n
      --target <approved build URL>
      --scan-mode quick|standard
      --max-budget <usd>
      --max-turns <n>
      --instruction-file <worker-authored file>
      [--target <sanitized OpenAPI document path>]
```

- `-n` (headless) is required. `--fail-on` is omitted, so exit `2` means any reported
  finding.
- Depth maps directly: Quick → `quick`, Standard → `standard`. Deep is not offered.
- The instruction file contains the profile focus, approved origins, and bounded focus routes
  (added/changed OpenAPI operations and operator-selected paths). Credentials are never written
  into it; authenticated exploration would require a separate, documented, short-lived
  credential path.
- API specs are parsed offline, validated against the project origin allowlist, stripped of
  all server overrides, and written as a local sanitized document. A spec host never
  authorizes a destination.
- Environment: a restricted PATH/HOME plus the provider variables the worker already holds.
  No user input becomes an argument, and no shell is involved.

## Exit codes and lifecycle

| Exit | Adapter interpretation |
|---|---|
| `0` | Scan finished; may still be partial if `run.json` says `stopped`, or coverage says incomplete |
| `1` | Fatal engine error → run `failed`, sanitized log tail retained, no blind retry |
| `2` | Findings at or above threshold → ingest normally; coverage still required for completeness |

Additional normalisation:

- `status: stopped` in `run.json` (budget ceiling) → completed run with an explicit
  limitation and `coverage_complete=false`.
- Cancel or timeout → terminate the **process group** (`SIGTERM`, then `SIGKILL`), mark the
  run `canceled`/`interrupted`, and never treat partial output as complete.
- Unconfirmed cleanup (process group still present, or wait failure) → limitation recorded
  and job error `cleanup_unconfirmed`; redispatch is blocked until an operator verifies the
  runtime is stopped.
- Artifacts are discovered from the newest `strix_runs/*/run.json` directory after the
  process exits.

## Artifacts consumed

| Artifact | Use |
|---|---|
| `run.json` | status, targets, scan mode, LLM usage/cost, engine metadata |
| `vulnerabilities.json` | finding records: `id`, `title`, `severity`, `timestamp`, `description`, `impact`, `endpoint`, `method`, `evidence`, `technical_analysis`, `poc_description`, `remediation_steps`, `cwe`, `confidence`, … |
| `vulnerabilities/<id>.md` | kept on the volume as raw provenance (not re-rendered as HTML) |
| `coverage.json` | `entries[]` with `surface`, `risk_area`, `outcome`, `outcome_label`, `evidence`, `source=agent_reported`; `completeness.complete` + caveats; `gaps[]` |
| `findings.sarif` | optional engine artifact; not exported as a first-class format |
| `http_exchanges.json` (optional) | resolves `http_exchange_ids` into captured evidence |

Ingest rules:

- Coverage outcomes map to app states: `reported → finding_observed`,
  `no_issue_found|ruled_out → tested_without_finding`, `not_applicable → not_applicable`,
  `needs_follow_up → needs_review`. Gaps become explicit `not_run` rows.
- Reaching a route during recon only adds it to the surface inventory. A finding requires a
  recorded check.
- A referenced HTTP evidence ID is only presented as captured proof when the referenced
  exchange resolves. If it does not, the report states that the linked evidence was
  unavailable; a missing artifact never masquerades as proof.
- Coverage completeness requires `coverage.completeness.complete` **and** no unaddressed
  planned/blocked/needs-review rows. Budget-stopped and auth-blocked runs cannot appear
  fully covered.
- The parser tolerates missing optional fields and records unparsed artifacts explicitly.
- Demo mode writes fixtures in the same artifact shapes and labels them everywhere:
  run mode `demo`, a report banner, and export notices. Demo and live runs are excluded from
  cross-mode comparison.

## Prompt-injection and untrusted content

Agent-generated text, PoCs, response bodies, Markdown, and imported scripts are untrusted
data. They are stored as text, rendered without HTML execution, and never executed. Evidence
is displayed through text nodes and escaped PDF primitives. Replay uses only typed recipe
assertions, not agent-authored scripts.

## What is verified, and what is not

Verified in this repository:

- argv construction, restricted environment, per-run directory, artifact discovery;
- exit `0/2` normalization, launch-failure reporting;
- cancellation and deadline termination of the process group;
- demo artifacts normalized through the same ingest path;
- target policy denial, loopback guard, redirect re-validation;
- seeded runs, retests against the real lab, and frozen exports.

Unverified until a provisioned worker exists:

- execution against the real `v1.7.1` binary and container sandbox;
- provider/model behaviour, spend estimation, and refusal/telemetry handling;
- actual child-sandbox network isolation and cancellation cleanup;
- real linked-HTTP-evidence sample shapes beyond the documented contract.

The adapter is implemented, not proven live. Record the pinned image digest, CLI version
output, and isolation probe results in the deployment runbook before calling the pilot ready.

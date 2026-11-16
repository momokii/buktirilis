# Research note — pilot hardening decisions

Date: 2026-11-16. Scope: the approved defaults for the remaining code-side gaps, plus the
security guardrails. Findings are traced to the source that owns the claim. Where a source is
implementation documentation (a tool's own docs), it is cited as such.

## 1. Authorization regression testing and snapshot evidence

OWASP's Authorization Regression Testing Cheat Sheet defines automated authorization tests as a
matrix of horizontal, vertical, and tenant-isolation checks, including explicit positive controls,
and treats these as regression suites that run continuously. It also distinguishes baseline
authorization controls from the regression test design.

- Source: <https://cheatsheetseries.owasp.org/cheatsheets/Authorization_Regression_Testing_Cheat_Sheet.html>
- Applied: replay recipes always include a legitimate-owner positive control; a checked denial
  without a working control is inconclusive, not a fix. This is why evidence and verification are
  derived from per-build observations rather than mutable status.

OWASP WSTG's reporting section treats the report as a point-in-time snapshot and requires the
methodology, scope, and limitations to travel with the technical findings.

- Source: <https://wstg.owasp.org/v4.2/5-Reporting/>
- Applied: exports embed snapshot time, scope, limitations, and evidence availability; later work
  is separated into **Latest verification** rather than rewriting the run's snapshot.

**Decision:** snapshot a run's findings, verification, and evidence status at completion; review
decisions after that are append-only history and do not change a historical comparison or export.

## 2. OpenAPI operation identity

OpenAPI 3.0.3 defines a Paths Object whose fields are path templates beginning with `/`, and Path
Item Objects whose operations are the HTTP methods on that path. Path-level `servers` and operation
`servers` can override the root server list. The path is appended to the expanded server URL.

- Source: <https://spec.openapis.org/oas/v3.0.3.html> (Paths Object, Path Item Object, Server Object)
- Applied: operation identity is the normalized `METHOD /path` key. Added/changed/removed sets are
  computed from that key; operationId/summary changes count as changed. Server overrides remain
  validated against the target policy before a spec is accepted.

**Decision:** compare operations with `(method, path)` as the stable key and record added/changed
operations as discovery candidates. Without both specs, the diff is explicitly unavailable and
surface reconnaissance remains the discovery source.

## 3. Missing surfaces

The brief distinguishes inventory from tested scope: reaching a route during recon only adds it to
the inventory, while testing requires a recorded check. A finding whose affected route is absent
from the current surface inventory therefore cannot be inferred fixed.

- Source: BuktiRilis brief §3 (Coverage & Methodology) and §4 (release comparison semantics).
- Applied: an absent route produces **Awaiting verification** with a `surface_absent` reason, never
  a fix. This follows the same "absence is not evidence of a fix" rule used for missing evidence.

## 4. Worker-side prerequisite probes

The brief requires reachability and identity verification for test accounts and says a failed
authenticated prerequisite must show the blocked scenarios and require an explicit decision before
running reduced scope. Running probes from the worker keeps runtime/network control off the web
service (brief §6 deployment boundaries; `docs/decisions.md` ADR-006).

- Applied: the worker probes each selected identity through the approved target before discovery,
  plus recipe fixture checks for planned replays. Any failure fails the run closed with the exact
  identity/fixture listed. Submission still supports the explicit reduced-scope acknowledgement.

## 5. Dependency, secret, and image scanning

- **pip-audit** audits a locally installed environment and/or requirements files and has defined
  exit codes. Source: <https://pypi.org/project/pip-audit/> and the project README.
- **npm audit** submits the lockfile tree and exits non-zero based on `--audit-level`.
  Source: <https://docs.npmjs.com/cli/v10/commands/npm-audit>
- **detect-secrets** supports baselines and a hook mode; baseline entries are reviewed false
  positives, while new findings fail. Source: <https://github.com/Yelp/detect-secrets>
- **Bandit** is a Python static analyzer for common security issues. Source:
  <https://bandit.readthedocs.io/>
- **Trivy** scans container images for vulnerabilities and supports severity filtering and a
  failing exit code. Source: <https://trivy.dev/latest/docs/>
- **GitHub Actions security hardening** recommends pinning third-party actions to a full-length
  commit SHA and granting least privilege. Source:
  <https://docs.github.com/en/actions/security-guides/security-hardening-for-github-actions>

**Decision:** enforce Python/Node dependency audits, Bandit, baseline-based secret scanning, and a
pinned version of Trivy in CI; pin action SHAs and use `permissions: contents: read`. The current
local results are recorded in `docs/security-guardrails.md`.

## 6. Encrypted transport for the tailnet

Tailscale Serve terminates HTTPS using a tailnet certificate and proxies to a local service; that
is the preferred way to expose a private web app with Secure cookies over Tailscale.

- Source: <https://tailscale.com/kb/1312/serve>
- Current deployment: the Tailscale CLI is not installed on this host, so the app is bound to the
  tailnet IPv4 over HTTP (`COOKIE_SECURE=false`, WireGuard-encrypted in transit). Setting up Serve
  requires an operator install/Tailnet HTTPS decision.

## 7. Live engine contract

The adapter remains pinned to Strix v1.7.1 and follows the CLI/artifact contract already recorded
in `docs/strix-contract.md`. Live execution still requires model credentials, the pinned image, and
a worker with a proven isolation boundary; research cannot substitute for that provisioning.

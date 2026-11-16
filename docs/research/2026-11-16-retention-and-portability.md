# Research note — retention, guided revisions, and portable deployment

Date: 2026-11-16. Scope: closing the last in-app product gaps and making the same demo
stack reproducible on another machine. Each decision is traced to its owning source.

## 1. Evidence retention

NIST SP 800-53 AU-11 requires an organization-defined retention period for audit/security
records, with archiving and protection for the retention period. It does not prescribe one
number, so the retention window must be deployment configuration, not a hardcoded value.
- Source: <https://csrc.nist.gov/pubs/sp/800/53/r5/upd1/final> (AU-11 Audit Record Retention)

OWASP's Logging Cheat Sheet likewise treats retention as a policy decision and warns that logs
may contain sensitive data; retaining less raw data reduces exposure.
- Source: <https://cheatsheetseries.owasp.org/cheatsheets/Logging_Cheat_Sheet.html>

**Decision:** `EVIDENCE_RETENTION_DAYS` defaults to `0` (keep everything). The
`prune-evidence` command removes raw payloads and attachments older than the window while
retaining the evidence row, its summary, the finding, accepted observations/verdicts, and
already-frozen export bytes. A pruned row is visibly marked; it is not presented as proof.
Frozen PDF/CSV/JSON exports remain downloadable because they store their own bytes.

## 2. Guided-step revisions

OWASP WSTG reporting guidance requires a reproducible procedure and preserving the evidence
that supported a finding. A reviewer correcting the procedure must therefore add a revision,
not overwrite the original observation or the steps used for an earlier attempt.
- Source: <https://wstg.owasp.org/v4.2/5-Reporting/>

**Decision:** `guided_step_revisions` is append-only. The finding's original
`reproduction_steps` stay unchanged; the guided package and new submissions use the latest
revision. Submissions record the revision they followed, and an unknown revision is rejected.

## 3. Portable single-host deployment

Docker's Compose production guidance recommends explicit configuration, persistent volumes,
health checks, and reproducible images for a single-host service.
- Source: <https://docs.docker.com/compose/how-tos/production/>

Docker documents that an image digest is an immutable identifier; pinning by digest is the
reproducible reference, while a tag alone can move.
- Source: <https://docs.docker.com/reference/cli/docker/image/pull/#pull-an-image-by-digest-immutable-identifier>

Tailscale Serve terminates HTTPS with a tailnet certificate and proxies to a local service;
it is the preferred way to expose the private app with Secure cookies.
- Source: <https://tailscale.com/kb/1312/serve>

**Decision:** ship `scripts/deploy.sh` for a one-command demo deployment (generates local
secrets, starts Compose, seeds, copies credentials, verifies health) and document the same
steps manually. The Compose file exposes only the web port on an explicit bind interface.
For non-Tailscale access, terminate TLS at a trusted reverse proxy/Tailscale Serve and set
`PUBLIC_ORIGIN=https://...` plus `COOKIE_SECURE=true`. Image tags remain tagged by version;
digests are recorded in the deployment runbook for release pinning.

## 4. What the demo cannot prove

The demo lab, identities, and artifacts are synthetic. Live Strix execution, model-provider
behaviour, and sandbox egress isolation still require a provisioned worker and authorized
target; no retention or portability change alters that boundary.

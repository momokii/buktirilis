# BuktiRilis user guide

This is a pointer page. The canonical end-to-end user guide lives with the web app so it can
ship inside the deployed SPA and be read on GitHub from the same source:

- In the app: `/guide` (after signing in)
- In the repository: [`web/src/content/guide/guide/`](../web/src/content/guide/guide/)

Installation, deployment, TLS, backup, and worker provisioning are separate:
[deploying elsewhere](deploying-elsewhere.md), [deployment](deployment.md), and
[single-VM monodeploy](monodeploy.md).

## Guide contents

| Page | What it covers |
| --- | --- |
| [Start here](../web/src/content/guide/guide/00-start-here.md) | Audience, demo vs live, roles, help |
| [First assessment](../web/src/content/guide/guide/01-first-run.md) | One full run from sign-in to PDF |
| [Set up a project](../web/src/content/guide/guide/02-project-setup.md) | Accounts, project, policy, identities, members |
| [Register a build](../web/src/content/guide/guide/03-builds.md) | Destination, expected identity, attestation |
| [Queue an assessment](../web/src/content/guide/guide/04-queue-run.md) | Kind, depth, identities, preflight, queue |
| [Watch a run](../web/src/content/guide/guide/05-monitor-run.md) | Statuses, cancellation, failures |
| [Read a report](../web/src/content/guide/guide/06-read-report.md) | Overview, findings, coverage, provenance |
| [Understand a finding](../web/src/content/guide/guide/07-work-finding.md) | Proof, reproduction, evidence, history |
| [Retest a finding](../web/src/content/guide/guide/08-retest.md) | Automatic, guided, review, verdict |
| [Compare releases](../web/src/content/guide/guide/09-compare.md) | Buckets, scope, coverage |
| [Export evidence](../web/src/content/guide/guide/10-export.md) | PDF, CSV, JSON, frozen snapshots |
| [Where things live](../web/src/content/guide/guide/11-where-things-live.md) | Route and label map |
| [Roles and permissions](../web/src/content/guide/guide/12-roles.md) | Capability matrix and membership |
| [Glossary](../web/src/content/guide/guide/13-glossary.md) | Statuses, outcomes, buckets, reasons |
| [Troubleshooting](../web/src/content/guide/guide/14-troubleshooting.md) | Blockers and next actions |
| [Limits](../web/src/content/guide/guide/15-limits.md) | Coverage, zero findings, non-certification |

The Markdown is checked by `web/e2e/guide.spec.ts` for structure, links, route coverage, and
label drift.

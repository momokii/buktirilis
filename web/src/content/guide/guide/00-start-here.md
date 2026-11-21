# Start here

Use this guide when the app is already installed and reachable, and you need to run an
assessment, read the result, or hand the evidence to someone else.

## What this guide covers

This is the user guide for the app at your deployment URL. It covers projects, builds, target
scope, test identities, runs, findings, retests, comparisons, exports, roles, and the limits of
the result.

## What it does not cover

Installation, TLS, backups, worker provisioning, the Docker socket, and deployment
troubleshooting are operator concerns. They live outside this guide. If the app cannot be
reached at all, the deployment is not ready; ask the operator before using the workflow here.

## Demo and live runs

The deployment decides whether runs are demo or live. A **Demo** banner and badge mean the
workspace is showing synthetic fixtures. A live deployment has no demo banner. A run always
records its own `mode`; a demo run and a live run are never compared with each other.

> [!NOTE]
> The badge reflects the deployment, not a choice in the run wizard. You cannot turn a single
> run into demo mode from the UI.

## Roles at a glance

Table: What each role can do at a glance
| Role | Typical use |
| --- | --- |
| Viewer | Read projects, runs, findings, comparisons, and exports. |
| Developer | Also submit evidence and retests, and mark a finding ready for retest. |
| Operator | Also approve target policy, builds and test identities; queue runs; edit recipes; accept a retest verdict. |
| Administrator | Installation-wide accounts and projects, plus operator capability on every project. |

The server is authoritative. A button that is missing usually means your project role does not
allow that action.

## Where to get help

Start with [Troubleshooting](/guide/troubleshooting) for a blocked action, or
[Where things live](/guide/where-things-live) when you cannot find a screen. Use
[Limits and how to read results](/guide/limits) before treating a report as a clean result.

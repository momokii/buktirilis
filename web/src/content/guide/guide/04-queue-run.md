# Queue an assessment

Use this page when the project, target policy, build, and identities are ready.

**Who can do this:** operator or administrator.

## Choose baseline or release scan

A **Baseline assessment** discovers and records the current surface. A **Release scan** first
replays known findings from an earlier completed run, then discovers new work. A release scan
requires a completed comparison baseline.

## Choose a depth

- **Quick — bounded** is the first pass. It has a smaller check and time budget.
- **Standard — full profile coverage** allows more discovery and a larger budget.

The selected profile is **Web & API Access Control v1**. The current wizard shows it read-only;
it is not a profile picker.

## Select identities

Turn off **Deliberately run unauthenticated** to select stored test identities. For an
access-control profile, select at least two identities that represent different tenants or
privilege levels. If you run unauthenticated, the preflight marks identity-dependent scenarios
as blocked and asks for reduced-scope acknowledgement.

## Add discovery routes

**Operator-selected discovery routes** is optional. Enter relative paths, one per line or comma
separated. They augment routes proposed by the target's OpenAPI changes. Use routes that are
inside the approved path prefix.

## Run preflight

Choose **Check prerequisites**. Read every row, including warnings. A pass is required to
queue; a warning can still require acknowledgement. The server runs preflight again on submit,
so a stale preview will not bypass a later blocker.

Common passing checks are build binding, target policy, recorded identity, depth limits, daily
quota, authentication mode, scenario scope, kind, and execution mode.

## Accept a reduced scope

When scenarios need identities you did not select, the preview shows them as blocked and sets
**requires reduced-scope acknowledgement**. Review the blocked scenarios, then enable the
acknowledgement before choosing **Queue run**. A reduced-scope run is valid, but its report
must not be presented as full profile coverage.

## Queue the run

Choose **Queue run**. The response may return a new run or an existing identical active run
(`created: false`). An identical active run is reused deliberately; do not queue repeatedly to
force a second execution.

## Why a run may be reused

The server treats an identical queued or running request as the same work. Change the build,
kind, depth, identities, or routes if you need a distinct run. Do not cancel a run just to
create a duplicate.

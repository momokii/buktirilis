# Troubleshooting

Use this page when an action is blocked, a run does not start, or a report looks wrong.

## You cannot see a project

Ask an administrator to check **Project → Settings → Membership**. The top-level **Projects**
page only lists projects you can access. An administrator can see every project; a project
member sees only their memberships.

## The build is rejected

Read the error under the build form. A destination outside the approved origin or path prefix is
a scope decision, not a typo to force through. Ask an operator to record a new policy revision
only when the deployment genuinely moved. A duplicate label needs a new label.

## Preflight is blocked

Open the preflight row that failed and follow its recovery text. The server repeats preflight on
submit, so rerunning **Check prerequisites** after a change is required. If scenarios are
blocked by missing identities, either add them or acknowledge reduced scope.

## The run never starts

A queued run needs a worker. Check **Settings (top bar)** for worker status. If the worker is
down, ask the operator; do not queue duplicate runs. If the run is claimed but no progress
appears, give the run ID to the operator and keep the page open for the activity log.

## Coverage is incomplete

Read **Coverage & methodology** and the report's limitations. `blocked`, `not_run`, and
`needs_review` rows are not clean results. A completed run can still have incomplete coverage.
Do not describe zero findings as “the target is clean” unless the report says coverage is
complete.

## A retest is inconclusive

Read the named reason on the attempt. Expired credentials, a missing fixture, a failed positive
control, or a build identity mismatch require an input fix, not another click. If the reason is
unrecognized, record it in the ticket and ask an operator to inspect the attempt.

## An export is unavailable

Exports require a completed run. A queued, running, failed, canceled, or interrupted run has no
stable snapshot to export. Finish a successful run first. If the run is completed and the export
still fails, note the run ID and the error.

## The guide and the screen disagree

The app is authoritative. If a label, route, or status in this guide no longer matches the
screen, report the mismatch with the page URL and the guide page. A mismatch is a documentation
defect, not a reason to guess at the workflow.

## You cannot sign in

Use the password shared through your approved channel. If web bootstrap is disabled, the first
administrator must be created by the operator with the CLI. Repeated failures are rate-limited;
wait before retrying rather than opening many tabs.

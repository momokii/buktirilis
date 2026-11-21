# Your first assessment, end to end

Use this page when you want one complete pass through the app and a report you can open.

**Who can do this:** the demo lane is available to signed-in users. The own-project lane needs
an operator or administrator to queue the run.

## Before you start

- You can sign in and see at least one project.
- A build exists, or you can ask an operator to register one.
- You know whether the deployment is demo or live; check the banner.

## Lane A: the seeded demo

1. Open **Projects** and choose the demo project. The project name and demo badge identify it.
2. Open **Project → Runs**. Select a completed run and choose **Open report**.
3. On the report, read **Risk and work remaining**, then open the **Findings** tab.
4. Open one finding and read **Proof summary**, **Prerequisites and reproduction**, and
   **Evidence**.
5. Return to the report and generate **Export PDF**. The download is available immediately.

This lane uses synthetic fixtures and is safe to click through. It does not prove that a live
target was tested.

## Lane B: your own project

1. Ask an operator to create the project and its **Approved target policy** in
   **Project → Settings**.
2. The operator registers a build under **Project → Builds**, with an expected identity when
   the target exposes one.
3. The operator opens **Project → Runs**, chooses **New run**, and selects the build.
4. For an authenticated profile, select the required test identities. For an unauthenticated
   first pass, use **Deliberately run unauthenticated** and accept the reduced scope.
5. Choose **Check prerequisites**. If it passes, choose **Queue run**. If it is blocked, read
   the failing check before changing anything.
6. Open the run report when it appears and follow **Watch a run** until the status is terminal.
7. Read the **Findings** and **Coverage & methodology** tabs, then export the report.

## Choose the build

A build binds the destination URL to a release label and, when configured, an expected deployed
identity. Pick the build that represents the code you are authorized to test. Do not reuse a
build for a different deployment; register a new one.

## Check prerequisites

**Check prerequisites** is a preview, not a promise. The server runs preflight again when you
queue the run. A pass means the currently checked inputs are acceptable; it does not guarantee
that the engine will finish.

## Queue and watch

**Queue run** returns a run with a status. Open it and watch **Live progress**. The report may
show activity before it shows a result. Do not treat an in-progress count as a finding.

## Read the report

Start with the overview, then inspect findings, then coverage. A run with zero findings is only
a clean result when coverage is complete. The report states both conditions separately.

## Export the PDF

Export is enabled only after the run completes. The PDF is a frozen snapshot of the recorded
run, not a live query. If the run is still queued or running, the button is disabled.

## If the preflight blocks you

Read the failing check and its recovery text. Common causes are a missing target revision, no
test identities, a policy mismatch, or an identity that no longer matches the build. The
[Troubleshooting](/guide/troubleshooting) page maps each blocker to the next action.

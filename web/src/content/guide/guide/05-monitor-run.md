# Watch a run

Use this page after you queue a run, or when a run appears stuck.

## Run statuses

Table: Run status meanings
| Status | Meaning |
| --- | --- |
| queued | Accepted and waiting for a worker. |
| running | A worker has claimed it and execution is in progress. |
| cancel_requested | Cancellation was requested; the worker is stopping it. |
| completed | The engine finished and its artifacts were ingested. |
| failed | Execution or ingestion failed; inspect the failure reason. |
| canceled | The run was stopped on request. |
| interrupted | The worker lease or execution deadline ended the run. |

## Stages

The report shows **Live progress** with preflight, known-finding verification, discovery,
ingestion, and finalization. A stage can be pending, running, done, failed, skipped, or canceled.
A queued run has no start time; a running run has activity rows.

## Activity log

The activity list records stage transitions and safe messages. Use it to see whether the worker
started, whether the target identity was observed, and where a failure occurred. It is not a
substitute for the run's limitations.

## Cancel a run

Use **Cancel run** while the run is active. Cancellation is cooperative: the worker stops the
process group and records a limitation if cleanup cannot be confirmed. Do not assume a canceled
run produced complete coverage.

## Failed, interrupted, or canceled

Open the report and read **Limitations** and the failure reason. A failed run is not a clean run.
If the failure names a missing identity or fixture, fix that input before retrying. If the
failure is an engine or worker problem, give the run ID and failure reason to the operator.

## Retry with passing identities

After a prerequisite failure, the report can offer **Retry with passing identities**. This
creates a reduced-scope retry using only the identities that passed. It does not repair missing
fixtures or a broken target. Review the resulting scope before treating the retry as comparable.

## When nothing starts

A run can remain queued when no worker is running or the worker cannot claim work. Check
**Settings (top bar)** for worker status, then ask the operator to inspect the worker. Repeatedly
canceling and re-queueing does not create a worker.

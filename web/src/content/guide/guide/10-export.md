# Export evidence

Use this page when a run is complete and you need a stable report for a ticket, review, or
release record.

## Formats

- **Export PDF** is a readable report snapshot.
- **CSV** is a tabular export for review or spreadsheets.
- **JSON** is the machine-readable snapshot for integrations or archival.

All three are generated on the server from the recorded run state. The browser downloads the
stored bytes; it does not render the report itself.

## What is frozen

An export freezes the run payload and the rendered bytes together. Later retests, evidence
changes, or new observations do not alter the downloaded snapshot; they appear in the
**Latest verification** panel instead.

## Download and verify

1. Open the completed run.
2. Choose **Export PDF**, **CSV**, or **JSON**.
3. Wait for the export row to show a download link.
4. Download and open the file.
5. Record the export's checksum or ID if your process requires an audit trail.

## When to export again

Export again after a meaningful change to the run state, such as an accepted retest verdict.
Do not overwrite an old export to hide a change; create a new snapshot and keep both.

## Exports before completion

Exports are disabled until the run is completed, and the server rejects an export request with
a conflict. This is deliberate: a queued or running run has no stable report to freeze.

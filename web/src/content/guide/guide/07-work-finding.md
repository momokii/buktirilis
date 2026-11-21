# Understand a finding

Use this page when you open a finding from a report, comparison, or project link.

## Proof summary

**Proof summary** states the claim, severity, scope, and the evidence status. Evidence status is
about the strength of the proof, not about whether you agree with the finding. A
`needs_validation` finding is not a verified defect yet.

## Prerequisites and reproduction

This section lists the preconditions and ordered steps a reviewer can repeat. If the report says
the steps are incomplete, do not treat the finding as independently reproduced. The root-cause
hypothesis is labelled when it is unconfirmed.

## Evidence

**Evidence** contains the captured engine report, replay exchanges, or reviewer submissions.
Each item shows its attribution and actor. An attachment is available only when the stored
artifact still exists; a missing artifact is marked unavailable and is not presented as proof.

## Verification history

**Verification history** is append-only. Observations are scoped to a build and ordered by when
they were made. A later observation can support or contradict an earlier one; the report shows
both rather than overwriting history.

## Assessment state

**Assessment state** shows the derived verification, evidence status, disposition, and whether a
retest is available. The app does not use a mutable “fixed” checkbox; it derives the state from
recorded observations.

## Possible duplicates

The finding may show **Possible duplicates**. Treat this as a review prompt, not an automatic
merge. Confirm the scope, actor, and condition before marking a disposition.

## Where to go next

- To reproduce on a new build, use [Retest a finding](/guide/retest).
- To understand the verdict vocabulary, use [Status and outcome glossary](/guide/glossary).
- To download the evidence, use [Export evidence](/guide/export).

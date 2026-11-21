# Status and outcome glossary

Use this page when a badge or a table uses a term you have not seen.

## Run statuses

Table: Run status terms
| Term | Meaning |
| --- | --- |
| queued | Waiting for a worker. |
| running | A worker is executing the run. |
| cancel_requested | A cancellation is being processed. |
| completed | Execution and ingestion finished. |
| failed | Execution or ingestion failed. |
| canceled | The run was stopped on request. |
| interrupted | The worker lease or deadline ended the run. |

## Coverage results

Table: Coverage result terms
| Term | Meaning |
| --- | --- |
| planned | A check is in the plan but has no result. |
| tested_no_finding | The check ran and did not record a finding. |
| finding_observed | The check recorded a finding. |
| blocked | A prerequisite prevented the check. |
| not_run | The check has no result. |
| not_applicable | The check does not apply to this scope. |
| needs_review | A human decision is required. |

## Verification outcomes

Table: Verification terms
| Term | Meaning |
| --- | --- |
| fix_verified | A conclusive retest did not reproduce the finding. |
| still_reproducible | A conclusive retest reproduced the finding. |
| inconclusive | The attempt could not support a verdict. |
| awaiting_retest | A retest is expected but has not produced a verdict. |

## Comparison buckets

Table: Comparison terms
| Term | Meaning |
| --- | --- |
| fix_verified | The current build no longer reproduces a baseline finding. |
| still_reproducible | The current build still reproduces it. |
| newly_observed | A finding appears in the current run but not the baseline. |
| regressed | A previously fixed finding is reproducible again. |
| awaiting_verification | The finding exists without a conclusive verdict. |
| needs_validation | The evidence is not strong enough for a verdict. |
| incomparable | Scope or evidence differences prevent a safe comparison. |

## Retest methods

Table: Retest terms
| Term | Meaning |
| --- | --- |
| automatic | A constrained replay using an approved recipe and owner control. |
| guided | A human-performed package submitted for review. |
| pending_evidence_review | A human must review the proof before retesting. |

## Evidence status

Table: Evidence status terms
| Term | Meaning |
| --- | --- |
| supported | The recorded evidence supports the finding. |
| needs_validation | The evidence needs a reviewer or stronger capture. |

## Inconclusive reasons

An inconclusive retest names its reason, including expired credentials, identity mismatch,
missing fixture, failed positive control, build identity mismatch, scope denial, transport error,
blocked redirect, unrecognized response, revoked authorization, or a superseded recipe. Read the
reason before retrying; retrying the same broken input will produce the same result.

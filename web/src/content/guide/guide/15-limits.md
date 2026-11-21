# Limits and how to read results

Use this page before presenting a report as evidence of security.

## What a run covers

A run covers the build, target policy, identities, fixtures, routes, and profile recorded in its
scope snapshot. Coverage counts planned checks with a recorded result, not every route that was
seen. Recon can add a surface to the inventory without testing it.

## Zero findings

Zero findings means no finding was recorded in the tested checks. It is a clean result only when
the report says coverage is complete and the limitations do not describe missing scope. A
completed run with blocked or not-run checks is not a clean bill of health.

## What is not tested

The report lists blocked, not-run, and needs-review rows. Identity-dependent checks are blocked
when no suitable identities were selected. A target with no account or tenant model cannot
exercise cross-account authorization even if the scanner runs successfully.

## Demo versus live

Demo runs use deterministic synthetic artifacts and real replays against the bundled lab. Live
runs use the configured engine and the approved target. The two modes are labelled and are
never compared with each other.

## Engine and model boundaries

The engine and model are tools, not proof. A model can miss a vulnerability, misinterpret a
response, or stop before it records coverage. The app preserves the engine's artifacts and the
operator's review rather than presenting a generated claim as verified fact.

## Not a certification

BuktiRilis records what was tested and what changed. It is not a compliance certificate, a
penetration-test attestation, or a guarantee that untested code is safe. Use the report's scope,
coverage, and limitations in any external statement.

## A good release statement

Say: “Run `<id>` tested `<scope>` with `<coverage>`; it recorded `<n>` findings and `<n>` gaps.
The result is limited to the recorded scope.” Do not say “the application is secure.”

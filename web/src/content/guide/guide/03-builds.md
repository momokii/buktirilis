# Register a build

Use this page when a release or deployment needs to be tested as a distinct build.

**Who can do this:** operator or administrator.

## When a new build is required

Register a new build when the release label, destination URL, expected build identity, or
OpenAPI revision changes. A build binds the exact target policy revision that was current when
it was created. Reusing a build across deployments makes the report ambiguous.

## Register the build

1. Open **Project → Builds**.
2. Choose **Register build**.
3. Enter a build label, the approved destination URL, and an optional commit SHA.
4. Enter an expected build identity when the deployment exposes one.
5. Attach an OpenAPI revision if the project has one and this build changed the API.
6. Save. The build appears with its destination and identity status.

The server checks the destination against the approved policy. A rejected destination is a
scope problem, not a form problem; fix the policy or choose the correct URL.

## Record or attest the deployed identity

If the build exposes an identity endpoint, the worker observes it before the run. When the
deployment does not expose one, an operator may use **Attest identity** and record the identity
they observed out of band, with a note. An attested identity is not an observed identity; the
report keeps that distinction.

An observed identity that differs from the expected identity blocks the run. Do not attest
around a mismatch; investigate the deployment first.

## Fix a rejected build

- **Destination outside the approved origin**: use the origin from the current policy, or ask
  an operator to record a new policy revision if the deployment genuinely moved.
- **Destination outside the path restriction**: include the approved deployment prefix.
- **Duplicate label**: choose a new label; builds are historical records.
- **No approved target policy**: record the first target policy in **Project → Settings**.

## What the build does not do

A build does not create a test account, grant authorization, or start a run. It is the bridge
between the approved target and the recorded release you are assessing.

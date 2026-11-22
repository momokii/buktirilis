# Set up a project (administrator)

Use this page when a new application or environment needs its own project and approved scope.

**Who can do this:** administrators create accounts and projects. Operators manage the target
policy, builds, identities, and members inside an existing project.

## Create user accounts

1. Open **Admin** from the top navigation.
2. Choose **New account**.
3. Enter an email, display name, and an initial password of at least 12 characters.
4. Give the account a project membership with the least role it needs.
5. Share the password through an approved channel; the app never shows it again.

The first administrator is created by the operator with the bootstrap CLI outside development.
The login page explains this when web bootstrap is disabled.

Projects, builds, and runs are historical records. The current UI has **no delete or archive
action** for them; remove a member when access ends, and record a new revision or build when
the deployment changes.

## Create the project

1. Open **Admin** and choose **New project**, or use **New project** on the **Projects** page.
2. Enter a name, optional slug, and a short description.
3. Record the **Approved base URL**, allowed origins, optional path restrictions, environment
   label, scope owner, and authorization reference.
4. Save. The first target policy is revision 1.

The target policy is the authorization boundary. A build cannot use an origin or path that is
not in the current revision.

## Record the target policy

Open **Project → Settings** and read **Approved target policy**. A policy revision is immutable;
existing builds stay bound to the revision they used. When the deployment destination changes,
record a new revision instead of editing history.

Use a path prefix when the target is mounted under a deployment path. The exact origin and path
are checked again at execution time.

## Attach an OpenAPI revision

In **Project → Settings**, upload an OpenAPI document when the target publishes one. The server
parses it offline, limits its size, and rejects declared servers outside the approved origin.
The build can then use the operations for discovery candidates and changed-route focus.

You do not need OpenAPI to queue a run. Without it, discovery is based on the target and the
profile, and coverage may be less precise.

## Add test identities

1. In **Project → Settings**, find **Test identities**.
2. Choose **Add test identity**.
3. Enter a name, role label, optional tenant label, the credential, and the identity-check path.
4. Save. The credential is encrypted and resolved only when a run executes.

Use at least two identities from different tenants or privilege levels for an access-control
run. Use short-lived test credentials, never a real administrator account. Rotate a credential
with **Rotate credential** when it changes.

## Add members

In **Project → Settings → Membership**, add a user and choose viewer, developer, or operator.
Administrators already have operator capability on every project. Remove a member when access
is no longer required.

## When a new revision is required

Create a new target revision when the origin, path prefix, or authorization boundary changes.
Create a new build when the release, destination URL, expected identity, or attached OpenAPI
revision changes. Do not widen the current policy just to make a rejected build pass.

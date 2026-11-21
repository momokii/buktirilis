# Roles and permissions

Use this page when an action is missing, or before giving someone access.

## Capability matrix

Table: Project capabilities by role
| Capability | Viewer | Developer | Operator | Administrator |
| --- | --- | --- | --- | --- |
| Read projects, runs, findings, comparisons | Yes | Yes | Yes | Yes |
| Download exports | Yes | Yes | Yes | Yes |
| Submit evidence and retests | No | Yes | Yes | Yes |
| Mark a finding ready for retest | No | Yes | Yes | Yes |
| Register builds and run preflight | No | No | Yes | Yes |
| Queue runs and cancel runs | No | No | Yes | Yes |
| Edit recipes and revise guided steps | No | No | Yes | Yes |
| Accept a retest verdict | No | No | Yes | Yes |
| Record target policy and test identities | No | No | Yes | Yes |
| Manage project members | No | No | Yes | Yes |
| Create accounts and projects | No | No | No | Yes |
| Manage installation settings and audit | No | No | No | Yes |

The server enforces these checks. If a button is missing, do not ask another user to click it
for you; ask them to perform the action with their own account.

## Project membership

An administrator adds an existing account to a project in **Project → Settings → Membership**.
Membership is per project; the same user can have different roles in different projects. Remove
a member when their access ends.

## Installation settings

**Settings (top bar)** shows installation configuration, worker status, and execution mode. It
does not change a project's target policy or membership. Administrators can inspect it; not
every setting is editable from the browser.

## Worker status

The worker is the process that executes queued work. A run can remain queued when no worker is
running. The Settings page reports worker heartbeat and active/queued counts. This is an
operator concern; a normal project user should report it rather than changing deployment files.

## Audit trail

Project settings show project-scoped audit events. Admin shows installation-wide events. Use the
audit trail to answer who created a project, changed a target policy, rotated a credential, or
accepted a review. It is not a substitute for the finding's evidence history.

## Least privilege

Give viewers read access, developers the ability to submit and retest, and operators the ability
to change scope and accept verdicts. Do not make every user an administrator to make a button
appear; that removes the review boundary the app is designed to preserve.

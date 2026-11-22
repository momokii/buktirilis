# Research note — staging label, project creation, and worker spacing

Date: 2026-11-22. Scope: the questions raised from the deployed Projects and Settings screens.
Read-only investigation against the repository source; no external claims are needed beyond
"configuration labels do not establish deployment parity."

## Verdict

**`STAGING` is an `APP_ENV` deployment label, not a production parity guarantee.** It selects
deployment behavior and is shown so operators do not confuse environments. The app has no
mechanism that proves a staging target is a 1:1 copy of production.

**Project creation is installation-administrator-only.** The server enforces this, and the
operator account is correctly unable to create a project. The discovery gap was in the UI: the
only creation action lived inside the Admin page and the Projects page had no admin shortcut.
That is now fixed with an admin-only **New project** action and an operator instruction.

## Evidence

| # | Claim | Owning source |
|---|---|---|
| E1 | `APP_ENV` accepts `development`, `staging`, or `production`; unknown values normalize to production-safe behavior. | `backend/app/config.py` (`APP_ENVS`, field validator) |
| E2 | Deployment behavior changes by environment (cookie security, demo/live defaults), so the label is behavioral. | `backend/app/config.py` (`_apply_defaults`) |
| E3 | The deployed app is explicitly `APP_ENV=staging`; the project target also records `environment_label: staging`. | `docs/deployment.md`; `backend/app/services/lab_seed.py` |
| E4 | The top bar displays the active environment and now states that the label is not a parity guarantee. | `web/src/AppShell.tsx`; `web/src/pages/Settings.tsx` |
| E5 | Creating a project requires the admin role in the API. | `backend/app/routers/projects.py` (`create_project`, `require_admin`) |
| E6 | The Admin page owns the project registration dialog. Operators do not see the Admin navigation item. | `web/src/pages/Admin.tsx`; `web/src/AppShell.tsx` |
| E7 | The Projects page previously offered no create action for admins and no explanation for operators. | `web/src/pages/Projects.tsx` (before this change) |
| E8 | The Worker section placed the active-runs cards and recent-jobs table as adjacent siblings without a consistent gap. | `web/src/pages/Settings.tsx`; `web/src/styles.css` |
| E9 | The server-side role model is the authority; hiding a button is not authorization. | `backend/app/deps.py`; `.claude/SECURITY_STANDARDS.md` §6 |

## Implemented corrections

- Projects now shows **New project** to administrators only, linking to `/admin?new=project`;
  the Admin page recognizes that query and opens the existing dialog.
- Non-administrators see: "Only an installation administrator can create a project."
- The top-bar environment tooltip, Settings copy, deployment guide, and user guide distinguish
  the deployment label from production parity.
- Worker counters, table, and notices use a `worker-status` stack with a consistent gap.
- Regression coverage: admin can start project creation from Projects; operator sees the hint
  and no create link.

## Unverified / limits

- This note is code-research, not a production-parity test. No production deployment exists;
  staging cannot be claimed as a 1:1 production replica.
- The provider/model and sandbox isolation caveats remain those recorded in `CURRENT_STATUS.md`.

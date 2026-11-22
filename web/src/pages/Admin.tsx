import { useEffect, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { useApi } from "../auth";
import { api, errorMessage } from "../api";
import type { AdminUser, Project } from "../api";
import { Button, Dialog, ErrorState, Field, Loading, Mono, Notice, PageHeader, RelativeTime, Section, TableWrap, TextInput, useToast } from "../ui";
import { ConfirmDialog } from "../components/ConfirmDialog";
import { MembershipEditor, type MembershipDraft } from "../components/MembershipEditor";
import { ProjectDialog } from "../components/ProjectDialog";

interface AuditRow {
  id: string;
  at: string;
  actor: string;
  action: string;
  target_type: string;
  target_id: string;
  project_id: string | null;
  metadata: Record<string, unknown>;
}

interface AuditPage {
  items: AuditRow[];
  total: number;
  limit: number;
  offset: number;
}

interface ConfirmState {
  user: AdminUser;
  patch: Record<string, unknown>;
  title: string;
  description: string;
  confirmLabel: string;
  tone: "primary" | "danger";
}

const AUDIT_PAGE_SIZE = 20;

export function AdminPage() {
  const [searchParams, setSearchParams] = useSearchParams();
  const users = useApi<{ items: AdminUser[] }>("/api/admin/users");
  const projects = useApi<{ items: Project[] }>("/api/projects");
  const [auditPage, setAuditPage] = useState(0);
  const audit = useApi<AuditPage>(
    `/api/admin/audit?limit=${AUDIT_PAGE_SIZE}&offset=${auditPage * AUDIT_PAGE_SIZE}`,
  );
  const { notify } = useToast();

  const [userOpen, setUserOpen] = useState(false);
  const [projectOpen, setProjectOpen] = useState(false);
  const [busy, setBusy] = useState(false);
  const [userError, setUserError] = useState<string | null>(null);
  const [confirm, setConfirm] = useState<ConfirmState | null>(null);
  const [resetUser, setResetUser] = useState<AdminUser | null>(null);
  const [resetPassword, setResetPassword] = useState("");
  const [resetConfirm, setResetConfirm] = useState("");
  const [resetError, setResetError] = useState<string | null>(null);
  const [accessUser, setAccessUser] = useState<AdminUser | null>(null);
  const [accessMemberships, setAccessMemberships] = useState<MembershipDraft[]>([]);
  const [accessError, setAccessError] = useState<string | null>(null);

  const [email, setEmail] = useState("");
  const [name, setName] = useState("");
  const [password, setPassword] = useState("");
  const [isAdmin, setIsAdmin] = useState(false);
  const [memberships, setMemberships] = useState<MembershipDraft[]>([]);

  useEffect(() => {
    if (searchParams.get("new") !== "project") return;
    setProjectOpen(true);
    const next = new URLSearchParams(searchParams);
    next.delete("new");
    setSearchParams(next, { replace: true });
  }, [searchParams, setSearchParams]);

  useEffect(() => {
    const totalPages = Math.max(1, Math.ceil((audit.data?.total ?? 0) / AUDIT_PAGE_SIZE));
    if (auditPage >= totalPages) {
      setAuditPage(Math.max(0, totalPages - 1));
    }
  }, [audit.data?.total, auditPage]);

  const projectOptions = (projects.data?.items ?? []).map((project) => ({
    id: project.id,
    name: project.name,
  }));

  const openUserDialog = () => {
    setUserError(null);
    setMemberships([{ project_id: "", role: "developer" }]);
    setUserOpen(true);
  };

  const closeUserDialog = () => {
    setUserOpen(false);
    setUserError(null);
    setEmail("");
    setName("");
    setPassword("");
    setIsAdmin(false);
    setMemberships([]);
  };

  const createUser = async () => {
    setBusy(true);
    setUserError(null);
    try {
      await api("/api/admin/users", {
        method: "POST",
        body: JSON.stringify({
          email,
          display_name: name,
          password,
          is_admin: isAdmin,
          memberships: isAdmin
            ? []
            : memberships
                .filter((membership) => membership.project_id)
                .map((membership) => ({
                  project_id: membership.project_id,
                  role: membership.role,
                })),
        }),
      });
      notify("success", "Account provisioned with its scoped access.");
      closeUserDialog();
      users.refresh();
    } catch (caught) {
      setUserError(errorMessage(caught));
    } finally {
      setBusy(false);
    }
  };

  const requestConfirm = (next: ConfirmState) => setConfirm(next);

  const applyConfirmedPatch = async () => {
    if (!confirm) return;
    setBusy(true);
    try {
      await api(`/api/admin/users/${confirm.user.id}`, {
        method: "PATCH",
        body: JSON.stringify(confirm.patch),
      });
      notify("success", "Account updated.");
      setConfirm(null);
      users.refresh();
    } catch (caught) {
      notify("error", errorMessage(caught));
    } finally {
      setBusy(false);
    }
  };

  const openReset = (user: AdminUser) => {
    setResetUser(user);
    setResetPassword("");
    setResetConfirm("");
    setResetError(null);
  };

  const saveReset = async () => {
    if (!resetUser) return;
    if (resetPassword.length < 12) {
      setResetError("Use at least 12 characters.");
      return;
    }
    if (resetPassword !== resetConfirm) {
      setResetError("The password confirmation does not match.");
      return;
    }
    setBusy(true);
    setResetError(null);
    try {
      await api(`/api/admin/users/${resetUser.id}`, {
        method: "PATCH",
        body: JSON.stringify({ password: resetPassword }),
      });
      notify("success", "Password reset. Share the new password through an approved channel.");
      setResetUser(null);
    } catch (caught) {
      setResetError(errorMessage(caught));
    } finally {
      setBusy(false);
    }
  };

  const openAccess = (user: AdminUser) => {
    setAccessUser(user);
    setAccessMemberships(
      user.memberships.map((membership) => ({
        project_id: membership.project_id,
        role: membership.role,
      })),
    );
    setAccessError(null);
  };

  const saveAccess = async () => {
    if (!accessUser) return;
    setBusy(true);
    setAccessError(null);
    try {
      await api(`/api/admin/users/${accessUser.id}`, {
        method: "PATCH",
        body: JSON.stringify({
          memberships: accessMemberships
            .filter((membership) => membership.project_id)
            .map((membership) => ({
              project_id: membership.project_id,
              role: membership.role,
            })),
        }),
      });
      notify("success", "Project access updated.");
      setAccessUser(null);
      users.refresh();
    } catch (caught) {
      setAccessError(errorMessage(caught));
    } finally {
      setBusy(false);
    }
  };

  const auditTotal = audit.data?.total ?? 0;
  const auditPages = Math.max(1, Math.ceil(auditTotal / AUDIT_PAGE_SIZE));

  return (
    <div className="admin-page">
      <PageHeader
        title="Administration"
        description="Provision accounts with scoped project roles, register approved project scopes, and review security-relevant events."
        actions={
          <>
            <Button onClick={openUserDialog}>New account</Button>
            <Button variant="primary" onClick={() => setProjectOpen(true)}>
              New project
            </Button>
          </>
        }
      />
      <Notice tone="info" title="Least privilege">
        Project roles: viewer reads and exports, developer reviews evidence and runs retests,
        operator manages builds, runs, recipes, and verdicts. Administrators manage scope, membership,
        and credentials. All checks are enforced server-side.
      </Notice>

      <Section title="Accounts">
        {users.loading && !users.data ? <Loading label="Loading accounts" /> : null}
        {users.error ? <ErrorState message="Accounts could not be loaded." onRetry={users.refresh} /> : null}
        {users.data ? (
          <TableWrap label="Accounts">
            <table>
              <thead>
                <tr>
                  <th scope="col">Account</th>
                  <th scope="col">Access</th>
                  <th scope="col">State</th>
                  <th scope="col">Created</th>
                  <th scope="col">
                    <span className="visually-hidden">Actions</span>
                  </th>
                </tr>
              </thead>
              <tbody>
                {users.data.items.map((user) => (
                  <tr key={user.id}>
                    <td>
                      <span className="cell-title">{user.display_name}</span>
                      <div className="cell-sub">{user.email}</div>
                    </td>
                    <td>
                      {user.is_admin ? <span className="badge badge-info">Admin</span> : null}
                      <ul className="inline-code-list" style={{ marginTop: "0.2rem" }}>
                        {user.memberships.map((membership) => (
                          <li key={membership.project_id}>
                            <span className="badge badge-neutral">
                              {membership.project_name}: {membership.role}
                            </span>
                          </li>
                        ))}
                        {user.memberships.length === 0 && !user.is_admin ? (
                          <li className="muted small">No project access</li>
                        ) : null}
                      </ul>
                    </td>
                    <td>
                      {user.is_active ? (
                        <span className="badge badge-pass">Active</span>
                      ) : (
                        <span className="badge badge-neutral">Disabled</span>
                      )}
                    </td>
                    <td>
                      <RelativeTime value={user.created_at} />
                    </td>
                    <td className="actions">
                      <Button size="sm" onClick={() => openReset(user)}>
                        Reset password
                      </Button>
                      <Button size="sm" onClick={() => openAccess(user)}>
                        Edit access
                      </Button>
                      <Button
                        size="sm"
                        aria-label={`${user.is_active ? "Disable" : "Enable"} ${user.email}`}
                        onClick={() =>
                          requestConfirm({
                            user,
                            patch: { is_active: !user.is_active },
                            title: user.is_active ? "Disable this account?" : "Enable this account?",
                            description: user.is_active
                              ? `${user.email} will no longer be able to sign in. Existing evidence is not changed.`
                              : `${user.email} will be able to sign in again with its existing credentials.`,
                            confirmLabel: user.is_active ? "Disable account" : "Enable account",
                            tone: user.is_active ? "danger" : "primary",
                          })
                        }
                      >
                        {user.is_active ? "Disable" : "Enable"}
                      </Button>
                      <Button
                        size="sm"
                        aria-label={`${user.is_admin ? "Remove admin from" : "Make admin"} ${user.email}`}
                        onClick={() =>
                          requestConfirm({
                            user,
                            patch: { is_admin: !user.is_admin },
                            title: user.is_admin
                              ? "Remove installation administrator?"
                              : "Make installation administrator?",
                            description: user.is_admin
                              ? `${user.email} will lose installation-wide administration and keep only explicit project memberships.`
                              : `${user.email} will be able to manage all projects, accounts, and credentials.`,
                            confirmLabel: user.is_admin ? "Remove admin" : "Make admin",
                            tone: user.is_admin ? "danger" : "primary",
                          })
                        }
                      >
                        {user.is_admin ? "Remove admin" : "Make admin"}
                      </Button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </TableWrap>
        ) : null}
      </Section>

      <Section title="Projects">
        {projects.loading && !projects.data ? <Loading label="Loading projects" /> : null}
        {projects.data ? (
          <ul className="member-list">
            {projects.data.items.map((project) => (
              <li key={project.id}>
                <span>
                  <Link to={`/projects/${project.id}`}>{project.name}</Link>
                  <div className="cell-sub">
                    <Mono>{project.slug}</Mono> ·{" "}
                    {project.target ? project.target.base_url : "no target policy"}
                  </div>
                </span>
                <span className="row">
                  <span className="badge badge-neutral">{project.counts.builds} builds</span>
                  <span className="badge badge-neutral">{project.counts.runs} runs</span>
                  <span className="badge badge-neutral">{project.counts.open_findings} open</span>
                </span>
              </li>
            ))}
          </ul>
        ) : null}
      </Section>

      <Section title="Audit events">
        {audit.loading && !audit.data ? <Loading label="Loading audit" /> : null}
        {audit.error ? <ErrorState message="Audit could not be loaded." onRetry={audit.refresh} /> : null}
        {audit.data && audit.data.items.length > 0 ? (
          <>
            <TableWrap label="Installation audit">
              <table className="audit-table">
                <thead>
                  <tr>
                    <th scope="col">When</th>
                    <th scope="col">Actor</th>
                    <th scope="col">Action</th>
                    <th scope="col">Target</th>
                  </tr>
                </thead>
                <tbody>
                  {audit.data.items.map((row) => (
                    <tr key={row.id}>
                      <td>
                        <RelativeTime value={row.at} />
                      </td>
                      <td>{row.actor || "system"}</td>
                      <td>
                        <Mono>{row.action}</Mono>
                      </td>
                      <td>
                        {row.target_type} · {row.target_id.slice(0, 16)}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </TableWrap>
            <nav className="pagination" aria-label="Audit pages">
              <span className="small muted">
                {auditTotal} event(s) · page {auditPage + 1} of {auditPages}
              </span>
              <div className="pagination-actions">
                <Button
                  size="sm"
                  disabled={auditPage === 0 || audit.loading}
                  onClick={() => setAuditPage((page) => Math.max(0, page - 1))}
                >
                  Previous
                </Button>
                <Button
                  size="sm"
                  disabled={auditPage + 1 >= auditPages || audit.loading}
                  onClick={() => setAuditPage((page) => page + 1)}
                >
                  Next
                </Button>
              </div>
            </nav>
          </>
        ) : audit.data ? (
          <p className="muted small">No events recorded.</p>
        ) : null}
      </Section>

      <Dialog
        open={userOpen}
        onClose={closeUserDialog}
        title="Provision an account"
        description="Passwords are hashed with Argon2id. Add one membership row per project the account should access."
        footer={
          <>
            <Button onClick={closeUserDialog}>Cancel</Button>
            <Button
              variant="primary"
              busy={busy}
              onClick={() => void createUser()}
              disabled={!email || !name || password.length < 12}
            >
              Create account
            </Button>
          </>
        }
      >
        <div className="grid-2">
          <Field label="Email" htmlFor="admin-email">
            <TextInput id="admin-email" type="email" value={email} onChange={(event) => setEmail(event.target.value)} />
          </Field>
          <Field label="Display name" htmlFor="admin-name">
            <TextInput id="admin-name" value={name} onChange={(event) => setName(event.target.value)} />
          </Field>
        </div>
        <Field
          label="Initial password"
          htmlFor="admin-password"
          hint="At least 12 characters; share through an approved channel."
        >
          <TextInput
            id="admin-password"
            type="password"
            autoComplete="new-password"
            minLength={12}
            value={password}
            onChange={(event) => setPassword(event.target.value)}
          />
        </Field>
        <div className="checkbox-row">
          <input
            id="admin-is-admin"
            type="checkbox"
            checked={isAdmin}
            onChange={(event) => setIsAdmin(event.target.checked)}
          />
          <label htmlFor="admin-is-admin">
            Installation administrator
            <span className="field-hint">
              Off by default. Administrators can access every project; project memberships are not
              required.
            </span>
          </label>
        </div>
        {isAdmin ? (
          <Notice tone="info" title="Administrator account">
            This account bypasses project membership. It can manage every project, account, and
            credential.
          </Notice>
        ) : (
          <MembershipEditor
            projects={projectOptions}
            values={memberships}
            onChange={setMemberships}
            label="Project access"
          />
        )}
        {userError ? <Notice tone="error">{userError}</Notice> : null}
      </Dialog>

      <Dialog
        open={Boolean(resetUser)}
        onClose={() => setResetUser(null)}
        title={`Reset password${resetUser ? ` for ${resetUser.display_name}` : ""}`}
        description="The new password is not shown again. Share it through an approved channel."
        footer={
          <>
            <Button onClick={() => setResetUser(null)}>Cancel</Button>
            <Button variant="primary" busy={busy} onClick={() => void saveReset()}>
              Reset password
            </Button>
          </>
        }
      >
        <Field label="New password" htmlFor="reset-password" hint="At least 12 characters.">
          <TextInput
            id="reset-password"
            type="password"
            autoComplete="new-password"
            value={resetPassword}
            onChange={(event) => setResetPassword(event.target.value)}
          />
        </Field>
        <Field label="Confirm new password" htmlFor="reset-password-confirm">
          <TextInput
            id="reset-password-confirm"
            type="password"
            autoComplete="new-password"
            value={resetConfirm}
            onChange={(event) => setResetConfirm(event.target.value)}
          />
        </Field>
        {resetError ? <Notice tone="error">{resetError}</Notice> : null}
      </Dialog>

      <Dialog
        open={Boolean(accessUser)}
        onClose={() => setAccessUser(null)}
        title={`Project access${accessUser ? ` for ${accessUser.display_name}` : ""}`}
        description="Saving replaces the account's current project memberships."
        footer={
          <>
            <Button onClick={() => setAccessUser(null)}>Cancel</Button>
            <Button variant="primary" busy={busy} onClick={() => void saveAccess()}>
              Save access
            </Button>
          </>
        }
      >
        <MembershipEditor
          projects={projectOptions}
          values={accessMemberships}
          onChange={setAccessMemberships}
          label="Project membership"
        />
        {accessUser?.is_admin ? (
          <Notice tone="info" title="Installation administrator">
            This account already has access to every project; these explicit memberships are
            additional.
          </Notice>
        ) : null}
        {accessError ? <Notice tone="error">{accessError}</Notice> : null}
      </Dialog>

      <ConfirmDialog
        open={Boolean(confirm)}
        title={confirm?.title ?? ""}
        description={confirm?.description ?? ""}
        confirmLabel={confirm?.confirmLabel ?? "Continue"}
        tone={confirm?.tone}
        busy={busy}
        onCancel={() => setConfirm(null)}
        onConfirm={() => void applyConfirmedPatch()}
      />

      <ProjectDialog
        open={projectOpen}
        onClose={() => setProjectOpen(false)}
        onCreated={() => {
          projects.refresh();
          setProjectOpen(false);
        }}
      />
    </div>
  );
}

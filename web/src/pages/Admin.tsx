import { useState } from "react";
import { Link } from "react-router-dom";
import { useApi } from "../auth";
import { api, errorMessage } from "../api";
import type { AdminUser, Project } from "../api";
import {
  Button,
  Dialog,
  ErrorState,
  Field,
  Loading,
  Mono,
  Notice,
  PageHeader,
  RelativeTime,
  Section,
  Select,
  TableWrap,
  TextInput,
  useToast,
} from "../ui";

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

export function AdminPage() {
  const users = useApi<{ items: AdminUser[] }>("/api/admin/users");
  const projects = useApi<{ items: Project[] }>("/api/projects");
  const audit = useApi<{ items: AuditRow[] }>("/api/admin/audit?limit=40");
  const { notify } = useToast();
  const [userOpen, setUserOpen] = useState(false);
  const [projectOpen, setProjectOpen] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const [email, setEmail] = useState("");
  const [name, setName] = useState("");
  const [password, setPassword] = useState("");
  const [isAdmin, setIsAdmin] = useState(false);
  const [membershipProject, setMembershipProject] = useState("");
  const [membershipRole, setMembershipRole] = useState("developer");

  const [projectName, setProjectName] = useState("");
  const [slug, setSlug] = useState("");
  const [description, setDescription] = useState("");
  const [baseUrl, setBaseUrl] = useState("");
  const [origins, setOrigins] = useState("");
  const [prefixes, setPrefixes] = useState("/");
  const [environment, setEnvironment] = useState("staging");
  const [scopeOwner, setScopeOwner] = useState("");
  const [authorization, setAuthorization] = useState("");

  const createUser = async () => {
    setBusy(true);
    setError(null);
    try {
      await api("/api/admin/users", {
        method: "POST",
        body: JSON.stringify({
          email,
          display_name: name,
          password,
          is_admin: isAdmin,
          memberships: membershipProject
            ? [{ project_id: membershipProject, role: membershipRole }]
            : [],
        }),
      });
      notify("success", "Account provisioned with its scoped membership.");
      setUserOpen(false);
      setEmail("");
      setName("");
      setPassword("");
      setIsAdmin(false);
      setMembershipProject("");
      users.refresh();
    } catch (caught) {
      setError(errorMessage(caught));
    } finally {
      setBusy(false);
    }
  };

  const createProject = async () => {
    setBusy(true);
    setError(null);
    try {
      await api("/api/projects", {
        method: "POST",
        body: JSON.stringify({
          name: projectName,
          slug: slug || null,
          description,
          target: {
            base_url: baseUrl,
            allowed_origins: origins
              .split(",")
              .map((item) => item.trim())
              .filter(Boolean),
            path_prefixes: prefixes
              .split(",")
              .map((item) => item.trim())
              .filter(Boolean),
            environment_label: environment,
            scope_owner: scopeOwner,
            authorization_reference: authorization,
            run_limits: { max_depth: "standard", max_replay_checks: 20, max_runs_per_day: 8 },
          },
        }),
      });
      notify("success", "Project registered with its first approved target revision.");
      setProjectOpen(false);
      setProjectName("");
      setSlug("");
      setBaseUrl("");
      setOrigins("");
      setDescription("");
      projects.refresh();
    } catch (caught) {
      setError(errorMessage(caught));
    } finally {
      setBusy(false);
    }
  };

  const patchUser = async (user: AdminUser, patch: Record<string, unknown>) => {
    try {
      await api(`/api/admin/users/${user.id}`, {
        method: "PATCH",
        body: JSON.stringify(patch),
      });
      notify("success", "Account updated.");
      users.refresh();
    } catch (caught) {
      notify("error", errorMessage(caught));
    }
  };

  return (
    <>
      <PageHeader
        title="Administration"
        description="Provision accounts with scoped project roles, register approved project scopes, and review security-relevant events."
        actions={
          <>
            <Button onClick={() => setUserOpen(true)}>New account</Button>
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
                      <Button
                        size="sm"
                        onClick={() => void patchUser(user, { is_active: !user.is_active })}
                      >
                        {user.is_active ? "Disable" : "Enable"}
                      </Button>
                      <Button
                        size="sm"
                        onClick={() => void patchUser(user, { is_admin: !user.is_admin })}
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
        ) : audit.data ? (
          <p className="muted small">No events recorded.</p>
        ) : null}
      </Section>

      <Dialog
        open={userOpen}
        onClose={() => setUserOpen(false)}
        title="Provision an account"
        description="Passwords are hashed with Argon2id. Memberships scope the account to one project; add more in project settings."
        footer={
          <>
            <Button onClick={() => setUserOpen(false)}>Cancel</Button>
            <Button variant="primary" busy={busy} onClick={() => void createUser()} disabled={!email || !password}>
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
        <Field label="Initial password" htmlFor="admin-password" hint="At least 12 characters; share through an approved channel.">
          <TextInput
            id="admin-password"
            type="password"
            autoComplete="new-password"
            minLength={12}
            value={password}
            onChange={(event) => setPassword(event.target.value)}
          />
        </Field>
        <div className="grid-2">
          <Field label="Project" htmlFor="admin-project">
            <Select
              id="admin-project"
              value={membershipProject}
              onChange={(event) => setMembershipProject(event.target.value)}
            >
              <option value="">No project yet</option>
              {(projects.data?.items ?? []).map((project) => (
                <option key={project.id} value={project.id}>
                  {project.name}
                </option>
              ))}
            </Select>
          </Field>
          <Field label="Project role" htmlFor="admin-role">
            <Select
              id="admin-role"
              value={membershipRole}
              onChange={(event) => setMembershipRole(event.target.value)}
            >
              <option value="viewer">Viewer</option>
              <option value="developer">Developer</option>
              <option value="operator">Operator</option>
            </Select>
          </Field>
        </div>
        <div className="checkbox-row">
          <input
            id="admin-is-admin"
            type="checkbox"
            checked={isAdmin}
            onChange={(event) => setIsAdmin(event.target.checked)}
          />
          <label htmlFor="admin-is-admin">Installation administrator</label>
        </div>
        {error ? <Notice tone="error">{error}</Notice> : null}
      </Dialog>

      <Dialog
        open={projectOpen}
        onClose={() => setProjectOpen(false)}
        wide
        title="Register an approved project"
        description="The first target policy revision is created with the project. Runs can only target destinations inside it."
        footer={
          <>
            <Button onClick={() => setProjectOpen(false)}>Cancel</Button>
            <Button
              variant="primary"
              busy={busy}
              onClick={() => void createProject()}
              disabled={!projectName || !baseUrl}
            >
              Create project
            </Button>
          </>
        }
      >
        <div className="grid-2">
          <Field label="Project name" htmlFor="project-name">
            <TextInput id="project-name" value={projectName} onChange={(event) => setProjectName(event.target.value)} />
          </Field>
          <Field label="Slug (optional)" htmlFor="project-slug">
            <TextInput id="project-slug" value={slug} onChange={(event) => setSlug(event.target.value)} />
          </Field>
        </div>
        <Field label="Description" htmlFor="project-description">
          <TextInput
            id="project-description"
            value={description}
            onChange={(event) => setDescription(event.target.value)}
          />
        </Field>
        <Field label="Approved base URL" htmlFor="project-base">
          <TextInput id="project-base" value={baseUrl} onChange={(event) => setBaseUrl(event.target.value)} placeholder="https://staging.example.internal" />
        </Field>
        <div className="grid-2">
          <Field
            label="Allowed origins (comma separated)"
            htmlFor="project-origins"
            hint="Origin only: scheme://host:port. Empty defaults to the base URL."
          >
            <TextInput id="project-origins" value={origins} onChange={(event) => setOrigins(event.target.value)} />
          </Field>
          <Field label="Path restrictions (comma separated)" htmlFor="project-prefixes">
            <TextInput id="project-prefixes" value={prefixes} onChange={(event) => setPrefixes(event.target.value)} />
          </Field>
        </div>
        <div className="grid-2">
          <Field label="Environment label" htmlFor="project-env">
            <TextInput id="project-env" value={environment} onChange={(event) => setEnvironment(event.target.value)} />
          </Field>
          <Field label="Scope owner" htmlFor="project-owner">
            <TextInput id="project-owner" value={scopeOwner} onChange={(event) => setScopeOwner(event.target.value)} />
          </Field>
        </div>
        <Field label="Authorization reference" htmlFor="project-auth">
          <TextInput id="project-auth" value={authorization} onChange={(event) => setAuthorization(event.target.value)} />
        </Field>
        {error ? <Notice tone="error">{error}</Notice> : null}
      </Dialog>
    </>
  );
}

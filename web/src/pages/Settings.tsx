import { useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import { useApi } from "../auth";
import { api, errorMessage } from "../api";
import type { AdminUser, TestAccount } from "../api";
import { useProject } from "./Project";
import {
  Button,
  DefinitionList,
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
  metadata: Record<string, unknown>;
}

export function ProjectSettingsPage() {
  const { project } = useProject();
  const { projectId } = useParams();
  const accounts = useApi<{ items: TestAccount[] }>(`/api/projects/${projectId}/accounts`);
  const audit = useApi<{ items: AuditRow[] }>(
    project.capabilities?.can_operate ? `/api/projects/${projectId}/audit` : null,
  );
  const users = useApi<{ items: AdminUser[] }>(
    project.capabilities?.can_admin ? "/api/admin/users" : null,
  );
  const { notify } = useToast();
  const [targetOpen, setTargetOpen] = useState(false);
  const [memberOpen, setMemberOpen] = useState(false);
  const [accountOpen, setAccountOpen] = useState(false);
  const [rotate, setRotate] = useState<TestAccount | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const [baseUrl, setBaseUrl] = useState(project.target?.base_url ?? "");
  const [origins, setOrigins] = useState((project.target?.allowed_origins ?? []).join(", "));
  const [prefixes, setPrefixes] = useState((project.target?.path_prefixes ?? []).join(", "));
  const [scopeOwner, setScopeOwner] = useState(project.target?.scope_owner ?? "");
  const [authorization, setAuthorization] = useState(project.target?.authorization_reference ?? "");
  const [environment, setEnvironment] = useState(project.target?.environment_label ?? "staging");

  const [memberId, setMemberId] = useState("");
  const [memberRole, setMemberRole] = useState("developer");
  const [accountName, setAccountName] = useState("");
  const [accountRole, setAccountRole] = useState("developer");
  const [accountTenant, setAccountTenant] = useState("");
  const [credential, setCredential] = useState("");
  const [rotateValue, setRotateValue] = useState("");
  const [uploading, setUploading] = useState(false);
  const [uploadResult, setUploadResult] = useState<{ operations: { path: string; method: string }[]; filename: string } | null>(null);

  useEffect(() => {
    if (project.target) {
      setBaseUrl(project.target.base_url);
      setOrigins(project.target.allowed_origins.join(", "));
      setPrefixes(project.target.path_prefixes.join(", "));
      setScopeOwner(project.target.scope_owner);
      setAuthorization(project.target.authorization_reference);
      setEnvironment(project.target.environment_label);
    }
  }, [project.target]);

  const canAdmin = project.capabilities?.can_admin ?? false;

  const createTargetRevision = async () => {
    setBusy(true);
    setError(null);
    try {
      await api(`/api/projects/${project.id}/target-configs`, {
        method: "POST",
        body: JSON.stringify({
          base_url: baseUrl,
          allowed_origins: origins.split(",").map((item) => item.trim()).filter(Boolean),
          path_prefixes: prefixes.split(",").map((item) => item.trim()).filter(Boolean),
          environment_label: environment,
          scope_owner: scopeOwner,
          authorization_reference: authorization,
          run_limits: project.target?.run_limits ?? {},
        }),
      });
      notify("success", "New target policy revision recorded. Queued work is re-validated against it.");
      setTargetOpen(false);
      window.location.reload();
    } catch (caught) {
      setError(errorMessage(caught));
    } finally {
      setBusy(false);
    }
  };

  const addMember = async () => {
    setBusy(true);
    setError(null);
    try {
      await api(`/api/projects/${project.id}/members`, {
        method: "POST",
        body: JSON.stringify({ user_id: memberId, role: memberRole }),
      });
      notify("success", "Membership updated.");
      setMemberOpen(false);
      window.location.reload();
    } catch (caught) {
      setError(errorMessage(caught));
    } finally {
      setBusy(false);
    }
  };

  const createAccount = async () => {
    setBusy(true);
    setError(null);
    try {
      await api(`/api/projects/${project.id}/accounts`, {
        method: "POST",
        body: JSON.stringify({
          name: accountName,
          role_label: accountRole,
          tenant_label: accountTenant,
          credential,
        }),
      });
      notify("success", "Test identity stored with an encrypted credential.");
      setAccountOpen(false);
      setCredential("");
      setAccountName("");
      accounts.refresh();
    } catch (caught) {
      setError(errorMessage(caught));
    } finally {
      setBusy(false);
    }
  };

  const rotateCredential = async () => {
    if (!rotate) return;
    setBusy(true);
    setError(null);
    try {
      await api(`/api/projects/${project.id}/accounts/${rotate.id}/credential`, {
        method: "PATCH",
        body: JSON.stringify({ credential: rotateValue }),
      });
      notify(
        "success",
        "Credential rotated. Queued jobs source credentials at execution time, so no replay can run with the old value.",
      );
      setRotate(null);
      setRotateValue("");
      accounts.refresh();
    } catch (caught) {
      setError(errorMessage(caught));
    } finally {
      setBusy(false);
    }
  };

  const uploadSpec = async (file: File) => {
    setUploading(true);
    setError(null);
    try {
      const form = new FormData();
      form.append("file", file);
      const response = await api<{ filename: string; operations: { path: string; method: string }[] }>(
        `/api/projects/${project.id}/openapi`,
        { method: "POST", body: form },
      );
      setUploadResult(response);
      notify("success", "OpenAPI document validated and sanitized.");
    } catch (caught) {
      setError(errorMessage(caught));
    } finally {
      setUploading(false);
    }
  };

  return (
    <>
      <PageHeader
        title="Project settings"
        description="Approved scope, membership, test identities, and the audit trail. Secrets are stored encrypted and never returned to the browser."
        actions={
          canAdmin ? (
            <Button variant="primary" onClick={() => setTargetOpen(true)}>
              New target revision
            </Button>
          ) : null
        }
      />
      {!canAdmin ? (
        <Notice tone="info" title="Read-only settings">
          Target policy, membership, and credentials are managed by an administrator. Operators can
          review the audit trail.
        </Notice>
      ) : null}

      <div className="two-col">
        <div className="stack">
          <Section title="Approved target policy" description="Immutable revisions; builds bind to the revision recorded when they were registered.">
            {project.target ? (
              <DefinitionList
                items={[
                  { term: "Revision", value: `${project.target.revision}` },
                  { term: "Base URL", value: <Mono>{project.target.base_url}</Mono> },
                  { term: "Origins", value: project.target.allowed_origins.join(", ") },
                  { term: "Path restrictions", value: project.target.path_prefixes.join(", ") || "none" },
                  { term: "Environment", value: project.target.environment_label },
                  { term: "Scope owner", value: project.target.scope_owner || "—" },
                  { term: "Authorization", value: project.target.authorization_reference || "—" },
                  {
                    term: "Run limits",
                    value: <pre className="code code-light" tabIndex={0} role="region" aria-label="Scrollable code excerpt">{JSON.stringify(project.target.run_limits, null, 2)}</pre>,
                  },
                ]}
              />
            ) : (
              <p className="muted">No target policy recorded.</p>
            )}
          </Section>

          <Section title="OpenAPI revision" description="Uploads are parsed offline, size-limited, and rejected when any declared server is outside the approved origin.">
            {canAdmin ? (
              <div className="stack-sm">
                <input
                  className="file-input"
                  type="file"
                  accept=".json,.yaml,.yml"
                  aria-label="Upload OpenAPI document"
                  onChange={(event) => {
                    const file = event.target.files?.[0];
                    if (file) void uploadSpec(file);
                  }}
                />
                {uploading ? <Loading label="Validating document" /> : null}
                {uploadResult ? (
                  <Notice tone="success" title={`${uploadResult.filename} accepted`}>
                    {uploadResult.operations.length} operation(s) recorded.{" "}
                    {uploadResult.operations.slice(0, 6).map((operation) => `${operation.method} ${operation.path}`).join(", ")}
                  </Notice>
                ) : null}
                <p className="small muted">
                  Attach the revision when registering a build. Server URLs declared by the document
                  cannot authorize a destination.
                </p>
              </div>
            ) : (
              <p className="muted small">Only an administrator can upload an API document.</p>
            )}
          </Section>

          <Section title="Test identities" description="Credentials are encrypted with the deployment key and resolved only at execution time.">
            {accounts.loading && !accounts.data ? <Loading label="Loading identities" /> : null}
            {accounts.error ? (
              <ErrorState message="Identities could not be loaded." onRetry={accounts.refresh} />
            ) : null}
            {accounts.data ? (
              <ul className="account-list">
                {accounts.data.items.map((account) => (
                  <li key={account.id}>
                    <span>
                      <strong>{account.name}</strong>
                      <div className="cell-sub">
                        {account.role} {account.tenant ? `· tenant ${account.tenant}` : ""} ·{" "}
                        {account.has_credential ? "credential stored" : "credential missing"}
                      </div>
                    </span>
                    {canAdmin ? (
                      <Button size="sm" onClick={() => setRotate(account)}>
                        Rotate credential
                      </Button>
                    ) : null}
                  </li>
                ))}
                {accounts.data.items.length === 0 ? (
                  <li className="muted small">No test identities configured.</li>
                ) : null}
              </ul>
            ) : null}
            {canAdmin ? (
              <Button size="sm" variant="primary" style={{ marginTop: "0.6rem" }} onClick={() => setAccountOpen(true)}>
                Add test identity
              </Button>
            ) : null}
          </Section>

          <Section title="Audit trail" description="Security-relevant events, newest first.">
            {audit.loading && !audit.data ? <Loading label="Loading audit" /> : null}
            {audit.error ? <ErrorState message="Audit trail could not be loaded." onRetry={audit.refresh} /> : null}
            {audit.data && audit.data.items.length > 0 ? (
              <TableWrap label="Project audit trail">
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
                          {row.target_type} · {row.target_id.slice(0, 12)}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </TableWrap>
            ) : null}
            {audit.data && audit.data.items.length === 0 ? (
              <p className="muted small">No events recorded.</p>
            ) : null}
          </Section>
        </div>

        <div className="stack">
          <Section title="Membership">
            {project.members && project.members.length > 0 ? (
              <ul className="member-list">
                {project.members.map((member) => (
                  <li key={member.user_id}>
                    <span>
                      <strong>{member.display_name || member.email}</strong>
                      <div className="cell-sub">{member.email}</div>
                    </span>
                    <span className="row">
                      <span className="badge badge-neutral">{member.role}</span>
                      {canAdmin ? (
                        <Button
                          size="sm"
                          variant="danger"
                          onClick={async () => {
                            try {
                              await api(
                                `/api/projects/${project.id}/members/${member.user_id}`,
                                { method: "DELETE" },
                              );
                              notify("success", "Membership removed.");
                              window.location.reload();
                            } catch (caught) {
                              notify("error", errorMessage(caught));
                            }
                          }}
                        >
                          Remove
                        </Button>
                      ) : null}
                    </span>
                  </li>
                ))}
              </ul>
            ) : (
              <p className="muted small">No project members recorded.</p>
            )}
            {canAdmin ? (
              <Button size="sm" variant="primary" style={{ marginTop: "0.6rem" }} onClick={() => setMemberOpen(true)}>
                Add or update member
              </Button>
            ) : null}
          </Section>
          <Section title="Execution settings">
            <DefinitionList
              items={[
                { term: "Demo mode", value: "Deterministic fixtures + real lab replay" },
                { term: "Live mode", value: "Requires worker provisioning on the host" },
                { term: "Max runs / day", value: String(project.target?.run_limits.max_runs_per_day ?? 8) },
                { term: "Replay cap", value: String(project.target?.run_limits.max_replay_checks ?? 20) },
                { term: "Depth cap", value: String(project.target?.run_limits.max_depth ?? "standard") },
              ]}
            />
            <p className="small muted" style={{ marginTop: "0.5rem" }}>
              Credential rotation affects queued jobs only at execution time; already-accepted
              evidence is unchanged.
            </p>
          </Section>
        </div>
      </div>

      <Dialog
        open={targetOpen}
        onClose={() => setTargetOpen(false)}
        title="Record a new target policy revision"
        description="Narrowing the policy prevents previously queued work from running outside the current authorization."
        footer={
          <>
            <Button onClick={() => setTargetOpen(false)}>Cancel</Button>
            <Button variant="primary" busy={busy} onClick={() => void createTargetRevision()}>
              Save revision
            </Button>
          </>
        }
      >
        <Field label="Base URL" htmlFor="target-base">
          <TextInput id="target-base" value={baseUrl} onChange={(event) => setBaseUrl(event.target.value)} />
        </Field>
        <Field label="Approved origins (comma separated)" htmlFor="target-origins">
          <TextInput id="target-origins" value={origins} onChange={(event) => setOrigins(event.target.value)} />
        </Field>
        <Field label="Path restrictions (comma separated)" htmlFor="target-prefixes">
          <TextInput id="target-prefixes" value={prefixes} onChange={(event) => setPrefixes(event.target.value)} />
        </Field>
        <div className="grid-2">
          <Field label="Environment label" htmlFor="target-env">
            <TextInput id="target-env" value={environment} onChange={(event) => setEnvironment(event.target.value)} />
          </Field>
          <Field label="Scope owner" htmlFor="target-owner">
            <TextInput id="target-owner" value={scopeOwner} onChange={(event) => setScopeOwner(event.target.value)} />
          </Field>
        </div>
        <Field label="Authorization reference" htmlFor="target-auth">
          <TextInput id="target-auth" value={authorization} onChange={(event) => setAuthorization(event.target.value)} />
        </Field>
        {error ? <Notice tone="error">{error}</Notice> : null}
      </Dialog>

      <Dialog
        open={memberOpen}
        onClose={() => setMemberOpen(false)}
        title="Add or update a member"
        footer={
          <>
            <Button onClick={() => setMemberOpen(false)}>Cancel</Button>
            <Button variant="primary" busy={busy} onClick={() => void addMember()} disabled={!memberId}>
              Save membership
            </Button>
          </>
        }
      >
        <Field label="User" htmlFor="member-user">
          <Select id="member-user" value={memberId} onChange={(event) => setMemberId(event.target.value)}>
            <option value="">Select a user</option>
            {(users.data?.items ?? []).map((user) => (
              <option key={user.id} value={user.id}>
                {user.display_name} · {user.email}
              </option>
            ))}
          </Select>
        </Field>
        <Field label="Project role" htmlFor="member-role">
          <Select id="member-role" value={memberRole} onChange={(event) => setMemberRole(event.target.value)}>
            <option value="viewer">Viewer — read and export</option>
            <option value="developer">Developer — review evidence, run retests</option>
            <option value="operator">Operator — builds, runs, recipes, review verdicts</option>
          </Select>
        </Field>
        {error ? <Notice tone="error">{error}</Notice> : null}
      </Dialog>

      <Dialog
        open={accountOpen}
        onClose={() => setAccountOpen(false)}
        title="Add a test identity"
        description="Use a short-lived, test-only credential. It is encrypted before storage and never returned."
        footer={
          <>
            <Button onClick={() => setAccountOpen(false)}>Cancel</Button>
            <Button
              variant="primary"
              busy={busy}
              onClick={() => void createAccount()}
              disabled={!accountName || !credential}
            >
              Store identity
            </Button>
          </>
        }
      >
        <Field label="Name" htmlFor="account-name">
          <TextInput id="account-name" value={accountName} onChange={(event) => setAccountName(event.target.value)} />
        </Field>
        <div className="grid-2">
          <Field label="Role label" htmlFor="account-role">
            <TextInput id="account-role" value={accountRole} onChange={(event) => setAccountRole(event.target.value)} />
          </Field>
          <Field label="Tenant label" htmlFor="account-tenant">
            <TextInput id="account-tenant" value={accountTenant} onChange={(event) => setAccountTenant(event.target.value)} />
          </Field>
        </div>
        <Field label="Bearer credential" htmlFor="account-credential" hint="Typed into this form over your session; stored encrypted.">
          <TextInput
            id="account-credential"
            type="password"
            autoComplete="off"
            value={credential}
            onChange={(event) => setCredential(event.target.value)}
          />
        </Field>
        {error ? <Notice tone="error">{error}</Notice> : null}
      </Dialog>

      <Dialog
        open={rotate !== null}
        onClose={() => setRotate(null)}
        title={`Rotate credential for ${rotate?.name ?? ""}`}
        footer={
          <>
            <Button onClick={() => setRotate(null)}>Cancel</Button>
            <Button variant="primary" busy={busy} onClick={() => void rotateCredential()} disabled={!rotateValue}>
              Rotate
            </Button>
          </>
        }
      >
        <Field label="New bearer credential" htmlFor="rotate-value">
          <TextInput
            id="rotate-value"
            type="password"
            autoComplete="off"
            value={rotateValue}
            onChange={(event) => setRotateValue(event.target.value)}
          />
        </Field>
        {error ? <Notice tone="error">{error}</Notice> : null}
      </Dialog>
    </>
  );
}

export function SettingsPage() {
  const meta = useApi<{
    app_env: string;
    demo_enabled: boolean;
    live_enabled: boolean;
    live_requires: string[];
    strix_version: string;
    profiles: { code: string; version: number; name: string; scenarios: { code: string; title: string; owasp_refs: string[] }[] }[];
    depths: string[];
    export_formats: string[];
    notice: string;
  }>("/api/system/meta");
  const worker = useApi<{
    queued: number;
    running: number;
    active_runs: number;
    jobs: { id: string; kind: string; state: string; attempts: number; error_code: string | null; claimed_by: string | null }[];
  }>("/api/system/worker", { pollMs: 5000 });

  return (
    <>
      <PageHeader
        title="Settings"
        description="Installation configuration, execution mode, and worker health. Project-specific scope lives in each project."
      />
      <div className="two-col">
        <div className="stack">
          <Section title="Execution mode">
            {meta.loading && !meta.data ? <Loading label="Loading system settings" /> : null}
            {meta.error ? <ErrorState message="System settings could not be loaded." onRetry={meta.refresh} /> : null}
            {meta.data ? (
              <>
                <DefinitionList
                  items={[
                    { term: "Environment", value: `${meta.data.app_env} (deployment label)` },
                    { term: "Demo mode", value: meta.data.demo_enabled ? "enabled" : "disabled" },
                    { term: "Live execution", value: meta.data.live_enabled ? "enabled" : "not provisioned" },
                    { term: "Pinned engine", value: `Strix ${meta.data.strix_version} adapter` },
                    { term: "Export formats", value: meta.data.export_formats.join(", ").toUpperCase() },
                  ]}
                />
                {!meta.data.live_enabled ? (
                  <Notice tone="info" title="Live execution is off">
                    Demo runs stay labelled and are excluded from live comparisons. To enable live
                    execution, provision the worker with:
                    <ul className="steps">
                      {meta.data.live_requires.map((requirement) => (
                        <li key={requirement}>{requirement}</li>
                      ))}
                    </ul>
                  </Notice>
                ) : null}
                <p className="small muted" style={{ marginTop: "0.5rem" }}>
                  {meta.data.notice} The model provider only receives what the worker sends to the
                  engine; keys never reach the browser.
                </p>
                <p className="small muted" style={{ marginTop: "0.35rem" }}>
                  The environment name is a deployment label selected by APP_ENV. It controls
                  deployment behavior, not production parity; compare a production deployment only
                  after separately validating its build, target policy, identities, and coverage.
                </p>
              </>
            ) : null}
          </Section>
          <Section title="Profiles">
            {meta.data?.profiles.map((profile) => (
              <div key={`${profile.code}-${profile.version}`} style={{ marginBottom: "0.8rem" }}>
                <h3>
                  {profile.name} v{profile.version}
                </h3>
                <ul className="steps">
                  {profile.scenarios.map((scenario) => (
                    <li key={scenario.code} className="small">
                      {scenario.title} <span className="muted">({scenario.owasp_refs.join("; ")})</span>
                    </li>
                  ))}
                </ul>
              </div>
            ))}
          </Section>
        </div>
        <div className="stack">
          <Section title="Worker" description="Queued work is claimed with a lease; interrupted work is never silently re-run.">
            {worker.error ? <ErrorState message="Worker status could not be loaded." onRetry={worker.refresh} /> : null}
            {worker.data ? (
              <div className="worker-status">
                <div className="bucket-grid">
                  <div className="bucket">
                    <span className="bucket-label">Queued</span>
                    <span className="bucket-value">{worker.data.queued}</span>
                  </div>
                  <div className="bucket">
                    <span className="bucket-label">Running</span>
                    <span className="bucket-value">{worker.data.running}</span>
                  </div>
                  <div className="bucket">
                    <span className="bucket-label">Active runs</span>
                    <span className="bucket-value">{worker.data.active_runs}</span>
                  </div>
                </div>
                <TableWrap label="Recent jobs">
                  <table className="audit-table">
                    <thead>
                      <tr>
                        <th scope="col">Job</th>
                        <th scope="col">State</th>
                        <th scope="col">Attempts</th>
                      </tr>
                    </thead>
                    <tbody>
                      {worker.data.jobs.map((job) => (
                        <tr key={job.id}>
                          <td>
                            <Mono>{job.id.slice(0, 8)}</Mono> {job.kind}
                          </td>
                          <td>
                            {job.state}
                            {job.error_code ? ` (${job.error_code})` : ""}
                          </td>
                          <td>{job.attempts}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </TableWrap>
                {worker.data.queued > 0 && worker.data.running === 0 ? (
                  <Notice tone="warn" title="No worker heartbeat">
                    Queued jobs are waiting. Start the worker process, then retry the action.
                  </Notice>
                ) : null}
              </div>
            ) : (
              <Loading label="Loading worker status" />
            )}
          </Section>
          <Section title="Deployment notes">
            <ul className="steps small">
              <li>Single-host Compose starts db, api, worker, and web; the lab is a demo profile.</li>
              <li>Keep live execution on an isolated worker with deny-by-default egress.</li>
              <li>Back up the database and the protected artifact volume together.</li>
              <li>Rotate test credentials without rewriting historical evidence.</li>
            </ul>
          </Section>
        </div>
      </div>
    </>
  );
}

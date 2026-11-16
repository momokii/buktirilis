import { useEffect, useMemo, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { useApi } from "../auth";
import { ApiError, api, errorMessage } from "../api";
import type { Project, RunSummary, TestAccount, Build } from "../api";
import { useProject } from "./Project";
import {
  Button,
  Dialog,
  EmptyState,
  ErrorState,
  Field,
  LinkButton,
  Loading,
  ModeBadge,
  Notice,
  PageHeader,
  RelativeTime,
  Select,
  StatusBadge,
  TableWrap,
  TextInput,
  useToast,
} from "../ui";

interface PreflightCheck {
  code: string;
  label: string;
  status: "pass" | "warn" | "fail";
  detail: string;
  recovery: string;
}

interface BlockedScenario {
  code: string;
  title: string;
  reason: string;
}

interface PreflightPreview {
  preflight: {
    ok: boolean;
    checks: PreflightCheck[];
    blocked_scenarios: BlockedScenario[];
    requires_reduced_scope_ack: boolean;
  };
  profile: { name: string; version: number; description: string };
  depth: { name: string; limits: Record<string, unknown>; note: string };
  expected_checks: { scenario_code: string; title: string; owasp_refs: string[]; automatic: boolean; method_note: string }[];
}

export function RunsPage() {
  const { project } = useProject();
  const { projectId } = useParams();
  const [kind, setKind] = useState("");
  const [status, setStatus] = useState("");
  const query = new URLSearchParams();
  if (kind) query.set("kind", kind);
  if (status) query.set("status", status);
  const runs = useApi<{ items: RunSummary[] }>(
    `/api/projects/${projectId}/runs${query.toString() ? `?${query}` : ""}`,
  );
  const [wizardOpen, setWizardOpen] = useState(false);

  return (
    <>
      <PageHeader
        title="Runs"
        description="Every assessment binds to a build, profile version, depth, and identity selection. Queued work is re-authorised before dispatch."
        actions={
          project.capabilities?.can_operate ? (
            <Button variant="primary" onClick={() => setWizardOpen(true)}>
              New run
            </Button>
          ) : null
        }
      />
      <div className="filters">
        <Field label="Kind" htmlFor="filter-kind">
          <Select id="filter-kind" value={kind} onChange={(event) => setKind(event.target.value)}>
            <option value="">All kinds</option>
            <option value="baseline">Baseline</option>
            <option value="release_scan">Release scan</option>
          </Select>
        </Field>
        <Field label="Status" htmlFor="filter-status">
          <Select id="filter-status" value={status} onChange={(event) => setStatus(event.target.value)}>
            <option value="">All statuses</option>
            <option value="queued">Queued</option>
            <option value="running">Running</option>
            <option value="completed">Completed</option>
            <option value="failed">Failed</option>
            <option value="canceled">Canceled</option>
            <option value="interrupted">Interrupted</option>
          </Select>
        </Field>
      </div>
      {runs.loading && !runs.data ? <Loading label="Loading runs" /> : null}
      {runs.error ? <ErrorState message="Runs could not be loaded." onRetry={runs.refresh} /> : null}
      {runs.data && runs.data.items.length === 0 ? (
        <EmptyState
          title="No runs match"
          action={
            project.capabilities?.can_operate ? (
              <Button variant="primary" onClick={() => setWizardOpen(true)}>
                Start a baseline
              </Button>
            ) : undefined
          }
        >
          A project's first assessment is a baseline. Release scans compare against an earlier
          completed run.
        </EmptyState>
      ) : null}
      {runs.data && runs.data.items.length > 0 ? (
        <TableWrap label="Runs">
          <table>
            <thead>
              <tr>
                <th scope="col">Run</th>
                <th scope="col">Build</th>
                <th scope="col">Status</th>
                <th scope="col">Coverage</th>
                <th scope="col">Started</th>
                <th scope="col">Completed</th>
                <th scope="col">
                  <span className="visually-hidden">Actions</span>
                </th>
              </tr>
            </thead>
            <tbody>
              {runs.data.items.map((run) => (
                <tr key={run.id}>
                  <td>
                    <Link to={`/projects/${project.id}/runs/${run.id}`}>
                      {run.kind.replace(/_/g, " ")} · {run.depth}
                    </Link>
                    <div className="cell-sub">
                      {run.profile.code} v{run.profile.version} ·{" "}
                      {run.counts ? `${run.counts.records} finding record(s)` : "no findings yet"}
                    </div>
                  </td>
                  <td>
                    {run.build?.label ?? "—"}
                    <div className="cell-sub">
                      <ModeBadge mode={run.mode} />
                    </div>
                  </td>
                  <td>
                    <StatusBadge status={run.status} />
                    {run.failure_reason ? (
                      <div className="reason-note">{run.failure_reason}</div>
                    ) : null}
                  </td>
                  <td>
                    {run.coverage_complete ? (
                      <span className="badge badge-pass">Complete</span>
                    ) : (
                      <span className="badge badge-warn">Incomplete</span>
                    )}
                  </td>
                  <td>
                    <RelativeTime value={run.started_at ?? run.created_at} />
                  </td>
                  <td>
                    <RelativeTime value={run.completed_at} />
                  </td>
                  <td className="actions">
                    <LinkButton to={`/projects/${project.id}/runs/${run.id}`} size="sm">
                      Open report
                    </LinkButton>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </TableWrap>
      ) : null}
      <RunWizard
        open={wizardOpen}
        onClose={() => setWizardOpen(false)}
        project={project}
        runs={runs.data?.items ?? []}
        onCreated={() => {
          setWizardOpen(false);
          runs.refresh();
        }}
      />
    </>
  );
}

function RunWizard({
  open,
  onClose,
  project,
  runs,
  onCreated,
}: {
  open: boolean;
  onClose: () => void;
  project: Project;
  runs: RunSummary[];
  onCreated: () => void;
}) {
  const builds = useApi<{ items: Build[] }>(open ? `/api/projects/${project.id}/builds` : null);
  const accounts = useApi<{ items: TestAccount[] }>(open ? `/api/projects/${project.id}/accounts` : null);
  const navigate = useNavigate();
  const { notify } = useToast();
  const [buildId, setBuildId] = useState("");
  const [kind, setKind] = useState<"baseline" | "release_scan">("baseline");
  const [depth, setDepth] = useState("quick");
  const [selected, setSelected] = useState<string[]>([]);
  const [unauthenticated, setUnauthenticated] = useState(false);
  const [baselineRunId, setBaselineRunId] = useState("");
  const [discoveryRoutes, setDiscoveryRoutes] = useState("");
  const [ack, setAck] = useState(false);
  const [preview, setPreview] = useState<PreflightPreview | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const completedRuns = useMemo(
    () => runs.filter((run) => run.status === "completed" && run.mode === (runs[0]?.mode ?? "demo")),
    [runs],
  );

  useEffect(() => {
    if (!open) return;
    setPreview(null);
    setError(null);
    setAck(false);
    setDiscoveryRoutes("");
    setBuildId((current) => current || builds.data?.items[0]?.id || "");
    if (accounts.data) {
      setSelected(accounts.data.items.map((account) => account.id));
    }
    setBaselineRunId((current) => current || completedRuns[0]?.id || "");
  }, [open, builds.data, accounts.data, completedRuns]);

  const payload = useMemo(
    () => ({
      build_id: buildId,
      kind,
      depth,
      profile_code: "web-api-access-control",
      profile_version: 1,
      account_ids: unauthenticated ? [] : selected,
      unauthenticated,
      baseline_run_id: kind === "release_scan" ? baselineRunId || null : null,
      discovery_routes: discoveryRoutes
        .split(/[\n,]/)
        .map((route) => route.trim())
        .filter(Boolean),
    }),
    [buildId, kind, depth, selected, unauthenticated, baselineRunId, discoveryRoutes],
  );

  const runPreflight = async () => {
    setBusy(true);
    setError(null);
    try {
      const response = await api<PreflightPreview>(`/api/projects/${project.id}/runs/preflight`, {
        method: "POST",
        body: JSON.stringify(payload),
      });
      setPreview(response);
    } catch (caught) {
      setError(errorMessage(caught));
    } finally {
      setBusy(false);
    }
  };

  const submit = async () => {
    setBusy(true);
    setError(null);
    try {
      const response = await api<{ run: RunSummary; created: boolean; message: string }>(
        `/api/projects/${project.id}/runs`,
        { method: "POST", body: JSON.stringify({ ...payload, accept_reduced_scope: ack }) },
      );
      notify("success", response.message);
      onCreated();
      navigate(`/projects/${project.id}/runs/${response.run.id}`);
    } catch (caught) {
      if (caught instanceof ApiError && caught.status === 409) {
        const detail = caught.payload as { detail?: { blocked_scenarios?: BlockedScenario[]; checks?: PreflightCheck[]; message?: string } };
        setError(detail.detail?.message ?? errorMessage(caught));
        setAck(false);
      } else if (caught instanceof ApiError && caught.status === 422) {
        const detail = caught.payload as { detail?: { message?: string; checks?: PreflightCheck[]; blocked_scenarios?: BlockedScenario[] } };
        setError(detail.detail?.message ?? "Preflight failed.");
      } else {
        setError(errorMessage(caught));
      }
    } finally {
      setBusy(false);
    }
  };

  const checkList = preview?.preflight.checks ?? [];
  const blocked = preview?.preflight.blocked_scenarios ?? [];
  const needsAck = preview?.preflight.requires_reduced_scope_ack ?? false;

  return (
    <Dialog
      open={open}
      onClose={onClose}
      wide
      title="Request an assessment run"
      description="Initialize the scope, verify prerequisites, and review the limits before submission."
      footer={
        <>
          <Button onClick={onClose}>Cancel</Button>
          <Button busy={busy} onClick={() => void runPreflight()} disabled={!buildId}>
            Check prerequisites
          </Button>
          <Button
            variant="primary"
            busy={busy}
            onClick={() => void submit()}
            disabled={!buildId || (needsAck && !ack)}
          >
            Queue run
          </Button>
        </>
      }
    >
      <div className="grid-2">
        <Field label="Build" htmlFor="run-build">
          <Select
            id="run-build"
            value={buildId}
            onChange={(event) => setBuildId(event.target.value)}
          >
            {(builds.data?.items ?? []).map((build) => (
              <option key={build.id} value={build.id}>
                {build.label}
              </option>
            ))}
          </Select>
        </Field>
        <Field label="Run kind" htmlFor="run-kind">
          <Select
            id="run-kind"
            value={kind}
            onChange={(event) => setKind(event.target.value as "baseline" | "release_scan")}
          >
            <option value="baseline">Baseline assessment</option>
            <option value="release_scan">Release scan (verify known + discover)</option>
          </Select>
        </Field>
        <Field
          label="Depth"
          htmlFor="run-depth"
          hint="Depth sets exploration effort and resource limits; spend can overshoot the cap."
        >
          <Select id="run-depth" value={depth} onChange={(event) => setDepth(event.target.value)}>
            <option value="quick">Quick — bounded</option>
            <option value="standard">Standard — full profile coverage</option>
          </Select>
        </Field>
        <Field label="Profile" htmlFor="run-profile">
          <TextInput id="run-profile" value="Web & API Access Control v1" readOnly />
        </Field>
      </div>
      {kind === "release_scan" ? (
        <Field
          label="Comparison baseline"
          htmlFor="run-baseline"
          hint="The release scan replays known findings against this baseline snapshot."
        >
          <Select
            id="run-baseline"
            value={baselineRunId}
            onChange={(event) => setBaselineRunId(event.target.value)}
          >
            <option value="">Select a completed run</option>
            {completedRuns.map((run) => (
              <option key={run.id} value={run.id}>
                {run.kind.replace(/_/g, " ")} · {run.build?.label} ·{" "}
                {new Date(run.completed_at ?? run.created_at).toLocaleString()}
              </option>
            ))}
          </Select>
        </Field>
      ) : null}

      <Field
        label="Operator-selected discovery routes (optional)"
        htmlFor="run-discovery-routes"
        hint="One relative path per line or comma separated. These augment OpenAPI-diff candidates."
      >
        <textarea
          id="run-discovery-routes"
          className="input"
          value={discoveryRoutes}
          onChange={(event) => setDiscoveryRoutes(event.target.value)}
          placeholder="/api/exports/{invoice_id}/pdf"
        />
      </Field>

      <fieldset>
        <legend>Test identities</legend>
        <div className="checkbox-row">
          <input
            id="run-unauth"
            type="checkbox"
            checked={unauthenticated}
            onChange={(event) => setUnauthenticated(event.target.checked)}
          />
          <label htmlFor="run-unauth">
            Deliberately run unauthenticated
            <span className="field-hint">
              Scenarios that need authenticated identities are shown as blocked and require
              reduced-scope confirmation.
            </span>
          </label>
        </div>
        {unauthenticated ? null : (
          <div style={{ marginTop: "0.4rem" }}>
            {(accounts.data?.items ?? []).map((account) => (
              <div className="checkbox-row" key={account.id}>
                <input
                  id={`account-${account.id}`}
                  type="checkbox"
                  checked={selected.includes(account.id)}
                  onChange={(event) =>
                    setSelected((current) =>
                      event.target.checked
                        ? [...current, account.id]
                        : current.filter((id) => id !== account.id),
                    )
                  }
                />
                <label htmlFor={`account-${account.id}`}>
                  {account.name}
                  <span className="field-hint">
                    {account.role}
                    {account.tenant ? ` · tenant ${account.tenant}` : ""} · credential sourced at
                    execution time
                  </span>
                </label>
              </div>
            ))}
            {accounts.data?.items.length === 0 ? (
              <p className="muted small">
                No test identities are configured. An administrator adds them in project settings.
              </p>
            ) : null}
          </div>
        )}
      </fieldset>

      {error ? (
        <Notice tone="error" title="Cannot queue this run">
          {error}
        </Notice>
      ) : null}
      {preview ? (
        <div className="stack-sm">
          <div className="spread">
            <strong>Preflight</strong>
            <span className={`badge ${preview.preflight.ok ? "badge-pass" : "badge-fail"}`}>
              {preview.preflight.ok ? "ready" : "blocked"}
            </span>
          </div>
          <ul className="activity-list" tabIndex={0} aria-label="Preflight check results">
            {checkList.map((check) => (
              <li key={check.code}>
                <span
                  className={`badge ${check.status === "pass" ? "badge-pass" : check.status === "warn" ? "badge-warn" : "badge-fail"}`}
                >
                  {check.status}
                </span>{" "}
                <strong>{check.label}</strong> — {check.detail}
                {check.recovery ? <div className="reason-note">{check.recovery}</div> : null}
              </li>
            ))}
          </ul>
          {blocked.length > 0 ? (
            <div className="notice notice-warn">
              <div>
                <strong>Reduced scope</strong>
                <ul className="steps" style={{ marginTop: "0.3rem" }}>
                  {blocked.map((scenario) => (
                    <li key={scenario.code}>
                      {scenario.title}: {scenario.reason}
                    </li>
                  ))}
                </ul>
              </div>
            </div>
          ) : null}
          {needsAck ? (
            <div className="checkbox-row">
              <input
                id="run-ack"
                type="checkbox"
                checked={ack}
                onChange={(event) => setAck(event.target.checked)}
              />
              <label htmlFor="run-ack">
                I understand this run covers a reduced scenario set
              </label>
            </div>
          ) : null}
          <p className="small muted">
            Depth {preview.depth.name}: {JSON.stringify(preview.depth.limits)}. {preview.depth.note}
          </p>
          <details>
            <summary className="small">Expected scenarios</summary>
            <ul className="steps">
              {preview.expected_checks.map((check) => (
                <li key={check.scenario_code}>
                  <strong>{check.title}</strong> — {check.method_note}{" "}
                  <span className="muted">{check.owasp_refs.join("; ")}</span>
                </li>
              ))}
            </ul>
          </details>
        </div>
      ) : null}
    </Dialog>
  );
}

export function RunsIndexPage() {
  const projects = useApi<{ items: Project[] }>("/api/projects");
  return (
    <>
      <PageHeader title="Runs" description="Recent assessments across the projects you can access." />
      {projects.loading ? <Loading label="Loading projects" /> : null}
      {projects.error ? (
        <ErrorState message="Projects could not be loaded." onRetry={projects.refresh} />
      ) : null}
      {projects.data?.items.map((project) => (
        <ProjectRunPreview key={project.id} project={project} />
      ))}
    </>
  );
}

function ProjectRunPreview({ project }: { project: Project }) {
  const runs = useApi<{ items: RunSummary[] }>(`/api/projects/${project.id}/runs?limit=5`);
  return (
    <section className="section" aria-label={`Runs for ${project.name}`}>
      <div className="section-header">
        <h2>
          <Link to={`/projects/${project.id}`}>{project.name}</Link>
        </h2>
        <LinkButton to={`/projects/${project.id}/runs`} size="sm">
          All runs
        </LinkButton>
      </div>
      {runs.loading && !runs.data ? <Loading label="Loading runs" /> : null}
      {runs.error ? <ErrorState message="Runs could not be loaded." onRetry={runs.refresh} /> : null}
      {runs.data && runs.data.items.length === 0 ? (
        <p className="muted small">No runs recorded for this project yet.</p>
      ) : null}
      {runs.data && runs.data.items.length > 0 ? (
        <ul className="member-list">
          {runs.data.items.map((run) => (
            <li key={run.id}>
              <span>
                <Link to={`/projects/${project.id}/runs/${run.id}`}>
                  {run.kind.replace(/_/g, " ")} · {run.build?.label}
                </Link>
                <div className="cell-sub">
                  {run.depth} · {run.mode} · <RelativeTime value={run.started_at ?? run.created_at} />
                </div>
              </span>
              <span className="row">
                <StatusBadge status={run.status} />
                {run.coverage_complete ? (
                  <span className="badge badge-pass">coverage complete</span>
                ) : (
                  <span className="badge badge-warn">incomplete coverage</span>
                )}
              </span>
            </li>
          ))}
        </ul>
      ) : null}
    </section>
  );
}

import { createContext, useContext } from "react";
import { Link, NavLink, Outlet, useParams } from "react-router-dom";
import { useApi } from "../auth";
import type { Project, RunSummary } from "../api";
import {
  Breadcrumbs,
  EmptyState,
  ErrorState,
  LinkButton,
  Loading,
  Notice,
  PageHeader,
  RelativeTime,
  StatusBadge,
  TableWrap,
} from "../ui";

interface ProjectContextValue {
  project: Project;
  reload: () => void;
}

const ProjectContext = createContext<ProjectContextValue | null>(null);

export function useProject(): ProjectContextValue {
  const context = useContext(ProjectContext);
  if (!context) throw new Error("useProject must be used inside ProjectLayout");
  return context;
}

export function ProjectLayout() {
  const { projectId } = useParams();
  const { data, error, loading, refresh } = useApi<Project>(projectId ? `/api/projects/${projectId}` : null);

  if (loading && !data) return <Loading label="Loading project" />;
  if (error) return <ErrorState message="This project could not be loaded." onRetry={refresh} />;
  if (!data) return null;

  return (
    <ProjectContext.Provider value={{ project: data, reload: refresh }}>
      <Breadcrumbs items={[{ label: "Projects", to: "/projects" }, { label: data.name }]} />
      <div className="project-bar">
        <div className="row">
          <span className="eyebrow">
            {data.target?.environment_label ?? "no environment"} · target revision{" "}
            {data.target?.revision ?? "—"}
          </span>
          <span className="badge badge-neutral">{data.role}</span>
          {data.target ? (
            <>
              <code className="mono">{data.target.base_url}</code>
              {data.target.path_prefixes.length > 0 ? (
                <span className="muted small">paths: {data.target.path_prefixes.join(", ")}</span>
              ) : null}
            </>
          ) : (
            <span className="badge badge-warn">No approved target</span>
          )}
        </div>
        <strong className="project-bar-name">{data.name}</strong>
      </div>
      <ProjectTabs projectId={data.id} />
      <Outlet context={{ project: data, reload: refresh } satisfies ProjectContextValue} />
    </ProjectContext.Provider>
  );
}

function ProjectTabs({ projectId }: { projectId: string }) {
  const tabs = [
    { to: `/projects/${projectId}`, label: "Overview", end: true },
    { to: `/projects/${projectId}/builds`, label: "Builds" },
    { to: `/projects/${projectId}/runs`, label: "Runs" },
    { to: `/projects/${projectId}/compare`, label: "Compare" },
    { to: `/projects/${projectId}/settings`, label: "Settings" },
  ];
  return (
    <nav className="tablist" aria-label="Project sections" style={{ marginBottom: "1rem" }}>
      {tabs.map((tab) => (
        <NavLink
          key={tab.to}
          to={tab.to}
          end={tab.end}
          className={({ isActive }) => `tab ${isActive ? "tab-active" : ""}`}
        >
          {tab.label}
        </NavLink>
      ))}
    </nav>
  );
}

export function ProjectOverview() {
  const { project } = useProject();
  const runs = useApi<{ items: RunSummary[] }>(`/api/projects/${project.id}/runs?limit=6`);
  const latest = runs.data?.items?.[0] ?? null;
  const completed = runs.data?.items?.filter((run) => run.status === "completed") ?? [];
  const capabilities = project.capabilities;

  return (
    <div className="stack">
      <PageHeader
        title={project.name}
        description={project.description || "No project description recorded."}
        meta={
          <>
            <span>{project.counts.builds} builds</span>
            <span className="sep">·</span>
            <span>{project.counts.runs} runs</span>
            <span className="sep">·</span>
            <span>{project.counts.open_findings} open findings</span>
          </>
        }
      />
      <div className="counts-row" aria-label="Project totals">
        <Link className="stat stat-link" to={`/projects/${project.id}/builds`}>
          <span className="stat-label">Builds</span>
          <span className="stat-value">{project.counts.builds}</span>
          <span className="stat-hint">recorded deployments</span>
        </Link>
        <Link className="stat stat-link" to={`/projects/${project.id}/runs`}>
          <span className="stat-label">Runs</span>
          <span className="stat-value">{project.counts.runs}</span>
          <span className="stat-hint">assessments and release scans</span>
        </Link>
        <div className="stat">
          <span className="stat-label">Open findings</span>
          <span className="stat-value">{project.counts.open_findings}</span>
          <span className="stat-hint">distinct project-level records</span>
        </div>
        <div className="stat stat-info">
          <span className="stat-label">Comparison readiness</span>
          <span className="stat-value">{completed.length >= 2 ? "Ready" : "Baseline first"}</span>
          <span className="stat-hint">
            {completed.length >= 2
              ? "two completed runs can be compared"
              : "a completed run is the first baseline"}
          </span>
        </div>
      </div>

      <div className="two-col">
        <section className="section" aria-labelledby="recent-runs">
          <div className="section-header">
            <div>
              <h2 id="recent-runs">Recent runs</h2>
              <p className="section-description">
                Each run binds to one approved build and its recorded configuration revision.
              </p>
            </div>
            <LinkButton to={`/projects/${project.id}/runs`} size="sm">
              All runs
            </LinkButton>
          </div>
          {runs.loading && !runs.data ? <Loading label="Loading runs" /> : null}
          {runs.error ? <ErrorState message="Runs could not be loaded." onRetry={runs.refresh} /> : null}
          {runs.data && runs.data.items.length === 0 ? (
            <EmptyState
              title="No runs yet"
              action={
                capabilities?.can_operate ? (
                  <LinkButton to={`/projects/${project.id}/runs`} variant="primary" size="sm">
                    Start the first baseline
                  </LinkButton>
                ) : undefined
              }
            >
              The first assessment in a project is a baseline. Intended deep links and evidence
              appear only after a run records them.
            </EmptyState>
          ) : null}
          {runs.data && runs.data.items.length > 0 ? (
            <TableWrap label="Recent runs">
              <table>
                <thead>
                  <tr>
                    <th scope="col">Run</th>
                    <th scope="col">Build</th>
                    <th scope="col">Status</th>
                    <th scope="col">Started</th>
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
                          {run.mode === "demo" ? "Demo" : "Live"} · {run.profile.code} v
                          {run.profile.version}
                        </div>
                      </td>
                      <td>{run.build?.label ?? "—"}</td>
                      <td>
                        <StatusBadge status={run.status} />
                      </td>
                      <td>
                        <RelativeTime value={run.started_at ?? run.created_at} />
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </TableWrap>
          ) : null}
        </section>

        <div className="stack">
          <section className="section" aria-labelledby="scope-summary">
            <h2 id="scope-summary">Approved scope</h2>
            {project.target ? (
              <dl className="meta-list" style={{ marginTop: "0.6rem" }}>
                <div>
                  <dt>Base URL</dt>
                  <dd>
                    <code className="mono">{project.target.base_url}</code>
                  </dd>
                </div>
                <div>
                  <dt>Origins</dt>
                  <dd>{project.target.allowed_origins.join(", ")}</dd>
                </div>
                <div>
                  <dt>Path restrictions</dt>
                  <dd>
                    {project.target.path_prefixes.length > 0
                      ? project.target.path_prefixes.join(", ")
                      : "none"}
                  </dd>
                </div>
                <div>
                  <dt>Scope owner</dt>
                  <dd>{project.target.scope_owner || "—"}</dd>
                </div>
                <div>
                  <dt>Authorization</dt>
                  <dd>{project.target.authorization_reference || "—"}</dd>
                </div>
                <div>
                  <dt>Depth cap</dt>
                  <dd>{String(project.target.run_limits.max_depth ?? "standard")}</dd>
                </div>
              </dl>
            ) : (
              <p className="muted">No approved target policy.</p>
            )}
          </section>
          <section className="section" aria-labelledby="what-next">
            <h2 id="what-next">What to do next</h2>
            {latest ? (
              <p style={{ marginTop: "0.5rem" }}>
                Open the latest report for build{" "}
                <strong>{latest.build?.label ?? "unknown"}</strong> to review findings, coverage,
                and open evidence.{" "}
                <Link to={`/projects/${project.id}/runs/${latest.id}`}>Open report</Link>.
              </p>
            ) : (
              <p style={{ marginTop: "0.5rem" }}>
                Register an approved build, prepare test identities, and queue a baseline.
              </p>
            )}
            {project.counts.runs > 0 && completed.length < 2 ? (
              <Notice tone="info" title="Comparison needs two runs">
                This project has no second completed run yet, so comparisons remain unavailable
                until a later build is assessed.
              </Notice>
            ) : null}
          </section>
        </div>
      </div>
      {capabilities && !capabilities.can_operate ? (
        <Notice tone="info" title="Read-only access">
          Your role can review evidence and export reports. Starting runs and retests requires an
          operator or developer role.
        </Notice>
      ) : null}
    </div>
  );
}

import { useEffect, useMemo, useRef, useState } from "react";
import { Link, useParams, useSearchParams } from "react-router-dom";
import { useApi } from "../auth";
import { api, errorMessage } from "../api";
import type {
  CoverageReport,
  ExportRow,
  Overview,
  ReportFinding,
  RunDetail,
} from "../api";
import { useProject } from "./Project";
import {
  Breadcrumbs,
  Button,
  CoverageBadge,
  ErrorState,
  EvidenceBadge,
  LinkButton,
  Loading,
  MethodBadge,
  ModeBadge,
  Mono,
  Notice,
  RelativeTime,
  Section,
  SeverityBadge,
  Stat,
  StatusBadge,
  TableWrap,
  Tabs,
  VerdictBadge,
  useToast,
} from "../ui";

const BUCKET_LABELS: Record<string, string> = {
  fix_verified: "Fixes verified on this build",
  still_reproducible: "Previously known, still reproducible",
  newly_observed: "Newly observed",
  regressed: "Regressions",
  awaiting_verification: "Awaiting verification",
  needs_validation: "Needs validation",
  incomparable: "Incomparable",
};

const VERIFICATION_LABELS: Record<string, string> = {
  fix_verified: "Fix verified",
  still_reproducible: "Still reproducible",
  inconclusive: "Inconclusive",
  awaiting_retest: "Awaiting retest",
};

function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

export function ReportPage() {
  const { project, reload: reloadProject } = useProject();
  const { runId } = useParams();
  const [params, setParams] = useSearchParams();
  const tab = params.get("tab") ?? "overview";
  const run = useApi<RunDetail>(runId ? `/api/projects/${project.id}/runs/${runId}` : null, {
    pollMs:
      tab === "overview"
        ? 0
        : 0,
  });
  const active = run.data && ["queued", "running", "cancel_requested"].includes(run.data.status);
  const progress = useApi<RunDetail["progress"]>(
    runId && active ? `/api/projects/${project.id}/runs/${runId}/progress` : null,
    { pollMs: 2500 },
  );
  const overview = useApi<Overview>(
    runId && run.data && tab === "overview"
      ? `/api/projects/${project.id}/runs/${runId}/report/overview`
      : null,
  );
  const { notify } = useToast();
  const [exporting, setExporting] = useState(false);
  const exportsList = useApi<{ items: ExportRow[] }>(
    runId ? `/api/projects/${project.id}/runs/${runId}/exports` : null,
  );

  useEffect(() => {
    if (!active) return;
    const timer = window.setInterval(() => run.refresh(), 2500);
    return () => window.clearInterval(timer);
  }, [active, run]);

  useEffect(() => {
    if (run.data && !active && run.data.status === "completed") {
      reloadProject();
    }
  }, [run.data?.status, active, reloadProject, run.data]);

  if (run.loading && !run.data) return <Loading label="Loading report" />;
  if (run.error) return <ErrorState message="This run could not be loaded." onRetry={run.refresh} />;
  if (!run.data) return null;

  const current = run.data;
  const stageRows = progress.data?.stages ?? current.progress.stages;
  const activities = progress.data?.activities ?? current.progress.activities;

  const setTab = (next: string) => {
    const updated = new URLSearchParams(params);
    updated.set("tab", next);
    setParams(updated, { replace: false });
  };

  const createExport = async (format: "pdf" | "csv" | "json") => {
    setExporting(true);
    try {
      const response = await api<{ exports: ExportRow[]; message: string }>(
        `/api/projects/${project.id}/runs/${current.id}/exports`,
        { method: "POST", body: JSON.stringify({ format }) },
      );
      notify("success", response.message);
      exportsList.refresh();
      const first = response.exports[0];
      if (first) {
        window.location.assign(first.download_url);
      }
    } catch (caught) {
      notify("error", errorMessage(caught));
    } finally {
      setExporting(false);
    }
  };

  const cancelRun = async () => {
    try {
      await api(`/api/projects/${project.id}/runs/${current.id}/cancel`, { method: "POST" });
      notify("info", "Cancellation requested. The worker stops at the next stage boundary.");
      run.refresh();
    } catch (caught) {
      notify("error", errorMessage(caught));
    }
  };

  return (
    <>
      <Breadcrumbs
        items={[
          { label: "Projects", to: "/projects" },
          { label: project.name, to: `/projects/${project.id}` },
          { label: "Runs", to: `/projects/${project.id}/runs` },
          { label: `${current.kind.replace(/_/g, " ")} · ${current.build?.label ?? ""}` },
        ]}
      />
      <header className="report-header">
        <div className="report-title-row">
          <div>
            <div className="eyebrow">
              {current.kind.replace(/_/g, " ")} report · {project.name}
            </div>
            <h1>
              Build {current.build?.label ?? "unknown"}{" "}
              <span className="muted" style={{ fontWeight: 400, fontSize: "0.9rem" }}>
                {current.build?.commit_sha ? `· ${current.build.commit_sha.slice(0, 12)}` : ""}
              </span>
            </h1>
            <div className="report-meta">
              <StatusBadge status={current.status} />
              <ModeBadge mode={current.mode} />
              <span className="sep">·</span>
              <span>{current.depth} depth</span>
              <span className="sep">·</span>
              <span>
                {current.profile.code} v{current.profile.version}
              </span>
              <span className="sep">·</span>
              <span>
                {current.engine} {current.engine_version}
              </span>
              <span className="sep">·</span>
              <span>
                Started <RelativeTime value={current.started_at} />
              </span>
              <span className="sep">·</span>
              <span>
                Completed <RelativeTime value={current.completed_at} />
              </span>
              {current.coverage_complete ? (
                <span className="badge badge-pass">Coverage complete</span>
              ) : (
                <span className="badge badge-warn">Coverage incomplete</span>
              )}
            </div>
          </div>
          <div className="page-actions">
            {active ? (
              <Button variant="danger" onClick={() => void cancelRun()}>
                Cancel run
              </Button>
            ) : null}
            <Button
              variant="secondary"
              busy={exporting}
              onClick={() => void createExport("pdf")}
              disabled={current.status !== "completed"}
            >
              Export PDF
            </Button>
            <Button
              onClick={() => void createExport("csv")}
              disabled={current.status !== "completed"}
            >
              CSV
            </Button>
            <Button
              onClick={() => void createExport("json")}
              disabled={current.status !== "completed"}
            >
              JSON
            </Button>
            <LinkButton to={`/projects/${project.id}/compare?current=${current.id}`} variant="secondary">
              Compare builds
            </LinkButton>
          </div>
        </div>
        {current.summary ? <p className="report-summary">{current.summary}</p> : null}
      </header>

      {active ? (
        <Section title="Live progress" description="Grounded in recorded stage transitions and worker activity.">
          <div className="progress-list">
            {stageRows.map((stage) => (
              <div className="progress-stage" key={stage.code}>
                <span className="mono">{stage.code.replace(/_/g, " ")}</span>
                <span>
                  <CoverageBadge
                    result={
                      stage.state === "done"
                        ? "tested_no_finding"
                        : stage.state === "failed"
                          ? "blocked"
                          : stage.state === "skipped"
                            ? "not_run"
                            : "planned"
                    }
                  />{" "}
                  {stage.detail || "—"}
                </span>
                <span className="elapsed muted">
                  {stage.finished_at ? <RelativeTime value={stage.finished_at} /> : "in progress"}
                </span>
              </div>
            ))}
          </div>
          <ul className="activity-list" tabIndex={0} aria-label="Run activity" style={{ marginTop: "0.6rem" }}>
            {activities.map((activity, index) => (
              <li key={`${activity.at}-${index}`}>
                <time>{new Date(activity.at).toLocaleTimeString()}</time>
                {activity.message}
              </li>
            ))}
          </ul>
        </Section>
      ) : null}

      {current.status === "failed" || current.status === "interrupted" || current.status === "canceled" ? (
        <Notice
          tone={current.status === "canceled" ? "info" : "error"}
          title={`Run ${current.status.replace(/_/g, " ")}`}
          action={
            project.capabilities?.can_operate ? (
              <LinkButton to={`/projects/${project.id}/runs`} size="sm">
                Request a new run
              </LinkButton>
            ) : null
          }
        >
          {current.failure_reason ?? "No failure detail was recorded."}{" "}
          {current.ingest_state !== "complete"
            ? "Partial results, if any, stay visible with an incomplete label."
            : null}
        </Notice>
      ) : null}

      {current.status === "completed" ? (
        <>
          <div className="counts-row" aria-label="Report counts">
            {(["critical", "high", "medium", "low", "info"] as const).map((severity) => (
              <Stat
                key={severity}
                label={severity}
                value={current.counts.severity[severity] ?? 0}
                tone={severity === "critical" || severity === "high" ? "fail" : undefined}
                to={`?tab=findings&severity=${severity}`}
                hint="open findings"
              />
            ))}
            <Stat
              label="Awaiting verification"
              value={overview.data?.counts.awaiting_verification ?? "—"}
              tone="warn"
              to="?tab=findings&outcome=awaiting_retest"
            />
            <Stat
              label="Needs validation"
              value={overview.data?.counts.needs_validation ?? "—"}
              tone="warn"
              to="?tab=findings&method=pending_evidence_review"
            />
            <Stat
              label="Coverage"
              value={`${current.counts.coverage.counts.tested_no_finding + current.counts.coverage.counts.finding_observed}/${current.counts.coverage.denominator}`}
              to="?tab=coverage"
              hint="planned checks with a result"
            />
          </div>

          <Tabs
            label="Report sections"
            value={tab}
            onChange={setTab}
            items={[
              { id: "overview", label: "Overview" },
              { id: "findings", label: "Findings", count: current.counts.records },
              { id: "coverage", label: "Coverage & methodology" },
            ]}
          >
            {tab === "overview" ? (
              <OverviewTab
                projectId={project.id}
                run={current}
                overview={overview}
                onRetestRefresh={() => {
                  overview.refresh();
                  run.refresh();
                }}
              />
            ) : null}
            {tab === "findings" ? (
              <FindingsTab
                projectId={project.id}
                run={current}
                canDevelop={project.capabilities?.can_develop ?? false}
              />
            ) : null}
            {tab === "coverage" ? <CoverageTab projectId={project.id} runId={current.id} /> : null}
          </Tabs>

          <Section
            title="Exports"
            description="Each export freezes the run snapshot. Later retests or reviews require a new export."
          >
            {exportsList.data && exportsList.data.items.length > 0 ? (
              <TableWrap label="Exports">
                <table>
                  <thead>
                    <tr>
                      <th scope="col">Format</th>
                      <th scope="col">Scope</th>
                      <th scope="col">Created</th>
                      <th scope="col" className="col-wide">Size</th>
                      <th scope="col" className="col-wide">SHA-256</th>
                      <th scope="col">
                        <span className="visually-hidden">Download</span>
                      </th>
                    </tr>
                  </thead>
                  <tbody>
                    {exportsList.data.items.map((row) => (
                      <tr key={row.id}>
                        <td>{row.format.replace(/_/g, " ")}</td>
                        <td>{row.scope}</td>
                        <td>
                          <RelativeTime value={row.created_at} compact />
                        </td>
                        <td className="col-wide">{formatBytes(row.size_bytes)}</td>
                        <td className="col-wide">
                          <Mono>{row.sha256.slice(0, 12)}…</Mono>
                        </td>
                        <td className="actions">
                          <a className="btn btn-secondary btn-sm btn-link" href={row.download_url}>
                            Download
                          </a>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </TableWrap>
            ) : (
              <p className="muted small">No export snapshot has been generated for this run.</p>
            )}
            {exportsList.error ? (
              <ErrorState message="Export history could not be loaded." onRetry={exportsList.refresh} />
            ) : null}
          </Section>
        </>
      ) : null}
    </>
  );
}

function OverviewTab({
  projectId,
  run,
  overview,
  onRetestRefresh,
}: {
  projectId: string;
  run: RunDetail;
  overview: ReturnType<typeof useApi<Overview>>;
  onRetestRefresh: () => void;
}) {
  const data = overview.data;
  if (overview.loading && !data) return <Loading label="Loading overview" />;
  if (overview.error) return <ErrorState message="Overview could not be loaded." onRetry={overview.refresh} />;
  if (!data) return null;
  const totalChecks = data.coverage.denominator;
  const tested = (data.coverage.counts.tested_no_finding ?? 0) + (data.coverage.counts.finding_observed ?? 0);
  return (
    <div className="stack">
      {data.zero_findings_message ? (
        <Notice tone={run.coverage_complete ? "success" : "warn"} title="No open findings">
          {data.zero_findings_message}
        </Notice>
      ) : null}
      <div className="two-col">
        <div className="stack">
          <Section title="Risk and work remaining" description={data.summary}>
            <TableWrap label="Severity breakdown">
              <table>
                <caption className="visually-hidden">
                  Open findings by severity; each row links to the matching findings filter.
                </caption>
                <thead>
                  <tr>
                    <th scope="col">Severity</th>
                    <th scope="col">Open findings</th>
                    <th scope="col" className="col-wide">
                      Records
                    </th>
                  </tr>
                </thead>
                <tbody>
                  {(["critical", "high", "medium", "low", "info"] as const).map((severity) => (
                    <tr key={severity}>
                      <td>
                        <SeverityBadge severity={severity} />
                      </td>
                      <td>
                        <Link to={`?tab=findings&severity=${severity}`}>
                          {data.severity[severity] ?? 0}
                        </Link>
                      </td>
                      <td className="col-wide">
                        {run.counts.severity[severity] ?? 0} record(s) in this run
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </TableWrap>
            <div className="row" style={{ marginTop: "0.6rem" }}>
              <span className="badge badge-warn">{data.counts.awaiting_verification} awaiting verification</span>
              <span className="badge badge-warn">{data.counts.needs_validation} need validation</span>
              <span className="badge badge-pending">{data.counts.guided_pending} guided or review</span>
            </div>
          </Section>

          {data.comparison ? (
            <Section
              title="Compared with the baseline"
              description={`Baseline build ${data.comparison.baseline_build_id.slice(0, 8)} · changes are labelled against that snapshot.`}
            >
              <div className="bucket-grid">
                {Object.entries(BUCKET_LABELS).map(([bucket, label]) => (
                  <Link
                    key={bucket}
                    className={`bucket bucket-${bucket}`}
                    to={`?tab=findings&bucket=${bucket}`}
                  >
                    <span className="bucket-label">{label}</span>
                    <span className="bucket-value">{data.comparison?.bucket_counts[bucket] ?? 0}</span>
                  </Link>
                ))}
              </div>
              {data.comparison.scope.limitations.length > 0 ? (
                <ul className="steps" style={{ marginTop: "0.6rem" }}>
                  {data.comparison.scope.limitations.map((limitation) => (
                    <li key={limitation} className="small muted">
                      {limitation}
                    </li>
                  ))}
                </ul>
              ) : null}
              <div className="row" style={{ marginTop: "0.6rem" }}>
                <LinkButton
                  size="sm"
                  to={`/projects/${projectId}/compare?baseline=${data.comparison.baseline_run_id}&current=${run.id}`}
                >
                  Open release comparison
                </LinkButton>
              </div>
            </Section>
          ) : (
            <Notice tone="info" title="No comparison selected">
              This run has no earlier baseline, or comparison is unavailable. The first assessment
              in a project is the baseline; select a completed earlier run to compare.
            </Notice>
          )}

          <Section title="Latest verification" description="Evidence recorded after this run's snapshot is labelled separately.">
            {data.latest_verification.length === 0 ? (
              <p className="muted small">No later verification has been recorded for this build.</p>
            ) : (
              <TableWrap label="Latest verification">
                <table>
                  <thead>
                    <tr>
                      <th scope="col">Finding</th>
                      <th scope="col">Outcome</th>
                      <th scope="col">Observed</th>
                    </tr>
                  </thead>
                  <tbody>
                    {data.latest_verification.map((row) => (
                      <tr key={row.finding_id}>
                        <td>
                          <Link to={`/projects/${projectId}/findings/${row.finding_id}?run=${run.id}`}>
                            {row.public_id} — {row.title}
                          </Link>
                        </td>
                        <td>
                          <VerdictBadge outcome={row.outcome} />
                        </td>
                        <td>
                          <RelativeTime value={row.observed_at} compact />
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </TableWrap>
            )}
          </Section>
        </div>
        <div className="stack">
          <Section title="Coverage limitations">
            {run.limitations.length === 0 ? (
              <p className="muted small">No limitations recorded.</p>
            ) : (
              <ul className="steps">
                {run.limitations.map((limitation) => (
                  <li key={limitation} className="small">
                    {limitation}
                  </li>
                ))}
              </ul>
            )}
          </Section>
          <Section title="Coverage snapshot">
            <div className="bucket-grid">
              <div className="bucket">
                <span className="bucket-label">Tested</span>
                <span className="bucket-value">{tested}</span>
              </div>
              <div className="bucket">
                <span className="bucket-label">Planned checks</span>
                <span className="bucket-value">{totalChecks}</span>
              </div>
              <div className="bucket">
                <span className="bucket-label">Unknown coverage</span>
                <span className="bucket-value">{data.coverage.unknown}</span>
              </div>
            </div>
            <p className="small muted" style={{ marginTop: "0.5rem" }}>
              A denominator covers only the defined planned set. Reaching a route during recon does
              not count as testing it.
            </p>
            <div className="row" style={{ marginTop: "0.5rem" }}>
              <LinkButton to="?tab=coverage" size="sm">
                Inspect checks
              </LinkButton>
              <Button size="sm" onClick={onRetestRefresh}>
                Refresh counts
              </Button>
            </div>
          </Section>
          <Section title="Run provenance">
            <dl className="meta-list">
              <div>
                <dt>Requested by</dt>
                <dd>{run.requested_by || "—"}</dd>
              </div>
              <div>
                <dt>Engine</dt>
                <dd>
                  {run.engine} {run.engine_version}
                </dd>
              </div>
              <div>
                <dt>Mode</dt>
                <dd>
                  <ModeBadge mode={run.mode} />
                </dd>
              </div>
              <div>
                <dt>Build identity</dt>
                <dd>
                  {run.build?.identity.expected ? (
                    <Mono>{run.build.identity.expected}</Mono>
                  ) : (
                    "not recorded"
                  )}
                </dd>
              </div>
              <div>
                <dt>Ingest state</dt>
                <dd>{run.ingest_state}</dd>
              </div>
            </dl>
          </Section>
        </div>
      </div>
    </div>
  );
}

const scrollPositions = new Map<string, number>();

function FindingsTab({
  projectId,
  run,
  canDevelop,
}: {
  projectId: string;
  run: RunDetail;
  canDevelop: boolean;
}) {
  const [params, setParams] = useSearchParams();
  const { notify } = useToast();
  const listKey = `${projectId}:${run.id}:${params.toString()}`;
  const restored = useRef(false);
  const query = useMemo(() => {
    const copy = new URLSearchParams();
    for (const key of ["severity", "outcome", "method", "surface", "q", "sort", "bucket"]) {
      const value = params.get(key);
      if (value) copy.set(key, value);
    }
    if (!copy.get("sort")) copy.set("sort", "severity");
    return copy.toString();
  }, [params]);
  const findings = useApi<{
    items: ReportFinding[];
    total: number;
    filtered: number;
    facets: { severity: string[]; outcome: string[]; method: string[] };
  }>(`/api/projects/${projectId}/runs/${run.id}/report/findings?${query}`);
  const [busyId, setBusyId] = useState<string | null>(null);

  useEffect(() => {
    if (restored.current) return;
    const saved = scrollPositions.get(listKey);
    if (saved !== undefined) {
      window.scrollTo({ top: saved });
      restored.current = true;
    }
  }, [listKey]);

  useEffect(() => {
    return () => {
      scrollPositions.set(listKey, window.scrollY);
    };
  }, [listKey]);

  const update = (key: string, value: string) => {
    const next = new URLSearchParams(params);
    if (value) next.set(key, value);
    else next.delete(key);
    next.set("tab", "findings");
    setParams(next, { replace: true });
  };

  const bucket = params.get("bucket");
  const items = (findings.data?.items ?? []).filter((item) =>
    bucket ? item.bucket === bucket : true,
  );

  const retest = async (finding: ReportFinding) => {
    setBusyId(finding.id);
    try {
      await api(`/api/projects/${projectId}/findings/${finding.id}/retests`, {
        method: "POST",
        body: JSON.stringify({ build_id: run.build?.id }),
      });
      notify("success", `Retest queued for ${finding.public_id}. The worker records the outcome here.`);
      findings.refresh();
    } catch (caught) {
      notify("error", errorMessage(caught));
    } finally {
      setBusyId(null);
    }
  };

  const detailLink = (finding: ReportFinding) => {
    const back = new URLSearchParams(params);
    back.set("tab", "findings");
    return `/projects/${projectId}/runs/${run.id}/findings/${finding.id}?${back.toString()}`;
  };

  const actionFor = (finding: ReportFinding) => {
    if (finding.disposition !== "open") {
      return (
        <Link className="btn btn-secondary btn-sm btn-link" to={detailLink(finding)}>
          Open
        </Link>
      );
    }
    if (finding.retest_method === "automatic") {
      return (
        <Button size="sm" variant="primary" busy={busyId === finding.id} onClick={() => void retest(finding)}>
          Retest
        </Button>
      );
    }
    if (finding.retest_method === "guided") {
      return (
        <Link className="btn btn-primary btn-sm btn-link" to={`${detailLink(finding)}&retest=guided#guided`}>
          Guided retest
        </Link>
      );
    }
    return (
      <Link className="btn btn-primary btn-sm btn-link" to={`${detailLink(finding)}#verify`}>
        Review evidence
      </Link>
    );
  };

  return (
    <div className="stack">
      <div className="filters">
        <div className="field field-search">
          <label htmlFor="findings-search">Search</label>
          <input
            id="findings-search"
            className="input"
            type="search"
            defaultValue={params.get("q") ?? ""}
            placeholder="Title or finding ID"
            onKeyDown={(event) => {
              if (event.key === "Enter") update("q", (event.target as HTMLInputElement).value);
            }}
          />
        </div>
        <div className="field">
          <label htmlFor="findings-severity">Severity</label>
          <select
            id="findings-severity"
            className="input select"
            value={params.get("severity") ?? ""}
            onChange={(event) => update("severity", event.target.value)}
          >
            <option value="">All severities</option>
            {(findings.data?.facets.severity ?? []).map((value) => (
              <option key={value} value={value}>
                {value}
              </option>
            ))}
          </select>
        </div>
        <div className="field">
          <label htmlFor="findings-outcome">Verification</label>
          <select
            id="findings-outcome"
            className="input select"
            value={params.get("outcome") ?? ""}
            onChange={(event) => update("outcome", event.target.value)}
          >
            <option value="">All outcomes</option>
            {Object.entries(VERIFICATION_LABELS).map(([value, label]) => (
              <option key={value} value={value}>
                {label}
              </option>
            ))}
          </select>
        </div>
        <div className="field">
          <label htmlFor="findings-method">Retest method</label>
          <select
            id="findings-method"
            className="input select"
            value={params.get("method") ?? ""}
            onChange={(event) => update("method", event.target.value)}
          >
            <option value="">All methods</option>
            <option value="automatic">Automatic replay</option>
            <option value="guided">Guided retest</option>
            <option value="pending_evidence_review">Review evidence</option>
          </select>
        </div>
        <div className="field">
          <label htmlFor="findings-surface">Affected surface</label>
          <input
            id="findings-surface"
            className="input"
            defaultValue={params.get("surface") ?? ""}
            placeholder="/api/invoices"
            onBlur={(event) => update("surface", event.target.value)}
            onKeyDown={(event) => {
              if (event.key === "Enter") update("surface", (event.target as HTMLInputElement).value);
            }}
          />
        </div>
        <div className="field">
          <label htmlFor="findings-sort">Sort</label>
          <select
            id="findings-sort"
            className="input select"
            value={params.get("sort") ?? "severity"}
            onChange={(event) => update("sort", event.target.value)}
          >
            <option value="severity">Severity</option>
            <option value="title">Title</option>
            <option value="outcome">Verification state</option>
            <option value="last_attempt">Last attempt</option>
          </select>
        </div>
      </div>

      <div className="filter-summary" role="status">
        Showing {items.length} of {findings.data?.total ?? 0} finding records
        {bucket ? ` · bucket: ${BUCKET_LABELS[bucket] ?? bucket}` : ""}
        {params.get("severity") ? ` · severity ${params.get("severity")}` : ""}
        {params.get("outcome") ? ` · ${VERIFICATION_LABELS[params.get("outcome") ?? ""] ?? params.get("outcome")}` : ""}
        {bucket ? (
          <Button size="sm" variant="ghost" onClick={() => update("bucket", "")}>
            Clear bucket
          </Button>
        ) : null}
      </div>

      {findings.loading && !findings.data ? <Loading label="Loading findings" /> : null}
      {findings.error ? (
        <ErrorState message="Findings could not be loaded." onRetry={findings.refresh} />
      ) : null}
      {items.length === 0 && findings.data ? (
        <div className="state state-empty">
          <h3>No findings match these filters</h3>
          <p>Clear a filter or open the coverage tab to inspect what was actually checked.</p>
        </div>
      ) : null}

      {items.length > 0 ? (
        <>
          <div className="desktop-table">
            <TableWrap label="Findings">
              <table>
                <thead>
                  <tr>
                    <th scope="col">Finding</th>
                    <th scope="col">Severity</th>
                    <th scope="col">Verification</th>
                    <th scope="col">Retest</th>
                    <th scope="col">Last attempt</th>
                    <th scope="col">
                      <span className="visually-hidden">Action</span>
                    </th>
                  </tr>
                </thead>
                <tbody>
                  {items.map((finding) => (
                    <tr key={finding.id}>
                      <td className="wrap">
                        <div className="finding-row-title">
                          <Link to={detailLink(finding)}>{finding.title}</Link>
                        </div>
                        <div className="cell-sub">
                          <Mono>{finding.public_id}</Mono> · {finding.scope_summary} ·{" "}
                          {finding.actors_summary}
                        </div>
                        <div className="row" style={{ marginTop: "0.3rem" }}>
                          <EvidenceBadge status={finding.evidence_status} />
                          {finding.disposition !== "open" ? (
                            <span className="badge badge-neutral">{finding.disposition}</span>
                          ) : null}
                        </div>
                      </td>
                      <td>
                        <SeverityBadge severity={finding.severity} />
                      </td>
                      <td>
                        <VerdictBadge outcome={finding.verification.outcome} />
                        {finding.verification.reason &&
                        finding.verification.outcome !== "fix_verified" &&
                        finding.verification.outcome !== "still_reproducible" ? (
                          <div className="reason-note">{finding.verification.reason}</div>
                        ) : null}
                        {finding.verification.stale ? (
                          <div className="reason-note">Stale verification — fresh evidence required.</div>
                        ) : null}
                      </td>
                      <td>
                        <MethodBadge method={finding.retest_method} />
                      </td>
                      <td>
                        <RelativeTime value={finding.last_attempt_at} />
                      </td>
                      <td className="actions">{actionFor(finding)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </TableWrap>
          </div>
          <ul className="finding-mobile-list" aria-label="Findings">
            {items.map((finding) => (
              <li key={finding.id} className="finding-mobile-item">
                <div className="finding-mobile-top">
                  <SeverityBadge severity={finding.severity} />
                  <VerdictBadge outcome={finding.verification.outcome} />
                </div>
                <Link className="finding-mobile-title" to={detailLink(finding)}>
                  {finding.title}
                </Link>
                <div className="finding-mobile-meta">
                  {finding.public_id} · {finding.last_attempt_at ? (
                    <RelativeTime value={finding.last_attempt_at} />
                  ) : (
                    "no attempt yet"
                  )}
                </div>
                {finding.verification.reason ? (
                  <div className="finding-mobile-meta">{finding.verification.reason}</div>
                ) : null}
                <div className="finding-mobile-actions">{actionFor(finding)}</div>
              </li>
            ))}
          </ul>
        </>
      ) : null}
      {!canDevelop ? (
        <Notice tone="info">
          Your role can review evidence and download exports. A developer role is required to start
          retests.
        </Notice>
      ) : null}
    </div>
  );
}

function CoverageTab({ projectId, runId }: { projectId: string; runId: string }) {
  const coverage = useApi<CoverageReport>(`/api/projects/${projectId}/runs/${runId}/report/coverage`);
  if (coverage.loading && !coverage.data) return <Loading label="Loading coverage" />;
  if (coverage.error)
    return <ErrorState message="Coverage could not be loaded." onRetry={coverage.refresh} />;
  const data = coverage.data;
  if (!data) return null;
  const counts = data.coverage.counts;
  return (
    <div className="stack">
      {!data.coverage_complete ? (
        <Notice tone="warn" title="Coverage is incomplete">
          This report cannot be read as a fully covered assessment. Rows marked not run, blocked, or
          needs review are gaps, not passes.
        </Notice>
      ) : null}
      <Section
        title="Coverage summary"
        description="A denominator covers only the defined planned checks; unknown coverage stays unknown."
      >
        <div className="bucket-grid">
          {[
            ["tested_no_finding", "Tested — no finding"],
            ["finding_observed", "Finding observed"],
            ["blocked", "Blocked"],
            ["not_run", "Not run"],
            ["not_applicable", "Not applicable"],
            ["needs_review", "Needs review"],
          ].map(([key, label]) => (
            <div className="bucket" key={key}>
              <span className="bucket-label">{label}</span>
              <span className="bucket-value">{counts[key] ?? 0}</span>
            </div>
          ))}
          <div className="bucket">
            <span className="bucket-label">Planned checks</span>
            <span className="bucket-value">{data.coverage.denominator}</span>
          </div>
        </div>
      </Section>

      <Section title="Recorded checks" description="One row per planned or recorded execution, with its result and reason.">
        <TableWrap label="Coverage checks">
          <table>
            <thead>
              <tr>
                <th scope="col">Scenario</th>
                <th scope="col">Surface</th>
                <th scope="col">Actor</th>
                <th scope="col">Approach</th>
                <th scope="col">Source</th>
                <th scope="col">Result</th>
              </tr>
            </thead>
            <tbody>
              {data.checks.map((check) => (
                <tr key={check.id}>
                  <td>
                    <span className="cell-title">{check.scenario_title}</span>
                    <div className="cell-sub">
                      {check.stage} · {check.scenario_code}
                      {check.owasp_refs.length > 0 ? ` · ${check.owasp_refs.join("; ")}` : ""}
                    </div>
                  </td>
                  <td>
                    {check.surface ? <Mono>{check.surface}</Mono> : "—"}
                    {check.method ? <div className="cell-sub">{check.method}</div> : null}
                  </td>
                  <td>{check.actor || "—"}</td>
                  <td className="wrap">
                    {check.approach || "—"}
                    {check.result_detail ? <div className="reason-note">{check.result_detail}</div> : null}
                  </td>
                  <td>{check.source}</td>
                  <td>
                    <CoverageBadge result={check.result} />
                    {check.finding_public_id ? (
                      <div className="cell-sub">
                        <Link to={`/projects/${projectId}/findings/${check.finding_id}?run=${runId}`}>
                          {check.finding_public_id}
                        </Link>
                      </div>
                    ) : null}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </TableWrap>
      </Section>

      {data.methodology.release_plan ? (
        <Section
          title="Release scan plan"
          description="The candidate set and eligible recipes snapshotted when this release scan was submitted."
        >
          {(() => {
            const plan = data.methodology.release_plan as {
              candidates?: {
                public_id: string;
                severity: string;
                action: string;
                reason: string;
                previous_outcome?: string;
                outcome?: string;
              }[];
              openapi_diff?: {
                available: boolean;
                reason: string;
                added: string[];
                changed: string[];
                removed: string[];
              };
              discovery_candidates?: { method: string; route: string; reason: string }[];
              discovery_rationale?: string;
              budget?: Record<string, unknown>;
            };
            return (
              <>
                {plan.openapi_diff ? (
                  <div className="stack-sm">
                    <h3>OpenAPI operation changes</h3>
                    {!plan.openapi_diff.available ? (
                      <p className="muted small">{plan.openapi_diff.reason}</p>
                    ) : (
                      <div className="bucket-grid">
                        <div className="bucket">
                          <span className="bucket-label">Added</span>
                          <span className="bucket-value">{plan.openapi_diff.added.length}</span>
                        </div>
                        <div className="bucket">
                          <span className="bucket-label">Changed</span>
                          <span className="bucket-value">{plan.openapi_diff.changed.length}</span>
                        </div>
                        <div className="bucket">
                          <span className="bucket-label">Removed</span>
                          <span className="bucket-value">{plan.openapi_diff.removed.length}</span>
                        </div>
                      </div>
                    )}
                    {plan.openapi_diff.added.length + plan.openapi_diff.changed.length > 0 ? (
                      <ul className="inline-code-list">
                        {[...plan.openapi_diff.added, ...plan.openapi_diff.changed].map((operation) => (
                          <li key={operation}>
                            <Mono>{operation}</Mono>
                          </li>
                        ))}
                      </ul>
                    ) : null}
                    {plan.discovery_rationale ? (
                      <p className="small muted">{plan.discovery_rationale}</p>
                    ) : null}
                  </div>
                ) : null}
                {plan.discovery_candidates && plan.discovery_candidates.length > 0 ? (
                  <div className="stack-sm">
                    <h3>Discovery candidates</h3>
                    <ul className="inline-code-list">
                      {plan.discovery_candidates.map((candidate) => (
                        <li key={`${candidate.method}-${candidate.route}`}>
                          <Mono>
                            {candidate.method} {candidate.route}
                          </Mono>{" "}
                          <span className="muted small">({candidate.reason})</span>
                        </li>
                      ))}
                    </ul>
                  </div>
                ) : null}
                <TableWrap label="Release scan candidates">
                  <table>
                    <thead>
                      <tr>
                        <th scope="col">Finding</th>
                        <th scope="col">Severity</th>
                        <th scope="col">Planned action</th>
                        <th scope="col">Reason</th>
                      </tr>
                    </thead>
                    <tbody>
                      {(plan.candidates ?? []).map((candidate) => (
                        <tr key={candidate.public_id}>
                          <td>{candidate.public_id}</td>
                          <td>
                            <SeverityBadge severity={candidate.severity} />
                          </td>
                          <td>{candidate.action.replace(/_/g, " ")}</td>
                          <td>{candidate.reason || candidate.outcome || "queued within the plan"}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </TableWrap>
              </>
            );
          })()}
        </Section>
      ) : null}

      {data.methodology.prerequisite_probe ? (
        <Section
          title="Prerequisite probes"
          description="Identity and fixture checks performed by the worker before discovery."
        >
          {data.methodology.prerequisite_probe.blocked_scenarios &&
          data.methodology.prerequisite_probe.blocked_scenarios.length > 0 ? (
            <Notice tone="warn" title="Blocked scenarios">
              <ul className="steps">
                {data.methodology.prerequisite_probe.blocked_scenarios.map((scenario) => (
                  <li key={scenario.code}>
                    <strong>{scenario.title}</strong> — {scenario.reason}
                  </li>
                ))}
              </ul>
            </Notice>
          ) : null}
          <div className="grid-2">
            <div>
              <h3>Identities</h3>
              {data.methodology.prerequisite_probe.accounts.length === 0 ? (
                <p className="muted small">
                  {data.methodology.prerequisite_probe.unauthenticated
                    ? "Unauthenticated run (operator selected)."
                    : "No authenticated identities selected."}
                </p>
              ) : (
                <ul className="steps">
                  {data.methodology.prerequisite_probe.accounts.map((account) => (
                    <li key={account.name} className="small">
                      <span className={`badge ${account.ok ? "badge-pass" : "badge-fail"}`}>
                        {account.ok ? "pass" : "fail"}
                      </span>{" "}
                      {account.name} — {account.detail}
                    </li>
                  ))}
                </ul>
              )}
            </div>
            <div>
              <h3>Fixtures</h3>
              {data.methodology.prerequisite_probe.fixtures.length === 0 ? (
                <p className="muted small">No recipe fixtures were required.</p>
              ) : (
                <ul className="steps">
                  {data.methodology.prerequisite_probe.fixtures.map((fixture) => (
                    <li key={`${fixture.revision}-${fixture.name}`} className="small">
                      <span className={`badge ${fixture.ok ? "badge-pass" : "badge-fail"}`}>
                        {fixture.ok ? "pass" : "fail"}
                      </span>{" "}
                      recipe r{fixture.revision} · {fixture.name} — {fixture.detail}
                    </li>
                  ))}
                </ul>
              )}
            </div>
          </div>
        </Section>
      ) : null}

      <div className="two-col">
        <Section title="Surface inventory" description="Reaching a route during recon lists it here; testing requires a recorded check.">
          {data.surfaces.length === 0 ? (
            <p className="muted small">No surface inventory was recorded.</p>
          ) : (
            <TableWrap label="Surfaces">
              <table>
                <thead>
                  <tr>
                    <th scope="col">Route</th>
                    <th scope="col">Source</th>
                    <th scope="col">Tested</th>
                  </tr>
                </thead>
                <tbody>
                  {data.surfaces.map((surface) => (
                    <tr key={surface.route}>
                      <td>
                        <Mono>{surface.route}</Mono>
                      </td>
                      <td>{surface.source}</td>
                      <td>
                        {surface.tested ? (
                          <span className="badge badge-pass">check recorded</span>
                        ) : (
                          <span className="badge badge-neutral">inventory only</span>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </TableWrap>
          )}
        </Section>
        <div className="stack">
          <Section title="Methodology">
            <dl className="meta-list">
              <div>
                <dt>Profile</dt>
                <dd>
                  {data.methodology.profile.name} v{data.methodology.profile.version}
                </dd>
              </div>
              <div>
                <dt>Depth</dt>
                <dd>
                  {data.methodology.depth} — {String(data.methodology.depth_limits.description ?? "")}
                </dd>
              </div>
              <div>
                <dt>Base URL</dt>
                <dd>
                  <Mono>{String(data.methodology.scope.base_url ?? "—")}</Mono>
                </dd>
              </div>
              <div>
                <dt>Path restrictions</dt>
                <dd>{String((data.methodology.scope.path_prefixes as string[] | undefined)?.join(", ") ?? "none")}</dd>
              </div>
              <div>
                <dt>Identity mode</dt>
                <dd>
                  {data.methodology.scope.unauthenticated
                    ? "unauthenticated (operator selected)"
                    : "authenticated test identities"}
                </dd>
              </div>
              <div>
                <dt>Build identity</dt>
                <dd>{String(data.methodology.scope.build_identity ?? "not recorded")}</dd>
              </div>
            </dl>
          </Section>
          <Section title="Reference scenarios">
            <ul className="steps">
              {data.methodology.profile.scenarios
                .filter((scenario) => Array.isArray((scenario as { owasp_refs?: string[] }).owasp_refs))
                .map((scenario) => {
                  const typed = scenario as {
                    code: string;
                    title: string;
                    owasp_refs: string[];
                    automatic_eligible: boolean;
                    method_note: string;
                  };
                  return (
                    <li key={typed.code} className="small">
                      <strong>{typed.title}</strong>
                      {typed.automatic_eligible ? " (automatic)" : " (guided)"} — {typed.method_note}
                      <div className="muted">{typed.owasp_refs.join("; ")}</div>
                    </li>
                  );
                })}
            </ul>
          </Section>
          <Section title="Limitations">
            {data.limitations.length === 0 ? (
              <p className="muted small">No limitations recorded.</p>
            ) : (
              <ul className="steps">
                {data.limitations.map((limitation) => (
                  <li key={limitation} className="small">
                    {limitation}
                  </li>
                ))}
              </ul>
            )}
          </Section>
        </div>
      </div>
    </div>
  );
}

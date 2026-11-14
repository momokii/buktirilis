import { useMemo } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { useApi } from "../auth";
import type { CompareResponse, CompareRow } from "../api";
import { useProject } from "./Project";
import {
  Button,
  ErrorState,
  Field,
  LinkButton,
  Loading,
  Mono,
  Notice,
  PageHeader,
  RelativeTime,
  Section,
  Select,
  SeverityBadge,
  TableWrap,
  VerdictBadge,
} from "../ui";

const BUCKET_LABELS: Record<string, string> = {
  fix_verified: "Fix verified",
  still_reproducible: "Still reproducible",
  newly_observed: "Newly observed",
  regressed: "Regressed",
  awaiting_verification: "Awaiting verification",
  needs_validation: "Needs validation",
  incomparable: "Incomparable",
};

export function ComparePage() {
  const { project } = useProject();
  const [params, setParams] = useSearchParams();
  const baseline = params.get("baseline") ?? "";
  const current = params.get("current") ?? "";
  const bucket = params.get("bucket") ?? "";
  const query = new URLSearchParams();
  if (baseline) query.set("baseline_run_id", baseline);
  if (current) query.set("current_run_id", current);
  const compare = useApi<CompareResponse>(
    `/api/projects/${project.id}/compare?${query.toString()}`,
  );

  const rows = useMemo(() => {
    const items = compare.data?.rows ?? [];
    return bucket ? items.filter((row) => row.bucket === bucket) : items;
  }, [compare.data, bucket]);

  const update = (key: string, value: string) => {
    const next = new URLSearchParams(params);
    if (value) next.set(key, value);
    else next.delete(key);
    setParams(next, { replace: true });
  };

  if (compare.loading && !compare.data) return <Loading label="Loading comparison" />;
  if (compare.error)
    return <ErrorState message="The comparison could not be loaded." onRetry={compare.refresh} />;
  const data = compare.data;
  if (!data) return null;

  return (
    <>
      <PageHeader
        title="Release comparison"
        description="Compare two completed runs within the same project. Each run contributes its recorded snapshot, not its current mutable state."
        actions={
          data.current ? (
            <LinkButton to={`/projects/${project.id}/runs/${data.current.id}`} variant="secondary">
              Open current report
            </LinkButton>
          ) : null
        }
      />
      <div className="filters">
        <Field label="Baseline run" htmlFor="compare-baseline">
          <Select
            id="compare-baseline"
            value={baseline || (data.baseline?.id ?? "")}
            onChange={(event) => update("baseline", event.target.value)}
          >
            {(data.selectors ?? []).map((selector) => (
              <option key={selector.id} value={selector.id}>
                {selector.label} · {selector.status}
              </option>
            ))}
          </Select>
        </Field>
        <Field label="Current run" htmlFor="compare-current">
          <Select
            id="compare-current"
            value={current || data.current.id}
            onChange={(event) => update("current", event.target.value)}
          >
            {(data.selectors ?? []).map((selector) => (
              <option key={selector.id} value={selector.id}>
                {selector.label} · {selector.status}
              </option>
            ))}
          </Select>
        </Field>
        <div className="spacer" />
        {bucket ? (
          <Button
            variant="ghost"
            size="sm"
            onClick={() => update("bucket", "")}
          >
            Clear bucket filter
          </Button>
        ) : null}
      </div>

      {!data.baseline ? (
        <Notice tone="info" title="No baseline available">
          {data.incomparable_reason ||
            "Complete a baseline run first. A project's first assessment is the baseline."}
        </Notice>
      ) : null}

      {data.baseline ? (
        <>
          <div className="spread" style={{ marginBottom: "0.8rem" }}>
            <div>
              <span className="eyebrow">Baseline</span>
              <div>
                <Link to={`/projects/${project.id}/runs/${data.baseline.id}`}>
                  {data.baseline.kind.replace(/_/g, " ")} · build {data.baseline.build?.label}
                </Link>{" "}
                <span className="muted small">
                  completed <RelativeTime value={data.baseline.completed_at} /> ·{" "}
                  {data.baseline.mode}
                </span>
              </div>
            </div>
            <div>
              <span className="eyebrow">Current</span>
              <div>
                <Link to={`/projects/${project.id}/runs/${data.current.id}`}>
                  {data.current.kind.replace(/_/g, " ")} · build {data.current.build?.label}
                </Link>{" "}
                <span className="muted small">
                  completed <RelativeTime value={data.current.completed_at} /> · {data.current.mode}
                </span>
              </div>
            </div>
          </div>

          {!data.comparable ? (
            <Notice tone="error" title="Comparison is limited">
              {data.incomparable_reason}
            </Notice>
          ) : null}
          {data.scope.limitations.length > 0 ? (
            <Notice tone="warn" title="Changes that affect interpretation">
              <ul className="steps">
                {data.scope.limitations.map((limitation) => (
                  <li key={limitation}>{limitation}</li>
                ))}
              </ul>
            </Notice>
          ) : null}

          <div className="bucket-grid" style={{ margin: "0.8rem 0" }}>
            {Object.entries(BUCKET_LABELS).map(([key, label]) => (
              <Link
                key={key}
                className={`bucket bucket-${key}`}
                to={`?${(() => {
                  const next = new URLSearchParams(params);
                  next.set("bucket", key);
                  return next.toString();
                })()}`}
              >
                <span className="bucket-label">{label}</span>
                <span className="bucket-value">{data.bucket_counts[key] ?? 0}</span>
              </Link>
            ))}
          </div>

          <div className="grid-2" style={{ marginBottom: "1rem" }}>
            <Section title="Coverage comparison">
              <TableWrap label="Coverage comparison">
                <table>
                  <thead>
                    <tr>
                      <th scope="col">Metric</th>
                      <th scope="col">Baseline</th>
                      <th scope="col">Current</th>
                    </tr>
                  </thead>
                  <tbody>
                    <tr>
                      <td>Planned checks</td>
                      <td>{data.coverage.baseline.denominator}</td>
                      <td>{data.coverage.current.denominator}</td>
                    </tr>
                    <tr>
                      <td>Tested — no finding</td>
                      <td>{data.coverage.baseline.counts.tested_no_finding ?? 0}</td>
                      <td>{data.coverage.current.counts.tested_no_finding ?? 0}</td>
                    </tr>
                    <tr>
                      <td>Finding observed</td>
                      <td>{data.coverage.baseline.counts.finding_observed ?? 0}</td>
                      <td>{data.coverage.current.counts.finding_observed ?? 0}</td>
                    </tr>
                    <tr>
                      <td>Not run</td>
                      <td>{data.coverage.baseline.counts.not_run ?? 0}</td>
                      <td>{data.coverage.current.counts.not_run ?? 0}</td>
                    </tr>
                    <tr>
                      <td>Coverage complete</td>
                      <td>{data.coverage.baseline.coverage_complete ? "yes" : "no"}</td>
                      <td>{data.coverage.current.coverage_complete ? "yes" : "no"}</td>
                    </tr>
                  </tbody>
                </table>
              </TableWrap>
            </Section>
            <Section title="Scope changes">
              <dl className="meta-list">
                <div>
                  <dt>Profile changed</dt>
                  <dd>{data.scope.profile_changed ? "yes" : "no"}</dd>
                </div>
                <div>
                  <dt>Origin changed</dt>
                  <dd>{data.scope.origins_changed ? "yes" : "no"}</dd>
                </div>
                <div>
                  <dt>Path restrictions changed</dt>
                  <dd>{data.scope.path_restrictions_changed ? "yes" : "no"}</dd>
                </div>
                <div>
                  <dt>Surfaces added</dt>
                  <dd>
                    {data.scope.surfaces.added.length === 0 ? (
                      "none"
                    ) : (
                      <ul className="inline-code-list">
                        {data.scope.surfaces.added.map((surface) => (
                          <li key={surface}>
                            <Mono>{surface}</Mono>
                          </li>
                        ))}
                      </ul>
                    )}
                  </dd>
                </div>
                <div>
                  <dt>Surfaces removed</dt>
                  <dd>
                    {data.scope.surfaces.removed.length === 0 ? (
                      "none"
                    ) : (
                      <ul className="inline-code-list">
                        {data.scope.surfaces.removed.map((surface) => (
                          <li key={surface}>
                            <Mono>{surface}</Mono>
                          </li>
                        ))}
                      </ul>
                    )}
                  </dd>
                </div>
              </dl>
            </Section>
          </div>

          <Section title="Findings" description="Each comparable finding is assigned one primary bucket.">
            <TableWrap label="Comparison findings">
              <table>
                <thead>
                  <tr>
                    <th scope="col">Finding</th>
                    <th scope="col">Severity</th>
                    <th scope="col">Baseline</th>
                    <th scope="col">Current</th>
                    <th scope="col">Bucket</th>
                    <th scope="col">Evidence</th>
                  </tr>
                </thead>
                <tbody>
                  {rows.map((row) => (
                    <CompareRowView key={row.id} row={row} projectId={project.id} />
                  ))}
                </tbody>
              </table>
            </TableWrap>
            {rows.length === 0 ? (
              <p className="muted small" style={{ marginTop: "0.5rem" }}>
                No rows match this bucket.
              </p>
            ) : null}
          </Section>

          <Section title="Latest verification" description="Recorded after the selected snapshots; not part of the frozen comparison.">
            {data.latest_verification.length === 0 ? (
              <p className="muted small">No later conclusive verification exists for this build.</p>
            ) : (
              <ul className="member-list">
                {data.latest_verification.map((entry) => (
                  <li key={entry.finding_id}>
                    <span>
                      <Link to={`/projects/${project.id}/findings/${entry.finding_id}?run=${data.current.id}`}>
                        {entry.public_id} — {entry.title}
                      </Link>
                      <div className="cell-sub">
                        {entry.source} · <RelativeTime value={entry.observed_at} />
                      </div>
                    </span>
                    <VerdictBadge outcome={entry.outcome} />
                  </li>
                ))}
              </ul>
            )}
          </Section>
        </>
      ) : null}
    </>
  );
}

function CompareRowView({ row, projectId }: { row: CompareRow; projectId: string }) {
  return (
    <tr>
      <td className="wrap">
        <Link to={`/projects/${projectId}/findings/${row.id}`}>
          {row.public_id} — {row.title}
        </Link>
        <div className="cell-sub">{row.scope_summary}</div>
      </td>
      <td>
        <SeverityBadge severity={row.severity} />
      </td>
      <td>
        {row.baseline_outcome ? <VerdictBadge outcome={row.baseline_outcome} /> : "no accepted observation"}
      </td>
      <td>
        <VerdictBadge outcome={row.verification.outcome} />
        {row.verification.reason ? <div className="reason-note">{row.verification.reason}</div> : null}
      </td>
      <td>
        <span className={`badge ${row.bucket === "regressed" ? "badge-fail" : row.bucket === "fix_verified" ? "badge-pass" : "badge-neutral"}`}>
          {BUCKET_LABELS[row.bucket] ?? row.bucket}
        </span>
        {row.bucket_reason ? <div className="reason-note">{row.bucket_reason}</div> : null}
      </td>
      <td>
        <Link to={`/projects/${projectId}/findings/${row.id}`}>Before / after evidence</Link>
        <div className="cell-sub">{row.in_current_run ? "checked in current run" : "not tested in current run"}</div>
      </td>
    </tr>
  );
}

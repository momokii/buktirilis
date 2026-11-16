import { useEffect, useMemo, useRef, useState } from "react";
import { Link, useParams, useSearchParams } from "react-router-dom";
import { useApi } from "../auth";
import { api, errorMessage } from "../api";
import type { Attempt, Build, EvidenceItem, FindingDetail } from "../api";
import { useProject } from "./Project";
import {
  Breadcrumbs,
  Button,
  DefinitionList,
  Dialog,
  ErrorState,
  EvidenceBadge,
  Field,
  LinkButton,
  Loading,
  MethodBadge,
  Mono,
  Notice,
  RelativeTime,
  Section,
  Select,
  SeverityBadge,
  TextInput,
  VerdictBadge,
  useToast,
} from "../ui";

interface GuidedPackage {
  finding_id: string;
  public_id: string;
  build_id: string;
  build_label: string;
  automation_limit: string;
  retest_method: string;
  required_identities: { name: string; role: string; tenant: string }[];
  required_fixtures: string[];
  steps: string[];
  expected_after_fix: string;
  observed_behavior: string;
  control_check: Record<string, unknown>;
  capture_instructions: string[];
  missing_prerequisites: string[];
  latest_observation: { outcome: string; source: string; observed_at: string } | null;
  can_submit: boolean;
  copyable_details: Record<string, unknown>;
}

function requestResponse(payload: Record<string, unknown>) {
  const request = (payload.request ?? {}) as Record<string, unknown>;
  const response = (payload.response ?? {}) as Record<string, unknown>;
  return { request, response };
}

export function FindingPage() {
  const { project } = useProject();
  const { findingId, runId: routeRunId } = useParams();
  const [params] = useSearchParams();
  const runId = routeRunId ?? params.get("run");
  const buildId = params.get("build");
  const detailPath = useMemo(() => {
    const query = new URLSearchParams();
    if (runId) query.set("run_id", runId);
    if (buildId) query.set("build_id", buildId);
    return `/api/projects/${project.id}/findings/${findingId}${query.toString() ? `?${query}` : ""}`;
  }, [project.id, findingId, runId, buildId]);
  const finding = useApi<FindingDetail>(detailPath);
  const recipe = useApi<{ recipe: { id: string; state: string; revisions: Record<string, unknown>[] } | null }>(
    `/api/projects/${project.id}/findings/${findingId}/recipe`,
  );
  const builds = useApi<{ items: Build[] }>(`/api/projects/${project.id}/builds`);
  const accounts = useApi<{ items: { id: string; name: string; role: string; tenant: string }[] }>(
    `/api/projects/${project.id}/accounts`,
  );
  const { notify } = useToast();
  const [selectedBuild, setSelectedBuild] = useState("");
  const [busy, setBusy] = useState(false);
  const [recipeOpen, setRecipeOpen] = useState(false);
  const [dispositionOpen, setDispositionOpen] = useState(false);
  const [showAllEvidence, setShowAllEvidence] = useState(false);

  const data = finding.data;
  useEffect(() => {
    // Always follow the build the report was opened for; fall back only when absent.
    if (data?.build?.id) setSelectedBuild(data.build.id);
  }, [data?.build?.id]);
  useEffect(() => {
    if (!selectedBuild && builds.data?.items[0]) {
      setSelectedBuild(builds.data.items[0].id);
    }
  }, [builds.data, selectedBuild]);

  const activeAttempt = data?.attempts.find((attempt) => attempt.state === "queued" || attempt.state === "running");
  useEffect(() => {
    if (!activeAttempt) return;
    const timer = window.setInterval(() => finding.refresh(), 2500);
    return () => window.clearInterval(timer);
  }, [activeAttempt, finding]);

  if (finding.loading && !data) return <Loading label="Loading finding" />;
  if (finding.error) return <ErrorState message="This finding could not be loaded." onRetry={finding.refresh} />;
  if (!data) return null;

  const backParams = new URLSearchParams();
  for (const key of ["tab", "severity", "outcome", "method", "surface", "q", "sort", "bucket"]) {
    const value = params.get(key);
    if (value) backParams.set(key, value);
  }
  backParams.set("tab", "findings");
  const backLink = runId
    ? `/projects/${project.id}/runs/${runId}?${backParams.toString()}`
    : `/projects/${project.id}/runs`;

  const buildOptions = builds.data?.items ?? [];
  const targetBuild = buildOptions.find((build) => build.id === selectedBuild);

  const action = async (
    path: string,
    body?: unknown,
    method = "POST",
    successMessage = "Recorded.",
  ) => {
    setBusy(true);
    try {
      await api(path, { method, body: body ? JSON.stringify(body) : undefined });
      notify("success", successMessage);
      finding.refresh();
      recipe.refresh();
    } catch (caught) {
      notify("error", errorMessage(caught));
    } finally {
      setBusy(false);
    }
  };

  return (
    <>
      <Breadcrumbs
        items={[
          { label: "Projects", to: "/projects" },
          { label: project.name, to: `/projects/${project.id}` },
          ...(runId
            ? [
                { label: "Report", to: `/projects/${project.id}/runs/${runId}` },
                { label: "Findings", to: backLink },
              ]
            : []),
          { label: data.public_id },
        ]}
      />
      <header className="report-header">
        <div className="report-title-row">
          <div>
            <div className="row">
              <Mono>{data.public_id}</Mono>
              <SeverityBadge severity={data.severity} />
              <EvidenceBadge status={data.evidence_status} />
              {data.verification ? <VerdictBadge outcome={data.verification.outcome} /> : null}
              <MethodBadge method={data.retest_method} />
            </div>
            <h1 style={{ marginTop: "0.4rem" }}>{data.title}</h1>
            <div className="report-meta">
              <span>
                Build <strong>{data.build?.label ?? "not selected"}</strong>
              </span>
              <span className="sep">·</span>
              <Mono>{data.scope_summary}</Mono>
              <span className="sep">·</span>
              <span>{data.actors_summary}</span>
            </div>
          </div>
          <div className="page-actions">
            {data.disposition === "open" && data.retest_method === "automatic" ? (
              <Button
                variant="primary"
                busy={busy}
                disabled={!selectedBuild}
                onClick={() =>
                  void action(
                    `/api/projects/${project.id}/findings/${data.id}/retests`,
                    { build_id: selectedBuild || data.build?.id },
                    "POST",
                    "Retest queued. The worker records the outcome and evidence here.",
                  )
                }
              >
                Retest on {data.build?.label ?? "selected build"}
              </Button>
            ) : null}
            {data.disposition === "open" && data.retest_method === "guided" ? (
              <a className="btn btn-primary btn-md btn-link" href="#guided">
                Guided retest
              </a>
            ) : null}
            {data.disposition === "open" && data.retest_method === "pending_evidence_review" ? (
              <a className="btn btn-primary btn-md btn-link" href="#verify">
                Review evidence
              </a>
            ) : null}
            <LinkButton to={backLink} variant="secondary">
              Back to findings
            </LinkButton>
            {data.build && data.capabilities.can_retest ? (
              <Button
                onClick={() =>
                  void action(`/api/projects/${project.id}/findings/${data.id}/ready`, {
                    build_id: data.build?.id,
                  })
                }
                busy={busy}
                disabled={Boolean(data.marked_ready_at)}
              >
                {data.marked_ready_at ? "Ready for retest" : "Mark ready for retest"}
              </Button>
            ) : null}
            {data.capabilities.can_operate ? (
              <Button onClick={() => setDispositionOpen(true)}>Disposition</Button>
            ) : null}
          </div>
        </div>
        <p className="report-summary impact">{data.impact || "No impact statement recorded."}</p>
        {data.marked_ready_at ? (
          <p className="small muted">
            Ready for retest since <RelativeTime value={data.marked_ready_at} />. This marker
            schedules work; it does not change the verification outcome.
          </p>
        ) : null}
      </header>

      <div className="two-col" style={{ marginTop: "1rem" }}>
        <div className="stack">
          <Section title="Proof summary">
            <DefinitionList
              items={[
                { term: "Expected behavior", value: data.expected_behavior || "—" },
                { term: "Observed behavior", value: data.observed_behavior || "—" },
                { term: "Affected build", value: data.build?.label ?? "—" },
                { term: "Scope", value: <Mono>{data.scope_summary || "—"}</Mono> },
                { term: "Evidence status", value: <EvidenceBadge status={data.evidence_status} /> },
              ]}
            />
          </Section>

          <Section title="Prerequisites and reproduction" description="Ordered steps a reviewer can repeat on the selected build.">
            <h3>Prerequisites</h3>
            {data.prerequisites.length === 0 ? (
              <p className="muted small">No prerequisites recorded.</p>
            ) : (
              <ul className="steps">
                {data.prerequisites.map((item) => (
                  <li key={item}>{item}</li>
                ))}
              </ul>
            )}
            <h3 style={{ marginTop: "0.8rem" }}>Steps</h3>
            {data.reproduction_steps.length === 0 ? (
              <Notice tone="warn" title="Reproduction steps are incomplete">
                Review the evidence and complete the procedure before scheduling a retest.
              </Notice>
            ) : (
              <ol className="steps">
                {data.reproduction_steps.map((step) => (
                  <li key={step}>{step}</li>
                ))}
              </ol>
            )}
            <h3 style={{ marginTop: "0.8rem" }}>Remediation</h3>
            <p className="small">{data.remediation || "No remediation guidance recorded."}</p>
            {data.root_cause_hypothesis ? (
              <Notice tone="info" title="Unconfirmed root-cause hypothesis">
                {data.root_cause_hypothesis}
              </Notice>
            ) : null}
          </Section>

          <Section
            title="Evidence"
            description="Sanitized captures attributed to their source. Missing content is called out explicitly."
          >
            {data.evidence_missing.length > 0 ? (
              <Notice tone="error" title="Missing evidence">
                {data.evidence_missing.map((item) => `${item.summary}: ${item.reason}`).join(" · ")}
              </Notice>
            ) : null}
            <div className="evidence-list">
              {(showAllEvidence ? data.evidence : data.evidence.slice(0, 3)).map((item) => (
                <EvidenceCard key={item.id} item={item} />
              ))}
              {data.evidence.length === 0 ? (
                <p className="muted small">No evidence is linked to this finding.</p>
              ) : null}
            </div>
            {data.evidence.length > 3 ? (
              <Button
                size="sm"
                variant="ghost"
                style={{ marginTop: "0.5rem" }}
                onClick={() => setShowAllEvidence((current) => !current)}
              >
                {showAllEvidence
                  ? "Show newest three"
                  : `Show ${data.evidence.length - 3} older evidence item(s)`}
              </Button>
            ) : null}
          </Section>

          <Section title="Verification history" description="Observations are scoped to their build and ordered by when they were made.">
            {data.observations.length === 0 ? (
              <p className="muted small">No accepted observation has been recorded.</p>
            ) : (
              <ol className="timeline">
                {data.observations.map((observation) => (
                  <li key={observation.id}>
                    <span className="when">
                      <RelativeTime value={observation.observed_at} />
                      <br />
                      <span className="muted">{observation.build_label}</span>
                    </span>
                    <span className="what">
                      <span className="row">
                        <VerdictBadge outcome={observation.outcome} />
                        <span className="badge badge-neutral">{observation.source}</span>
                        {observation.stale ? (
                          <span className="badge badge-warn">stale</span>
                        ) : null}
                      </span>
                      {observation.run ? (
                        <Link to={`/projects/${project.id}/runs/${observation.run.id}`}>
                          {observation.run.kind.replace(/_/g, " ")} run
                        </Link>
                      ) : null}
                    </span>
                  </li>
                ))}
              </ol>
            )}
          </Section>

          <Section title="Retest attempts" description="Each attempt records the recipe revision, build, requester, and sanitized evidence.">
            {data.attempts.length === 0 ? (
              <p className="muted small">No retest attempt has been recorded.</p>
            ) : (
              <div className="stack">
                {data.attempts.slice(0, 3).map((attempt) => (
                  <AttemptCard
                    key={attempt.id}
                    attempt={attempt}
                    canReview={data.capabilities.can_operate}
                    onReview={async (decision, reason) => {
                      await action(`/api/projects/${project.id}/attempts/${attempt.id}/review`, {
                        decision,
                        reason,
                      });
                    }}
                  />
                ))}
                {data.attempts.length > 3 ? (
                  <details>
                    <summary className="small">
                      {data.attempts.length - 3} older attempt(s)
                    </summary>
                    <div className="stack" style={{ marginTop: "0.5rem" }}>
                      {data.attempts.slice(3).map((attempt) => (
                        <AttemptCard
                          key={attempt.id}
                          attempt={attempt}
                          canReview={data.capabilities.can_operate}
                          onReview={async (decision, reason) => {
                            await action(
                              `/api/projects/${project.id}/attempts/${attempt.id}/review`,
                              { decision, reason },
                            );
                          }}
                        />
                      ))}
                    </div>
                  </details>
                ) : null}
              </div>
            )}
          </Section>
        </div>

        <div className="sticky-side stack">
          <Section title="Assessment state">
            <DefinitionList
              items={[
                { term: "Severity", value: <SeverityBadge severity={data.severity} /> },
                {
                  term: "Evidence strength",
                  value:
                    data.evidence_status === "supported"
                      ? "Supported by accepted evidence"
                      : "Needs validation",
                },
                {
                  term: "Verification",
                  value: data.verification ? (
                    <>
                      <VerdictBadge outcome={data.verification.outcome} />
                      {data.verification.reason ? (
                        <div className="reason-note">{data.verification.reason}</div>
                      ) : null}
                    </>
                  ) : (
                    "—"
                  ),
                },
                { term: "Retest eligibility", value: <MethodBadge method={data.retest_method} /> },
                { term: "Disposition", value: data.disposition },
              ]}
            />
          </Section>
          <Section
            title="Retest"
            description="The retest path is chosen independently of the evidence decision."
            id="retest-panel"
          >
            <Field label="Target build" htmlFor="finding-build">
              <Select
                id="finding-build"
                value={selectedBuild}
                onChange={(event) => setSelectedBuild(event.target.value)}
              >
                {buildOptions.map((build) => (
                  <option key={build.id} value={build.id}>
                    {build.label}
                  </option>
                ))}
              </Select>
            </Field>
            {data.retest_method === "automatic" ? (
              <>
                <p className="small muted" style={{ marginTop: "0.5rem" }}>
                  {recipe.data?.recipe
                    ? `Approved recipe r${String((recipe.data.recipe.revisions[0] as { revision?: number })?.revision ?? "?")} replays one read-only request with a legitimate-owner control.`
                    : "An approved recipe will be used; if it is missing the server rejects the retest."}
                </p>
                <div className="row" style={{ marginTop: "0.5rem" }}>
                  <Button
                    variant="primary"
                    busy={busy}
                    disabled={!selectedBuild}
                    onClick={() =>
                      void action(
                        `/api/projects/${project.id}/findings/${data.id}/retests`,
                        { build_id: selectedBuild },
                        "POST",
                        "Retest queued. The worker records the outcome and evidence here.",
                      )
                    }
                  >
                    Run automatic retest
                  </Button>
                  {data.capabilities.can_operate ? (
                    <Button size="sm" onClick={() => setRecipeOpen(true)}>
                      Edit recipe
                    </Button>
                  ) : null}
                </div>
              </>
            ) : (
              <p className="small muted" style={{ marginTop: "0.5rem" }}>
                {data.retest_method === "guided"
                  ? "This case needs a guided retest; see the guided package below."
                  : "The evidence needs validation before a verdict can be scheduled."}{" "}
                <a href={data.retest_method === "guided" ? "#guided" : "#verify"}>
                  {data.retest_method === "guided" ? "Open guided retest" : "Review evidence"}
                </a>
              </p>
            )}
            {activeAttempt ? (
              <Notice tone="info" title="Attempt in progress">
                {activeAttempt.kind === "automatic"
                  ? "The constrained runner is executing the approved recipe."
                  : "Waiting for reviewer acceptance."}
              </Notice>
            ) : null}
          </Section>
          <Section title="Links">
            <div className="stack-sm">
              {data.run ? (
                <Link to={`/projects/${project.id}/runs/${data.run.id}`}>Source run</Link>
              ) : null}
              {runId ? <Link to={backLink}>Report findings</Link> : null}
              {data.build ? (
                <Link to={`/projects/${project.id}/compare?current=${runId ?? ""}`}>
                  Compare with a baseline
                </Link>
              ) : null}
            </div>
          </Section>
          {data.duplicate_candidates.length > 0 ? (
            <Notice tone="warn" title="Possible duplicates">
              {data.duplicate_candidates.map((candidate) => (
                <div key={candidate.id} className="small">
                  <Link to={`/projects/${project.id}/findings/${candidate.id}`}>
                    {candidate.public_id} — {candidate.title}
                  </Link>{" "}
                  ({candidate.disposition})
                </div>
              ))}
              Review these records before merging or closing either finding.
            </Notice>
          ) : null}
        </div>
      </div>

      {data.retest_method !== "automatic" ? (
        <GuidedSection
          projectId={project.id}
          findingId={data.id}
          buildId={selectedBuild || data.build?.id || ""}
          canSubmit={data.capabilities.can_retest}
          onSubmitted={() => finding.refresh()}
        />
      ) : null}
      <ReviewEvidenceSection
        projectId={project.id}
        finding={data}
        onChanged={() => finding.refresh()}
      />

      <RecipeDialog
        open={recipeOpen}
        onClose={() => setRecipeOpen(false)}
        projectId={project.id}
        finding={data}
        build={targetBuild ?? data.build ?? null}
        accounts={accounts.data?.items ?? []}
        onSaved={() => {
          setRecipeOpen(false);
          recipe.refresh();
          finding.refresh();
        }}
      />

      <DispositionDialog
        open={dispositionOpen}
        onClose={() => setDispositionOpen(false)}
        projectId={project.id}
        finding={data}
        onSaved={() => {
          setDispositionOpen(false);
          finding.refresh();
        }}
      />
    </>
  );
}

function EvidenceCard({ item }: { item: EvidenceItem }) {
  const { request, response } = requestResponse(item.payload);
  const headers = (request.headers ?? {}) as Record<string, string>;
  const responseHeaders = (response.headers ?? {}) as Record<string, string>;
  const body = typeof response.body === "string" ? response.body : "";
  const engine = item.payload as Record<string, unknown>;
  return (
    <article className="evidence" aria-label={`Evidence ${item.summary}`}>
      <div className="evidence-head">
        <div>
          <strong>{item.summary}</strong>
          <div className="evidence-caption">
            {item.attribution.replace(/_/g, " ")} · {item.actor_label || "attributed capture"} ·{" "}
            <RelativeTime value={item.created_at} /> {item.build_label ? `· ${item.build_label}` : ""}
          </div>
        </div>
        <div className="row">
          {item.method ? <span className="badge badge-neutral">{item.method}</span> : null}
          {item.artifact ? (
            item.artifact.available ? (
              <a className="btn btn-secondary btn-sm btn-link" href={item.artifact.download_url}>
                Attachment
              </a>
            ) : (
              <span className="badge badge-warn">Attachment unavailable</span>
            )
          ) : null}
        </div>
      </div>
      <div className="evidence-body">
        {item.endpoint ? (
          <div className="exchange">
            <span className="exchange-label">Endpoint</span>
            <Mono wrap>{item.endpoint}</Mono>
          </div>
        ) : null}
        {item.highlight.length > 0 ? (
          <div className="highlight">
            <span className="exchange-label">What proves the outcome</span>
            {item.highlight.map((line) => (
              <code key={line}>{line}</code>
            ))}
          </div>
        ) : null}
        {body || request.url ? (
          <div className="exchange">
            <span className="exchange-label">Captured exchange</span>
            <pre className="code" tabIndex={0} role="region" aria-label="Scrollable code excerpt">
{`${String(request.method ?? item.method ?? "GET")} ${String(request.url ?? item.endpoint ?? "")}
${Object.entries(headers)
  .map(([key, value]) => `${key}: ${value}`)
  .join("\n")}

HTTP ${String(response.status ?? "—")}
${Object.entries(responseHeaders)
  .map(([key, value]) => `${key}: ${value}`)
  .join("\n")}

${body}`}
            </pre>
          </div>
        ) : null}
        {engine.description ? (
          <div className="exchange">
            <span className="exchange-label">Engine description</span>
            <p className="small">{String(engine.description)}</p>
          </div>
        ) : null}
        {engine.evidence && item.attribution === "engine_report" ? (
          <div className="exchange">
            <span className="exchange-label">Engine evidence excerpt</span>
            <pre className="code code-light" tabIndex={0} role="region" aria-label="Scrollable code excerpt">{String(engine.evidence)}</pre>
          </div>
        ) : null}
        <details className="raw-details">
          <summary>Sanitized details</summary>
          <pre className="code code-light" tabIndex={0} role="region" aria-label="Scrollable code excerpt">{JSON.stringify(item.payload, null, 2)}</pre>
        </details>
      </div>
    </article>
  );
}

function AttemptCard({
  attempt,
  canReview,
  onReview,
}: {
  attempt: Attempt;
  canReview: boolean;
  onReview: (decision: "accepted" | "changes_requested", reason: string) => Promise<void>;
}) {
  const [reason, setReason] = useState("");
  const [busy, setBusy] = useState(false);
  const pending = attempt.kind === "guided" && attempt.pending_review && canReview;
  return (
    <article className="evidence">
      <div className="evidence-head">
        <div>
          <strong>
            {attempt.kind === "automatic" ? "Automatic replay" : "Guided submission"} ·{" "}
            {attempt.recipe_revision || "manual"}
          </strong>
          <div className="evidence-caption">
            Build {attempt.build_label} · requested by {attempt.requested_by} ·{" "}
            <RelativeTime value={attempt.requested_at} />
          </div>
        </div>
        <div className="row">
          {attempt.outcome ? <VerdictBadge outcome={attempt.outcome} /> : null}
          <span className={`badge ${attempt.state === "completed" ? "badge-neutral" : "badge-info"}`}>
            {attempt.state}
          </span>
          {attempt.pending_review ? <span className="badge badge-warn">pending review</span> : null}
        </div>
      </div>
      <div className="evidence-body">
        {attempt.reason ? <p className="small">{attempt.reason}</p> : null}
        {attempt.notes ? <p className="small">{attempt.notes}</p> : null}
        <div className="row">
          <span className="badge badge-neutral">
            identity {attempt.build_identity.observed || "unavailable"} / expected{" "}
            {attempt.build_identity.expected || "unrecorded"}
          </span>
          {attempt.positive_control && Object.keys(attempt.positive_control).length > 0 ? (
            <span className="badge badge-neutral">
              control {String(attempt.positive_control.ok ?? "—")}
            </span>
          ) : null}
        </div>
        <details className="raw-details">
          <summary>
            Attempt detail — {attempt.reviews.length} review(s), {attempt.evidence.length}{" "}
            evidence item(s)
          </summary>
          {attempt.reviews.length > 0 ? (
            <ul className="steps small">
              {attempt.reviews.map((review) => (
                <li key={review.id}>
                  {review.decision.replace(/_/g, " ")} by {review.reviewer} —{" "}
                  {review.reason || "no reason"}
                </li>
              ))}
            </ul>
          ) : null}
          {attempt.evidence.map((item) => (
            <div key={item.id} className="exchange">
              <span className="exchange-label">Attempt evidence</span>
              <pre className="code code-light" tabIndex={0} role="region" aria-label="Scrollable code excerpt">
                {JSON.stringify(
                  {
                    request: item.payload.request,
                    response: item.payload.response,
                    actor: item.actor_label,
                  },
                  null,
                  2,
                )}
              </pre>
            </div>
          ))}
        </details>
        {pending ? (
          <div className="stack-sm">
            <Field label="Review reason" htmlFor={`review-${attempt.id}`}>
              <TextInput
                id={`review-${attempt.id}`}
                value={reason}
                onChange={(event) => setReason(event.target.value)}
                placeholder="Required when requesting changes"
              />
            </Field>
            <div className="row">
              <Button
                variant="primary"
                size="sm"
                busy={busy}
                onClick={() => {
                  setBusy(true);
                  void onReview("accepted", reason).finally(() => setBusy(false));
                }}
              >
                Accept verdict
              </Button>
              <Button
                size="sm"
                busy={busy}
                onClick={() => {
                  setBusy(true);
                  void onReview("changes_requested", reason).finally(() => setBusy(false));
                }}
              >
                Request changes
              </Button>
            </div>
          </div>
        ) : null}
        <span className="small muted">Attempt {attempt.id.slice(0, 8)}</span>
      </div>
    </article>
  );
}

function GuidedSection({
  projectId,
  findingId,
  buildId,
  canSubmit,
  onSubmitted,
}: {
  projectId: string;
  findingId: string;
  buildId: string;
  canSubmit: boolean;
  onSubmitted: () => void;
}) {
  const guided = useApi<GuidedPackage>(
    buildId ? `/api/projects/${projectId}/findings/${findingId}/guided?build_id=${buildId}` : null,
  );
  const [outcome, setOutcome] = useState("fix_verified");
  const [notes, setNotes] = useState("");
  const [link, setLink] = useState("");
  const [artifactId, setArtifactId] = useState<string | null>(null);
  const [uploading, setUploading] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const { notify } = useToast();
  const fileRef = useRef<HTMLInputElement | null>(null);

  if (!buildId) return null;
  if (guided.loading && !guided.data) return <Loading label="Preparing guided retest" />;
  if (guided.error) {
    return (
      <Section title="Guided retest" id="guided">
        <ErrorState message="The guided package could not be prepared." onRetry={guided.refresh} />
      </Section>
    );
  }
  const data = guided.data;
  if (!data) return null;

  const submit = async () => {
    setBusy(true);
    setError(null);
    try {
      await api(`/api/projects/${projectId}/findings/${findingId}/guided-attempts`, {
        method: "POST",
        body: JSON.stringify({
          build_id: buildId,
          outcome,
          notes,
          evidence_link: link,
          artifact_id: artifactId,
          steps_revision: 1,
        }),
      });
      notify("success", "Submitted for reviewer acceptance. The build verdict is unchanged until accepted.");
      setNotes("");
      setLink("");
      setArtifactId(null);
      guided.refresh();
      onSubmitted();
    } catch (caught) {
      setError(errorMessage(caught));
    } finally {
      setBusy(false);
    }
  };

  const upload = async (file: File) => {
    setUploading(true);
    setError(null);
    try {
      const form = new FormData();
      form.append("file", file);
      const response = await api<{ id: string; filename: string }>(
        `/api/projects/${projectId}/artifacts`,
        { method: "POST", body: form },
      );
      setArtifactId(response.id);
      notify("success", `Attached ${response.filename}.`);
    } catch (caught) {
      setError(errorMessage(caught));
    } finally {
      setUploading(false);
    }
  };

  return (
    <div id="guided">
      <Section
        title={`Guided retest for ${data.public_id}`}
        description="Automation is not used for this case. Follow the steps, capture the control, and submit on a chosen build."
      >
        <Notice tone="info" title="Why automation is unavailable">
          {data.automation_limit}
        </Notice>
        <div className="grid-2" style={{ marginTop: "0.7rem" }}>
          <div>
            <h3>Required identities</h3>
            <ul className="steps">
              {data.required_identities.map((identity) => (
                <li key={identity.name}>
                  <strong>{identity.name}</strong> — {identity.role}
                  {identity.tenant ? ` · tenant ${identity.tenant}` : ""}
                </li>
              ))}
            </ul>
            <h3 style={{ marginTop: "0.7rem" }}>Fixtures and prerequisites</h3>
            {data.required_fixtures.length === 0 ? (
              <p className="muted small">None recorded.</p>
            ) : (
              <ul className="steps">
                {data.required_fixtures.map((fixture) => (
                  <li key={fixture}>{fixture}</li>
                ))}
              </ul>
            )}
            <h3 style={{ marginTop: "0.7rem" }}>Steps to perform</h3>
            {data.steps.length === 0 ? (
              <p className="muted small">No steps recorded.</p>
            ) : (
              <ol className="steps">
                {data.steps.map((step) => (
                  <li key={step}>{step}</li>
                ))}
              </ol>
            )}
          </div>
          <div>
            <h3>Expected after the fix</h3>
            <p className="small">{data.expected_after_fix || "—"}</p>
            <h3 style={{ marginTop: "0.7rem" }}>Legitimate control</h3>
            <pre className="code code-light" tabIndex={0} role="region" aria-label="Scrollable code excerpt">{JSON.stringify(data.control_check, null, 2)}</pre>
            <h3 style={{ marginTop: "0.7rem" }}>Capture</h3>
            <ul className="steps">
              {data.capture_instructions.map((instruction) => (
                <li key={instruction} className="small">
                  {instruction}
                </li>
              ))}
            </ul>
            <details style={{ marginTop: "0.6rem" }}>
              <summary className="small">Copyable sanitized details</summary>
              <pre className="code code-light" tabIndex={0} role="region" aria-label="Scrollable code excerpt">{JSON.stringify(data.copyable_details, null, 2)}</pre>
            </details>
          </div>
        </div>
        {data.missing_prerequisites.length > 0 ? (
          <Notice tone="warn" title="Prerequisites are incomplete">
            <ul className="steps">
              {data.missing_prerequisites.map((missing) => (
                <li key={missing}>{missing}</li>
              ))}
            </ul>
          </Notice>
        ) : null}

        {canSubmit ? (
          <form
            className="stack"
            style={{ marginTop: "0.8rem" }}
            onSubmit={(event) => {
              event.preventDefault();
              void submit();
            }}
          >
            <h3>Submit a guided result</h3>
            <div className="grid-2">
              <Field label="Outcome" htmlFor="guided-outcome">
                <Select
                  id="guided-outcome"
                  value={outcome}
                  onChange={(event) => setOutcome(event.target.value)}
                >
                  <option value="fix_verified">Fix verified</option>
                  <option value="still_reproducible">Still reproducible</option>
                  <option value="inconclusive">Inconclusive</option>
                </Select>
              </Field>
              <Field label="Evidence link" htmlFor="guided-link" hint="Approved artifact link, if you are not uploading a file.">
                <TextInput
                  id="guided-link"
                  value={link}
                  onChange={(event) => setLink(event.target.value)}
                  placeholder="https://evidence.internal/…"
                />
              </Field>
            </div>
            <Field label="What did you observe?" htmlFor="guided-notes">
              <textarea
                id="guided-notes"
                className="input"
                value={notes}
                onChange={(event) => setNotes(event.target.value)}
                required
              />
            </Field>
            <div className="upload-row">
              <input
                ref={fileRef}
                className="file-input"
                type="file"
                aria-label="Attach evidence screenshot or JSON"
                accept="image/png,image/jpeg,application/json,text/plain"
                onChange={(event) => {
                  const file = event.target.files?.[0];
                  if (file) void upload(file);
                }}
              />
              {uploading ? <span className="spinner" aria-hidden="true" /> : null}
              {artifactId ? <span className="badge badge-pass">Attachment ready</span> : null}
            </div>
            {error ? <Notice tone="error">{error}</Notice> : null}
            <div className="row">
              <Button type="submit" variant="primary" busy={busy} disabled={!notes.trim()}>
                Submit for review
              </Button>
              <span className="small muted">
                A conclusive result needs an attachment or an approved artifact link. Pending
                submissions do not change the verdict.
              </span>
            </div>
          </form>
        ) : (
          <Notice tone="info">A developer or operator role can submit a guided result.</Notice>
        )}
      </Section>
    </div>
  );
}

function ReviewEvidenceSection({
  projectId,
  finding,
  onChanged,
}: {
  projectId: string;
  finding: FindingDetail;
  onChanged: () => void;
}) {
  const { notify } = useToast();
  const [note, setNote] = useState("");
  const [busy, setBusy] = useState(false);
  const needsValidation = finding.evidence_status === "needs_validation";
  const missing = finding.reproduction_steps.length === 0 || !finding.observed_behavior;
  return (
    <div id="verify">
      <Section
        title="Review evidence"
        description="Evidence strength is independent of verification. A well-proven finding can still require a guided retest."
      >
        <DefinitionList
          items={[
            { term: "Evidence status", value: <EvidenceBadge status={finding.evidence_status} /> },
            { term: "Reproduction procedure", value: missing ? "Incomplete" : "Recorded" },
            { term: "Next validation step", value: needsValidation ? "Accept or reject the evidence" : "Schedule the retest path above" },
            { term: "Original observation", value: finding.latest_observation ? `${finding.latest_observation.outcome} on ${finding.build?.label}` : "—" },
          ]}
        />
        {needsValidation ? (
          <Notice tone="warn" title="What is missing">
            The recorded evidence is not strong enough to rely on. Confirm the capture and the
            reproduction procedure, or document a false positive or duplicate with a reason.
          </Notice>
        ) : (
          <p className="small muted" style={{ marginTop: "0.5rem" }}>
            The evidence is supported. {missing ? "The reproduction procedure still needs completion." : "Verification history is kept with its original build."}
          </p>
        )}
        {finding.evidence_decisions.length > 0 ? (
          <details className="raw-details" style={{ marginTop: "0.5rem" }}>
            <summary>Evidence decision history ({finding.evidence_decisions.length})</summary>
            <ul className="steps small">
              {finding.evidence_decisions.map((decision) => (
                <li key={`${decision.at}-${decision.status}`}>
                  <strong>{decision.status.replace(/_/g, " ")}</strong> by {decision.actor} ·{" "}
                  <RelativeTime value={decision.at} /> — {decision.reason}
                </li>
              ))}
            </ul>
          </details>
        ) : null}
        {finding.capabilities.can_operate ? (
          <div className="stack-sm" style={{ marginTop: "0.6rem" }}>
            <Field label="Reviewer note" htmlFor="evidence-note">
              <TextInput
                id="evidence-note"
                value={note}
                onChange={(event) => setNote(event.target.value)}
                placeholder="What did you confirm?"
              />
            </Field>
            <div className="row">
              <Button
                variant="primary"
                size="sm"
                busy={busy}
                onClick={async () => {
                  setBusy(true);
                  try {
                    await api(`/api/projects/${projectId}/findings/${finding.id}/evidence-status`, {
                      method: "POST",
                      body: JSON.stringify({ status: "supported", note }),
                    });
                    notify("success", "Evidence marked supported. Retest path remains independent.");
                    onChanged();
                  } catch (caught) {
                    notify("error", errorMessage(caught));
                  } finally {
                    setBusy(false);
                  }
                }}
              >
                Accept evidence
              </Button>
              <Button
                size="sm"
                busy={busy}
                onClick={async () => {
                  setBusy(true);
                  try {
                    await api(`/api/projects/${projectId}/findings/${finding.id}/evidence-status`, {
                      method: "POST",
                      body: JSON.stringify({ status: "needs_validation", note }),
                    });
                    notify("info", "Evidence kept in needs validation.");
                    onChanged();
                  } catch (caught) {
                    notify("error", errorMessage(caught));
                  } finally {
                    setBusy(false);
                  }
                }}
              >
                Keep needs validation
              </Button>
            </div>
          </div>
        ) : null}
      </Section>
    </div>
  );
}

function RecipeDialog({
  open,
  onClose,
  projectId,
  finding,
  build,
  accounts,
  onSaved,
}: {
  open: boolean;
  onClose: () => void;
  projectId: string;
  finding: FindingDetail;
  build: Build | null;
  accounts: { id: string; name: string }[];
  onSaved: () => void;
}) {
  const { notify } = useToast();
  const [method, setMethod] = useState("GET");
  const [path, setPath] = useState("/api/invoices/{invoice_id}");
  const [fixtureName, setFixtureName] = useState("invoice_id");
  const [fixtureValue, setFixtureValue] = useState("INV-A-1001");
  const [checkPath, setCheckPath] = useState("/api/invoices/INV-A-1001");
  const [actor, setActor] = useState("tenant-b-dev");
  const [owner, setOwner] = useState("tenant-a-owner");
  const [assertionKind, setAssertionKind] = useState("cross_tenant_json_object");
  const [ownerField, setOwnerField] = useState("tenant_id");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [preview, setPreview] = useState<Record<string, unknown> | null>(null);

  useEffect(() => {
    if (!open) return;
    setError(null);
    setPreview(null);
  }, [open]);

  const payload = useMemo(
    () => ({
      method,
      path_template: path,
      fixture_refs: [
        {
          name: fixtureName,
          value: fixtureValue,
          check_path: checkPath,
          expect: { status: 200, json_field: "tenant_id", equals: "owner_tenant" },
        },
      ],
      identity_refs: { actor, owner },
      expected_authorized:
        assertionKind === "cross_tenant_document"
          ? { status: 200, contains_marker: fixtureName }
          : { status: 200, json_field: "tenant_id", equals_identity_tenant: true },
      expected_unauthorized: {
        statuses: [200],
        denial_statuses: [403, 404],
        denial_error_field: "error.code",
        denial_error_prefix: "TENANT_",
      },
      assertion:
        assertionKind === "cross_tenant_document"
          ? { kind: assertionKind, owner_marker_fixture: fixtureName, content_type: "application/pdf" }
          : {
              kind: assertionKind,
              owner_field: ownerField,
              highlight_fields: [ownerField, fixtureName, "total_cents"],
            },
      preconditions: ["build_identity", "actor_identity", "fixture_present", "positive_control"],
    }),
    [method, path, fixtureName, fixtureValue, checkPath, actor, owner, assertionKind, ownerField],
  );

  const save = async (approve: boolean) => {
    setBusy(true);
    setError(null);
    try {
      await api(`/api/projects/${projectId}/findings/${finding.id}/recipes`, {
        method: "POST",
        body: JSON.stringify({ ...payload, approve }),
      });
      notify("success", approve ? "Recipe revision approved." : "Recipe revision saved as draft.");
      onSaved();
    } catch (caught) {
      setError(errorMessage(caught));
    } finally {
      setBusy(false);
    }
  };

  const previewTarget = async () => {
    if (!build) return;
    setBusy(true);
    setError(null);
    try {
      const created = await api<{ revision_id: string }>(
        `/api/projects/${projectId}/findings/${finding.id}/recipes`,
        { method: "POST", body: JSON.stringify(payload) },
      );
      const response = await api<Record<string, unknown>>(
        `/api/projects/${projectId}/findings/${finding.id}/recipes/${created.revision_id}/preview?build_id=${build.id}`,
      );
      setPreview(response);
    } catch (caught) {
      setError(errorMessage(caught));
    } finally {
      setBusy(false);
    }
  };

  return (
    <Dialog
      open={open}
      onClose={onClose}
      wide
      title="Replay recipe"
      description="Approved recipes are limited to read-oriented requests with typed assertions. Credentials are sourced at execution time."
      footer={
        <>
          <Button onClick={onClose}>Cancel</Button>
          <Button busy={busy} onClick={() => void previewTarget()} disabled={!build}>
            Preview target
          </Button>
          <Button busy={busy} onClick={() => void save(false)}>
            Save draft
          </Button>
          <Button variant="primary" busy={busy} onClick={() => void save(true)}>
            Save and approve
          </Button>
        </>
      }
    >
      <div className="grid-2">
        <Field label="Method" htmlFor="recipe-method">
          <Select id="recipe-method" value={method} onChange={(event) => setMethod(event.target.value)}>
            <option value="GET">GET</option>
            <option value="HEAD">HEAD</option>
          </Select>
        </Field>
        <Field label="Assertion type" htmlFor="recipe-assertion">
          <Select
            id="recipe-assertion"
            value={assertionKind}
            onChange={(event) => setAssertionKind(event.target.value)}
          >
            <option value="cross_tenant_json_object">Cross-tenant JSON object</option>
            <option value="cross_tenant_document">Cross-tenant document</option>
          </Select>
        </Field>
      </div>
      <Field label="Relative path template" htmlFor="recipe-path" hint="No origin, no traversal. Placeholders resolve from fixtures.">
        <TextInput id="recipe-path" value={path} onChange={(event) => setPath(event.target.value)} />
      </Field>
      <div className="grid-2">
        <Field label="Fixture placeholder" htmlFor="recipe-fixture-name">
          <TextInput
            id="recipe-fixture-name"
            value={fixtureName}
            onChange={(event) => setFixtureName(event.target.value)}
          />
        </Field>
        <Field label="Fixture value" htmlFor="recipe-fixture-value">
          <TextInput
            id="recipe-fixture-value"
            value={fixtureValue}
            onChange={(event) => setFixtureValue(event.target.value)}
          />
        </Field>
        <Field label="Fixture check path" htmlFor="recipe-check-path">
          <TextInput
            id="recipe-check-path"
            value={checkPath}
            onChange={(event) => setCheckPath(event.target.value)}
          />
        </Field>
        <Field label="Owner field" htmlFor="recipe-owner-field">
          <TextInput
            id="recipe-owner-field"
            value={ownerField}
            onChange={(event) => setOwnerField(event.target.value)}
          />
        </Field>
        <Field label="Acting identity" htmlFor="recipe-actor">
          <Select id="recipe-actor" value={actor} onChange={(event) => setActor(event.target.value)}>
            {accounts.map((account) => (
              <option key={account.id} value={account.name}>
                {account.name}
              </option>
            ))}
          </Select>
        </Field>
        <Field label="Owner identity" htmlFor="recipe-owner">
          <Select id="recipe-owner" value={owner} onChange={(event) => setOwner(event.target.value)}>
            {accounts.map((account) => (
              <option key={account.id} value={account.name}>
                {account.name}
              </option>
            ))}
          </Select>
        </Field>
      </div>
      {preview ? (
        <div className="stack-sm">
          <strong>Preview</strong>
          <pre className="code code-light" tabIndex={0} role="region" aria-label="Scrollable code excerpt">{JSON.stringify(preview, null, 2)}</pre>
        </div>
      ) : null}
      {error ? <Notice tone="error">{error}</Notice> : null}
    </Dialog>
  );
}

function DispositionDialog({
  open,
  onClose,
  projectId,
  finding,
  onSaved,
}: {
  open: boolean;
  onClose: () => void;
  projectId: string;
  finding: FindingDetail;
  onSaved: () => void;
}) {
  const [disposition, setDisposition] = useState(finding.disposition);
  const [reason, setReason] = useState(finding.disposition_reason);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const { notify } = useToast();
  return (
    <Dialog
      open={open}
      onClose={onClose}
      title="Finding disposition"
      description="Closing a finding preserves the original observation and requires a reason."
      footer={
        <>
          <Button onClick={onClose}>Cancel</Button>
          <Button
            variant="primary"
            busy={busy}
            onClick={async () => {
              setBusy(true);
              try {
                await api(`/api/projects/${projectId}/findings/${finding.id}`, {
                  method: "PATCH",
                  body: JSON.stringify({ disposition, reason }),
                });
                notify("success", "Disposition recorded.");
                onSaved();
              } catch (caught) {
                setError(errorMessage(caught));
              } finally {
                setBusy(false);
              }
            }}
          >
            Save disposition
          </Button>
        </>
      }
    >
      <Field label="Disposition" htmlFor="disposition-value">
        <Select
          id="disposition-value"
          value={disposition}
          onChange={(event) => setDisposition(event.target.value)}
        >
          <option value="open">Open</option>
          <option value="false_positive">False positive</option>
          <option value="duplicate">Duplicate</option>
        </Select>
      </Field>
      <Field label="Reason" htmlFor="disposition-reason">
        <textarea
          id="disposition-reason"
          className="input"
          value={reason}
          onChange={(event) => setReason(event.target.value)}
        />
      </Field>
      {error ? <Notice tone="error">{error}</Notice> : null}
    </Dialog>
  );
}

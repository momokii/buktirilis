/* API client and shared types. */

export type Role = "admin" | "operator" | "developer" | "viewer";

export interface SessionUser {
  id: string;
  email: string;
  display_name: string;
  is_admin: boolean;
}

export interface SessionProject {
  id: string;
  slug: string;
  name: string;
  role: Role;
}

export interface Session {
  user: SessionUser;
  csrf_token: string;
  projects: SessionProject[];
  environment: { app_env: string; demo_enabled: boolean; live_enabled: boolean };
}

export interface ProjectCounts {
  builds: number;
  runs: number;
  open_findings: number;
}

export interface TargetConfig {
  id: string;
  revision: number;
  base_url: string;
  allowed_origins: string[];
  path_prefixes: string[];
  environment_label: string;
  scope_owner: string;
  authorization_reference: string;
  run_limits: Record<string, number | string>;
  created_at: string;
}

export interface Project {
  id: string;
  slug: string;
  name: string;
  description: string;
  role: Role;
  counts: ProjectCounts;
  target: TargetConfig | null;
  last_run: { id: string; status: string; kind: string; mode: string; created_at: string } | null;
  target_configs?: TargetConfig[];
  members?: { user_id: string; email: string; display_name: string; role: string; added_at: string }[];
  builds?: Build[];
  accounts?: TestAccount[];
  capabilities?: { can_admin: boolean; can_operate: boolean; can_develop: boolean; can_export: boolean };
  profiles?: { code: string; version: number; name: string; surfaces: string[] }[];
  environment?: string;
}

export interface Build {
  id: string;
  label: string;
  target_url: string;
  commit_sha: string | null;
  build_metadata: Record<string, unknown>;
  identity: { expected: string; observed: boolean; attested: boolean; source: string };
  target_config_id: string;
  created_at: string;
  run_count: number;
  openapi: { id: string; filename: string; sha256: string; operations: number; declared_server_url: string } | null;
}

export interface TestAccount {
  id: string;
  name: string;
  role: string;
  tenant: string;
  identity_check_path: string;
  credential_kind: string;
  has_credential: boolean;
  created_at: string;
}

export interface RunSummary {
  id: string;
  build: { id: string; label: string } | null;
  baseline_run_id: string | null;
  kind: string;
  mode: string;
  depth: string;
  status: string;
  profile: { code: string; version: number };
  engine: string;
  engine_version: string;
  requested_by: string;
  created_at: string;
  started_at: string | null;
  completed_at: string | null;
  coverage_complete: boolean;
  ingest_state: string;
  summary: string;
  failure_reason: string | null;
  budget: Record<string, unknown>;
  limitations: string[];
  counts?: { records: number; severity: Record<string, number> };
}

export interface Stage {
  code: string;
  state: string;
  detail: string;
  started_at: string | null;
  finished_at: string | null;
}

export interface Activity {
  at: string;
  level: string;
  code: string;
  message: string;
}

export interface RunDetail extends RunSummary {
  build: Build;
  baseline: { id: string; build_id: string; kind: string; mode: string; completed_at: string } | null;
  progress: {
    run_id: string;
    status: string;
    started_at: string | null;
    completed_at: string | null;
    elapsed_seconds: number | null;
    stages: Stage[];
    activities: Activity[];
    mode: string;
    failure_reason: string | null;
  };
  counts: {
    records: number;
    severity: Record<string, number>;
    coverage: CoverageSummary;
  };
  scope: {
    base_url: string;
    allowed_origins: string[];
    path_prefixes: string[];
    accounts: { name: string; role: string; tenant: string }[];
    unauthenticated: boolean;
    build_identity: string;
  };
}

export interface CoverageSummary {
  total: number;
  counts: Record<string, number>;
  unknown: number;
  denominator: number;
  surfaces_checked: number;
  coverage_complete: boolean;
}

export interface VerificationState {
  outcome: "fix_verified" | "still_reproducible" | "inconclusive" | "awaiting_retest";
  source: string | null;
  observed_at: string | null;
  reason_code: string | null;
  reason: string;
  stale: boolean;
  stale_note?: string;
}

export type RetestMethod = "automatic" | "guided" | "pending_evidence_review";

export interface ReportFinding {
  id: string;
  public_id: string;
  title: string;
  severity: string;
  issue_class: string;
  scope_summary: string;
  actors_summary: string;
  evidence_status: "supported" | "needs_validation";
  retest_method: RetestMethod;
  disposition: string;
  marked_ready?: boolean;
  verification: VerificationState;
  evidence_count: number;
  last_attempt_at: string | null;
  run_outcome: string | null;
  bucket?: string;
  bucket_reason?: string;
  baseline_outcome?: string | null;
  in_current_run?: boolean;
}

export interface EvidenceItem {
  id: string;
  kind: string;
  attribution: string;
  summary: string;
  actor_label: string;
  method: string;
  endpoint: string;
  artifact_id: string | null;
  created_at: string;
  payload: Record<string, unknown>;
  highlight: string[];
  artifact?: {
    id: string;
    filename: string;
    content_type: string;
    size_bytes: number;
    available: boolean;
    download_url: string;
  } | null;
  build_id?: string | null;
  build_label?: string;
  run?: { id: string; kind: string; created_at: string } | null;
}

export interface Attempt {
  id: string;
  kind: "automatic" | "guided";
  state: string;
  outcome: string | null;
  reason_code: string | null;
  reason: string;
  notes: string;
  mode: string;
  build_id: string;
  build_label: string;
  finding_id: string;
  finding_public_id: string;
  recipe_revision: string;
  requested_by: string;
  requested_at: string;
  started_at: string | null;
  finished_at: string | null;
  build_identity: { expected: string; observed: string };
  prerequisites: Record<string, unknown>;
  positive_control: Record<string, unknown>;
  assertion_result: Record<string, unknown>;
  reviews: { id: string; decision: string; reason: string; reviewer: string; created_at: string }[];
  pending_review: boolean;
  evidence: EvidenceItem[];
}

export interface ObservationRow {
  id: string;
  outcome: string;
  source: string;
  observed_at: string;
  recorded_at: string;
  accepted: boolean;
  build_id: string;
  build_label: string;
  stale: boolean;
  reason: Record<string, unknown>;
  run: { id: string; kind: string; created_at: string } | null;
}

export interface FindingDetail {
  id: string;
  public_id: string;
  project_id: string;
  title: string;
  severity: string;
  issue_class: string;
  scope_summary: string;
  actors_summary: string;
  impact: string;
  expected_behavior: string;
  observed_behavior: string;
  remediation: string;
  prerequisites: string[];
  reproduction_steps: string[];
  root_cause_hypothesis: string | null;
  evidence_status: "supported" | "needs_validation";
  retest_method: RetestMethod;
  disposition: string;
  disposition_reason: string;
  first_run_id: string | null;
  created_at: string;
  build: Build | null;
  run: { id: string; kind: string; mode: string; completed_at: string } | null;
  verification: VerificationState | null;
  latest_observation: {
    id: string;
    outcome: string;
    source: string;
    observed_at: string;
    stale: boolean;
  } | null;
  marked_ready_at: string | null;
  recipe: { id: string; state: string } | null;
  evidence: EvidenceItem[];
  evidence_missing: { evidence_id: string; summary: string; reason: string }[];
  attempts: Attempt[];
  observations: ObservationRow[];
  duplicate_candidates: { id: string; public_id: string; title: string; disposition: string }[];
  capabilities: { can_operate: boolean; can_retest: boolean; can_export: boolean };
}

export interface CoverageCheck {
  id: string;
  stage: string;
  scenario_code: string;
  scenario_title: string;
  surface: string;
  method: string;
  actor: string;
  approach: string;
  source: string;
  result: string;
  result_detail: string;
  owasp_refs: string[];
  finding_id: string | null;
  finding_public_id: string | null;
}

export interface CoverageReport {
  run_id: string;
  coverage: CoverageSummary;
  planned: Record<string, unknown>[];
  checks: CoverageCheck[];
  surfaces: { route: string; methods: string[]; source: string; tested: boolean }[];
  methodology: {
    profile: { code: string; version: number; name: string; description: string; reference_links: string[]; scenarios: Record<string, unknown>[] };
    depth: string;
    depth_limits: Record<string, unknown>;
    limits: Record<string, unknown>;
    scope: Record<string, unknown>;
    release_plan: Record<string, unknown> | null;
    identity_checks: Record<string, unknown>[];
  };
  limitations: string[];
  coverage_complete: boolean;
}

export interface Overview {
  run: RunSummary;
  build: { id: string; label: string } | null;
  severity: Record<string, number>;
  counts: { total: number; open: number; awaiting_verification: number; needs_validation: number; guided_pending: number };
  comparison: {
    bucket_counts: Record<string, number>;
    baseline_run_id: string;
    baseline_build_id: string;
    scope: { comparable: boolean; incomparable_reason: string; limitations: string[]; profile_changed: boolean; origins_changed: boolean };
  } | null;
  coverage: CoverageSummary;
  limitations: string[];
  zero_findings_message: string;
  summary: string;
  engine: { name: string; version: string };
  mode: string;
  latest_verification: { finding_id: string; public_id: string; title: string; outcome: string; source: string; observed_at: string }[];
}

export interface ExportRow {
  id: string;
  format: string;
  scope: string;
  schema_version: string;
  sha256: string;
  size_bytes: number;
  created_at: string;
  download_url: string;
}

export interface CompareRow extends ReportFinding {
  baseline_outcome: string | null;
  bucket: string;
  bucket_reason: string;
  in_current_run: boolean;
}

export interface CompareResponse {
  comparable: boolean;
  incomparable_reason: string;
  baseline: RunSummary | null;
  current: RunSummary;
  rows: CompareRow[];
  bucket_counts: Record<string, number>;
  scope: {
    comparable: boolean;
    incomparable_reason: string;
    limitations: string[];
    profile_changed: boolean;
    origins_changed: boolean;
    path_restrictions_changed: boolean;
    surfaces: { added: string[]; removed: string[] };
    coverage: Record<string, unknown>;
    baseline_scope: Record<string, unknown>;
    current_scope: Record<string, unknown>;
  };
  coverage: { baseline: CoverageSummary; current: CoverageSummary };
  latest_verification: Overview["latest_verification"];
  selectors: { id: string; build_id: string; label: string; status: string; mode: string; created_at: string }[];
}

export interface AdminUser {
  id: string;
  email: string;
  display_name: string;
  is_admin: boolean;
  is_active: boolean;
  created_at: string;
  memberships: { project_id: string; project_name: string; role: string }[];
}

let csrfToken: string | null = null;

export function setCsrfToken(token: string | null): void {
  csrfToken = token;
}

export class ApiError extends Error {
  status: number;
  payload: unknown;
  detail: string;

  constructor(status: number, detail: string, payload: unknown) {
    super(detail);
    this.status = status;
    this.detail = detail;
    this.payload = payload;
  }
}

function detailFrom(payload: unknown, fallback: string): string {
  if (typeof payload === "object" && payload !== null) {
    const record = payload as Record<string, unknown>;
    const detail = record.detail;
    if (typeof detail === "string") return detail;
    if (detail && typeof detail === "object") {
      const message = (detail as Record<string, unknown>).message;
      if (typeof message === "string") return message;
    }
  }
  return fallback;
}

export async function api<T>(path: string, init: RequestInit = {}): Promise<T> {
  const headers = new Headers(init.headers);
  const method = (init.method ?? "GET").toUpperCase();
  if (init.body && !(init.body instanceof FormData) && !headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json");
  }
  if (csrfToken && method !== "GET" && method !== "HEAD") {
    headers.set("X-CSRF-Token", csrfToken);
  }
  let response: Response;
  try {
    response = await fetch(path, { ...init, headers, credentials: "include" });
  } catch {
    throw new ApiError(0, "The API could not be reached. Check that it is running.", null);
  }
  if (response.status === 204) {
    return undefined as T;
  }
  const contentType = response.headers.get("content-type") ?? "";
  const payload: unknown = contentType.includes("application/json")
    ? await response.json().catch(() => null)
    : await response.text();
  if (!response.ok) {
    if (response.status === 401 && !path.startsWith("/api/auth/")) {
      window.dispatchEvent(new Event("buktirilis:unauthorized"));
    }
    throw new ApiError(response.status, detailFrom(payload, `Request failed (${response.status})`), payload);
  }
  return payload as T;
}

export async function apiBlob(path: string): Promise<Blob> {
  const response = await fetch(path, { credentials: "include" });
  if (!response.ok) {
    throw new ApiError(response.status, `Download failed (${response.status})`, null);
  }
  return response.blob();
}

export function errorMessage(error: unknown): string {
  if (error instanceof ApiError) return error.detail;
  if (error instanceof Error) return error.message;
  return "Something went wrong.";
}

export function reduceDetail(payload: unknown): Record<string, unknown> | null {
  if (errorLike(payload)) return payload;
  return null;
}

function errorLike(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null;
}

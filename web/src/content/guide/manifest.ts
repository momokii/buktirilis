/**
 * Ordered guide pages. The H1 in each Markdown file is the page title; this manifest
 * only carries navigation metadata and the app routes each page documents.
 */

export type GuideGroup = "Start" | "Set up" | "Run" | "Review" | "Reference";

export interface GuidePageMeta {
  slug: string;
  file: string;
  group: GuideGroup;
  summary: string;
  covers: readonly string[];
}

export const GUIDE_PAGES: readonly GuidePageMeta[] = [
  {
    slug: "start-here",
    file: "00-start-here.md",
    group: "Start",
    summary: "What this guide covers, who can do what, and how demo and live runs differ.",
    covers: [],
  },
  {
    slug: "first-run",
    file: "01-first-run.md",
    group: "Start",
    summary: "Follow one assessment from sign-in to a downloaded PDF.",
    covers: ["/projects", "/projects/:projectId/runs/:runId"],
  },
  {
    slug: "project-setup",
    file: "02-project-setup.md",
    group: "Set up",
    summary: "Create the project, target policy, identities, members, and OpenAPI revision.",
    covers: [
      "/projects",
      "/projects/:projectId",
      "/projects/:projectId/settings",
      "/admin",
    ],
  },
  {
    slug: "builds",
    file: "03-builds.md",
    group: "Set up",
    summary: "Bind a release to its approved destination and deployed identity.",
    covers: ["/projects/:projectId/builds"],
  },
  {
    slug: "queue-run",
    file: "04-queue-run.md",
    group: "Run",
    summary: "Choose the build, kind, depth, identities, and pass preflight.",
    covers: ["/projects/:projectId/runs"],
  },
  {
    slug: "monitor-run",
    file: "05-monitor-run.md",
    group: "Run",
    summary: "Read live progress, handle failures, retry, or cancel safely.",
    covers: ["/projects/:projectId/runs/:runId"],
  },
  {
    slug: "read-report",
    file: "06-read-report.md",
    group: "Review",
    summary: "Read the overview, findings, coverage, counts, and provenance.",
    covers: ["/projects/:projectId/runs/:runId"],
  },
  {
    slug: "work-finding",
    file: "07-work-finding.md",
    group: "Review",
    summary: "Understand the proof, reproduction, evidence, and verification history.",
    covers: [
      "/projects/:projectId/findings/:findingId",
      "/projects/:projectId/runs/:runId/findings/:findingId",
    ],
  },
  {
    slug: "retest",
    file: "08-retest.md",
    group: "Review",
    summary: "Choose automatic or guided retest, review evidence, and accept a verdict.",
    covers: [
      "/projects/:projectId/findings/:findingId",
      "/projects/:projectId/runs/:runId/findings/:findingId",
    ],
  },
  {
    slug: "compare",
    file: "09-compare.md",
    group: "Review",
    summary: "Compare two completed runs and read the release buckets correctly.",
    covers: ["/projects/:projectId/compare"],
  },
  {
    slug: "export",
    file: "10-export.md",
    group: "Review",
    summary: "Download the frozen PDF, CSV, or JSON snapshot and know what it contains.",
    covers: ["/projects/:projectId/runs/:runId"],
  },
  {
    slug: "where-things-live",
    file: "11-where-things-live.md",
    group: "Reference",
    summary: "A route map that resolves the duplicated Settings, Runs, and report labels.",
    covers: [
      "/projects",
      "/projects/:projectId",
      "/projects/:projectId/builds",
      "/projects/:projectId/runs",
      "/projects/:projectId/runs/:runId",
      "/projects/:projectId/compare",
      "/projects/:projectId/settings",
      "/runs",
      "/settings",
      "/admin",
    ],
  },
  {
    slug: "roles",
    file: "12-roles.md",
    group: "Reference",
    summary: "Who can create, run, review, retest, export, and administer.",
    covers: [
      "/projects/:projectId/settings",
      "/settings",
      "/admin",
    ],
  },
  {
    slug: "glossary",
    file: "13-glossary.md",
    group: "Reference",
    summary: "The statuses, outcomes, buckets, and reasons shown in the interface.",
    covers: [],
  },
  {
    slug: "troubleshooting",
    file: "14-troubleshooting.md",
    group: "Reference",
    summary: "Common blockers and the next safe action for each.",
    covers: [],
  },
  {
    slug: "limits",
    file: "15-limits.md",
    group: "Reference",
    summary: "What a run can prove, what zero findings means, and what it does not mean.",
    covers: [],
  },
];

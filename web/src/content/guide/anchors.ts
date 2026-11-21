/**
 * Mechanical drift checks for the guide. These are intentionally data, not prose:
 * the Playwright content test verifies that every route is documented somewhere and
 * that the UI labels the guide quotes still exist in their owning source file.
 */

export const APP_ROUTES = [
  "/projects",
  "/projects/:projectId",
  "/projects/:projectId/builds",
  "/projects/:projectId/runs",
  "/projects/:projectId/runs/:runId",
  "/projects/:projectId/runs/:runId/findings/:findingId",
  "/projects/:projectId/findings/:findingId",
  "/projects/:projectId/compare",
  "/projects/:projectId/settings",
  "/runs",
  "/settings",
  "/admin",
] as const;

export const UI_LABELS = [
  { text: "New run", file: "src/pages/Runs.tsx" },
  { text: "Request an assessment run", file: "src/pages/Runs.tsx" },
  { text: "Check prerequisites", file: "src/pages/Runs.tsx" },
  { text: "Queue run", file: "src/pages/Runs.tsx" },
  { text: "Deliberately run unauthenticated", file: "src/pages/Runs.tsx" },
  { text: "Open report", file: "src/pages/Runs.tsx" },
  { text: "Register build", file: "src/pages/Builds.tsx" },
  { text: "Attest identity", file: "src/pages/Builds.tsx" },
  { text: "Cancel run", file: "src/pages/Report.tsx" },
  { text: "Export PDF", file: "src/pages/Report.tsx" },
  { text: "Coverage & methodology", file: "src/pages/Report.tsx" },
  { text: "Run automatic retest", file: "src/pages/Finding.tsx" },
  { text: "Revise guided steps", file: "src/pages/Finding.tsx" },
  { text: "Accept verdict", file: "src/pages/Finding.tsx" },
  { text: "Mark ready for retest", file: "src/pages/Finding.tsx" },
  { text: "Disposition", file: "src/pages/Finding.tsx" },
  { text: "Add test identity", file: "src/pages/Settings.tsx" },
  { text: "Rotate credential", file: "src/pages/Settings.tsx" },
  { text: "Release comparison", file: "src/pages/Compare.tsx" },
  { text: "Provision an account", file: "src/pages/Admin.tsx" },
  { text: "Register an approved project", file: "src/pages/Admin.tsx" },
] as const;

export const EXEMPT_ROUTES = new Set<string>([]);

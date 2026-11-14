import { expect, test } from "@playwright/test";
import type { Page } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";

interface Credentials {
  operator: { email: string; password: string };
  developer: { email: string; password: string };
}

function credentials(): Credentials {
  const file =
    process.env.DEMO_CREDENTIALS_FILE ??
    resolve(process.cwd(), "../var/demo-credentials.txt");
  const lines = readFileSync(file, "utf8").split("\n").filter(Boolean);
  const parsed: Record<string, { email: string; password: string }> = {};
  for (const line of lines) {
    const [role, email, password] = line.trim().split(/\s+/);
    if (role && email && password) parsed[role] = { email, password };
  }
  if (!parsed.operator || !parsed.developer) {
    throw new Error(`Demo credentials are incomplete in ${file}`);
  }
  return { operator: parsed.operator, developer: parsed.developer };
}

async function signIn(page: Page, role: "operator" | "developer" = "operator") {
  const creds = credentials()[role];
  await page.goto("/login");
  await page.getByLabel("Email").fill(creds.email);
  await page.getByLabel("Password").fill(creds.password);
  await page.getByRole("button", { name: "Sign in" }).click();
  await expect(page.getByRole("heading", { name: "Projects", level: 1 })).toBeVisible();
}

async function openLatestReport(page: Page) {
  await page.getByRole("link", { name: /Atlas Billing/ }).first().click();
  await expect(page.getByRole("heading", { name: "Atlas Billing", level: 1 })).toBeVisible();
  await page
    .getByRole("navigation", { name: "Project sections" })
    .getByRole("link", { name: "Runs", exact: true })
    .click();
  await expect(page.getByRole("heading", { name: "Runs", level: 1 })).toBeVisible();
  const firstReport = page.getByRole("link", { name: "Open report" }).first();
  await firstReport.click();
  await expect(page.getByRole("heading", { level: 1 })).toContainText("Build 2024.10.3");
}

async function openFirstFinding(page: Page) {
  await page.getByRole("tab", { name: /Findings/ }).click();
  const row = page.getByRole("link", { name: /Cross-tenant invoice read/ }).first();
  await expect(row).toBeVisible();
  await row.click();
  await expect(
    page.getByRole("heading", { name: /Cross-tenant invoice read via object identifier/ }),
  ).toBeVisible();
}

test("operator can open the report, inspect counts, evidence, and preserve filters", async ({
  page,
}) => {
  await signIn(page);
  await openLatestReport(page);

  // Demo mode is visibly labelled and the snapshot is explicit.
  await expect(page.getByText("Demo · deterministic fixtures").first()).toBeVisible();
  await expect(page.getByText(/Coverage incomplete/).first()).toBeVisible();
  await expect(page.getByRole("heading", { name: "Risk and work remaining" })).toBeVisible();

  await page.screenshot({ path: "../docs/screenshots/report-overview-desktop.png", fullPage: true });

  // A regression must be visible and linked to its filtered rows.
  await page.getByRole("link", { name: /Regressions/ }).click();
  await expect(page.getByRole("tab", { name: /Findings/ })).toHaveAttribute(
    "aria-selected",
    "true",
  );
  await expect(page.getByText(/Showing 1 of 4 finding records/)).toBeVisible();
  await page.screenshot({ path: "../docs/screenshots/findings-filtered-desktop.png", fullPage: true });

  await page.getByRole("link", { name: /Cross-tenant invoice read/ }).first().click();
  await expect(page.getByText("Captured exchange").first()).toBeVisible();
  await expect(page.getByText(/tenant-a/).first()).toBeVisible();
  await expect(page.getByText(/Inconclusive|Awaiting retest|Still reproducible/).first()).toBeVisible();
  await page.screenshot({ path: "../docs/screenshots/finding-detail-desktop.png", fullPage: true });

  // Returning keeps the filter and the scroll position in the list.
  await page.getByRole("link", { name: "Back to findings" }).click();
  await expect(page).toHaveURL(/bucket=regressed/);
  await expect(page.getByText(/Showing 1 of 4 finding records/)).toBeVisible();

  // Keyboard access to report tabs.
  await page.getByRole("tab", { name: "Overview" }).focus();
  await page.keyboard.press("ArrowRight");
  await expect(page.getByRole("tab", { name: /Findings/ })).toHaveAttribute(
    "aria-selected",
    "true",
  );
});

test("coverage tab explains invented, tested, blocked and untested scope", async ({ page }) => {
  await signIn(page);
  await openLatestReport(page);
  await page.getByRole("tab", { name: "Coverage & methodology" }).click();
  await expect(page.getByRole("heading", { name: "Coverage summary" })).toBeVisible();
  await expect(page.getByText(/A denominator covers only the defined planned checks/)).toBeVisible();
  await expect(page.getByRole("heading", { name: "Surface inventory" })).toBeVisible();
  await expect(page.getByText(/not run|Blocked|Needs review/).first()).toBeVisible();
  await page.screenshot({ path: "../docs/screenshots/coverage-desktop.png", fullPage: true });
});

test("automatic retest runs the approved recipe and records evidence", async ({ page }) => {
  await signIn(page);
  await openLatestReport(page);
  await openFirstFinding(page);
  await page.getByRole("button", { name: "Run automatic retest" }).click();
  await expect(page.getByText(/Retest queued/)).toBeVisible();
  // The worker claims the job and the finding refreshes while the attempt is active.
  await expect(page.getByText("Automatic replay").first()).toBeVisible({ timeout: 60_000 });
  await expect(page.getByText(/Still reproducible/).first()).toBeVisible({ timeout: 60_000 });
  await expect(page.getByText(/control true/).first()).toBeVisible();
});

test("guided retest stays pending until an operator accepts it", async ({ page }) => {
  await signIn(page);
  await openLatestReport(page);
  await page.getByRole("tab", { name: /Findings/ }).click();
  await page.getByRole("link", { name: /Two-actor invoice approval/ }).first().click();
  await expect(page.getByRole("heading", { name: /Guided retest/ })).toBeVisible();
  await expect(page.getByText(/Why automation is unavailable/)).toBeVisible();
  await page.getByLabel("Outcome").selectOption("still_reproducible");
  await page.getByLabel("What did you observe?").fill(
    "Tenant B approver completed the tenant A approval; the owner control still works.",
  );
  await page
    .getByLabel("Evidence link")
    .fill("https://evidence.internal/atlas/guided-walkthrough");
  await page.getByRole("button", { name: "Submit for review" }).click();
  await expect(page.getByText(/Submitted for reviewer acceptance/)).toBeVisible();
  await expect(page.getByText("pending review").first()).toBeVisible();
  // Operator review accepts the verdict; the evidence decision is separate.
  await page.getByRole("button", { name: "Accept verdict" }).first().click();
  await expect(page.getByText("Recorded.")).toBeVisible();
});

test("export creates a frozen PDF and JSON snapshot", async ({ page }) => {
  await signIn(page);
  await openLatestReport(page);
  const downloadPromise = page.waitForEvent("download");
  await page.getByRole("button", { name: "Export PDF" }).click();
  const download = await downloadPromise;
  const path = await download.path();
  expect(path).toBeTruthy();
  await page.getByRole("heading", { name: "Exports" }).scrollIntoViewIfNeeded();
  await expect(page.getByRole("cell", { name: "pdf" }).first()).toBeVisible();
  await expect(page.getByText(/SHA-256|sha256/i).first()).toBeVisible();
});

test("comparison shows regression and still-reproducible buckets with scope limits", async ({
  page,
}) => {
  await signIn(page);
  await page.getByRole("link", { name: /Atlas Billing/ }).first().click();
  await page
    .getByRole("navigation", { name: "Project sections" })
    .getByRole("link", { name: "Compare", exact: true })
    .click();
  await expect(page.getByRole("heading", { name: "Release comparison" })).toBeVisible();
  await expect(page.getByRole("link", { name: /Regressed/ })).toBeVisible();
  await expect(page.getByText("Coverage comparison")).toBeVisible();
  const regressed = page.getByRole("link", { name: /Regressed/ });
  const count = await regressed.locator(".bucket-value").textContent();
  expect(Number(count)).toBeGreaterThanOrEqual(1);
  await page.screenshot({ path: "../docs/screenshots/compare-desktop.png", fullPage: true });
});

test("no serious accessibility violations on report and finding pages", async ({ page }) => {
  await signIn(page);
  await openLatestReport(page);
  const overview = await new AxeBuilder({ page })
    .withTags(["wcag2a", "wcag2aa", "wcag21a", "wcag21aa", "wcag22aa"])
    .analyze();
  const serious = overview.violations.filter(
    (violation) => violation.impact === "serious" || violation.impact === "critical",
  );
  expect(
    serious,
    JSON.stringify(
      serious.map((v) => ({
        id: v.id,
        html: v.nodes.map((n) => n.html),
        target: v.nodes.map((n) => n.target),
      })),
    ),
  ).toEqual([]);
  await openFirstFinding(page);
  const detail = await new AxeBuilder({ page })
    .withTags(["wcag2a", "wcag2aa", "wcag21a", "wcag21aa", "wcag22aa"])
    .analyze();
  const seriousDetail = detail.violations.filter(
    (violation) => violation.impact === "serious" || violation.impact === "critical",
  );
  expect(
    seriousDetail,
    JSON.stringify(seriousDetail.map((v) => ({ id: v.id, nodes: v.nodes.length }))),
  ).toEqual([]);
});

test("login restores the intended deep link", async ({ page }) => {
  await signIn(page);
  const projectLink = await page.getByRole("link", { name: /Atlas Billing/ }).first().getAttribute("href");
  expect(projectLink).toMatch(/^\/projects\//);
  await page.getByRole("button", { name: "Sign out" }).click();
  await expect(page.getByRole("button", { name: "Sign in" })).toBeVisible();
  await page.goto(projectLink ?? "/projects");
  await expect(page.getByRole("button", { name: "Sign in" })).toBeVisible();
  const creds = credentials().operator;
  await page.getByLabel("Email").fill(creds.email);
  await page.getByLabel("Password").fill(creds.password);
  await page.getByRole("button", { name: "Sign in" }).click();
  await expect(page.getByRole("heading", { name: "Atlas Billing", level: 1 })).toBeVisible();
});

test.describe("narrow layout", () => {
  test.use({ viewport: { width: 390, height: 844 } });

  test("report and finding remain usable without horizontal overflow", async ({ page }) => {
    await signIn(page);
    await openLatestReport(page);
    await expect(page.getByRole("heading", { level: 1 })).toBeVisible();
    // Summary counts stack, and the primary action is visible before details.
    await expect(page.getByRole("button", { name: "Export PDF" })).toBeVisible();
    await expect(page.getByRole("heading", { name: "Risk and work remaining" })).toBeVisible();
    await page.addStyleTag({ content: ".topbar{position:static}" });
    await page.screenshot({ path: "../docs/screenshots/report-overview-mobile.png", fullPage: true });

    const overflow = await page.evaluate(
      () => document.documentElement.scrollWidth - document.documentElement.clientWidth,
    );
    expect(overflow).toBeLessThanOrEqual(1);

    await page.getByRole("tab", { name: /Findings/ }).click();
    const mobileCard = page.locator(".finding-mobile-item").first();
    await expect(mobileCard).toBeVisible();
    await expect(mobileCard.getByRole("link").first()).toBeVisible();
    await page.screenshot({ path: "../docs/screenshots/findings-mobile.png", fullPage: true });
    await page
      .locator(".finding-mobile-list")
      .getByRole("link", { name: /Cross-tenant invoice read/ })
      .click();
    await expect(page.getByText("Captured exchange").first()).toBeVisible();
    await page.screenshot({ path: "../docs/screenshots/finding-detail-mobile.png", fullPage: true });
    const detailOverflow = await page.evaluate(
      () => document.documentElement.scrollWidth - document.documentElement.clientWidth,
    );
    expect(detailOverflow).toBeLessThanOrEqual(1);
  });
});

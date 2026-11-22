import { expect, test } from "@playwright/test";
import type { Page } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";
import { readFileSync, readdirSync } from "node:fs";
import { resolve } from "node:path";
import { APP_ROUTES, UI_LABELS } from "../src/content/guide/anchors";
import { GUIDE_PAGES } from "../src/content/guide/manifest";
import { FIGURE_META } from "../src/content/guide/figureMeta";
import { parseGuide, parseInline, type GuideBlock } from "../src/content/guide/parse";

const webRoot = process.cwd();
const guideRoot = resolve(webRoot, "src/content/guide/guide");

function markdownFiles(): string[] {
  return readdirSync(guideRoot)
    .filter((file) => file.endsWith(".md"))
    .sort();
}

function inlineLinks(text: string): string[] {
  return parseInline(text)
    .filter((token) => token.kind === "link")
    .map((token) => (token.kind === "link" ? token.href : ""));
}

function blockTexts(block: GuideBlock): string[] {
  if (block.kind === "heading" || block.kind === "paragraph" || block.kind === "alert") {
    return [block.text];
  }
  if (block.kind === "figure") return [block.alt, block.caption];
  if (block.kind === "list") return block.items;
  if (block.kind === "table") {
    return [...block.headers, ...block.rows.flat()];
  }
  return [];
}

function allLinks(blocks: GuideBlock[]): string[] {
  return blocks.flatMap((block) => blockTexts(block).flatMap(inlineLinks));
}

interface ParsedPage {
  file: string;
  slug: string;
  result: ReturnType<typeof parseGuide>;
}

test.describe("guide content", () => {
  const pages: ParsedPage[] = GUIDE_PAGES.map((meta) => {
    const file = resolve(guideRoot, meta.file);
    const source = readFileSync(file, "utf8");
    return { file, slug: meta.slug, result: parseGuide(source, meta.slug) };
  });

  test("manifest and markdown files are one-to-one", () => {
    const manifestFiles = GUIDE_PAGES.map((page) => page.file).sort();
    expect(manifestFiles).toEqual(markdownFiles());
    expect(new Set(GUIDE_PAGES.map((page) => page.slug)).size).toBe(GUIDE_PAGES.length);
    expect(new Set(GUIDE_PAGES.map((page) => page.file)).size).toBe(GUIDE_PAGES.length);
  });

  test("every page parses with the supported grammar and one H1", () => {
    for (const page of pages) {
      const { result } = page;
      expect(result.problems, `${page.slug}: ${JSON.stringify(result.problems)}`).toEqual([]);
      expect(result.title, `${page.slug} has no title`).not.toBe("Untitled guide page");
      expect(result.blocks[0]?.kind, `${page.slug} does not start with a heading`).toBe(
        "heading",
      );
      const h1s = result.blocks.filter(
        (block) => block.kind === "heading" && block.level === 1,
      );
      expect(h1s, `${page.slug} must have exactly one H1`).toHaveLength(1);
      expect(h1s[0]?.kind === "heading" ? h1s[0].text : "", page.slug).toBe(result.title);
    }
  });

  test("heading ranks do not skip and anchors are unique", () => {
    for (const page of pages) {
      let lastRank = 1;
      const ids = new Set<string>();
      for (const block of page.result.blocks) {
        if (block.kind !== "heading") continue;
        expect(block.id, `${page.slug} anchor ${block.id}`).toMatch(/^[a-z0-9-]+$/);
        expect(ids.has(block.id), `${page.slug} duplicate anchor ${block.id}`).toBe(false);
        ids.add(block.id);
        if (block.level > lastRank + 1) {
          throw new Error(`${page.slug} skips from H${lastRank} to H${block.level}: ${block.text}`);
        }
        lastRank = block.level;
      }
      for (const heading of page.result.headings) {
        expect(ids.has(heading.id)).toBe(true);
      }
    }
  });

  test("internal guide links resolve and app links are catalogued", () => {
    const bySlug = new Map(pages.map((page) => [page.slug, page]));
    const slugs = new Set(GUIDE_PAGES.map((page) => page.slug));
    for (const page of pages) {
      for (const href of allLinks(page.result.blocks)) {
        if (href.startsWith("#")) {
          const id = href.slice(1);
          expect(
            page.result.headings.some((heading) => heading.id === id),
            `${page.slug} has no #${id}`,
          ).toBe(true);
          continue;
        }
        if (href.startsWith("/guide")) {
          const [slugPart, anchor] = href.replace(/^\/guide\/?/, "").split("#");
          if (slugPart) {
            const target = bySlug.get(slugPart);
            expect(target, `${page.slug} links to missing /guide/${slugPart}`).toBeTruthy();
            if (anchor && target) {
              expect(
                target.result.headings.some((heading) => heading.id === anchor),
                `${page.slug} links to missing /guide/${slugPart}#${anchor}`,
              ).toBe(true);
            }
          }
          continue;
        }
        expect(
          APP_ROUTES.includes(href as (typeof APP_ROUTES)[number]),
          `${page.slug} links to uncatalogued app route ${href}`,
        ).toBe(true);
      }
      expect(slugs.has(page.slug)).toBe(true);
    }
  });

  test("external links are HTTPS-only and limited to documentation hosts", () => {
    const allowed = new Set(["https://owasp.org", "https://www.w3.org"]);
    for (const page of pages) {
      for (const href of allLinks(page.result.blocks)) {
        if (href.startsWith("/") || href.startsWith("#")) continue;
        const url = new URL(href);
        expect(url.protocol, `${page.slug}: ${href}`).toBe("https:");
        const allowedHost = [...allowed].some(
          (origin) => href === origin || href.startsWith(`${origin}/`),
        );
        expect(allowedHost, `${page.slug}: external host is not allowlisted: ${href}`).toBe(true);
      }
    }
  });

  test("content has no dead-in-app docs links, IPs, or executable schemes", () => {
    for (const page of pages) {
      const source = readFileSync(page.file, "utf8");
      expect(source, page.slug).not.toMatch(/\b\d{1,3}(?:\.\d{1,3}){3}\b/);
      expect(source, page.slug).not.toContain("docs/");
      expect(source, page.slug).not.toContain("javascript:");
      expect(source, page.slug).not.toContain("data:");
      expect(source, page.slug).not.toContain("dangerouslySetInnerHTML");
      expect(source, page.slug).not.toMatch(/\bhttp:\/\//);
    }
    for (const file of ["src/pages/Guide.tsx", "src/content/guide/parse.ts"]) {
      const source = readFileSync(resolve(webRoot, file), "utf8");
      expect(source, file).not.toContain("dangerouslySetInnerHTML");
    }
  });

  test("every UI label quoted by the guide still exists in its source", () => {
    for (const label of UI_LABELS) {
      const source = readFileSync(resolve(webRoot, label.file), "utf8");
      expect(source, `${label.file} no longer contains “${label.text}”`).toContain(label.text);
    }
  });

  test("the manifest covers every app route", () => {
    const covered = new Set(GUIDE_PAGES.flatMap((page) => page.covers));
    for (const route of APP_ROUTES) {
      expect(covered.has(route), `No guide page covers ${route}`).toBe(true);
    }
  });

  test("figures have accessible text, valid sizes, and matching 2x files", () => {
    const imageRoot = resolve(guideRoot, "images");
    const referenced = new Set<string>();
    let totalBytes = 0;
    let totalFigures = 0;
    const pngSize = (file: string) => {
      const bytes = readFileSync(file);
      return { width: bytes.readUInt32BE(16), height: bytes.readUInt32BE(20) };
    };
    for (const page of pages) {
      const figures = page.result.blocks.filter((block) => block.kind === "figure");
      expect(figures.length, `${page.slug} has too many figures`).toBeLessThanOrEqual(2);
      figures.forEach((figure, index) => {
        if (figure.kind !== "figure") return;
        totalFigures += 1;
        expect(figure.number, `${page.slug} figure numbering`).toBe(index + 1);
        expect(figure.src, `${page.slug} figure source`).toMatch(
          /^images\/(?:[a-z0-9][a-z0-9-]*\/)*[a-z0-9][a-z0-9-]*\.png$/,
        );
        expect(figure.src, `${page.slug} figure must not name @2x`).not.toContain("@2x");
        expect(figure.alt.length, `${page.slug} figure alt`).toBeGreaterThanOrEqual(8);
        expect(figure.alt.length, `${page.slug} figure alt`).toBeLessThanOrEqual(155);
        expect(figure.caption.length, `${page.slug} figure caption`).toBeGreaterThanOrEqual(20);
        expect(figure.caption.length, `${page.slug} figure caption`).toBeLessThanOrEqual(240);
        expect(figure.caption, `${page.slug} figure caption punctuation`).toMatch(/[.!?]$/);
        expect(figure.alt, `${page.slug} figure alt duplicates caption`).not.toBe(figure.caption);
        const oneX = resolve(guideRoot, figure.src);
        const twoX = oneX.replace(/\.png$/, "@2x.png");
        referenced.add(figure.src);
        expect(readFileSync(oneX).subarray(1, 4).toString(), `${figure.src} is not PNG`).toBe("PNG");
        const oneSize = pngSize(oneX);
        const twoSize = pngSize(twoX);
        expect(twoSize.width).toBe(oneSize.width * 2);
        expect(twoSize.height).toBe(oneSize.height * 2);
        expect(FIGURE_META[figure.src], `${figure.src} has no figure meta`).toEqual(oneSize);
        const oneBytes = readFileSync(oneX).byteLength;
        const twoBytes = readFileSync(twoX).byteLength;
        expect(oneBytes, `${figure.src} 1x size`).toBeLessThanOrEqual(300_000);
        expect(twoBytes, `${figure.src} 2x size`).toBeLessThanOrEqual(700_000);
        totalBytes += oneBytes + twoBytes;
      });
    }
    expect(totalFigures).toBeGreaterThan(0);
    expect(totalFigures).toBeLessThanOrEqual(8);
    expect(totalBytes, "total guide image budget").toBeLessThanOrEqual(3_000_000);
    const allImages = readdirSync(imageRoot, { recursive: true })
      .filter((name): name is string => typeof name === "string" && name.endsWith(".png"))
      .filter((name) => !name.endsWith("@2x.png"))
      .map((name) => `images/${name.replaceAll("\\", "/")}`)
      .sort();
    expect(allImages).toEqual([...referenced].sort());
  });

  test("tables have captions and the guide stays within its size budget", () => {
    const total = markdownFiles().reduce(
      (sum, file) => sum + readFileSync(resolve(guideRoot, file), "utf8").length,
      0,
    );
    expect(total).toBeLessThan(120_000);
    for (const page of pages) {
      for (const block of page.result.blocks) {
        if (block.kind === "table") {
          expect(block.caption, `${page.slug} has a table without a caption`).toBeTruthy();
          expect(
            block.rows.some((row) => row.every((cell) => /^:?-{3,}:?$/.test(cell))),
            `${page.slug} rendered a table separator as data`,
          ).toBe(false);
        }
      }
    }
  });
});

async function signIn(page: Page) {
  const credentialsFile =
    process.env.DEMO_CREDENTIALS_FILE ?? resolve(webRoot, "../var/demo-credentials.txt");
  const line = readFileSync(credentialsFile, "utf8")
    .split("\n")
    .find((entry) => entry.startsWith("operator "));
  if (!line) throw new Error(`No operator credentials in ${credentialsFile}`);
  const [, email, password] = line.trim().split(/\s+/);
  await page.goto("/login");
  await page.getByLabel("Email").fill(email);
  await page.getByLabel("Password").fill(password);
  await page.getByRole("button", { name: "Sign in" }).click();
  await expect(page.getByRole("heading", { name: "Projects", level: 1 })).toBeVisible();
}

test("guide is public and reachable from the login page", async ({ page }) => {
  await page.goto("/guide");
  await expect(page.getByRole("heading", { name: "Guide", level: 1 })).toBeVisible();
  await expect(page.getByRole("link", { name: "Sign in", exact: true })).toBeVisible();
  await expect(page.locator("img.brand-logo")).toHaveAttribute("src", "/logo-mark.svg");
  await expect(page.locator('link[rel="icon"]')).toHaveAttribute("href", "/favicon.svg");
  const favicon = await page.request.get("/favicon.svg");
  expect(favicon.status()).toBe(200);
  await page.goto("/login");
  await page.getByRole("link", { name: "Read the user guide" }).click();
  await expect(page.getByRole("heading", { name: "Guide", level: 1 })).toBeVisible();
  await expect(page).toHaveTitle(/Guide/);

  const axe = await new AxeBuilder({ page })
    .withTags(["wcag2a", "wcag2aa", "wcag21a", "wcag21aa", "wcag22aa"])
    .analyze();
  const serious = axe.violations.filter(
    (violation) => violation.impact === "serious" || violation.impact === "critical",
  );
  expect(serious, JSON.stringify(serious.map((violation) => violation.id))).toEqual([]);
});

test("guide is reachable from the main navigation and search works", async ({ page }) => {
  await signIn(page);
  await page.getByRole("link", { name: "Guide", exact: true }).click();
  await expect(page.getByRole("heading", { name: "Guide", level: 1 })).toBeVisible();
  await expect(page.getByRole("searchbox", { name: "Search the guide" })).toBeVisible();
  await page.getByRole("searchbox", { name: "Search the guide" }).fill("retest");
  await expect(page.locator(".guide-result-count")).toContainText("result");
  await expect(page.getByRole("link", { name: /Retest a finding/ }).first()).toBeVisible();
});

test("guide figures render with alt text, dimensions, and 2x sources", async ({ page }) => {
  await page.goto("/guide/queue-run");
  const figure = page.locator("figure.guide-figure").first();
  await expect(figure).toBeVisible();
  const image = figure.locator("img");
  await expect(image).toHaveAttribute("alt", /\S{8,}/);
  await expect(image).toHaveAttribute("width", "768");
  await expect(image).toHaveAttribute("height", "888");
  await expect(image).toHaveAttribute("srcset", /@2x/);
  await expect(figure.locator("figcaption")).toContainText("Figure 1.");
  expect(await image.evaluate((node) => (node as HTMLImageElement).naturalWidth)).toBeGreaterThan(0);
  const axe = await new AxeBuilder({ page })
    .withTags(["wcag2a", "wcag2aa", "wcag21a", "wcag21aa", "wcag22aa"])
    .analyze();
  const serious = axe.violations.filter(
    (violation) => violation.impact === "serious" || violation.impact === "critical",
  );
  expect(serious, JSON.stringify(serious.map((violation) => violation.id))).toEqual([]);
});

test("guide page has one H1, a page title, working TOC focus, and no axe issues", async ({
  page,
}) => {
  await signIn(page);
  await page.goto("/guide/glossary");
  await expect(page.getByRole("heading", { level: 1 })).toHaveText("Status and outcome glossary");
  await expect(page).toHaveTitle(/Status and outcome glossary/);
  const toc = page.getByRole("navigation", { name: "On this page" });
  const firstLink = toc.getByRole("link").first();
  const targetId = (await firstLink.getAttribute("href"))?.slice(1);
  await firstLink.click();
  await expect
    .poll(() => page.evaluate(() => document.activeElement?.id ?? ""))
    .toBe(targetId);
  const top = await page.locator(`#${targetId}`).evaluate((node) => node.getBoundingClientRect().top);
  expect(top).toBeGreaterThanOrEqual(56);

  const axe = await new AxeBuilder({ page })
    .withTags(["wcag2a", "wcag2aa", "wcag21a", "wcag21aa", "wcag22aa"])
    .analyze();
  const serious = axe.violations.filter(
    (violation) => violation.impact === "serious" || violation.impact === "critical",
  );
  expect(serious, JSON.stringify(serious.map((violation) => violation.id))).toEqual([]);
});

test("mobile guide menu closes after choosing a page", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto("/guide/glossary");
  await page.getByText("Browse guide pages").click();
  await page.getByRole("link", { name: "Export evidence", exact: true }).click();
  await expect(page.getByRole("heading", { name: "Export evidence", level: 1 })).toBeVisible();
  await expect(page.locator("details.guide-mobile-nav")).not.toHaveAttribute("open", "");
});

test("guide index and page reflow at 320px and 390px without page overflow", async ({ page }) => {
  await signIn(page);
  for (const width of [320, 390]) {
    await page.setViewportSize({ width, height: 844 });
    for (const path of ["/guide", "/guide/glossary"]) {
      await page.goto(path);
      await expect(page.getByRole("heading", { level: 1 })).toBeVisible();
      const overflow = await page.evaluate(
        () => document.documentElement.scrollWidth - document.documentElement.clientWidth,
      );
      expect(overflow, `horizontal overflow at ${width}px on ${path}`).toBeLessThanOrEqual(1);
    }
  }
});

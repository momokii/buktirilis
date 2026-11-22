#!/usr/bin/env node
/**
 * Capture the reviewed, annotated guide figures from the local demo deployment.
 * This is intentionally not part of the app build. Run after starting a demo
 * stack with `APP_ENV=development` and `DEMO_SEED_ENABLED=true`.
 *
 *   CAPTURE_BASE_URL=http://127.0.0.1:5181 \
 *   DEMO_CREDENTIALS_FILE=/tmp/buktirilis-guide-shots/credentials.txt \
 *   node scripts/capture-guide-screenshots.mjs
 *
 * The script refuses to capture unless the demo banner is present. It uses
 * Playwright's device scale factor for 2x assets, adds numbered boxes, and uses
 * ImageMagick only for the final 1x/2x files. No real project data is read by
 * design; use the synthetic Atlas Billing fixture.
 */
import { chromium } from "@playwright/test";
import { execFileSync } from "node:child_process";
import { mkdirSync, readFileSync, rmSync, writeFileSync } from "node:fs";
import { dirname, resolve } from "node:path";

const baseURL = process.env.CAPTURE_BASE_URL ?? "http://127.0.0.1:5181";
const credentialsFile =
  process.env.DEMO_CREDENTIALS_FILE ?? resolve(process.cwd(), "../var/demo-credentials.txt");
const outRoot = resolve(process.cwd(), "src/content/guide/guide/images");
const rawRoot = "/tmp/buktirilis-guide-raw";
const figureMeta = {};

const credentials = readFileSync(credentialsFile, "utf8")
  .split("\n")
  .filter(Boolean)
  .map((line) => line.trim().split(/\s+/));
const operator = credentials.find(([role]) => role === "operator");
if (!operator) throw new Error(`No operator credentials in ${credentialsFile}`);

const browser = await chromium.launch({ headless: true });
const page = await browser.newPage({
  viewport: { width: 1440, height: 1000 },
  deviceScaleFactor: 2,
  colorScheme: "light",
  locale: "en-US",
  timezoneId: "UTC",
  reducedMotion: "reduce",
});

async function signIn() {
  await page.goto(`${baseURL}/login`);
  await page.getByLabel("Email").fill(operator[1]);
  await page.getByLabel("Password").fill(operator[2]);
  await page.getByRole("button", { name: "Sign in" }).click();
  await page.getByRole("heading", { name: "Projects", level: 1 }).waitFor();
  if ((await page.locator(".demo-banner").count()) === 0) {
    throw new Error("Refusing capture: demo banner is not visible");
  }
}

async function openProject() {
  await page.getByRole("link", { name: /Atlas Billing/ }).first().click();
  await page.getByRole("navigation", { name: "Project sections" }).waitFor();
}

async function openReport() {
  await page.getByRole("navigation", { name: "Project sections" }).getByRole("link", { name: "Runs", exact: true }).click();
  await page.getByRole("link", { name: "Open report" }).first().click();
  await page.getByRole("tab", { name: /Findings/ }).waitFor();
}

async function openFinding() {
  await page.getByRole("tab", { name: /Findings/ }).click();
  await page.getByRole("link", { name: /Cross-tenant invoice read/ }).first().click();
  await page.getByRole("heading", { name: /Cross-tenant invoice read/ }).waitFor();
}

function pageBox(locator) {
  return locator.evaluate((element) => {
    const rect = element.getBoundingClientRect();
    return {
      x: rect.left + window.scrollX,
      y: rect.top + window.scrollY,
      width: rect.width,
      height: rect.height,
    };
  });
}

async function resolveMarks(marks) {
  const resolved = [];
  for (const mark of marks) {
    const locator = page.locator(mark.selector).first();
    await locator.waitFor({ state: "visible", timeout: 15_000 });
    resolved.push({ ...mark, box: await pageBox(locator) });
  }
  return resolved;
}

async function paintOverlay(target, marks, options = {}) {
  await target.evaluate(
    (element, { marks, pad, offsetX, offsetY }) => {
      const previous = element.querySelector("[data-guide-capture-overlay]");
      previous?.remove();
      const overlay = document.createElement("div");
      overlay.dataset.guideCaptureOverlay = "true";
      overlay.style.position = "absolute";
      overlay.style.left = "0";
      overlay.style.top = "0";
      overlay.style.width = `${element.scrollWidth}px`;
      overlay.style.height = `${element.scrollHeight}px`;
      overlay.style.pointerEvents = "none";
      overlay.style.zIndex = "2147483647";
      for (const mark of marks) {
        const box = document.createElement("div");
        box.style.position = "absolute";
        box.style.left = `${mark.box.x - offsetX - pad}px`;
        box.style.top = `${mark.box.y - offsetY - pad}px`;
        box.style.width = `${mark.box.width + pad * 2}px`;
        box.style.height = `${mark.box.height + pad * 2}px`;
        box.style.border = "3px solid #1d4ed8";
        box.style.borderRadius = "7px";
        box.style.boxShadow = "0 0 0 2px #ffffff, 0 0 0 4px rgba(29, 78, 216, 0.2)";
        overlay.appendChild(box);

        const badge = document.createElement("div");
        badge.textContent = String(mark.number);
        badge.style.position = "absolute";
        badge.style.left = `${mark.box.x - offsetX - pad - 15}px`;
        badge.style.top = `${mark.box.y - offsetY - pad - 15}px`;
        badge.style.width = "30px";
        badge.style.height = "30px";
        badge.style.borderRadius = "999px";
        badge.style.background = "#0f172a";
        badge.style.color = "#ffffff";
        badge.style.border = "2px solid #ffffff";
        badge.style.boxShadow = "0 2px 6px rgba(15, 23, 42, 0.28)";
        badge.style.display = "flex";
        badge.style.alignItems = "center";
        badge.style.justifyContent = "center";
        badge.style.font = "700 17px/1 ui-sans-serif, system-ui, sans-serif";
        overlay.appendChild(badge);
      }
      element.appendChild(overlay);
    },
    { marks, pad: options.pad ?? 7, offsetX: options.offsetX ?? 0, offsetY: options.offsetY ?? 0 },
  );
}

async function clearOverlay(target) {
  await target.evaluate((element) => element.querySelector("[data-guide-capture-overlay]")?.remove());
}

function cropTo1x(raw, out, crop, padBottom = 0) {
  mkdirSync(dirname(out), { recursive: true });
  const width = Math.round(crop.width);
  const height = Math.round(crop.height);
  const x = Math.round(crop.x);
  const y = Math.round(crop.y);
  execFileSync("convert", [
    raw,
    "-crop",
    `${width * 2}x${height * 2}+${x * 2}+${y * 2}`,
    "+repage",
    "-resize",
    "50%",
    ...(padBottom ? ["-background", "#ffffff", "-gravity", "south", "-splice", `0x${padBottom}`] : []),
    "-define",
    "png:compression-level=9",
    "-strip",
    out,
  ]);
  const at2x = out.replace(/\.png$/, "@2x.png");
  execFileSync("convert", [
    raw,
    "-crop",
    `${width * 2}x${height * 2}+${x * 2}+${y * 2}`,
    "+repage",
    ...(padBottom ? ["-background", "#ffffff", "-gravity", "south", "-splice", `0x${padBottom * 2}`] : []),
    "-define",
    "png:compression-level=9",
    "-strip",
    at2x,
  ]);
  const png = readFileSync(out);
  return {
    width: png.readUInt32BE(16),
    height: png.readUInt32BE(20),
  };
}

function record(name, dimensions) {
  figureMeta[`images/${name}.png`] = dimensions;
}

async function captureElement({ name, selector, marks, prepare, viewport = { width: 820, height: 1200 } }) {
  await page.setViewportSize(viewport);
  await page.goto(`${baseURL}/projects`);
  await page.getByRole("heading", { name: "Projects", level: 1 }).waitFor();
  await openProject();
  await prepare();
  const target = page.locator(selector).first();
  await target.waitFor({ state: "visible" });
  const box = await pageBox(target);
  const resolved = await resolveMarks(marks);
  const crop = {
    x: Math.max(0, box.x - 16),
    y: Math.max(0, box.y - 30),
    width: box.width + 32,
    height: box.height + 60,
  };
  await page.evaluate(() => window.scrollTo(0, 0));
  await paintOverlay(page.locator("body"), resolved);
  const raw = `${rawRoot}/${name.replaceAll("/", "-")}.png`;
  await page.screenshot({ path: raw, fullPage: true, animations: "disabled", caret: "hide" });
  await clearOverlay(page.locator("body"));
  const out = `${outRoot}/${name}.png`;
  record(name, cropTo1x(raw, out, crop));
  console.log(`captured ${name}`);
}

async function capturePage({ name, crop, marks, prepare, viewport = { width: 1440, height: 1000 } }) {
  await page.setViewportSize(viewport);
  await page.goto(`${baseURL}/projects`);
  await page.getByRole("heading", { name: "Projects", level: 1 }).waitFor();
  await openProject();
  await prepare();
  await page.evaluate(() => window.scrollTo(0, 0));
  const resolved = await resolveMarks(marks);
  const raw = `${rawRoot}/${name.replaceAll("/", "-")}.png`;
  await paintOverlay(page.locator("body"), resolved);
  await page.screenshot({ path: raw, fullPage: true, animations: "disabled", caret: "hide" });
  await clearOverlay(page.locator("body"));
  const out = `${outRoot}/${name}.png`;
  record(name, cropTo1x(raw, out, crop));
  console.log(`captured ${name}`);
}

async function captureDialog({ name, marks, prepare, crop, padBottom = 0 }) {
  await page.setViewportSize({ width: 1440, height: 1200 });
  await page.goto(`${baseURL}/projects`);
  await page.getByRole("heading", { name: "Projects", level: 1 }).waitFor();
  await openProject();
  await prepare();
  const dialog = page.getByRole("dialog");
  await dialog.evaluate((element) => {
    element.style.maxHeight = "none";
    element.style.overflow = "visible";
    element.style.paddingBottom = "24px";
    const inner = element.querySelector(".dialog-inner");
    const body = element.querySelector(".dialog-body");
    if (inner instanceof HTMLElement) inner.style.maxHeight = "none";
    if (body instanceof HTMLElement) body.style.overflow = "visible";
  });
  await page.waitForTimeout(200);
  const dialogBox = await dialog.boundingBox();
  if (!dialogBox) throw new Error("Dialog has no bounding box");
  await page.setViewportSize({ width: 1440, height: Math.max(1200, Math.ceil(dialogBox.y + dialogBox.height + 50)) });
  const resolved = await resolveMarks(marks);
  await paintOverlay(dialog, resolved, { offsetX: dialogBox.x, offsetY: dialogBox.y });
  const raw = `${rawRoot}/${name.replaceAll("/", "-")}.png`;
  await dialog.screenshot({ path: raw, animations: "disabled", caret: "hide" });
  await clearOverlay(dialog);
  const out = `${outRoot}/${name}.png`;
  const finalCrop = crop ?? { x: 0, y: 0, width: dialogBox.width, height: dialogBox.height };
  record(name, cropTo1x(raw, out, finalCrop, padBottom));
  console.log(`captured ${name}`);
}

async function prepareTopography() {
  return;
}

async function prepareQueue() {
  await page.getByRole("navigation", { name: "Project sections" }).getByRole("link", { name: "Runs", exact: true }).click();
  await page.getByRole("button", { name: "New run" }).click();
  await page.getByLabel(/Deliberately run unauthenticated/).check();
  await page.getByRole("button", { name: "Check prerequisites" }).click();
  const dialog = page.getByRole("dialog");
  await dialog.getByText("Preflight", { exact: true }).waitFor({ timeout: 15_000 });
  await dialog.locator("#run-ack").waitFor({ timeout: 15_000 });
}

async function prepareReport() {
  await openReport();
}

async function prepareRetest() {
  await openReport();
  await openFinding();
}

async function prepareCompare() {
  await page.getByRole("navigation", { name: "Project sections" }).getByRole("link", { name: "Compare", exact: true }).click();
  await page.getByRole("heading", { name: "Release comparison", level: 1 }).waitFor();
  await page.getByText("Fix verified", { exact: true }).waitFor();
}

try {
  rmSync(rawRoot, { recursive: true, force: true });
  mkdirSync(rawRoot, { recursive: true });
  await signIn();

  await capturePage({
    name: "where-things-live/01-navigation-and-tabs",
    crop: { x: 0, y: 0, width: 760, height: 310 },
    prepare: prepareTopography,
    marks: [
      { selector: 'nav[aria-label="Main"] a[href="/runs"]', number: 1 },
      { selector: 'nav[aria-label="Main"] a[href="/settings"]', number: 2 },
      { selector: 'nav[aria-label="Project sections"] a[href$="/runs"]', number: 3 },
      { selector: 'nav[aria-label="Project sections"] a[href$="/settings"]', number: 4 },
    ],
  });

  await captureDialog({
    name: "queue-run/01-preflight-reduced-scope",
    prepare: prepareQueue,
    crop: { x: 0, y: 380, width: 768, height: 880 },
    padBottom: 16,
    marks: [
      { selector: "#run-unauth", number: 1 },
      { selector: ".notice-warn", number: 2 },
      { selector: 'label[for="run-ack"]', number: 3 },
      { selector: 'button:has-text("Queue run")', number: 4 },
    ],
  });

  await capturePage({
    name: "read-report/01-risk-and-coverage",
    viewport: { width: 820, height: 1200 },
    crop: { x: 20, y: 160, width: 760, height: 850 },
    prepare: prepareReport,
    marks: [
      { selector: "text=Coverage incomplete", number: 1 },
      { selector: "text=Risk and work remaining", number: 2 },
      { selector: "text=4 open finding(s)", number: 3 },
    ],
  });

  await captureElement({
    name: "retest/01-retest-panel",
    selector: "#retest-panel",
    prepare: prepareRetest,
    marks: [
      { selector: "#finding-build", number: 1 },
      { selector: "text=Approved recipe r1", number: 2 },
      { selector: 'button:has-text("Run automatic retest")', number: 3 },
    ],
  });

  await capturePage({
    name: "compare/01-run-selection-and-buckets",
    viewport: { width: 820, height: 1200 },
    crop: { x: 0, y: 160, width: 780, height: 1000 },
    prepare: prepareCompare,
    marks: [
      { selector: "#compare-baseline", number: 1 },
      { selector: "#compare-current", number: 2 },
      { selector: "text=Scope changes", number: 3 },
      { selector: "text=Fix verified", number: 4 },
    ],
  });

  writeFileSync(
    resolve(process.cwd(), "src/content/guide/figureMeta.ts"),
    `/** Generated by scripts/capture-guide-screenshots.mjs. */\nexport const FIGURE_META: Record<string, { width: number; height: number }> = ${JSON.stringify(figureMeta, null, 2)};\n`,
  );
  console.log("figureMeta.ts updated");
} finally {
  await browser.close();
}

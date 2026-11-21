# Research note — user-facing guide architecture (single source, in-app and repo)

Date: 2026-11-20. Scope: how BuktiRilis should document end-to-end **use** (not installation)
so the text is authoritative, reachable from the deployed SPA, and hard to let drift.
Read-only research: no code, dependency, test, or deployment change was made; no secret file
was read. Repo claims are marked `[E#]`, primary sources `[P#]`; both tables are below.
**Recommendation** marks a decision.

## Verdict

**One Markdown source, two renderers: `web/src/content/guide/*.md` is canonical; the SPA
renders it with a dependency-free parser into real React elements, and GitHub renders the same
files for repo readers. `docs/user-guide.md` is a pointer, not a copy.**

- Markdown-only in `docs/` cannot meet the requirement. The deployed web app is built from the
  `./web` build context `[E4]`, so `docs/*.md` is not in the bundle without changing the
  deployment. Users on `http://100.124.184.116:8088` would never see it.
- In-app-only TSX fails the repository half: no plain-text guide to review, search, paste into
  a ticket, or read on GitHub, and the README's existing retest prose `[E29]` drifts immediately.
- A shared source is the only shape that satisfies both without duplication. The only new code
  is a small parser; it must never call `dangerouslySetInnerHTML`.
- The guide is a **how-to** guide (Diátaxis `[P1]`–`[P3]`) with one tutorial lane `[P4]` and a
  reference appendix — not a second README, and not the deployment runbook `[E28]`.
- In-app shape: `Guide` in the top navigation, 16 pages in five groups, a grouped index with
  search, an on-page TOC, and previous/next links. No persistent sidebar in v1.

## Evidence

### Repository evidence

| # | Claim (verified) | Owning source |
|---|---|---|
| E1 | `/login` is public; every other route sits under `RequireAuth`; unknown paths redirect to `/projects`. The guide route must be added inside that boundary. | `web/src/main.tsx:47-66` |
| E2 | Top navigation is a labeled `<nav aria-label="Main">` with Projects, Runs, Settings, Admin (admin only); a working skip link targets `#main-content`. | `web/src/AppShell.tsx:12-14, 23-40` |
| E3 | Labels are overloaded: top-bar **Settings** is installation settings, while **Project → Settings** is scope/membership/identities; **Runs** exists both top-level and per project; **Builds** exists only as a project tab; a run is opened as a **report**. | `web/src/AppShell.tsx:27-32`, `web/src/pages/Project.tsx:68-84` |
| E4 | The web image is built from the `./web` context and the Dockerfile copies that context only; there is no `web/.dockerignore`. Root `.dockerignore` also lists `docs`, but the context alone already excludes it. | `compose.yaml:78`, `web/Dockerfile:1-9`, `.dockerignore:8` |
| E5 | The TypeScript project includes only `src`; the runtime deps are exactly React, React DOM, and React Router DOM. | `web/package.json` (`dependencies`), `web/tsconfig.app.json` |
| E6 | Nothing in the web app imports Markdown or uses `?raw` today. | repo grep: `web/src`, `web/vite.config.ts`, `web/package.json` |
| E7 | The production CSP is `default-src 'self'; script-src 'self'` with no nonce and no `unsafe-inline` for scripts. Inline-script tricks are blocked. | `web/nginx.conf:13` |
| E8 | Deep links are already safe: nginx falls back to `index.html` for unknown paths. A new `/guide/:slug` route needs no server change. | `web/nginx.conf:37-39` |
| E9 | The top bar is `position: sticky` at 56 px; the stylesheet has **zero** `scroll-margin` rules and no `scroll-behavior`, so anchor targets land under the bar and nothing smooth-scrolls. | `web/src/styles.css:185-192`; `grep -c scroll-margin web/src/styles.css` → 0; repo grep: `scroll-behavior` → none |
| E10 | `Section` derives its heading id from `useId`, not from the title; its `id` prop lands on the `<section>`. Guide headings need author-controlled ids instead. | `web/src/ui.tsx:555-577` |
| E11 | `Tabs` renders only the active panel and uses a roving tabindex. Guide content in tabs would be invisible to find-in-page and to a direct URL. | `web/src/ui.tsx:180-230` |
| E12 | Existing accessible patterns to reuse: a scrollable table region with an accessible name, and a scrollable code block with `role="region"` + `aria-label`. | `web/src/ui.tsx:647-652`, `web/src/pages/Settings.tsx:224-230`, `web/src/styles.css:1305-1319` |
| E13 | No route updates `document.title`; every page keeps the static `<title>BuktiRilis</title>`. | repo grep: `document.title` in `web/src` → none |
| E14 | The browser suite already runs axe with `wcag2a`, `wcag2aa`, `wcag21a`, `wcag21aa`, `wcag22aa` and checks horizontal overflow at 390 px — but not at 320 px. | `web/e2e/buktirilis.spec.ts:222-241, 310-382` |
| E15 | The run wizard has build, kind, depth, a read-only profile, discovery routes, identities, an unauthenticated switch, preflight, reduced-scope acknowledgement, and queue. It has **no** mode selector. | `web/src/pages/Runs.tsx:310-430`; profile/depths in `backend/app/services/profiles.py:16-31` |
| E16 | The server re-runs preflight on submit: a failed preflight is 422, a reduced-scope requirement without the acknowledgement is 409, and an identical active run is reused (`created: false`). | `backend/app/services/runs.py:604-638`, `backend/app/routers/runs.py:212-218` |
| E17 | Exports are 409 until the run completes; the UI disables all three export buttons until `completed`. | `backend/app/routers/exports.py:41-51`; `web/src/pages/Report.tsx:213-230` |
| E18 | Retest paths are `automatic`, `guided`, `pending_evidence_review`; the finding page exposes a retest panel, a guided package (`#guided`), and a review panel (`#verify`). | `web/src/pages/Finding.tsx:181-216, 416-470, 798, 1084`; `backend/app/domain.py:100-117` |
| E19 | Server-enforced minimum roles: read/export = viewer; mark-ready, retest, artifact upload = developer; recipe edits, guided-step revisions, evidence status, disposition, **review acceptance** = operator; administrators bypass and get operator on every project. | `backend/app/deps.py:19, 72-95, 111`; `backend/app/routers/findings.py:181, 214, 239, 299, 348, 387, 436, 476, 554, 619` |
| E20 | The Admin page's "Least privilege" notice says a developer "reviews evidence", which contradicts the operator-only review guard. The guide must follow the server, not the copy. | `web/src/pages/Admin.tsx:161-165` vs `backend/app/routers/findings.py:554` |
| E21 | Web bootstrap of the first administrator is development-only; other environments must run the CLI. The login page shows exactly that message. | `backend/app/routers/auth.py:110-122`; `web/src/pages/Login.tsx:46-60` |
| E22 | Demo vs live is a deployment mode (`demo_enabled`), surfaced as a banner and a badge, not a per-run choice. | `web/src/AppShell.tsx:64-72`, `web/src/ui.tsx:155-161`, `web/src/pages/Settings.tsx:572-590` |
| E23 | The domain vocabulary the guide must use verbatim: run statuses, coverage results, verification outcomes, comparison buckets, retest methods, evidence status, and 12 inconclusive reasons. | `backend/app/domain.py:26-228` |
| E24 | "No open findings" is conditional: with incomplete coverage the message explicitly says it is not a clean result. | `backend/app/routers/runs.py:444-456` |
| E25 | Build registration requires an approved target revision, enforces the origin/path policy, rejects duplicate labels, and separates observed from operator-attested identity. | `backend/app/routers/projects.py:451-500 (463, 471, 478)`; `web/src/pages/Builds.tsx:44-100` |
| E26 | Comparison needs two completed runs; the baseline defaults to the previous same-mode run and selecting the same run twice is a 422. | `backend/app/routers/runs.py:584-620` |
| E27 | Installation, deployment, TLS, backup, and live-worker provisioning already have their own documents. | `docs/deploying-elsewhere.md:1-20`, `docs/deployment.md`, `docs/monodeploy.md` |
| E28 | The README already contains user-facing prose (demo scenario, retest semantics) that will overlap and must not become a second source of truth. | `README.md:132-179, 245` |
| E29 | The deployment record names origin `http://100.124.184.116:8088` and deployed commit `99ec204`; HEAD is `7e0bf51`. The guide ships with the SPA, so it appears only after the next deploy. | `docs/progress.md:180-186`; `git log --oneline -1` |

### Primary sources

| # | Claim (verified) | Owning source |
|---|---|---|
| P1 | Documentation has four distinct forms — tutorial, how-to, reference, explanation — distinguished by the question they answer ("Can you teach me…", "How do I…", "What is…", "Why…"). | <https://diataxis.fr/map/> |
| P2 | A how-to guide is goal-oriented, written from the user's perspective rather than the machinery's, is action-only, and should link out instead of explaining. | <https://diataxis.fr/how-to-guides/> |
| P3 | Reference is neutral description of the machinery; it should not instruct, and instruction belongs in how-to guides. | <https://diataxis.fr/reference/> |
| P4 | A tutorial is a learning-oriented lesson; explanation is explicitly not the tutorial's job. | <https://diataxis.fr/tutorials/> |
| P5 | WCAG 2.2 SC 1.4.10 Reflow: content must work at 320 CSS px width without two-dimensional scrolling, except where two-dimensional layout is required. | <https://www.w3.org/TR/WCAG22/#reflow> |
| P6 | SC 1.4.12 Text Spacing: no loss of content when line height is 1.5×, paragraph spacing 2×, letter spacing 0.12×, word spacing 0.16×. | <https://www.w3.org/TR/WCAG22/#text-spacing> |
| P7 | SC 2.4.1 Bypass Blocks, 2.4.3 Focus Order, 2.4.7 Focus Visible. | <https://www.w3.org/TR/WCAG22/#bypass-blocks>, <https://www.w3.org/TR/WCAG22/#focus-order>, <https://www.w3.org/TR/WCAG22/#focus-visible> |
| P8 | SC 2.4.2 Page Titled: pages have titles that describe topic or purpose. | <https://www.w3.org/TR/WCAG22/#page-titled> |
| P9 | SC 2.4.5 Multiple Ways: more than one way to locate a page, except in a process. | <https://www.w3.org/TR/WCAG22/#multiple-ways> |
| P10 | SC 1.3.1 Info and Relationships; SC 2.4.6 Headings and Labels describe topic or purpose. | <https://www.w3.org/TR/WCAG22/#info-and-relationships>, <https://www.w3.org/TR/WCAG22/#headings-and-labels> |
| P11 | SC 2.4.11 Focus Not Obscured (Minimum): a focused component must not be entirely hidden by author-created content. | <https://www.w3.org/TR/WCAG22/#focus-not-obscured-minimum> |
| P12 | SC 2.5.8 Target Size (Minimum): pointer targets at least 24×24 CSS px, with defined exceptions. | <https://www.w3.org/TR/WCAG22/#target-size-minimum> |
| P13 | SC 3.2.6 Consistent Help: repeated self-help mechanisms occur in the same relative order across pages. | <https://www.w3.org/TR/WCAG22/#consistent-help> |
| P14 | WAI: nest headings by rank, avoid skipping ranks; use one main heading and let lower ranks form subsections. | <https://www.w3.org/WAI/tutorials/page-structure/headings/> |
| P15 | WAI: label every navigation menu; indicate the current item with `aria-current="page"` for a current page. | <https://www.w3.org/WAI/tutorials/page-structure/regions/>, <https://www.w3.org/WAI/tutorials/menus/structure/> |
| P16 | WAI: a table caption functions like a heading and is the primary way screen-reader users identify a table in tables mode. | <https://www.w3.org/WAI/tutorials/tables/caption-summary/> |
| P17 | ARIA 1.2 `aria-current` is a token (`page`, `step`, `location`, `date`, `time`, `true`); authors should mark only one element in a set as current. | <https://www.w3.org/TR/wai-aria-1.2/#aria-current> |
| P18 | React Router v7 `NavLink` automatically applies `aria-current="page"` when active; `end` restricts matching to the exact path. | <https://reactrouter.com/docs/en/v7/api/components/NavLink> |
| P19 | Hash scrolling in v7 is implemented inside `ScrollRestoration`, a separate component; the declarative `BrowserRouter` path does not include it, and the component injects an inline script for CSP nonce use. | <https://reactrouter.com/docs/en/v7/api/components/ScrollRestoration>; `react-router@7.9.4` `packages/react-router/lib/dom/lib.tsx` (`useScrollRestoration`, hash → `scrollIntoView`) |
| P20 | Vite: `?raw` imports a file as a string. | <https://vite.dev/guide/assets#importing-asset-as-string> |
| P21 | Vite: `import.meta.glob` supports `eager`, `import: 'default'`, and a custom `query`, e.g. `query: '?raw'`. | <https://vite.dev/guide/features#glob-import>, <https://vite.dev/guide/features#custom-queries> |
| P22 | Vite's own types declare `*?raw` as a string module and provide the eager glob generic used below. | `web/node_modules/vite/client.d.ts:243`; `web/node_modules/vite/types/importGlob.d.ts:80-88` |

## 1. Canonical shape: Markdown-only, in-app-only, or one source?

| Option | Drift risk | Maintenance | A11y control | Search | Offline / deploy | User context | Verdict |
|---|---|---|---|---|---|---|---|
| A. Markdown only in `docs/` | Low | Low | n/a | Repo only | Not in the SPA | Unreachable at `:8088` | Reject |
| B. In-app TSX only | High vs README/operator docs | Medium | High | In-app only | Ships with SPA | Good | Reject |
| C. One Markdown source under `web/`, rendered twice | Low | Medium | High | Repo + browser + in-app | Ships with SPA | Good | **Choose** |
| D. API-served Markdown | Medium | Medium | Medium | In-app | New route + file mount + auth | Good | Reject |
| E. Static HTML in `web/public/` | Medium | Medium | Manual | In-app | Ships, but second shell | Good | Reject |

Why C wins on each axis the question names:

- **Docs drift.** One file per topic; the app and GitHub render the same bytes. A pointer page
  (`docs/user-guide.md`) plus a README link gives repo discoverability without a second copy.
  Option A leaves the primary audience (signed-in users) with nothing; option B creates two
  prose sources the moment the README keeps its retest section `[E28]`. Where the guide and the
  README overlap, the guide becomes authoritative and the README is trimmed to bullets + link.
- **Maintenance.** Markdown is reviewable, diffable, and writable by non-TypeScript authors.
  The only code is a parser and a renderer. No content build step, no generated files, no
  second site to deploy. Option D adds a server route, a mount, caching, and an authorization
  question for content that is not sensitive.
- **Accessibility.** Rendering to React elements gives real `<h2>`, `<ol>`, `<table>`,
  `<caption>`, and `<nav>` landmarks. An iframe, canvas, PDF, or screenshot guide would not
  (and an iframe is the wrong tool for find-in-page and deep links). We control heading ranks
  and focus, and the same page can be axe-tested in the existing suite `[E14]`.
- **Searchability.** Three ways at once: browser find over real text, an in-app search over the
  bundled strings, and GitHub search over the same files `[P9]`. Tabs would hide inactive panels
  from find-in-page, which is why the guide must not reuse `Tabs` `[E11]`.
- **Offline / deployment.** The text is in the JS bundle, so it works on the Tailnet-only
  deployment with no internet egress, no extra nginx location, no new container, and no CSP
  change `[E7][E8]`. This is *offline in the sense of no external fetch*, not a service worker.
- **User context.** The guide is one click from the workflow it describes, can link to live
  routes, and is visible on the same origin the user is already debugging.

**Rejected variant:** keep the canonical files in `docs/` and copy them into the web image.
That needs a different Compose build context (or an additional build context), changes the
deployment for a documentation concern, and couples the SPA build to repository layout. The
content belongs with the UI it documents.

## 2. Least-risk in-app implementation

| Option | New deps | Main risk | Fit with this repo | Verdict |
|---|---|---|---|---|
| Structured TS block content | 0 | Authoring prose as objects; no repo-readable guide | Type-safe but unreadable in review | Reject |
| Markdown `?raw` + in-repo parser → React | 0 | Parser bugs; contained by a strict grammar and tests | Uses Vite glob, React, existing Playwright | **Choose** |
| Markdown `?raw` + `react-markdown` + sanitizer | 2+ packages | Supply chain, audit, pinning, DECISIONS_LOG; full CommonMark unnecessary | Violates "no new dependency if possible" | Reject for v1; sanctioned fallback |
| Static HTML in `web/public/` | 0 | Second shell, no shared links/components, manual responsive/a11y | Duplicates the design system | Reject |
| API-served files | 0 | New route, auth, mount; path traversal if names are client-controlled | Deployment change | Reject |

### 2.1 Source layout

```
web/src/content/guide/
  manifest.ts            # ordered pages: slug, file, group, covers[]
  anchors.ts             # route catalogue + UI labels + their source files
  parse.ts               # pure parser: string -> blocks/headings/problems
  content.ts             # glob loader; joins manifest with parsed files
  guide/                 # the canonical Markdown, one file per page
    00-start-here.md
    01-first-run.md
    ...
docs/user-guide.md       # pointer only: where the source lives, how to read it on GitHub
web/src/pages/Guide.tsx  # index + page renderer (no dangerouslySetInnerHTML)
web/e2e/guide.spec.ts    # content + rendering + a11y checks
```

`parse.ts` must import nothing (no React, no Vite APIs), so the test can call it directly with
strings read from disk.

### 2.2 Loading

```ts
// content.ts
import { GUIDE_PAGES } from "./manifest";
import { parseGuide } from "./parse";

const raw = import.meta.glob<string>("./guide/*.md", {
  eager: true,
  query: "?raw",
  import: "default",
});

export const GUIDE = GUIDE_PAGES.map((meta) => {
  const source = raw[`./guide/${meta.file}`];
  if (source === undefined) throw new Error(`Guide file missing: ${meta.file}`);
  return { ...meta, ...parseGuide(source, meta.slug) };
});
```

The generic form is typed as `Record<string, string>` by Vite's eager-glob overload `[P22]`
(`?raw` `[P20]`, glob `[P21]`). Eager loading keeps in-app search instant; today every route is
statically imported in `main.tsx`, so the text lands in the main bundle. A size budget test
(below) is the guard. If the guide exceeds roughly 120 KB of Markdown, lazy-load `Guide.tsx`
with `React.lazy` — the glob and search still work inside that chunk.

### 2.3 Grammar (deliberately small)

Supported blocks, all GitHub-renderable:

- exactly one `# H1` as the first non-blank line (the page title, single-sourced);
- `## H2`, `### H3` (no `####`, no setext headings);
- blank-line-separated paragraphs;
- `- ` unordered and `1. ` ordered lists, one level, with indented continuation lines;
- fenced code blocks with an optional language;
- pipe tables with a header separator row, and an optional `Table: <caption>` line immediately
  above the table (rendered as `<caption>`, a plain paragraph on GitHub);
- GitHub alert callouts: `> [!NOTE]`, `> [!WARNING]`, `> [!CAUTION]`;
- inline `**strong**`, `` `code` ``, and `[label](/path)` / `[label](https://…)` links.

Everything else is a **problem**, not a guess: raw HTML is not interpreted (it renders as
literal text because React escapes it), images, nested lists, footnotes, and definition lists
are rejected by the checker until deliberately added.

Inline links are resolved by one function:

- `/…` (not `//…`) → React Router `<Link>`;
- `#…` → plain `<a href="#…">` within the page;
- `https://…` → `<a>` with `rel="noopener noreferrer"`, restricted by the checker to a small
  documentation-host allowlist (for example `w3.org`, `owasp.org`) so the guide cannot
  accumulate environment-specific or stale endpoints;
- anything else (`javascript:`, `data:`, `//host`) → problem, rendered as text.

### 2.4 Rendering and security

- Build React elements directly. There is no `dangerouslySetInnerHTML` in the guide code; the
  checker asserts that string never appears under `web/src/content/guide` or `pages/Guide.tsx`.
  Escaping is then React's job, and a pasted `<script>` is visible text, not markup.
- Headings carry author-controlled ids (`<h2 id={slug} tabIndex={-1}>`). Do **not** reuse
  `Section`: its heading id comes from `useId` `[E10]`, which is not a URL fragment.
- No `target="_blank"` in v1, no embedded images, no iframes. All three add accessibility and
  CSP work without serving the core goal.
- A parse problem renders a visible `Notice` naming the file and line instead of silently
  dropping content; the checker fails first, so this is a safety net, not a normal state.

### 2.5 Routes and navigation

```tsx
// inside <RequireAuth>
<Route path="/guide" element={<GuideIndexPage />} />
<Route path="/guide/:slug" element={<GuidePage />} />
```

```tsx
// AppShell nav, between Runs and Settings; no `end`, so it stays active on child pages
<NavLink to="/guide" className={...}>Guide</NavLink>
```

`NavLink` supplies `aria-current="page"` automatically `[P18]`; omitting `end` keeps the item
active on `/guide/:slug`, matching the section-level behaviour of the other nav items. An
unknown slug renders a "page not found" state with links to the index — not a redirect, because
the catch-all would otherwise send a stale link to `/projects` and hide the mistake `[E1]`.

### 2.6 Why not `ScrollRestoration`

The app is declarative `BrowserRouter`; hash scrolling in v7 lives in the separate
`ScrollRestoration` component `[P19]`, and that component injects an inline script for CSP
nonce use. The deployment CSP forbids inline script `[E7]`. Use a small effect on
`location.hash` instead: scroll the target into view, then focus it with
`focus({ preventScroll: true })`. A plain `<a href="#id">` already scrolls natively; the effect
only adds focus management.

## 3. Information architecture

### 3.1 Boundary: use, not installation

The guide starts **after** the app is reachable. It does not contain `make deploy`, Compose,
TLS, backup/restore, credential rotation, or live-worker provisioning; those stay in
`docs/deploying-elsewhere.md`, `docs/deployment.md`, and `docs/monodeploy.md` `[E27]`. The one
operator exception is the first-administrator bootstrap, because the login screen itself tells
the user to run the CLI outside development `[E21]` — one labeled "Operator step" callout, not a
deployment chapter.

### 3.2 Pages

| # | Slug | H1 | Group | Purpose | Who (signed in) |
|---|---|---|---|---|---|
| 0 | `start-here` | Start here | Start | Scope, audience, demo vs live, roles, where help lives | Everyone |
| 1 | `first-run` | Your first assessment, end to end | Start | Tutorial: one lane on seeded demo data, one on a prepared project; ends at a PDF | Operator (lane A: everyone) |
| 2 | `project-setup` | Set up a project (administrator) | Set up | Accounts, project, target policy, OpenAPI, identities, members | Admin |
| 3 | `builds` | Register a build | Set up | Bind a release to a destination and an expected identity; attest when needed | Operator |
| 4 | `queue-run` | Queue an assessment | Run | Kind, depth, identities, routes, preflight, reduced scope, queue | Operator |
| 5 | `monitor-run` | Watch a run | Run | Statuses, stages, activity, cancel, failure, reduced retry | Everyone (cancel: operator) |
| 6 | `read-report` | Read a run report | Review | Overview, findings, coverage, counts, provenance | Everyone |
| 7 | `work-finding` | Understand a finding | Review | Proof, reproduction, evidence, observations, duplicates | Everyone |
| 8 | `retest` | Retest a finding | Review | Automatic, guided, evidence review, verdict, disposition | Developer / operator |
| 9 | `compare` | Compare two releases | Review | Pick runs, buckets, limits, coverage comparison | Everyone |
| 10 | `export` | Export evidence | Review | PDF/CSV/JSON, frozen snapshot, re-export rule | Everyone |
| 11 | `where-things-live` | Where things live | Reference | Route map that disambiguates the duplicated labels | Everyone |
| 12 | `roles` | Roles and permissions | Reference | Capability matrix, membership, installation settings, worker, audit | Everyone |
| 13 | `glossary` | Status and outcome glossary | Reference | Every status/outcome/bucket/reason the UI shows | Everyone |
| 14 | `troubleshooting` | Troubleshooting | Reference | Symptom → cause → action, using real messages | Everyone |
| 15 | `limits` | Limits and how to read results | Reference | Coverage semantics, zero findings, demo vs live, certifying | Everyone |

### 3.3 Section outline (implementation-ready)

```
start-here: what-this-guide-covers, what-it-does-not-cover, demo-and-live-runs,
  roles-at-a-glance, where-to-get-help
first-run: before-you-start, lane-a-the-seeded-demo, lane-b-your-own-project,
  choose-the-build, check-prerequisites, queue-and-watch, read-the-report,
  export-the-pdf, if-the-preflight-blocks-you
project-setup: create-user-accounts, create-the-project, record-the-target-policy,
  attach-an-openapi-revision, add-test-identities, add-members,
  when-a-new-revision-is-required
builds: when-a-new-build-is-required, register-the-build,
  record-or-attest-the-deployed-identity, fix-a-rejected-build   # [E25]
queue-run: choose-baseline-or-release-scan, choose-a-depth, select-identities,
  add-discovery-routes, run-preflight, accept-a-reduced-scope, queue-the-run,
  why-a-run-may-be-reused                                        # [E15][E16]
monitor-run: run-statuses, stages, activity-log, cancel-a-run,
  failed-interrupted-or-canceled, retry-with-passing-identities
read-report: overview, findings, coverage-and-methodology, what-the-counts-mean,
  latest-verification, run-provenance
work-finding: proof-summary, reproduction-steps, evidence, verification-history,
  assessment-state, possible-duplicates
retest: choose-the-retest-path, automatic-replay, guided-retest, review-evidence,
  accept-or-reject-a-verdict, mark-ready-for-retest, change-disposition   # [E18]
compare: pick-the-two-runs, buckets, scope-limitations, coverage-comparison,
  latest-verification
export: formats, what-is-frozen, download-and-verify, when-to-export-again
where-things-live: top-navigation, project-tabs, report-tabs, finding-page,
  admin-vs-project-settings
roles: capability-matrix, project-membership, installation-settings, worker-status,
  audit-trail
glossary: run-statuses, coverage-results, verification-outcomes, comparison-buckets,
  retest-methods, evidence-status, inconclusive-reasons          # [E23]
troubleshooting: you-cannot-see-a-project, the-build-is-rejected, preflight-is-blocked,
  the-run-never-starts, coverage-is-incomplete, a-retest-is-inconclusive,
  an-export-is-unavailable, the-guide-and-the-screen-disagree
limits: what-a-run-covers, zero-findings, what-is-not-tested, demo-vs-live,
  engine-and-model-boundaries, not-a-certification
```

### 3.4 Page template

1. `# H1` — the single source of the page title.
2. One sentence: "Use this page when…".
3. `Who can do this:` — role names as text, never colour alone.
4. `Before you start:` — up to five prerequisites.
5. `##` task sections with ordered steps; bold the exact UI label, then state the effect.
6. `## If something goes wrong` — 2–5 symptom → action items, linking to
   `/guide/troubleshooting#…`.
7. `## Where this is in the app` — links to `/projects`, `/guide/…`, etc.
8. Optional `Related` links to `glossary` and `limits`.

No page-level tabs, no `<details>` around core content, no explanation essays. Explanation lives
in `limits`, reference in `glossary` and `roles` — the Diátaxis separation `[P1]`–`[P4]`.

### 3.5 Traps the content must disambiguate

| Trap | What the app actually does | Guide rule |
|---|---|---|
| Two "Settings" `[E3]` | Top bar = installation (`/settings`); project tab = scope/members/identities | Always write "Settings (top bar)" or "Project → Settings" |
| Two "Runs" `[E3]` | Top bar = recent runs across projects; project tab = this project's runs | Always name the location |
| "Builds" has no top-level entry | It is a project tab only | Say "Project → Builds" |
| A run is the report | `Open report` opens `/projects/:id/runs/:runId`; there is no `/reports` | Never write "go to Reports" |
| Demo vs live | Deployment mode, shown as a banner/badge; not a wizard field `[E22]` | "The deployment decides; the badge shows which" |
| Missing action buttons | Role-based; the server enforces the same guard `[E19]` | "If the button is missing, your role is the reason" |
| Exports before completion | Disabled in the UI and 409 server-side `[E17]` | "Export after the run completes" |
| Coverage counts | Planned checks, not routes; recon only fills the surface inventory | "Tested" means a recorded check result `[E24]` |
| Zero findings | Only a clean result when coverage is complete `[E24]` | Never equate zero findings with clean |
| Comparison | Two completed runs, same mode `[E26]` | Say both conditions |
| Review acceptance | Operator/admin, despite the Admin page copy `[E20]` | Follow the server, and note the copy defect |

Two more authoring facts: the wizard's **Check prerequisites** is a preview, not a gate — the
server re-runs preflight on submit `[E16]` — and the profile is fixed in the request, so the
guide should name *Web & API Access Control v1* rather than promise a profile picker `[E15]`.

## 4. Keeping it accurate

Prose cannot be proven correct by a test. The achievable goal is to make the **mechanical**
claims — routes, labels, structure, links — fail loudly when the app changes, and to make the
semantic claims a review responsibility with an explicit trigger.

### 4.1 Two small catalogues

```ts
// web/src/content/guide/anchors.ts
export const APP_ROUTES = [
  "/projects", "/projects/:projectId", "/projects/:projectId/builds",
  "/projects/:projectId/runs", "/projects/:projectId/runs/:runId",
  "/projects/:projectId/runs/:runId/findings/:findingId",
  "/projects/:projectId/findings/:findingId", "/projects/:projectId/compare",
  "/projects/:projectId/settings", "/runs", "/settings", "/admin",
] as const;

export const UI_LABELS = [
  { text: "Register build", file: "src/pages/Builds.tsx" },
  { text: "Check prerequisites", file: "src/pages/Runs.tsx" },
  { text: "Queue run", file: "src/pages/Runs.tsx" },
  { text: "Deliberately run unauthenticated", file: "src/pages/Runs.tsx" },
  { text: "Coverage & methodology", file: "src/pages/Report.tsx" },
  { text: "Export PDF", file: "src/pages/Report.tsx" },
  { text: "Run automatic retest", file: "src/pages/Finding.tsx" },
  { text: "Revise guided steps", file: "src/pages/Finding.tsx" },
  { text: "Accept verdict", file: "src/pages/Finding.tsx" },
  // ~25 total, only static labels
] as const;
```

The manifest also records which app routes each page documents (`covers`). That is the
coverage contract: a new screen must be added to a page's `covers` list or explicitly exempted.

### 4.2 `web/e2e/guide.spec.ts` — content checks (no browser, no API)

1. Manifest slugs are unique and ordered; every file exists and is non-empty; every `*.md` in
   `guide/` is in the manifest (no orphans); the glob keys match the manifest files.
2. Every file parses with `problems.length === 0`.
3. Exactly one H1, first block; heading levels never skip (h1 → h2 → h3); every H2 has content.
4. Anchor ids match `^[a-z0-9-]+$`, are unique per page, and every `#…` / `/guide/slug#…`
   reference resolves.
5. Every `/…` link target is in `APP_ROUTES` or starts with `/guide`.
6. Every `UI_LABELS` text appears in its declared source file (catches renames).
7. Every `APP_ROUTES` entry is listed in at least one page's `covers` (or in an explicit
   `EXEMPT` set), and every top-level `path="/…"` literal in `main.tsx` is catalogued.
8. Total Markdown size is under budget (start at 120,000 characters).
9. No IPv4 literals, no `http://` links, no `javascript:`/`data:` links, no off-allowlist
   external hosts, no `docs/*.md` links (dead in-app), and no `dangerouslySetInnerHTML` in the
   guide code.
10. Optional, low cost: glossary values must still exist in `backend/app/domain.py`
    (regex over the `StrEnum` members). Drop it if it proves brittle.

### 4.3 `web/e2e/guide.spec.ts` — browser checks

11. `/guide` renders the H1, groups, and search; typing a known term produces a result link and
    a `role="status"` count.
12. Every page renders exactly one H1, `document.title` includes that H1, and there are no
    console or page errors.
13. axe with the repo's tag set (`wcag2a`, `wcag2aa`, `wcag21a`, `wcag21aa`, `wcag22aa`) reports
    no serious or critical violations on the index and one long page `[E14]`.
14. At 390 px **and 320 px** there is no horizontal overflow `[P5]`; the TOC remains operable.
15. Clicking a TOC link focuses the target heading (`document.activeElement.id` equals the
    anchor) and the heading's `top` is below the sticky top bar `[P11]`; the same holds after a
    full reload of `#anchor`.

Everything above runs under the existing Playwright install; there is no new test runner, no
new dependency `[E5][E6]`, and no change to `npm run build`. The browser half needs the seeded
stack, like the rest of the suite; the content half does not.

### 4.4 Definition-of-Done hook

Add one line to `.claude/CODING_STANDARDS.md` and the PR checklist:

> A change to a route, a page label, a run status, or a retest path updates
> `web/src/content/guide` and `anchors.ts`; `npx playwright test e2e/guide.spec.ts` passes.

This is the only mechanism that catches semantic drift (for example, preflight gaining a new
blocking check). The tests catch the mechanical half; the DoD line catches the rest. The guide's
own `the-guide-and-the-screen-disagree` anchor gives users a safe answer in the meantime: the
app is authoritative, and a mismatch should be reported.

## 5. Accessibility and UX specification

**Navigation.**

- Put `Guide` in the existing labeled main navigation `[E2]`, after `Runs`, with `NavLink`
  (auto `aria-current` `[P18]`). A repeated help entry in a consistent position satisfies
  Consistent Help `[P13]`; one entry point is enough. If a scroll-spy is added later, mark the
  current section with `aria-current="location"`, not `page` `[P17]`.
- The guide index is the hub: grouped links, search, and a short "start here" path. Pages get a
  breadcrumb (`Guide → page`), an "On this page" nav, and previous/next links. No persistent
  sidebar in v1: at 16 pages it costs a second column, a mobile disclosure, and focus-order
  complexity for little gain. Revisit only if the guide passes ~25 pages.
- Label every navigation region: `Main` exists `[E2]`; add `Breadcrumb` (already `[E2]`), an
  index `aria-label="Guide pages"` for the grouped list, and `On this page` for the TOC `[P15]`.
  One `<h1>` per page; the TOC nav may use a real `<h2>` ("On this page") so the outline stays
  honest.

**Headings and anchors.**

- Set `document.title` to the page H1 plus "BuktiRilis guide"; the app currently never updates
  it `[E13][P8]`.
- H1 from the file, H2 for tasks, H3 only for sub-steps; no skipped ranks `[P14]`; headings
  describe the section they introduce `[P10]`. The checker enforces structure rather than
  trusting review.
- Stable, human-readable slugs from heading text (`#accept-a-reduced-scope`), deduplicated.
  Headings get `tabIndex={-1}` and `scroll-margin-top` so the sticky 56 px bar does not cover
  them `[E9][P11]`; use about `4.5rem` on desktop and `5.5rem` at ≤760 px, where the bar wraps.
- In-page links are plain `<a href="#id">`; cross-page deep links are
  `<Link to="/guide/slug#id">` plus the hash effect in §2.6. After the jump, focus the heading
  so screen-reader and keyboard users land at the destination `[P7]`.
- Do not add hover-only "#" anchor links inside headings: they pollute the heading's accessible
  name unless carefully hidden, and the TOC already provides the URLs.

**Code and tables.**

- Code blocks wrap (`white-space: pre-wrap; overflow-wrap: anywhere`) and never scroll
  horizontally. That keeps 320 px reflow `[P5]` and text-spacing `[P6]` intact and avoids adding
  a tab stop to every block. No copy button in v1 (clipboard + live-region work for little gain).
- If a genuinely two-dimensional block appears, use the existing pattern: `role="region"` +
  `aria-label` + `tabIndex={0}` `[E12]` — but then it also needs a visible label.
- Tables always carry a `<caption>` `[P16]`, `scope="col"` headers, and the existing
  `.table-wrap` region with an accessible name `[E12]`. On mobile, tables scroll inside their
  wrapper, not the page; hide only non-essential columns, never the row label.

**Search.**

- A `<form role="search">` with a visible `<label>`; results are page titles plus matching
  headings, linking to `/guide/slug#anchor`. Announce the count with `role="status"` (the report
  filter summary already uses this pattern). Empty query shows the grouped index; no matches
  shows three suggested terms rather than a dead end. Search is an addition to the index and
  the top-bar link, not the only route to content `[P9]`.

**Mobile and reflow.**

- Verify at 320 px, not only 390 px `[E14][P5]`. Target size for TOC and pager links is at least
  24×24 px `[P12]`. The top bar wraps at ≤760 px and the nav scrolls horizontally `[E9]`; adding
  one short label ("Guide") is safe.
- No fixed heights on text containers and no `overflow: hidden` on the article, so 200 % zoom
  and 1.4.12 spacing hold `[P6]`.

**Colour, motion, language.**

- Role and status meaning is always text, never colour alone (the app's badges already include
  a text label). Reuse the existing tokens; do not introduce a low-contrast "faint" body
  colour.
- No animation is needed. If a disclosure or smooth scroll is added, honour
  `prefers-reduced-motion`; the app has no global smooth scrolling today `[E9]`.
- Content is English and `<html lang="en">` is already set; mixed-language passages would need
  `lang` attributes, so keep the guide monolingual.

## 6. Rollout and acceptance

| Phase | Work | Exit criteria |
|---|---|---|
| 1 | `Guide.tsx`, parser, manifest, `anchors.ts`, `Guide` nav item, `docs/user-guide.md` pointer, 3 pages (`start-here`, `first-run`, `troubleshooting`) | `npm run typecheck && npm run build`; guide renders at 1440/390/320; axe clean; content checks pass |
| 2 | Remaining 13 pages, full outline, search | All content checks green; every `APP_ROUTES` entry covered; no orphan files |
| 3 | Contextual links (report header, retest panel, preflight failure), README trim, docs table row | Links resolve; README keeps only a summary + pointer; DoD line added |

Commands for the implementing engineer:

```bash
cd web && npm run typecheck && npm run build
cd web && npx playwright test e2e/guide.spec.ts     # content checks; browser half needs the stack
cd web && npx playwright test                       # full suite, seeded demo required
```

Estimated effort (unverified): parser + renderer + tests ≈ 1.5 days; 16 pages with subject-matter
review ≈ 2–3 days; shell/route/CSS ≈ 0.5 day. The content is the long pole, not the code.

## What is still unverified

- **diataxis.fr direct fetch.** The site answered 429 (Cloudflare challenge) from this
  environment, so `[P1]`–`[P4]` were verified against the project's own source repository
  (`github.com/evildmp/diataxis-documentation-framework`, `source/map.rst`,
  `how-to-guides.rst`, `reference.rst`, `tutorials.rst`), which builds diataxis.fr. The prose
  claims are from those files, not from a secondary summary.
- **No prototype.** The parser, bundle size, and effort estimates are designs, not measurements.
  The 120 KB budget and the 1.5-day parser estimate are starting points to adjust after phase 1.
- **Playwright importing the pure parser.** Expected to work (Playwright transpiles TS and the
  parser has no Vite/React imports), but it was not executed here.
- **Hash + `BrowserRouter` focus behaviour.** The native fragment scroll is well-defined; the
  router-state update on a same-document fragment navigation and the focus effect were not
  prototyped. Test 15 is the arbiter.
- **320 px / axe on a real guide page.** The existing suite covers 390 px and axe on report,
  finding, login, admin, and the run dialog `[E14]`; the guide page has not been rendered.
- **Role copy inconsistency.** `Admin.tsx:161-165` says developers review evidence; the server
  requires operator for verdict acceptance `[E20]`. The guide will document the server. Whether
  to fix the copy is a separate, user-visible decision (it changes the admin screen).
- **Deployment lag.** `docs/progress.md` records deployed commit `99ec204` while HEAD is
  `7e0bf51` `[E29]`. The guide cannot appear at `:8088` until the web image is rebuilt and
  redeployed; that is an operator action, not part of this research.
- **No content was written.** The outline is a specification; wording, screenshots (none in
  v1), and the exact troubleshooting messages still need an author and a reviewer.

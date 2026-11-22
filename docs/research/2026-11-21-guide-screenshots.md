# Research note — annotated product screenshots for the BuktiRilis user guide

Date: 2026-11-21 (primary-source and GitHub checks executed 2026-11-22).
Scope: how to add a small set of useful, accessible, annotated UI screenshots to the
canonical Markdown guide, rendered both in the SPA at `/guide` and on GitHub.
Read-only research: no code, assets, dependencies, tests, deployment, container, secret file,
or other documentation was changed; the worktree was clean before this note `[E25]`. The only
repository write is this research note. No usable local stack was confirmed (`:8000` and `:5173`
refused; `:8099/healthz` returned 404), so no screenshot was produced here.
Repo claims are `[E#]`, primary sources `[P#]`; both tables are below.
**Recommendation** marks a decision. Claims labelled **Opinion** are design judgement, not
sourced fact.

## Verdict

**Use a plain Markdown image followed by a blank line and a bold `Figure N.` caption as the
single source; let the SPA upgrade that pair to `<figure><figcaption>`, and let GitHub render it
as an image plus a bold caption paragraph. Store the image beside the Markdown under
`web/src/content/guide/guide/images/`, not in `web/public/`, and resolve it with Vite `?url`.
Capture at the guide's 760 CSS-pixel content width with a 2× device scale, annotate with
numbered boxes/arrows, ship a 1× PNG for GitHub and a `@2x` sibling for the app. Start with five
images.**

The reasoning, in order of importance:

1. **GitHub strips `<figure>` and `<figcaption>`.** A live GitHub Markdown API render on
   2026-11-22 returned the image and the caption text but removed both tags `[P7]`. Raw
   `<figure>` therefore cannot be the single-source shape. A Markdown image plus a bold caption
   paragraph survived intact and is readable in both renderers `[P1][P2][P7][P19]`.
2. **Relative image paths are the only path that works in both renderers.** GitHub resolves a
   relative image path from the Markdown file's directory; a path beginning with `/` is resolved
   from the repository root, not the web origin `[P4]`. Keeping images in
   `web/src/content/guide/guide/images/` makes `images/foo.png` correct on GitHub, while Vite
   `?url` imports give the SPA a hashed, same-origin URL `[P26][P27]`. `web/public/guide/...`
   would need `/guide/...` on the web but a different repository-relative path on GitHub.
3. **A screenshot is a supplement, not the instruction.** The guide prose must remain complete
   without it: WCAG 1.1.1 requires an equivalent text alternative `[P13]`, WCAG 1.4.5 limits
   images of text `[P14]`, and Google's style guide says not to introduce new information only
   in an image `[P19]`. Annotations should be numbers and outlines whose meaning is explained in
   the real-text caption.
4. **Annotate only what the text cannot say efficiently.** Crop, outline, and 1–5 numbered
   callouts help; baked sentences, colour-only coding, translucent washes, blurred redaction,
   device frames, and full-page captures hurt `[P15][P16][P19]`.
5. **PNG 1× + PNG 2× is the safe format pair.** PNG is lossless and MDN recommends it for
   screenshots `[P22]`; GitHub's documented image types include PNG but not WebP `[P5]`. WebP is
   a useful optional app-only optimisation, not the canonical asset `[P22][P23]`.

## Evidence

### Repository evidence

| # | Claim (verified) | Owning source |
|---|---|---|
| E1 | The guide parser has no image token and no figure block; `parseInline` handles only `code`, `strong`, and `link`. | `web/src/content/guide/parse.ts:11-28, 60-115` |
| E2 | `BLOCK_START` does not include `!`, and paragraphs consume every non-blank line that is not a block start, so an image line is not a block. | `web/src/content/guide/parse.ts:46, 297-303` |
| E3 | The renderer handles heading, paragraph, list, code, table, and alert only; it never creates `<img>`, `<figure>`, or `<figcaption>`. | `web/src/guide/GuideContent.tsx:47-131` |
| E4 | The guide article is capped at 760 px with 15 px text; the app body is 14 px; the app is light-only (`color-scheme: light`). | `web/src/styles.css:1-2, 45-50, 2349-2359` |
| E5 | Guide Markdown is loaded with an eager `?raw` glob; there is no image glob or asset map. The guide has 16 Markdown pages. | `web/src/content/guide/content.ts:12-16`; `web/src/content/guide/guide/` |
| E6 | The content test asserts zero parser problems, but has no image/figure assertions; the browser tests use axe tags `wcag2a`, `wcag2aa`, `wcag21a`, `wcag21aa`, `wcag22aa` and check 320/390 px reflow. | `web/e2e/guide.spec.ts:60-74, 225-231, 279-291` |
| E7 | The production CSP is `img-src 'self' data:`; same-origin images need no CSP change. nginx serves `/assets/` with immutable caching and falls back to `index.html` for deep links. | `web/nginx.conf:13, 31-39` |
| E8 | The web image builds from the `./web` context and copies that context; assets under `web/src` or `web/public` ship without a Compose change. | `web/Dockerfile:1-9`; `compose.yaml` web build context |
| E9 | Existing documentation screenshots are full-page and stale. `report-overview-desktop.png` is 1440×2140 (322,982 B), `finding-detail-desktop.png` is 1440×6162 (862,963 B), and `guide-page-desktop.png` is 1440×1000 (130,079 B). The report screenshot's top bar lacks the current **Guide** item. | `docs/screenshots/`; `identify` output; `web/e2e/buktirilis.spec.ts:81,96`; current nav in `web/src/AppShell.tsx:20-35` |
| E10 | At a 760 px display width, a 1440 px full-viewport capture is scaled to 0.53×; 14–15 px UI text becomes about 7.4–7.9 px. The article's own 760 px column is the correct capture width. | E4, E9 |
| E11 | The top bar contains Projects, Runs, Guide, Settings, Admin; the project tabs contain Overview, Builds, Runs, Compare, Settings. The duplicated **Runs** and **Settings** labels are the guide's main orientation trap. | `web/src/AppShell.tsx:20-35`; `web/src/pages/Project.tsx:68-84`; `web/src/content/guide/guide/11-where-things-live.md:5-31` |
| E12 | The run dialog's preflight panel shows a `ready`/`blocked` badge, check rows with recovery text, blocked scenarios, a reduced-scope acknowledgement, and the **Check prerequisites** / **Queue run** footer. | `web/src/pages/Runs.tsx:301-325, 464-505`; `web/src/content/guide/guide/04-queue-run.md:34-48` |
| E13 | The report header shows the run status, the **Coverage complete/incomplete** badge, and disabled-until-complete export buttons; the overview starts with **Risk and work remaining**. | `web/src/pages/Report.tsx:203-235, 460`; `web/src/content/guide/guide/06-read-report.md:5-32` |
| E14 | The finding page has a **Retest** section with a target build, the automatic/guided/pending path, and **Run automatic retest**; verdict acceptance is separate. | `web/src/pages/Finding.tsx:415-480`; `web/src/content/guide/guide/08-retest.md:8-50` |
| E15 | The Compare page has **Baseline run** and **Current run** selectors, a **Comparison is limited** notice, scope limitations, and a bucket grid. | `web/src/pages/Compare.tsx:77-180`; `web/src/content/guide/guide/09-compare.md:5-34` |
| E16 | The demo seed is explicitly synthetic and idempotent, creates project **Atlas Billing**, and labels the mode in the UI; the demo banner is rendered only when demo mode is enabled. | `backend/app/services/lab_seed.py:1-5, 302-310`; `web/src/AppShell.tsx:62-72` |
| E17 | The browser suite signs in by reading the operator line from `var/demo-credentials.txt` (or `DEMO_CREDENTIALS_FILE`) and never prints it. | `web/e2e/guide.spec.ts:197-210` |
| E18 | The current deployment is on `http://100.124.184.116:8088`; the live worker shares the VM and the project accepts that only for authorized local use. This is not a capture target. | `docs/progress.md:57-59`; `.claude/state/CURRENT_STATUS.md:1-10, 39-48` |
| E19 | The guide architecture note explicitly rejected images in v1 ("no embedded images"; "images ... rejected"; "screenshots (none in v1)"). | `docs/research/2026-11-20-user-guide-architecture.md:200, 219, 552` |
| E20 | The current guide suite has 14 tests; the guide and its screenshots are documented as shipped guide UI work. | `.claude/state/CURRENT_STATUS.md:25-37`; `docs/progress.md:306-317` |
| E21 | Existing E2E screenshots use `fullPage: true`; one mobile report test also makes the top bar static before capture. That is the wrong shape for a guide figure (too tall, too wide when scaled). | `web/e2e/buktirilis.spec.ts:81,96,358-359` |
| E22 | The Playwright config uses a 1440×900 viewport and screenshots only on failure; there is no dedicated documentation-capture command. | `web/playwright.config.ts:22-27` |
| E23 | Local tools available: ImageMagick `convert`/`identify`, Pillow 10.2.0, Playwright; no `cwebp`, `pngquant`, `rsvg-convert`, or `tesseract`. | local `command -v` / Python import check |
| E24 | No usable local app stack was confirmed (`:8000` and `:5173` refused; `:8099/healthz` returned 404), so no live capture or axe run was possible here. | local `curl` checks |
| E25 | The worktree was clean before this note; no code or asset change was made. | `git status --short` (empty) |
| E26 | Project security policy forbids production execution and requires demo/fake credentials for development verification. | `.claude/SECURITY_STANDARDS.md` §3–§4; `.claude/AGENT_RULES.md` "Environment" |
| E27 | In-app guide search matches page title, summary, and heading text only; it does not index body blocks or future figure captions. | `web/src/guide/GuideIndex.tsx:15-27` |

### Primary sources

| # | Claim (verified) | Owning source |
|---|---|---|
| P1 | CommonMark image syntax is `![description](url "title")`; the image description is standardly used as the `alt` attribute; title is a tooltip, not a visible caption. | <https://spec.commonmark.org/0.31.2/#images> |
| P2 | GFM uses the same image syntax and alt semantics as CommonMark. | <https://github.github.com/gfm/#images> |
| P3 | GFM's tagfilter disallows only `title`, `textarea`, `style`, `xmp`, `iframe`, `noembed`, `noframes`, `script`, and `plaintext`; all other HTML tags are left untouched *by the parser*. GitHub's later sanitisation is separate. | <https://github.github.com/gfm/#disallowed-raw-html-extension> |
| P4 | GitHub relative links and image paths are resolved relative to the current file; paths starting with `/` are resolved relative to the repository root; `./` and `../` are allowed; relative paths are recommended for clones. | <https://docs.github.com/en/get-started/writing-on-github/getting-started-with-writing-and-formatting-on-github/basic-writing-and-formatting-syntax#relative-links> |
| P5 | GitHub's documented supported image types are PNG, GIF, JPEG, and SVG; the maximum image upload is 10 MB. WebP is not listed. | <https://docs.github.com/en/get-started/writing-on-github/working-with-advanced-formatting/attaching-files> |
| P6 | GitHub exposes `POST https://api.github.com/markdown` with `mode: "gfm"` and an optional repository `context`; it returns rendered HTML. | <https://docs.github.com/en/rest/markdown/markdown> |
| P7 | Live GitHub Markdown API check (2026-11-22, `mode: gfm`, context `buktirilis/buktirilis`): `<figure>`/`<figcaption>` were stripped and the caption became loose text; `![alt](x.png)` rendered as `<p><a><img alt="alt" ...></a></p>`; a following `**Figure 1.** ...` paragraph rendered as a separate `<p>`; a caption with no blank line merged into the image paragraph with `<br>`; raw `<img width height>` kept width/height but lost `loading`; `<picture><source srcset>` survived inside `<themed-picture>`; `srcset` on a bare `<img>` was stripped. | `POST https://api.github.com/markdown`; captured response in `/tmp` (not a repository file) |
| P8 | HTML `<figure>` represents self-contained content with an optional caption supplied by `<figcaption>`; the figure, caption, and contents are referenced as a single unit. | <https://html.spec.whatwg.org/multipage/grouping-content.html#the-figure-element> |
| P9 | `<figcaption>` provides the accessible name for the parent `<figure>`; the first `figcaption` is the caption; it may be the first or last child. | <https://developer.mozilla.org/en-US/docs/Web/HTML/Reference/Elements/figure> |
| P10 | WAI's complex-images guidance requires a two-part text alternative: a short description to identify the image and a long description that conveys the essential information; the long description should be available to everyone, and the image should be summarised in the surrounding text. | <https://www.w3.org/WAI/tutorials/images/complex/> |
| P11 | WAI's alt decision tree: informative simple images get a brief description; complex images include the information elsewhere on the page; images redundant to nearby text may use empty alt; if text appears only in the image, the alt must include it. | <https://www.w3.org/WAI/tutorials/images/decision-tree/> |
| P12 | WAI: use real text rather than images of text; genuine text can be resized without losing clarity; if an image of text is unavoidable, its text alternative must contain the same text. | <https://www.w3.org/WAI/tutorials/images/textual/> |
| P13 | WCAG 2.2 SC 1.1.1: all non-text content has a text alternative that serves the equivalent purpose, except for specified situations; pure decoration can be ignored by assistive technology. | <https://www.w3.org/WAI/WCAG22/Understanding/non-text-content.html> |
| P14 | WCAG 2.2 SC 1.4.5: use text rather than images of text unless the image is visually customizable or a particular presentation is essential. | <https://www.w3.org/WAI/WCAG22/Understanding/images-of-text.html> |
| P15 | WCAG 2.2 SC 1.4.1: colour is not the only visual means of conveying information, indicating an action, prompting a response, or distinguishing an element. | <https://www.w3.org/WAI/WCAG22/Understanding/use-of-color.html> |
| P16 | WCAG 2.2 SC 1.4.11: graphical objects required to understand content need at least 3:1 contrast against adjacent colours. | <https://www.w3.org/WAI/WCAG22/Understanding/non-text-contrast.html> |
| P17 | WCAG 2.2 SC 1.4.4: text, except captions and images of text, can be resized up to 200% without loss of content or functionality. | <https://www.w3.org/WAI/WCAG22/Understanding/resize-text.html> |
| P18 | WCAG 2.2 SC 1.4.10: content works at 320 CSS px without two-dimensional scrolling, except for parts that require two-dimensional layout (examples include images required for understanding, maps, diagrams, video, games, presentations, and data tables). | <https://www.w3.org/WAI/WCAG22/Understanding/reflow.html> |
| P19 | Google developer documentation style guide: use images only for useful visual explanation; be discreet with screenshots; crop to relevant information; don't use images of text/code/terminal output; prefer SVG for diagrams and PNG otherwise; no PII (use a solid 100%-opacity overlay, never blur/mosaic); alt ≤155 characters; figure captions are real text; don't embed explanatory text in images; numbered callouts may help a figure description but not detailed annotations; provide `srcset` 1×/2× with `src` at 1×, exact double dimensions, and never upscale a 1× image; don't use image maps. | <https://developers.google.com/style/images> |
| P20 | NN/g: graphics and videos are a secondary information source; for complex interactions they can help, but text-based help must still be offered. | <https://www.nngroup.com/articles/help-and-documentation/> |
| P21 | MDN `<img>`: `alt` replaces the image when it cannot be displayed; `width` and `height` let the browser reserve aspect ratio and reduce layout shift; `loading="lazy"` defers offscreen images; `srcset` supports 1×/2× descriptors and `src` is the fallback. | <https://developer.mozilla.org/en-US/docs/Web/HTML/Reference/Elements/img> |
| P22 | MDN image-format guide: PNG is lossless, widely supported, and better for screenshots/diagrams/line art; WebP lossless is typically 26% smaller than PNG; SVG is ideal for diagrams/icons that must scale, not for bitmap/photographic images. | <https://developer.mozilla.org/en-US/docs/Web/Media/Guides/Formats/Image_types> |
| P23 | Google WebP: lossless WebP images are 26% smaller than PNG; lossy WebP is 25–34% smaller than comparable JPEG; WebP is natively supported in current Chrome, Safari, Firefox, Edge, and Opera. | <https://developers.google.com/speed/webp> |
| P24 | Playwright `page.screenshot`: PNG is the default; `type` supports png/jpeg/webp; `scale` is `css` or `device` and defaults to `device`; `clip`, `fullPage`, `mask`, `animations: "disabled"`, `caret: "hide"`, and a temporary `style` sheet are supported. | <https://playwright.dev/docs/api/class-page#page-screenshot> |
| P25 | Playwright `locator.screenshot` captures one element and supports the same animation/caret/mask options. | <https://playwright.dev/docs/api/class-locator#locator-screenshot> |
| P26 | Vite asset imports return a resolved public URL; production URLs are hashed under `/assets/`; assets enter the build graph; small assets may be inlined below `assetsInlineLimit`. | <https://vite.dev/guide/assets> |
| P27 | Vite `import.meta.glob` supports `{ eager: true, query: "?url", import: "default" }` and produces URL values. | <https://vite.dev/guide/features#glob-import> |
| P28 | ImageMagick `-strip` removes profiles, comments, and specified PNG chunks; `-resize` changes pixel dimensions. | <https://imagemagick.org/command-line-options/#strip>; <https://imagemagick.org/command-line-options/#resize> |

## 1. The Markdown/HTML shape that works in both renderers

### 1.1 What Markdown actually provides

CommonMark and GFM have no figure or caption syntax. An image is inline content; its
description becomes the `alt` attribute, and a title becomes a tooltip `[P1][P2]`. A standalone
image line therefore renders as a paragraph containing an image, not as a figure with a caption.
That is why "just use `![alt](src)`" is incomplete: it gives alt text and GitHub rendering, but no
visible caption and no programmatic association. WAI's alt decision tree draws the same
distinction: informative images need a description, redundant images may use empty alt, and
text-bearing images need the text `[P11]`.

### 1.2 What HTML provides, and what GitHub does with it

HTML's `<figure>`/`<figcaption>` pair is the correct semantic shape: the figure is self-contained,
the caption is its accessible name, and the image and caption are one unit `[P8][P9]`. WAI's
complex-images guidance uses the same pairing for a short alt plus a visible long description
`[P10]`.

But GitHub's Markdown pipeline is not a general HTML renderer. In the live check, this input:

```html
<figure><img src="x.png" alt="Fallback alt"><figcaption>Visible caption</figcaption></figure>
```

produced:

```html
<p><a target="_blank" rel="noopener noreferrer" href="x.png"><img src="x.png" alt="Fallback alt" style="max-width: 100%;"></a></p>Visible caption
```

The `<figure>` and `<figcaption>` tags were removed; only the image and the loose caption text
survived `[P7]`. GFM's parser leaves most HTML tags alone `[P3]`, but GitHub's sanitisation is the
later step that removes them, so GFM compatibility does not imply figure support on GitHub.

### 1.3 The cross-renderer grammar

**Recommendation:** a figure is a standalone Markdown image, a blank line, and a bold caption
paragraph:

```markdown
![Preflight panel with a blocked identity scenario and the reduced-scope acknowledgement](images/queue-run/01-preflight-blocked.png)

**Figure 1.** The preflight marks identity-dependent scenarios as blocked. Select
**I understand this run covers a reduced scenario set** before **Queue run**.
```

Why this exact shape:

- **GitHub:** the image renders with alt text, and the caption renders as a visible bold
  paragraph. The blank line is required: without it, GitHub merged the caption into the image
  paragraph with a `<br>` `[P7]`. The image is wrapped in a link to the full file, which gives
  readers a click-to-open fallback `[P7]`.
- **SPA:** the parser recognises the image-plus-caption pair and emits one `figure` block, so
  React can render `<figure><img …><figcaption>…</figcaption></figure>`. The caption is real
  text, remains resizable, and is the figure's accessible name `[P9][P17]`.
- **Markdown readability:** no raw HTML, no custom directives, no second source of truth. A
  reviewer sees the image path, alt, and caption in the diff.

**Rejected variants:**

| Variant | Why not |
|---|---|
| Raw `<figure>`/`<figcaption>` | GitHub strips both tags `[P7]`; the SPA would need a raw-HTML parser, expanding the XSS surface. |
| `<img width height>` in Markdown | GitHub keeps width/height but strips `loading` and `srcset` on a bare `<img>` `[P7]`; the SPA parser would need a strict HTML attribute parser. Not worth it for v1. |
| `<picture><source srcset>` | It survives on GitHub `[P7]`, but it requires raw HTML in the Markdown and a second code path in the parser. Use it only if GitHub retina sharpness becomes a hard requirement. |
| Markdown `title` as caption | `title` is a tooltip, not visible text, and is not a reliable accessible caption `[P1]`. |
| Caption baked into the image | It cannot be resized, translated, searched, or read as text; WCAG 1.4.5/1.4.4 and WAI's images-of-text guidance oppose it `[P12][P14][P17]`. |
| `<table>` with image and caption | GitHub renders it, but the semantics are wrong and the caption is not associated with the image. |

### 1.4 Screen-reader behaviour

| Context | What is exposed | Consequence |
|---|---|---|
| SPA `<figure>` + `<figcaption>` | Figure role, caption as the figure's accessible name, image alt as the image description `[P8][P9]` | Best available semantics. Keep alt short and do not duplicate the caption verbatim. |
| GitHub Markdown image + caption paragraph | Link containing the image, image alt, then a separate caption paragraph `[P7]` | Still readable, but the caption is not programmatically grouped with the image. This is an accepted GitHub limitation, not a reason to add raw HTML. |
| `title` only | Tooltip; inconsistent screen-reader exposure | Reject as a caption. |
| Empty alt on an informative screenshot | Image ignored by assistive technology `[P13]` | Reject for guide screenshots; they carry orientation information. |

WAI's complex-images model maps cleanly: alt is the short description ("Preflight panel with a
blocked identity scenario"), and the visible caption is the long description that explains the
callouts `[P10]`. Google's stricter rules apply too: alt ≤155 characters, no "image of" opener,
and no new information that exists only in the picture `[P19]`. Modern browsers expose
`<figure>` natively `[P9]`; WAI lists `role="group"` only as backward compatibility for browsers
that do not convey the native semantics, so the SPA should not add redundant ARIA `[P10]`.

## 2. Annotation conventions: evidence vs opinion

| Technique | Evidence | Effect | Recommendation |
|---|---|---|---|
| Crop to the relevant panel | Google: crop screenshots to the relevant information; it focuses the reader and future-proofs the image `[P19]`. Local: a 1440-wide capture at 760 display halves 14–15 px text to 7.4–7.9 px `[E10]`. | Removes unrelated chrome and keeps UI text legible. | **Use.** Crop to the guide's 760 px column; split a tall screen into two figures rather than shrinking it. |
| Outline box around the target | WCAG 1.4.11 requires 3:1 for graphical objects needed to understand content `[P16]`. | Says "look here" without covering the label. | **Use** a 2–3 px outline with 3:1 contrast, 4–8 px padding, and no fill. |
| Arrow to a small target | No first-party guideline found that recommends arrows; the effect is design judgement. | Can disambiguate a tiny control, but easily crosses text and adds clutter. | **Opinion: use sparingly.** Only when a box cannot isolate the target; at most one arrow per figure; arrowhead stops at the target edge. |
| Numbered callouts (1–5) | Google: numbered callouts can help write a figure description, but don't use callouts for detailed annotations in the image `[P19]`. | Maps the image to a real-text legend without baking sentences. | **Use.** Numbers only; explain each number in the caption. |
| Text labels baked into the image | Google: avoid embedding explanatory text; it hurts accessibility, searchability, and localisation `[P19]`. WAI: images of text cannot be resized `[P12]`. | Adds information that assistive technology cannot read and that shrinks at 320 px. | **Avoid.** Put labels in the caption/prose. |
| Translucent highlight wash | WCAG 1.4.11/1.4.1: contrast and colour-only meaning `[P15][P16]`. | Can lower text contrast and obscure the very label being explained. | **Opinion: avoid.** Prefer an outline over a fill. |
| Blur or mosaic redaction | Google: blur/mosaic effects can be reversed; use a solid 100%-opacity overlay `[P19]`. | Looks redacted but may leak the original pixels. | **Never use for secrets/PII.** Re-capture with demo data first; if redaction is unavoidable, use an opaque solid rectangle. |
| Full-page screenshot | Google: crop; full-resolution screenshots often take too much space `[P19]`. The existing E2E captures use `fullPage: true` `[E21]`. Local: 1440→760 scaling makes text unreadable `[E10]`. | Forces the reader to zoom; annotation text becomes tiny. | **Avoid.** One decision per figure; maximum height about 900 CSS px. |
| Device/browser frame, drop shadow, perspective | No accessibility requirement; visual judgement. | Dates the screenshot and adds non-informative pixels. | **Opinion: avoid.** Capture page content only, no browser chrome or OS chrome. |
| Colour-only coding (red = bad, green = good) | WCAG 1.4.1: colour must not be the only means `[P15]`. | Fails for colour-vision deficiencies and monochrome displays. | **Avoid.** Pair colour with a number, shape, or text label. |
| Image map / clickable hotspot | Google: don't use image maps; they are problematic for accessibility and mobile `[P19]`. | Adds keyboard and scaling problems. | **Avoid.** Use a text list or ordinary links after the figure. |
| Animated GIF | Google: use MP4 rather than animated GIF for animation `[P19]`. | Large, uncontrollable motion; unnecessary for a static UI. | **Avoid** for guide figures. |

**What the evidence supports:** crop, real-text captions, numbered callouts, solid redaction,
non-colour cues, and 3:1 graphical contrast `[P15][P16][P19]`.
**What is opinion:** boxes over arrows, 2–3 px stroke weight, 4–8 px box padding, no device
frames, one arrow maximum. These follow from the constraints but are not quoted rules.

### 2.1 Recommended annotation style

**Opinion:** the measurements below are starting values to review on the first rendered figure,
not sourced rules. The sourced constraints are the contrast, non-colour, and real-text rules
above `[P15][P16][P19]`.

- **One teaching point per figure.** If the screenshot needs more than five callouts, split it.
- **Numbers, not sentences.** A 24–28 px circle at 1× with a white numeral and a dark fill; the
  caption says what each number means. At 2× the circle is 48–56 px.
- **Boxes before arrows.** A box preserves the label; an arrow can cover it. Use a 2–3 px stroke
  with a white under-stroke/halo so it remains visible over both light panels and coloured badges.
- **No fill over text.** If a region needs emphasis, outline it; a translucent fill lowers
  contrast and can make the screenshot look broken.
- **Use the app's own colours only as accents.** The guide tokens are light-theme colours
  `[E4]`; black/white plus the accent blue or danger red keeps annotations legible. Do not rely on
  red/green alone `[P15]`.
- **Caption carries the legend.** Example: "1 marks the blocked status; 2 is the blocked identity
  scenario; 3 is the acknowledgement that enables **Queue run**." The image itself contains only
  the numbers and outlines.

## 3. Format and resolution

### 3.1 Format comparison

| Format | Lossless | Text/alpha | Size on flat UI | GitHub docs | Verdict |
|---|---|---|---|---|---|
| PNG | Yes `[P22]` | Sharp; alpha supported `[P22]` | Larger than WebP | Listed `[P5]` | **Canonical.** 1× `src` plus `@2x` sibling. |
| WebP | Lossless or lossy `[P22][P23]` | Lossless is sharp; alpha supported `[P23]` | Lossless typically 26% smaller than PNG `[P22][P23]` | **Not listed** `[P5]` | Optional app-only optimisation; not the canonical asset until GitHub support is verified. |
| SVG | Vector | Sharp at any zoom; small for diagrams `[P22]` | Smallest for diagrams | Listed `[P5]` | Use for diagrams and annotation source, **not** for raster UI screenshots `[P22]`. |
| JPEG | Lossy `[P22]` | No alpha; ringing around text | Small | Listed `[P5]` | **Avoid** for UI text; artifacts make labels look blurred. |

Local measurement on two committed screenshots (not a general benchmark; the PNGs may not be
optimally encoded):

| Image | PNG | Lossless WebP | Lossy WebP q82 |
|---|---|---|---|
| `guide-page-desktop.png` (1440×1000) | 130,079 B | 54,382 B (−58.2%) | 50,454 B (−61.2%) |
| `report-overview-desktop.png` (1440×2140) | 322,982 B | 148,268 B (−54.1%) | 124,610 B (−61.4%) |

The savings are real for flat UI, but they do not change the GitHub support problem: WebP is not
in GitHub's documented image list `[P5]`. A repository-relative WebP may render in current
browsers, but that is unverified and not a guarantee. **Recommendation:** ship PNG as the
canonical file; if bandwidth becomes a problem, add a same-origin WebP sibling only through the
SPA's `<picture>` renderer, keeping the Markdown/GitHub PNG as the fallback. Do not use `srcset`
with WebP URLs and no `type`: `srcset` has no MIME fallback `[P21]`.

### 3.2 Resolution and capture geometry

| Surface | Viewport | Device scale | Crop | Files | Display |
|---|---|---|---|---|---|
| Desktop guide | 1440×1000 CSS px | 2 | 760 CSS px wide, ≤900 CSS px high | `foo.png` 760×H; `foo@2x.png` 1520×2H | 760 CSS px max; 2× on retina |
| Wide dialog | 1440×1000 CSS px | 2 | dialog's 768 CSS px width | `foo.png` 768×H; `foo@2x.png` 1536×2H | 760 CSS px max; 2× on retina |
| Mobile-specific | 390×844 CSS px | 2 | 390 CSS px wide | `foo.png` 390×844; `foo@2x.png` 780×1688 | 390 CSS px intrinsic; do not stretch |

Rules:

- **Capture at the guide's width, not the viewport's.** The article is 760 px `[E4]`; a 1440 px
  capture displayed at 760 halves text `[E10]`. Crop to 760 or capture the 768 px dialog
  `[E12]`; do not scale a 1320 px page down.
- **Use a 2× device scale.** Playwright's default `scale: "device"` produces one pixel per device
  pixel `[P24]`; with `deviceScaleFactor: 2`, a 760 CSS px crop is 1520 physical pixels. The 1×
  file is a high-quality downscale of the annotated 2× file, not an upscale. Google's rule is
  the same: 2× must be exactly twice, and never upscale a 1× image `[P19]`.
- **Set width/height.** MDN: width and height let the browser reserve the aspect ratio before
  load, reducing layout shift; this is especially important for lazy images `[P21]`. The SPA
  gets dimensions from a generated sidecar (below); GitHub has no width/height in plain Markdown,
  so it cannot reserve the aspect ratio and may shift after load. The 1× file's intrinsic size is
  still correct; the only GitHub fix would be raw `<img width height>`, which we reject for v1
  `[P7][P21]`.
- **Use `srcset` in the SPA.** `src=foo.png`, `srcSet="foo.png 1x, foo@2x.png 2x"` `[P21]`.
  GitHub uses `src` (1×) and wraps it in a full-size link `[P7]`. **Trade-off:** GitHub readers
  get a 1× image; the SPA gets 2× on retina. If GitHub retina sharpness becomes the priority,
  invert the names (2× `src`, `-1x` sibling) or use a `<picture>` block, accepting larger
  downloads and more complexity; decide after a draft-PR review.
- **Lazy-load only below the fold.** `loading="lazy"` defers offscreen images `[P21]`; make the
  first figure eager, the rest lazy, and always keep width/height. GitHub strips `loading` from
  raw HTML `[P7]`, so this is SPA-only.
- **Light UI only.** The app is `color-scheme: light` `[E4]`; capture with
  `colorScheme: "light"`, a consistent OS/browser, and no mixed themes, per Google's consistency
  guidance `[P19]`.
- **No upscaled mobile captures.** A 390 px layout captured at 390 CSS px / 2× is sharp at 390
  display; a desktop capture scaled to 390 is not. Use mobile captures only when the mobile
  layout is the subject. **Opinion:** the current guide tasks are written as desktop workflows,
  so v1 includes no mobile-specific figure.

**Legibility at 320 px:** the figure will shrink from 760 to 320 CSS px (0.42×), so 14 px UI
labels become about 6 px and baked annotation text becomes unusable. That is acceptable only
because the caption and prose carry the instruction; never put essential information solely in
the image `[P13][P19]`. If a mobile figure is added, use a 390 px-wide crop so its labels are
readable at 390, and test 320 px reflow `[E6][P18]`.

## 4. Implementation without breaking single-source, CSP, or reflow

### 4.1 Asset location: beside the Markdown, not in `web/public`

This is the most important implementation constraint. GitHub resolves image paths relative to
the Markdown file; a leading `/` is the repository root, not the web origin `[P4]`. The guide
files live at `web/src/content/guide/guide/*.md` `[E5]`. Therefore:

| Location | Markdown path needed on GitHub | URL in SPA | Problem |
|---|---|---|---|
| `web/public/guide/screenshots/foo.png` | `/guide/screenshots/foo.png` resolves to repo-root `guide/...`, not `web/public/...`; `../../../../public/guide/...` also works but is brittle `[P4]` | `/guide/screenshots/foo.png` | Two different paths for one source; the web path is not repository-relative. |
| `web/src/content/guide/guide/images/foo.png` | `images/foo.png` | Vite `?url` hashed URL, e.g. `/assets/foo-abc123.png` `[P26]` | **Recommended.** One relative path works on GitHub; one glob map works in the SPA. |

Recommended layout:

```text
web/src/content/guide/guide/
  04-queue-run.md
  images/
    queue-run/
      01-preflight-blocked.png
      01-preflight-blocked@2x.png
```

Markdown uses `images/queue-run/01-preflight-blocked.png` `[P4]`. The SPA loader:

```ts
// content.ts (sketch)
const imageUrls = import.meta.glob<string>("./guide/images/**/*.png", {
  eager: true,
  query: "?url",
  import: "default",
});

export function resolveFigure(src: string): { url: string; url2x?: string } {
  const url = imageUrls[`./guide/${src}`];
  if (!url) throw new Error(`Guide image missing: ${src}`);
  const url2x = imageUrls[`./guide/${src.replace(/\.png$/, "@2x.png")}`];
  return { url, url2x };
}
```

`?url` returns the resolved public URL and production Vite emits hashed files under `/assets/`
`[P26]`; `import.meta.glob` with `query: "?url"` is the documented way to collect them `[P27]`.
Screenshots will normally exceed Vite's small-asset inline threshold; if a tiny asset is inlined
as a `data:` URL, the CSP already allows it `[E7][P26]`.

### 4.2 Parser and grammar

**Recommendation:** add one `figure` block, keep images block-only, and fail loudly on anything
else.

```ts
// parse.ts (sketch)
| {
    kind: "figure";
    src: string;      // relative: images/<page>/<name>.png
    alt: string;
    number: number;
    caption: string;  // body after "**Figure N.**"
  }
```

Accepted source shape:

```markdown
![Alt text, plain and short](images/<page>/<name>.png)

**Figure N.** Caption body with **UI labels** and links.
```

Checks in the parser/checker:

- The image line must match
  `^!\[([^\]\n]{1,155})\]\((images\/(?:[a-z0-9][a-z0-9-]*\/)*[a-z0-9][a-z0-9-]*\.png)\)$`.
- The image must be its own paragraph: blank line before it, blank line after it. GFM without the
  second blank line merges the caption into the image paragraph with `<br>` `[P7]`.
- The next non-blank line must match `^\*\*Figure ([1-9][0-9]*)\.\*\*\s+(.+)$`; caption
  continuation lines are joined with spaces until the next blank line; the number must be the
  next sequential number on the page.
- Caption body: 20–240 characters, ends with `.`, `?`, or `!`, contains no "image above",
  "screenshot above", or "figure above" (Google's spatial-reference rule `[P19]`).
- Alt: 8–155 characters, no `**`/`` ` ``/`]`, no `image of`/`screenshot of` opener, not the
  generic words `screenshot`/`image` or the filename, not identical to the caption, ends with
  punctuation. Google's 155-character limit and "no image of" rule `[P19]`.
- Reject raw `<figure`, `<img`, `<picture`, `<source`, or `<svg` outside a code fence; GitHub
  strips figure tags `[P7]`, and the SPA must not grow a raw-HTML parser.
- Reject a bare `![` line that does not match the figure shape; currently `!` would render as
  text and `[...](...)` as a link `[E1][E2]`. A visible parser problem is better than a broken
  figure.
- Add `!\[` to `BLOCK_START` so a preceding paragraph cannot swallow the image `[E2]`.
- One image per figure. Multi-image before/after figures would need a layout that GitHub cannot
  reproduce without raw HTML; defer.

### 4.3 Renderer and CSS

```tsx
// GuideContent.tsx (sketch)
const firstFigureIndex = blocks.findIndex((block) => block.kind === "figure");
if (block.kind === "figure") {
  const { url, url2x } = resolveFigure(block.src);
  const meta = FIGURE_META[block.src]; // width/height from generated sidecar
  return (
    <figure className="guide-figure" key={index}>
      <img
        src={url}
        srcSet={url2x ? `${url} 1x, ${url2x} 2x` : undefined}
        width={meta.width}
        height={meta.height}
        alt={block.alt}
        loading={index === firstFigureIndex ? "eager" : "lazy"}
        decoding="async"
      />
      <figcaption>
        <strong>Figure {block.number}.</strong> <Inline text={block.caption} />
      </figcaption>
    </figure>
  );
}
```

CSS:

```css
.guide-figure {
  margin: 0;
  display: grid;
  gap: 0.55rem;
}
.guide-figure img {
  display: block;
  max-width: 100%;
  height: auto;
  border: 1px solid var(--border);
  border-radius: var(--radius);
  background: var(--surface);
}
.guide-figure figcaption {
  color: var(--text-muted);
  font-size: 0.8125rem;
  line-height: 1.55;
}
```

Do **not** use `width: 100%` on the image: a 390 px mobile capture would be stretched to 760.
`max-width: 100%; height: auto` with width/height attributes preserves the intended size and
shrinks at 320 px. The caption is real text and can wrap; no fixed heights or `overflow: hidden`
on the article. This is the same reflow discipline the guide already uses `[E6][P18]`.

`FIGURE_META` is a small generated map:

```ts
export const FIGURE_META: Record<string, { width: number; height: number }> = {
  "images/queue-run/01-preflight-blocked.png": { width: 768, height: 620 },
};
```

Generate it in the capture script by reading the PNG IHDR width/height (bytes 16–23, big-endian);
no new dependency is needed. The test compares it with the actual files and fails if stale. This
keeps Markdown as the source for alt/caption/path and moves only mechanical dimensions into a
typed sidecar. The alternative — putting dimensions in Markdown — would require raw HTML or a
non-Markdown directive and would break GitHub `[P4][P7]`.

### 4.4 Validation and tests

Add these to `web/e2e/guide.spec.ts` (content half, no browser):

| Check | Why |
|---|---|
| Every figure has alt 8–155 chars and a `**Figure N.**` caption 20–240 chars ending in punctuation. | Google's alt/caption rules `[P19]`; WAI's short/long description split `[P10]`. |
| Figure numbers are sequential per page; at most 2 figures per page; total images ≤ 8 for v1. | Keeps the set small and prevents caption drift. |
| `src` matches `^images/(?:[a-z0-9][a-z0-9-]*/)*[a-z0-9][a-z0-9-]*\.png$`; no `..`, leading `/`, `http://`, `https://`, `data:`, or `@2x` in Markdown. | GitHub relative-path rule `[P4]`; CSP/security `[E7]`; 2× is derived, not written. |
| The 1× file exists under `guide/images/`, is a PNG, and the `@2x` sibling exists and is exactly 2×. | Prevents broken images and accidental upscaling `[P19][P21]`. |
| `FIGURE_META` keys match the 1× files; each 1× is ≤300 KB, each 2× ≤700 KB, total ≤3 MB. | Proposed project budget; keeps the Tailnet page and GitHub page reasonable. |
| No orphan images in `guide/images/`. | Every asset is referenced by a figure; no dead weight. |
| No raw `<figure`, `<img`, `<picture`, `<source`, or `<svg` outside code fences. | GitHub strips figure tags `[P7]`; parser safety `[E3]`. |
| `allLinks`/`blockTexts` include figure captions, so caption links and `#anchors` are checked like other prose. | Existing link checker must not silently skip captions `[E6]`. |

Add these to the browser half:

- `/guide/queue-run` (or a page with a figure) renders one `<figure>`, one `<figcaption>`, and an
  `<img>` whose `alt` is non-empty and whose `naturalWidth > 0`.
- The image has `width`/`height` attributes and a `srcset` containing the `@2x` URL when present.
- At 320 and 390 px there is no horizontal overflow and the caption is visible `[E6][P18]`.
- axe with the existing tag set reports no serious/critical violations `[E6]`; `image-alt` is
  the relevant rule.
- No click target is added: the image is not a link in the SPA, so there is no focus trap or
  unexpected navigation.
- Search coverage: captions are visible and browser-findable, but the in-app search matches only
  titles, summaries, and headings `[E27]`. If caption terms matter for discovery, extend the
  search index separately; do not assume figures are searchable.

### 4.5 CSP, build, and deployment

- **CSP unchanged.** `img-src 'self' data:` already permits same-origin `/assets/` URLs and
  `data:` if Vite ever inlines a tiny asset `[E7]`. No `unsafe-inline`, no external host, no new
  nginx location.
- **Build unchanged.** Vite emits the images into `dist/assets/` with hashed names `[P26]`; the
  Dockerfile copies the `./web` context `[E8]`; nginx's `/assets/` location already serves
  immutable files `[E7]`. No Compose change.
- **GitHub unchanged.** The repository sees `web/src/content/guide/guide/images/...`; the relative
  Markdown path resolves `[P4]`. GitHub renders the 1× PNG and the bold caption; no app CSS is
  needed for meaning `[P7]`.
- **No external image hosts.** The validator rejects them; the CSP would block them anyway
  `[E7]`. This also keeps the guide usable on the Tailnet-only deployment.
- **No new dependency.** The architecture note rejected a Markdown library and dependency growth
  `[E19]`; PNG header parsing and the Vite glob keep the implementation dependency-free.

## 5. Repeatable, privacy-safe capture runbook

### 5.1 Guardrails before capture

1. **Local demo only.** Start the documented local stack (`make db`, `make migrate`, `make dev`;
   run `make demo` once the lab is up) and capture from `http://127.0.0.1:5180` or
   `http://127.0.0.1:5173`. Never capture `http://100.124.184.116:8088` `[E18][E26]`.
2. **Assert demo mode.** The demo banner must be visible (`Demo` badge) `[E16]`; the environment
   chip must not say `staging` or `production`; the project must be **Atlas Billing** `[E16]`.
   Abort if any assertion fails.
3. **Use the existing credential path without printing it.** Reuse the `signIn` pattern that
   reads `var/demo-credentials.txt` or `DEMO_CREDENTIALS_FILE` `[E17]`. Never log the file
   contents, email, or password.
4. **Do not mutate.** Clicking **Check prerequisites** is a read-only preview `[E12]`; do not
   click **Queue run**, **Run automatic retest**, export buttons, or anything that creates a
   record. If a page needs a different state, seed a fresh demo database instead of driving the
   live app.
5. **No live scans, no containers.** The demo seed produces synthetic artifacts; no Strix run is
   needed `[E16]`. Do not run `make deploy`, live scans, or container mutations.

### 5.2 Capture fixture

- **Browser context:** viewport 1440×1000, `deviceScaleFactor: 2`, `colorScheme: "light"`,
  `locale: "en-US"`, `timezoneId: "UTC"`, `reducedMotion: "reduce"`.
- **Deterministic rendering:** `animations: "disabled"`, `caret: "hide"` `[P24]`; wait for the
  heading/table that identifies the state, not a fixed sleep. If a toast appears, wait for it to
  disappear or hide only the toast container with a capture-only style; do not hide product
  notices.
- **Dialog handling:** the run dialog is 768 CSS px wide `[E12]`. For a full preflight figure,
  apply a capture-only style that removes the dialog's max-height/overflow so the panel is not
  clipped, then capture the dialog element with `locator.screenshot()` `[P25]`. This changes only
  the capture layout, not content; note it in the script.
- **Crop:** 760 CSS px for page content, 768 for the dialog, 390 for a mobile-specific figure.
  Include one header/breadcrumb line for orientation; exclude the footer, sidebar, browser
  chrome, URL bar, OS chrome, and any unrelated panel. Maximum height 900 CSS px; split taller
  content into two figures.
- **Naming:** `web/src/content/guide/guide/images/<page-slug>/<nn>-<subject>.png` plus
  `@2x.png`. Lowercase kebab-case, no dates, no environment names, no version numbers. Example:
  `images/queue-run/01-preflight-blocked.png`.

### 5.3 Annotation workflow with existing tools

The existing Playwright config has no documentation-capture command `[E22]`. The available
local tools are Playwright, ImageMagick `convert`/`identify`, and Pillow 10.2.0; there is no
`cwebp`, `pngquant`, `rsvg-convert`, or `tesseract` `[E23]`. Use Playwright for capture and
composition, ImageMagick for downscale/strip, and SVG for the annotation overlay.

1. **Capture raw 2×.** `page.screenshot({ path: raw2x, scale: "device", animations: "disabled",
   caret: "hide" })` `[P24]`. The output is 2× because the context has `deviceScaleFactor: 2`.
2. **Resolve annotation boxes from live locators.** For each mark, use
   `locator.boundingBox()` at capture time, convert to coordinates relative to the crop, and
   store them in a temporary JSON. This is more robust than hard-coded pixels; if a locator is
   missing, the script fails instead of annotating the wrong place.
3. **Compose at native 2×.** Build a local HTML page with `<img src="data:image/png;base64,…">`
   at its native 2× width and an absolutely positioned `<svg viewBox="0 0 W H">` overlay. Draw
   boxes, arrows, and numbered badges. Screenshot the stage at `scale: "css"` with a 1× device
   scale so the output is the native 2× pixels; this avoids resampling the screenshot twice. The
   SVG is an authoring source only: the committed asset is a PNG, so the SPA and GitHub show the
   same annotations and no runtime overlay is needed.
4. **Keep annotation text out of the image except numbers.** Use a 24–28 px badge at 1×, a
   high-contrast fill, a white numeral, and a white halo. The caption is the legend `[P19]`.
5. **Downscale to 1×.** `convert raw2x -filter Lanczos -resize 50% -strip foo.png` and keep the
   annotated 2× as `foo@2x.png` `[P28]`. `-strip` removes profiles/comments/PNG text chunks
   `[P28]`. Flatten alpha onto white if needed; screenshots should not have a transparent
   background.
6. **Validate.** `identify -format '%f %wx%h %b\n' foo.png foo@2x.png` must show exact 2×
   dimensions and the budgeted sizes. Open both at 100% and inspect: no clipped labels, no
   annotation over text, no accidental PII, readable at 760 and acceptable at 320.
7. **Update the sidecar.** Write `FIGURE_META` from the 1× PNG header; add the Markdown figure;
   run `cd web && npm run typecheck && npm run build` and
   `npx playwright test e2e/guide.spec.ts`.

Sketch of an annotation spec (resolved at capture time, not committed as pixel coordinates):

```json
{
  "source": "images/queue-run/01-preflight-blocked@2x.png",
  "cssWidth": 768,
  "marks": [
    { "kind": "box", "locator": "text=Preflight", "pad": 6 },
    { "kind": "badge", "locator": "text=blocked", "number": 1 },
    { "kind": "box", "locator": "text=Reduced scope", "pad": 6 },
    { "kind": "badge", "locator": "text=I understand this run covers a reduced scenario set", "number": 2 }
  ]
}
```

**Opinion:** this SVG-composite path is preferable to ImageMagick `-draw` for arrows and numerals
because SVG text and strokes stay crisp at 2× and the overlay is editable. ImageMagick is still
the right tool for resize/strip and for a quick `identify` check.

### 5.4 Privacy rules

- **Demo/synthetic data only.** No real project, target, scan, finding, evidence, identity, or
  user data. The demo project is explicitly synthetic `[E16]`.
- **No credential surfaces.** Do not capture **Project → Settings → Test identities**, the
  Admin audit table, or any credential entry field. Even if values are masked, the surrounding
  metadata is unnecessary.
- **No browser or OS chrome.** Exclude the URL bar, tabs, bookmarks, notifications, terminal
  windows, chat, and other applications. They can leak hostnames, usernames, and unrelated data.
- **No blur for redaction.** If something unexpected appears, re-capture with demo data. If that
  is impossible, cover it with a solid 100%-opacity rectangle; never blur or mosaic `[P19]`.
- **Strip metadata.** `-strip` removes profiles, comments, and text chunks `[P28]`; review the
  result at 100% because metadata removal does not remove pixels.
- **Manual review.** Scan each image for emails, IP addresses, tokens, tenant names, and
  hostnames. The Markdown checker rejects IPv4 literals in prose `[E6]`, but it cannot inspect
  pixels; this remains a human check.
- **Accidental exposure.** If a real secret appears, stop, delete/replace the image, report the
  location only, and follow the project's incident rules; do not commit the image or repeat the
  value `.claude/SECURITY_STANDARDS.md` §3/§13.

## 6. First five images (maximum comprehension per image)

These are ordered by comprehension gain, not by page order. Each is one decision, one crop, and
at most five callouts. Graphics are a secondary information source; the prose must still carry
the instruction, as NN/g recommends `[P20]`.

| Order | Page / section | Figure | Crop and callouts | Why this one |
|---|---|---|---|---|
| 1 | `where-things-live` — **Top navigation** and **Project tabs** | `images/where-things-live/01-top-navigation-and-project-tabs.png` | Top bar plus project header/tabs, 760×~190 CSS px. Callouts: 1 top-bar **Settings**, 2 project **Settings**, 3 top-bar **Runs**, 4 project **Runs**. | The guide's biggest trap is duplicated labels `[E11]`. One image shows the two scopes side by side; the existing table explains the destinations. |
| 2 | `queue-run` — **Run preflight** and **Accept a reduced scope** | `images/queue-run/01-preflight-blocked.png` | Run dialog, 768 CSS px wide. Callouts: 1 `blocked` status, 2 failing/warning check with recovery text, 3 blocked identity scenario, 4 reduced-scope acknowledgement, 5 disabled **Queue run**. | This is the highest-friction form: users must connect a blocked scenario to the acknowledgement and the disabled action `[E12]`. |
| 3 | `read-report` — **Overview** and **Zero findings** | `images/read-report/01-risk-and-coverage.png` | Report header, counts strip, and **Risk and work remaining**, 760×~600 CSS px. Callouts: 1 **Coverage incomplete** badge, 2 risk summary, 3 severity table, 4 coverage count. | The domain's core misreading is "zero findings = clean"; the image shows that coverage status comes before the count `[E13]`. |
| 4 | `retest` — **Choose the retest path** and **Automatic replay** | `images/retest/01-retest-panel.png` | Finding page **Retest** panel, 760×~400 CSS px. Callouts: 1 target build, 2 retest path/eligibility, 3 **Run automatic retest**, 4 verification history. | Users conflate evidence status, retest method, and verdict; the panel shows the path before the action `[E14]`. |
| 5 | `compare` — **Pick the two runs** and **Scope limitations** | `images/compare/01-run-selection-and-buckets.png` | Compare filters, baseline/current summary, scope notice, and bucket grid, 760×~600 CSS px. Callouts: 1 baseline selector, 2 current selector, 3 **Comparison is limited**/scope warning, 4 bucket grid. | Release comparison is easy to over-read; the image ties the selectors to the scope warning and the buckets `[E15]`. |

Optional sixth, after the first five are reviewed:

| 6 | `builds` — **Register the build** | `images/builds/01-register-build.png` | Build form, 760×~450 CSS px. Callouts: 1 release label, 2 target URL, 3 expected identity, 4 **Register build**. | The form is linear, so text is enough for many readers; the image helps only with the identity binding. Defer until the first five prove the pattern. |

**Do not add first:** `start-here` (no unique screen), `first-run` (reuse the detailed pages by
link; avoid duplicate images), `project-setup` (long forms; text/tables are clearer), `monitor-run`
(transient live states are hard to capture repeatably), `work-finding` (overlaps the retest
figure), `export` (a simple enabled/disabled state), `roles`/`glossary`/`limits` (tables), and
`troubleshooting` (error states would need forced failures). This is a deliberate limit: each
image costs maintenance, review, and accessibility surface.

## 7. Rollout and acceptance

| Phase | Work | Exit criteria |
|---|---|---|
| 1 | Parser `figure` block, renderer/CSS, `FIGURE_META`, content checks, one image on `where-things-live`; extend the existing 14-test guide suite `[E20]` | `npm run typecheck && npm run build`; parser problems zero; image path works in SPA and a GitHub draft PR; 320/390/760 px checked; axe clean. |
| 2 | Four more images: `queue-run`, `read-report`, `retest`, `compare` | All figure checks pass; captions/alt reviewed; total image budget ≤3 MB; no new dependency. |
| 3 | Optional `builds` image, documentation of the capture command, DoD line | Capture runbook reproduced by a second person; guide tests updated; GitHub preview checked. |

Acceptance commands (not run here; local stack was down `[E24]`):

```bash
cd web && npm run typecheck && npm run build
cd web && npx playwright test e2e/guide.spec.ts
identify -format '%f %wx%h %b\n' src/content/guide/guide/images/**/*.png
```

Add one line to the guide DoD in `.claude/CODING_STANDARDS.md`: a route, label, status, or retest
path change updates the guide, `anchors.ts`, and the figures whose callouts name that UI; then
run the guide suite.

## What is still unverified

- **GitHub API vs repo view.** The `POST /markdown` check exercises GitHub's rendering pipeline,
  but a repository blob view or pull-request preview could differ. Verify the actual figure in a
  draft PR before merging `[P6][P7]`.
- **GitHub `<figure>` stability.** The sanitisation result is a 2026-11-22 snapshot, not a
  contractual guarantee. The recommended grammar does not depend on it.
- **WebP on GitHub.** GitHub's docs omit WebP `[P5]`; a repository-relative WebP may or may not
  render consistently. This is why WebP is not canonical.
- **Vite `?url` glob + guide parser.** The path map is designed from the documented APIs
  `[P26][P27]`, not prototyped in this repository. The first implementation must prove that
  `images/foo.png` resolves in the SPA and on GitHub.
- **`FIGURE_META` generation.** The PNG IHDR reader and stale-metadata test are not written. They
  are small but unverified.
- **Capture script and annotation coordinates.** No screenshot was produced; the locator-based
  annotation spec, dialog max-height workaround, and 2× composition are designs, not measured
  results.
- **Legibility.** No 760 px or 320 px rendered figure was reviewed. The local math predicts
  7.4–7.9 px text for an uncropped 1440 px image `[E10]`, but the annotated crops still need a
  human check.
- **Accessibility testing.** No axe run or screen-reader pass was possible without the local
  stack `[E24]`. The expected `image-alt`/figure behaviour is based on the specs `[P9][P13]`, not
  an executed test.
- **Mobile layout.** No mobile-specific figure is planned for v1. If one is added, 320 px reflow
  and label legibility need a separate check `[E6][P18]`.
- **File-size budget.** The 300 KB/700 KB/3 MB numbers are proposed project limits, not measured
  outcomes; the only measurements are the two existing PNGs in §3.1 `[E9]`.
- **Current deployed guide.** The live deployment at `:8088` is a separate operator action
  `[E18]`; screenshots added now will not appear there until the web image is rebuilt and
  redeployed.
- **No state/docs wrap-up.** This is a read-only research task; `CURRENT_STATUS`, `TASK_QUEUE`,
  and `docs/progress.md` were not updated. The implementation task should do that at its own
  wrap-up.

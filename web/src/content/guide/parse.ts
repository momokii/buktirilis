/**
 * A deliberately small Markdown subset for the in-app guide.
 *
 * The guide is also read on GitHub, so it must stay plain Markdown. This parser only
 * accepts the blocks we use and reports anything else instead of guessing. It has no
 * React or Vite imports, which keeps it testable from Playwright and safe to reuse.
 */

export type GuideProblem = { line: number; message: string };

export type InlineToken =
  | { kind: "text"; text: string }
  | { kind: "strong"; text: string }
  | { kind: "code"; text: string }
  | { kind: "link"; text: string; href: string };

export type GuideBlock =
  | { kind: "heading"; level: 1 | 2 | 3; text: string; id: string }
  | { kind: "paragraph"; text: string }
  | { kind: "list"; ordered: boolean; items: string[] }
  | { kind: "code"; language: string; text: string }
  | {
      kind: "table";
      caption?: string;
      headers: string[];
      rows: string[][];
    }
  | { kind: "alert"; tone: "note" | "warning" | "caution"; title: string; text: string }
  | {
      kind: "figure";
      src: string;
      alt: string;
      number: number;
      caption: string;
    };

export type GuideHeading = { level: 2 | 3; text: string; id: string };

export interface ParsedGuide {
  title: string;
  titleId: string;
  blocks: GuideBlock[];
  headings: GuideHeading[];
  problems: GuideProblem[];
}

const ALERT_TONES = {
  NOTE: "note",
  WARNING: "warning",
  CAUTION: "caution",
} as const;

const BLOCK_START = /^(#{1,3}\s|```|!\[|[-*]\s|\d+\.\s|>\s*\[!|Table:\s|\|)/;

export function slugifyHeading(value: string): string {
  const plain = value
    .replace(/`([^`]*)`/g, "$1")
    .replace(/\*\*([^*]*)\*\*/g, "$1")
    .replace(/\[([^\]]+)\]\([^)]*\)/g, "$1")
    .toLowerCase()
    .replace(/&/g, " and ")
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "");
  return plain || "section";
}

export function parseInline(value: string): InlineToken[] {
  const tokens: InlineToken[] = [];
  let cursor = 0;
  let text = "";
  const flush = () => {
    if (text) {
      tokens.push({ kind: "text", text });
      text = "";
    }
  };

  while (cursor < value.length) {
    if (value[cursor] === "`") {
      const end = value.indexOf("`", cursor + 1);
      if (end !== -1) {
        flush();
        tokens.push({ kind: "code", text: value.slice(cursor + 1, end) });
        cursor = end + 1;
        continue;
      }
    }

    if (value.startsWith("**", cursor)) {
      const end = value.indexOf("**", cursor + 2);
      if (end !== -1) {
        flush();
        tokens.push({ kind: "strong", text: value.slice(cursor + 2, end) });
        cursor = end + 2;
        continue;
      }
    }

    if (value[cursor] === "[") {
      const labelEnd = value.indexOf("](", cursor + 1);
      if (labelEnd !== -1) {
        const urlEnd = value.indexOf(")", labelEnd + 2);
        if (urlEnd !== -1) {
          flush();
          tokens.push({
            kind: "link",
            text: value.slice(cursor + 1, labelEnd),
            href: value.slice(labelEnd + 2, urlEnd).trim(),
          });
          cursor = urlEnd + 1;
          continue;
        }
      }
    }

    text += value[cursor];
    cursor += 1;
  }

  flush();
  return tokens;
}

function cells(line: string): string[] {
  const trimmed = line.trim().replace(/^\|/, "").replace(/\|$/, "");
  return trimmed.split("|").map((cell) => cell.trim());
}

function isSeparator(line: string): boolean {
  const row = cells(line);
  return row.length > 0 && row.every((cell) => /^:?-{3,}:?$/.test(cell));
}

function startsBlock(line: string): boolean {
  return BLOCK_START.test(line);
}

export function parseGuide(source: string, pageSlug = "guide"): ParsedGuide {
  const lines = source.replace(/\r\n/g, "\n").replace(/\r/g, "\n").split("\n");
  const blocks: GuideBlock[] = [];
  const headings: GuideHeading[] = [];
  const problems: GuideProblem[] = [];
  const usedIds = new Set<string>();
  let title = "";
  let titleId = "";
  let index = 0;

  const addProblem = (line: number, message: string) => {
    problems.push({ line, message });
  };

  const headingId = (text: string) => {
    const base = slugifyHeading(text);
    let candidate = base;
    let suffix = 2;
    while (usedIds.has(candidate)) {
      candidate = `${base}-${suffix}`;
      suffix += 1;
    }
    usedIds.add(candidate);
    return candidate;
  };

  while (index < lines.length) {
    const line = lines[index];
    const lineNumber = index + 1;

    if (!line.trim()) {
      index += 1;
      continue;
    }

    if (line.startsWith("####")) {
      addProblem(lineNumber, "Use H1–H3 only; H4 is not part of the guide grammar.");
      index += 1;
      continue;
    }

    const heading = /^(#{1,3})\s+(.+)$/.exec(line);
    if (heading) {
      const level = heading[1].length as 1 | 2 | 3;
      const text = heading[2].trim();
      const id = headingId(text);
      if (level === 1) {
        if (title) {
          addProblem(lineNumber, "Only one H1 is allowed per page.");
        } else {
          title = text;
          titleId = id;
        }
      } else {
        headings.push({ level, text, id });
      }
      blocks.push({ kind: "heading", level, text, id });
      index += 1;
      continue;
    }

    const image = /^!\[([^\]\n]+)\]\((images\/[a-z0-9][a-z0-9/_-]*\.png)\)$/.exec(line);
    if (image) {
      const alt = image[1].trim();
      const src = image[2];
      let caption = "";
      let number = 0;
      let cursor = index + 1;
      let blankLines = 0;
      while (cursor < lines.length && !lines[cursor].trim()) {
        blankLines += 1;
        cursor += 1;
      }
      const captionLine = /^\*\*Figure ([1-9][0-9]*)\.\*\*\s+(.+)$/.exec(lines[cursor] ?? "");
      if (captionLine) {
        number = Number(captionLine[1]);
        const body = [captionLine[2].trim()];
        cursor += 1;
        while (cursor < lines.length && lines[cursor].trim() && !startsBlock(lines[cursor])) {
          body.push(lines[cursor].trim());
          cursor += 1;
        }
        caption = body.join(" ");
        if (blankLines === 0) {
          addProblem(lineNumber, "Put a blank line between the image and its caption.");
        }
        if (caption.length < 20 || caption.length > 240) {
          addProblem(lineNumber, "Figure caption must be 20–240 characters.");
        }
        if (!/[.!?]$/.test(caption)) {
          addProblem(lineNumber, "Figure caption must end with punctuation.");
        }
        index = cursor;
      } else {
        addProblem(lineNumber, "An image must be followed by a **Figure N.** caption.");
        index += 1;
      }
      if (!alt) {
        addProblem(lineNumber, "Figure image needs alt text.");
      }
      if (alt.length > 155) {
        addProblem(lineNumber, "Figure alt text must be 155 characters or fewer.");
      }
      blocks.push({ kind: "figure", src, alt, number, caption });
      continue;
    }

    if (line.startsWith("![") || line.startsWith("<figure") || line.startsWith("<img") || line.startsWith("<picture")) {
      addProblem(lineNumber, "Only a relative guide image with a Figure caption is supported.");
      index += 1;
      continue;
    }

    if (line.startsWith("```")) {
      const language = line.slice(3).trim();
      const body: string[] = [];
      index += 1;
      let closed = false;
      while (index < lines.length) {
        if (lines[index].startsWith("```")) {
          closed = true;
          index += 1;
          break;
        }
        body.push(lines[index]);
        index += 1;
      }
      if (!closed) {
        addProblem(lineNumber, "Code fence is not closed.");
      }
      blocks.push({ kind: "code", language, text: body.join("\n") });
      continue;
    }

    if (line.startsWith(">")) {
      const alert = /^>\s*\[!(NOTE|WARNING|CAUTION)\]\s*$/i.exec(line);
      if (!alert) {
        addProblem(lineNumber, "Only NOTE, WARNING, and CAUTION callouts are supported.");
        index += 1;
        continue;
      }
      const tone = ALERT_TONES[alert[1].toUpperCase() as keyof typeof ALERT_TONES];
      const body: string[] = [];
      index += 1;
      while (index < lines.length && lines[index].startsWith(">")) {
        body.push(lines[index].replace(/^>\s?/, ""));
        index += 1;
      }
      const text = body.join(" ").trim();
      if (!text) {
        addProblem(lineNumber, "Callout has no body.");
      }
      blocks.push({ kind: "alert", tone, title: alert[1].toUpperCase(), text });
      continue;
    }

    if (line.startsWith("Table:") && index + 1 < lines.length && lines[index + 1].startsWith("|")) {
      const caption = line.slice("Table:".length).trim();
      index += 1;
      const header = cells(lines[index]);
      if (index + 1 >= lines.length || !isSeparator(lines[index + 1])) {
        addProblem(index + 1, "Table needs a header separator row.");
        index += 1;
        continue;
      }
      index += 2;
      const rows: string[][] = [];
      while (index < lines.length && lines[index].startsWith("|")) {
        const row = cells(lines[index]);
        if (row.length !== header.length) {
          addProblem(index + 1, "Table row has a different number of cells than the header.");
        }
        rows.push(row);
        index += 1;
      }
      blocks.push({ kind: "table", caption: caption || undefined, headers: header, rows });
      continue;
    }

    if (line.startsWith("|")) {
      const header = cells(line);
      if (index + 1 >= lines.length || !isSeparator(lines[index + 1])) {
        addProblem(lineNumber, "Table needs a header separator row.");
        index += 1;
        continue;
      }
      index += 2;
      const rows: string[][] = [];
      while (index < lines.length && lines[index].startsWith("|")) {
        const row = cells(lines[index]);
        if (row.length !== header.length) {
          addProblem(index + 1, "Table row has a different number of cells than the header.");
        }
        rows.push(row);
        index += 1;
      }
      blocks.push({ kind: "table", headers: header, rows });
      continue;
    }

    const listMatch = /^([-*]|\d+\.)\s+(.*)$/.exec(line);
    if (listMatch) {
      const ordered = /\d+\./.test(listMatch[1]);
      const items: string[] = [];
      while (index < lines.length) {
        const item = /^([-*]|\d+\.)\s+(.*)$/.exec(lines[index]);
        if (!item) break;
        items.push(item[2].trim());
        index += 1;
        while (index < lines.length && /^\s{2,}\S/.test(lines[index])) {
          items[items.length - 1] += ` ${lines[index].trim()}`;
          index += 1;
        }
      }
      blocks.push({ kind: "list", ordered, items });
      continue;
    }

    const paragraph: string[] = [line.trim()];
    index += 1;
    while (index < lines.length && lines[index].trim() && !startsBlock(lines[index])) {
      paragraph.push(lines[index].trim());
      index += 1;
    }
    blocks.push({ kind: "paragraph", text: paragraph.join(" ") });
  }

  if (!title) {
    addProblem(1, `Page ${pageSlug} needs exactly one H1.`);
  }

  return { title: title || "Untitled guide page", titleId: titleId || "page", blocks, headings, problems };
}

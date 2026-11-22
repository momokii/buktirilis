import { GUIDE_PAGES, type GuideGroup, type GuidePageMeta } from "./manifest";
import { parseGuide, type GuideBlock, type GuideHeading } from "./parse";

export interface GuidePage extends GuidePageMeta {
  title: string;
  titleId: string;
  blocks: GuideBlock[];
  headings: GuideHeading[];
  problems: { line: number; message: string }[];
}

const sources = import.meta.glob<string>("./guide/*.md", {
  eager: true,
  query: "?raw",
  import: "default",
});

const imageUrls = import.meta.glob<string>("./guide/images/**/*.png", {
  eager: true,
  query: "?url",
  import: "default",
});

export function guideFigureUrls(src: string): { url: string; url2x?: string } {
  const url = imageUrls[`./guide/${src}`];
  if (!url) throw new Error(`Guide figure missing: ${src}`);
  const url2x = imageUrls[`./guide/${src.replace(/\.png$/, "@2x.png")}`];
  return { url, url2x };
}

export const GUIDE: GuidePage[] = GUIDE_PAGES.map((meta) => {
  const source = sources[`./guide/${meta.file}`];
  if (source === undefined) {
    throw new Error(`Guide file missing: ${meta.file}`);
  }
  const parsed = parseGuide(source, meta.slug);
  return {
    ...meta,
    title: parsed.title,
    titleId: parsed.titleId,
    blocks: parsed.blocks,
    headings: parsed.headings,
    problems: parsed.problems,
  };
});

export const GUIDE_GROUPS: GuideGroup[] = ["Start", "Set up", "Run", "Review", "Reference"];

export function guidePage(slug: string | undefined): GuidePage | undefined {
  return GUIDE.find((page) => page.slug === slug);
}

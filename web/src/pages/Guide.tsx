import { useEffect, useMemo, useState } from "react";
import { Link, useLocation, useParams } from "react-router-dom";
import { GUIDE, GUIDE_GROUPS, guidePage, type GuidePage } from "../content/guide/content";
import { parseInline, type GuideBlock } from "../content/guide/parse";
import { Breadcrumbs, PageHeader, TableWrap } from "../ui";

function Inline({ text }: { text: string }) {
  return (
    <>
      {parseInline(text).map((token, index) => {
        if (token.kind === "strong") return <strong key={index}>{token.text}</strong>;
        if (token.kind === "code") {
          return (
            <code className="mono" key={index}>
              {token.text}
            </code>
          );
        }
        if (token.kind === "link") {
          if (token.href.startsWith("/")) {
            return (
              <Link key={index} to={token.href}>
                {token.text}
              </Link>
            );
          }
          if (token.href.startsWith("#")) {
            return (
              <a key={index} href={token.href}>
                {token.text}
              </a>
            );
          }
          if (token.href.startsWith("https://")) {
            return (
              <a key={index} href={token.href} rel="noopener noreferrer">
                {token.text}
              </a>
            );
          }
          return <span key={index}>{token.text}</span>;
        }
        return <span key={index}>{token.text}</span>;
      })}
    </>
  );
}

function Blocks({ blocks }: { blocks: GuideBlock[] }) {
  return (
    <>
      {blocks.map((block, index) => {
        if (block.kind === "heading") {
          const Heading = `h${block.level}` as "h1" | "h2" | "h3";
          return (
            <Heading className="guide-heading" id={block.id} key={index} tabIndex={-1}>
              <Inline text={block.text} />
            </Heading>
          );
        }
        if (block.kind === "paragraph") {
          return (
            <p key={index}>
              <Inline text={block.text} />
            </p>
          );
        }
        if (block.kind === "list") {
          const List = block.ordered ? "ol" : "ul";
          return (
            <List key={index}>
              {block.items.map((item, itemIndex) => (
                <li key={itemIndex}>
                  <Inline text={item} />
                </li>
              ))}
            </List>
          );
        }
        if (block.kind === "code") {
          return (
            <pre
              className="code guide-code"
              key={index}
              tabIndex={0}
              role="region"
              aria-label={block.language ? `${block.language} code example` : "Code example"}
            >
              <code>{block.text}</code>
            </pre>
          );
        }
        if (block.kind === "table") {
          const label = block.caption ?? "Guide table";
          return (
            <TableWrap key={index} label={label}>
              <table>
                {block.caption ? <caption>{block.caption}</caption> : null}
                <thead>
                  <tr>
                    {block.headers.map((header, headerIndex) => (
                      <th key={headerIndex} scope="col">
                        <Inline text={header} />
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {block.rows.map((row, rowIndex) => (
                    <tr key={rowIndex}>
                      {row.map((cell, cellIndex) => (
                        <td key={cellIndex}>
                          <Inline text={cell} />
                        </td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
            </TableWrap>
          );
        }
        return (
          <div className={`notice notice-${block.tone}`} key={index} role="note">
            <div>
              <strong>{block.title}</strong>
              <p>
                <Inline text={block.text} />
              </p>
            </div>
          </div>
        );
      })}
    </>
  );
}

function useGuideTitle(title: string | undefined) {
  useEffect(() => {
    document.title = title ? `${title} — BuktiRilis guide` : "Guide — BuktiRilis";
    return () => {
      document.title = "BuktiRilis";
    };
  }, [title]);
}

function SearchResults({ query }: { query: string }) {
  const normalized = query.trim().toLowerCase();
  const results = useMemo(() => {
    if (!normalized) return [];
    return GUIDE.flatMap((page) => {
      const pageMatch =
        page.title.toLowerCase().includes(normalized) ||
        page.summary.toLowerCase().includes(normalized);
      const headingMatches = page.headings.filter((heading) =>
        heading.text.toLowerCase().includes(normalized),
      );
      if (!pageMatch && headingMatches.length === 0) return [];
      return [
        { page, heading: undefined as { text: string; id: string } | undefined },
        ...headingMatches.map((heading) => ({ page, heading })),
      ];
    });
  }, [normalized]);

  return (
    <>
      <p className="guide-result-count" role="status" aria-live="polite">
        {normalized
          ? `${results.length} result${results.length === 1 ? "" : "s"} for “${query.trim()}”`
          : "Browse the guide by group."}
      </p>
      {normalized && results.length === 0 ? (
        <div className="notice notice-info" role="note">
          <div>
            <strong>No match</strong>
            <p>
              Try “preflight”, “retest”, “coverage”, or “export”, or browse the groups below.
            </p>
          </div>
        </div>
      ) : null}
      {results.length > 0 ? (
        <ul className="guide-search-results" aria-label="Search results">
          {results.map(({ page, heading }, index) => (
            <li key={`${page.slug}-${heading?.id ?? "page"}-${index}`}>
              <Link to={`/guide/${page.slug}${heading ? `#${heading.id}` : ""}`}>
                {page.title}
                {heading ? <span className="guide-result-section"> → {heading.text}</span> : null}
              </Link>
            </li>
          ))}
        </ul>
      ) : null}
    </>
  );
}

function GuideGroups() {
  return (
    <div className="guide-groups">
      {GUIDE_GROUPS.map((group) => {
        const pages = GUIDE.filter((page) => page.group === group);
        if (pages.length === 0) return null;
        return (
          <section className="guide-group" key={group} aria-labelledby={`guide-group-${group}`}>
            <h2 id={`guide-group-${group}`} className="guide-group-title">
              {group}
            </h2>
            <ul>
              {pages.map((page) => (
                <li key={page.slug}>
                  <Link to={`/guide/${page.slug}`}>{page.title}</Link>
                  <span>{page.summary}</span>
                </li>
              ))}
            </ul>
          </section>
        );
      })}
    </div>
  );
}

export function GuideIndexPage() {
  useGuideTitle(undefined);
  const [query, setQuery] = useState("");
  return (
    <div className="stack guide-index">
      <PageHeader
        title="Guide"
        description="End-to-end help for using BuktiRilis after it has been installed. Install and deployment instructions are separate."
      />
      <form className="guide-search" role="search" onSubmit={(event) => event.preventDefault()}>
        <label htmlFor="guide-search">Search the guide</label>
        <input
          id="guide-search"
          type="search"
          value={query}
          onChange={(event) => setQuery(event.target.value)}
          placeholder="Try “preflight”, “retest”, or “export”"
        />
      </form>
      <SearchResults query={query} />
      {query.trim() ? null : (
        <nav aria-label="Guide pages">
          <GuideGroups />
        </nav>
      )}
    </div>
  );
}

function Toc({ page }: { page: GuidePage }) {
  if (page.headings.length === 0) return null;
  return (
    <nav className="guide-toc" aria-labelledby="guide-toc-title">
      <h2 id="guide-toc-title">On this page</h2>
      <ul>
        {page.headings.map((heading) => (
          <li className={heading.level === 3 ? "guide-toc-sub" : undefined} key={heading.id}>
            <a href={`#${heading.id}`}>{heading.text}</a>
          </li>
        ))}
      </ul>
    </nav>
  );
}

function Pager({ page }: { page: GuidePage }) {
  const index = GUIDE.findIndex((candidate) => candidate.slug === page.slug);
  const previous = index > 0 ? GUIDE[index - 1] : undefined;
  const next = index >= 0 && index < GUIDE.length - 1 ? GUIDE[index + 1] : undefined;
  return (
    <nav className="guide-pager" aria-label="Guide page navigation">
      {previous ? (
        <Link to={`/guide/${previous.slug}`}>
          <span>Previous</span>
          <strong>{previous.title}</strong>
        </Link>
      ) : (
        <span />
      )}
      {next ? (
        <Link to={`/guide/${next.slug}`} className="guide-pager-next">
          <span>Next</span>
          <strong>{next.title}</strong>
        </Link>
      ) : (
        <span />
      )}
    </nav>
  );
}

export function GuidePage() {
  const { slug } = useParams();
  const location = useLocation();
  const page = guidePage(slug);
  useGuideTitle(page?.title);

  useEffect(() => {
    if (!page) return;
    if (!location.hash) {
      window.scrollTo({ top: 0, behavior: "auto" });
      return;
    }
    const id = decodeURIComponent(location.hash.slice(1));
    const target = document.getElementById(id);
    if (!(target instanceof HTMLElement)) return;
    requestAnimationFrame(() => {
      target.scrollIntoView({ block: "start" });
      target.focus({ preventScroll: true });
    });
  }, [page, location.hash]);

  if (!page) {
    return (
      <div className="stack">
        <PageHeader title="Guide page not found" />
        <p>
          The guide page <code className="mono">{slug ?? ""}</code> does not exist.{" "}
          <Link to="/guide">Return to the guide index</Link>.
        </p>
      </div>
    );
  }

  return (
    <div className="stack guide-page">
      <Breadcrumbs items={[{ label: "Guide", to: "/guide" }, { label: page.title }]} />
      <header className="guide-header">
        <div className="eyebrow">{page.group}</div>
        <h1 id={page.titleId} tabIndex={-1}>
          {page.title}
        </h1>
        <p className="page-description">{page.summary}</p>
        {page.problems.length > 0 ? (
          <div className="notice notice-error" role="note">
            <div>
              <strong>Guide content problem</strong>
              <p>
                {page.problems.length} parser problem(s) in this page. Run the guide content
                check before publishing.
              </p>
            </div>
          </div>
        ) : null}
      </header>
      <div className="guide-layout">
        <article className="guide-article">
          <Blocks blocks={page.blocks.filter((block) => block.kind !== "heading" || block.level !== 1)} />
        </article>
        <aside className="guide-aside">
          <Toc page={page} />
          <Pager page={page} />
        </aside>
      </div>
    </div>
  );
}

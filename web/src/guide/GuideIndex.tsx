import { useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { GUIDE, GUIDE_GROUPS } from "../content/guide/content";
import { GuideMobileNav, GuideSidebar } from "./GuideChrome";
import { useGuideTitle } from "./useGuideTitle";

const GROUP_INTRO: Record<string, string> = {
  Start: "Understand the guide and follow one complete assessment.",
  "Set up": "Prepare the project, scope, identities, and build.",
  Run: "Queue an assessment and watch it safely.",
  Review: "Read the result, retest, compare releases, and export evidence.",
  Reference: "Look up a screen, a role, a term, or a limit.",
};

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
      return [
        ...(pageMatch || headingMatches.length > 0 ? [{ page, heading: undefined }] : []),
        ...headingMatches.map((heading) => ({ page, heading })),
      ];
    });
  }, [normalized]);

  return (
    <section className="guide-results" aria-labelledby="guide-results-title">
      <div className="guide-results-head">
        <h2 id="guide-results-title">Search results</h2>
        <p className="guide-result-count" role="status" aria-live="polite">
          {`${results.length} result${results.length === 1 ? "" : "s"} for “${query.trim()}”`}
        </p>
      </div>
      {results.length === 0 ? (
        <div className="notice notice-info" role="note">
          <div>
            <strong>No matching page</strong>
            <p>
              Try “preflight”, “retest”, “coverage”, or “export”, or clear the search to browse
              the guide.
            </p>
          </div>
        </div>
      ) : (
        <ul className="guide-search-results">
          {results.map(({ page, heading }, index) => (
            <li key={`${page.slug}-${heading?.id ?? "page"}-${index}`}>
              <Link to={`/guide/${page.slug}${heading ? `#${heading.id}` : ""}`}>
                {page.title}
                {heading ? <span className="guide-result-section"> / {heading.text}</span> : null}
              </Link>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}

function StartPath() {
  return (
    <section className="guide-start" aria-labelledby="guide-start-title">
      <div className="guide-start-copy">
        <h2 id="guide-start-title">Start with the workflow</h2>
        <p>
          Read the guide in the order you will use the app: understand the scope, create the
          first project, then follow one assessment to its report.
        </p>
      </div>
      <ol className="guide-start-list">
        <li>
          <span className="guide-step">1</span>
          <Link to="/guide/start-here">Start here</Link>
          <span>What this guide covers and how demo differs from live.</span>
        </li>
        <li>
          <span className="guide-step">2</span>
          <Link to="/guide/first-run">Your first assessment</Link>
          <span>Follow one run from sign-in to a downloaded PDF.</span>
        </li>
        <li>
          <span className="guide-step">3</span>
          <Link to="/guide/project-setup">Set up a project</Link>
          <span>Record the target, identities, members, and build.</span>
        </li>
      </ol>
    </section>
  );
}

function Directory() {
  return (
    <nav className="guide-directory" aria-label="Guide directory">
      {GUIDE_GROUPS.map((group) => {
        const pages = GUIDE.filter((page) => page.group === group);
        if (pages.length === 0) return null;
        return (
          <section className="guide-directory-group" key={group}>
            <div className="guide-directory-heading">
              <h2>{group}</h2>
              <p>{GROUP_INTRO[group]}</p>
            </div>
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
    </nav>
  );
}

export function GuideIndexPage() {
  useGuideTitle(undefined);
  const [query, setQuery] = useState("");

  return (
    <div className="guide-layout guide-index-layout">
      <aside className="guide-sidebar">
        <GuideSidebar />
      </aside>
      <div className="guide-main">
        <div className="guide-mobile-bar">
          <GuideMobileNav />
        </div>
        <header className="guide-index-header">
          <p className="guide-kicker">User guide</p>
          <h1>Guide</h1>
          <p className="guide-lead">
            End-to-end help for using BuktiRilis after installation. Find a task, read the
            workflow, and keep the evidence trail intact.
          </p>
          <form className="guide-search" role="search" onSubmit={(event) => event.preventDefault()}>
            <label htmlFor="guide-search">Search the guide</label>
            <div className="guide-search-control">
              <svg className="guide-search-icon" viewBox="0 0 20 20" aria-hidden="true">
                <circle cx="8.5" cy="8.5" r="5.5" fill="none" stroke="currentColor" strokeWidth="1.8" />
                <path d="m13 13 4 4" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" />
              </svg>
              <input
                id="guide-search"
                type="search"
                value={query}
                onChange={(event) => setQuery(event.target.value)}
                placeholder="Search tasks, statuses, or screens"
              />
              {query ? (
                <button
                  className="guide-search-clear"
                  type="button"
                  onClick={() => setQuery("")}
                  aria-label="Clear guide search"
                >
                  Clear
                </button>
              ) : null}
            </div>
          </form>
        </header>
        {query.trim() ? (
          <SearchResults query={query} />
        ) : (
          <>
            <StartPath />
            <Directory />
          </>
        )}
      </div>
    </div>
  );
}

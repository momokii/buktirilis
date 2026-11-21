import { useEffect, useMemo, useState } from "react";
import { Link, NavLink } from "react-router-dom";
import { GUIDE, GUIDE_GROUPS } from "../content/guide/content";
import type { GuideHeading } from "../content/guide/parse";
import type { GuidePage } from "../content/guide/content";

export function GuideSidebar({ mobile = false }: { mobile?: boolean }) {
  return (
    <nav
      className="guide-sidebar-nav"
      aria-label={mobile ? "Guide pages (mobile)" : "Guide pages"}
    >
      <div className="guide-sidebar-heading">
        <span>Guide</span>
        <Link to="/guide">All pages</Link>
      </div>
      {GUIDE_GROUPS.map((group) => {
        const pages = GUIDE.filter((page) => page.group === group);
        if (pages.length === 0) return null;
        return (
          <section className="guide-sidebar-group" key={group}>
            <p className="guide-sidebar-label">{group}</p>
            <ul>
              {pages.map((page) => (
                <li key={page.slug}>
                  <NavLink
                    to={`/guide/${page.slug}`}
                    end
                    className={({ isActive }) =>
                      `guide-sidebar-link ${isActive ? "guide-sidebar-link-active" : ""}`.trim()
                    }
                  >
                    {page.title}
                  </NavLink>
                </li>
              ))}
            </ul>
          </section>
        );
      })}
    </nav>
  );
}

export function GuideMobileNav() {
  return (
    <details className="guide-mobile-nav">
      <summary>Browse guide pages</summary>
      <div className="guide-mobile-nav-panel">
        <GuideSidebar mobile />
      </div>
    </details>
  );
}

function useActiveHeading(headings: GuideHeading[]): string {
  const ids = useMemo(() => headings.map((heading) => heading.id), [headings]);
  const [active, setActive] = useState(headings[0]?.id ?? "");

  useEffect(() => {
    if (ids.length === 0) return;
    const elements = ids
      .map((id) => document.getElementById(id))
      .filter((element): element is HTMLElement => element !== null);
    if (elements.length === 0) return;

    const observer = new IntersectionObserver(
      (entries) => {
        const visible = entries
          .filter((entry) => entry.isIntersecting)
          .sort((a, b) => a.boundingClientRect.top - b.boundingClientRect.top);
        if (visible[0]) {
          setActive(visible[0].target.id);
          return;
        }
        const above = elements
          .filter((element) => element.getBoundingClientRect().top < 96)
          .sort((a, b) => b.getBoundingClientRect().top - a.getBoundingClientRect().top);
        if (above[0]) setActive(above[0].id);
      },
      { rootMargin: "-88px 0px -66% 0px", threshold: [0, 1] },
    );
    elements.forEach((element) => observer.observe(element));
    return () => observer.disconnect();
  }, [ids]);

  return active;
}

export function GuideToc({ page }: { page: GuidePage }) {
  const active = useActiveHeading(page.headings);
  if (page.headings.length === 0) return null;
  return (
    <nav className="guide-toc" aria-labelledby="guide-toc-title">
      <h2 id="guide-toc-title">On this page</h2>
      <ul>
        {page.headings.map((heading) => (
          <li className={heading.level === 3 ? "guide-toc-sub" : undefined} key={heading.id}>
            <a
              href={`#${heading.id}`}
              aria-current={active === heading.id ? "location" : undefined}
            >
              {heading.text}
            </a>
          </li>
        ))}
      </ul>
    </nav>
  );
}

export function GuideMobileToc({ page }: { page: GuidePage }) {
  if (page.headings.length === 0) return null;
  return (
    <details className="guide-mobile-toc">
      <summary>On this page</summary>
      <ul>
        {page.headings.map((heading) => (
          <li className={heading.level === 3 ? "guide-toc-sub" : undefined} key={heading.id}>
            <a href={`#${heading.id}`}>{heading.text}</a>
          </li>
        ))}
      </ul>
    </details>
  );
}

export function GuidePager({ page }: { page: GuidePage }) {
  const index = GUIDE.findIndex((candidate) => candidate.slug === page.slug);
  const previous = index > 0 ? GUIDE[index - 1] : undefined;
  const next = index >= 0 && index < GUIDE.length - 1 ? GUIDE[index + 1] : undefined;
  return (
    <nav className="guide-pager" aria-label="Guide page navigation">
      {previous ? (
        <Link to={`/guide/${previous.slug}`} className="guide-pager-link">
          <span>Previous</span>
          <strong>{previous.title}</strong>
        </Link>
      ) : (
        <span />
      )}
      {next ? (
        <Link to={`/guide/${next.slug}`} className="guide-pager-link guide-pager-next">
          <span>Next</span>
          <strong>{next.title}</strong>
        </Link>
      ) : (
        <span />
      )}
    </nav>
  );
}

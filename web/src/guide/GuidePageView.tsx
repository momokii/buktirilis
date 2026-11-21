import { useEffect } from "react";
import { Link, useLocation, useParams } from "react-router-dom";
import { guidePage, type GuidePage as GuidePageData } from "../content/guide/content";
import { Breadcrumbs, PageHeader } from "../ui";
import { GuideBlocks } from "./GuideContent";
import {
  GuideMobileNav,
  GuideMobileToc,
  GuidePager,
  GuideSidebar,
  GuideToc,
} from "./GuideChrome";
import { useGuideTitle } from "./useGuideTitle";

function GuideNotFound({ slug }: { slug?: string }) {
  return (
    <div className="guide-layout">
      <aside className="guide-sidebar">
        <GuideSidebar />
      </aside>
      <div className="guide-main">
        <PageHeader title="Guide page not found" />
        <p>
          The guide page <code className="mono">{slug ?? ""}</code> does not exist.{" "}
          <Link to="/guide">Return to the guide index</Link>.
        </p>
      </div>
    </div>
  );
}

function GuideArticle({ page }: { page: GuidePageData }) {
  return (
    <article className="guide-article">
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
      <GuideBlocks blocks={page.blocks.filter((block) => block.kind !== "heading" || block.level !== 1)} />
    </article>
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

  if (!page) return <GuideNotFound slug={slug} />;

  return (
    <div className="guide-layout guide-page-layout">
      <aside className="guide-sidebar">
        <GuideSidebar />
      </aside>
      <div className="guide-main">
        <div className="guide-mobile-bar">
          <GuideMobileNav />
        </div>
        <Breadcrumbs items={[{ label: "Guide", to: "/guide" }, { label: page.title }]} />
        <header className="guide-page-header">
          <span className="guide-group-pill">{page.group}</span>
          <h1 id={page.titleId} tabIndex={-1}>
            {page.title}
          </h1>
          <p className="guide-lead">{page.summary}</p>
        </header>
        <GuideMobileToc page={page} />
        <GuideArticle page={page} />
        <GuidePager page={page} />
      </div>
      <aside className="guide-toc-column">
        <GuideToc page={page} />
      </aside>
    </div>
  );
}

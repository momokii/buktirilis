import type { ReactNode } from "react";
import { Link } from "react-router-dom";
import { Brand } from "./Brand";

export function GuideShell({ children }: { children: ReactNode }) {
  return (
    <div className="app-shell">
      <a className="skip-link" href="#main-content">
        Skip to content
      </a>
      <header className="topbar">
        <div className="topbar-inner">
          <Brand to="/guide" />
          <div className="topbar-right">
            <Link className="btn btn-secondary btn-sm" to="/login">
              Sign in
            </Link>
          </div>
        </div>
      </header>
      <main className="main" id="main-content">
        {children}
      </main>
      <footer className="footer">
        BuktiRilis records what was tested and what changed. The guide is public; project data
        is not.
      </footer>
    </div>
  );
}

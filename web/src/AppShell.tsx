import { Link, NavLink, Outlet, useNavigate } from "react-router-dom";
import type { ReactNode } from "react";
import { useAuth } from "./auth";
import { Button, Loading } from "./ui";

export function AppShell({ children }: { children?: ReactNode }) {
  const { session, demoEnabled, logout } = useAuth();
  const navigate = useNavigate();

  return (
    <div className="app-shell">
      <a className="skip-link" href="#main-content">
        Skip to content
      </a>
      <header className="topbar">
        <div className="topbar-inner">
          <Link to="/projects" className="brand">
            <span className="brand-mark" aria-hidden="true">
              BR
            </span>
            BuktiRilis
          </Link>
          <nav className="nav" aria-label="Main">
            <NavLink to="/projects" className={({ isActive }) => `nav-link ${isActive ? "active" : ""}`}>
              Projects
            </NavLink>
            <NavLink to="/runs" className={({ isActive }) => `nav-link ${isActive ? "active" : ""}`}>
              Runs
            </NavLink>
            <NavLink to="/settings" className={({ isActive }) => `nav-link ${isActive ? "active" : ""}`}>
              Settings
            </NavLink>
            {session?.user.is_admin ? (
              <NavLink to="/admin" className={({ isActive }) => `nav-link ${isActive ? "active" : ""}`}>
                Admin
              </NavLink>
            ) : null}
          </nav>
          <div className="topbar-right">
            {session ? (
              <>
                <span className="env-chip" title="Active deployment environment">
                  {session.environment.app_env}
                </span>
                <span className="user-chip">
                  <span className="name">{session.user.display_name}</span>
                  {session.user.is_admin ? <span className="badge badge-info">Admin</span> : null}
                </span>
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => {
                    void logout().then(() => navigate("/login"));
                  }}
                >
                  Sign out
                </Button>
              </>
            ) : null}
          </div>
        </div>
      </header>
      {demoEnabled ? (
        <div className="demo-banner" role="note">
          <div className="demo-banner-inner">
            <span className="badge badge-demo">Demo</span>
            <span>
              Findings and coverage come from deterministic synthetic Strix artifacts. Automatic
              retests send real requests to the bundled lab.
            </span>
          </div>
        </div>
      ) : null}
      <main className="main" id="main-content">
        {children ?? <Outlet />}
      </main>
      <footer className="footer">
        BuktiRilis records what was tested and what changed. Results cover only the recorded scope
        and are not a compliance certification.
      </footer>
    </div>
  );
}

export function AppLoading() {
  return (
    <AppShell>
      <Loading label="Loading workspace" />
    </AppShell>
  );
}

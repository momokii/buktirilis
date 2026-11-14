import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { BrowserRouter, Navigate, Route, Routes, useLocation, useSearchParams } from "react-router-dom";
import "./styles.css";
import { AuthProvider, useAuth } from "./auth";
import { AppLoading, AppShell } from "./AppShell";
import { ToastProvider } from "./ui";
import { LoginPage } from "./pages/Login";
import { ProjectsPage } from "./pages/Projects";
import { ProjectLayout, ProjectOverview } from "./pages/Project";
import { BuildsPage } from "./pages/Builds";
import { RunsPage, RunsIndexPage } from "./pages/Runs";
import { ReportPage } from "./pages/Report";
import { FindingPage } from "./pages/Finding";
import { ComparePage } from "./pages/Compare";
import { ProjectSettingsPage, SettingsPage } from "./pages/Settings";
import { AdminPage } from "./pages/Admin";
import { Navigate as RouterNavigate } from "react-router-dom";

function RequireAuth() {
  const { session, loading } = useAuth();
  const location = useLocation();
  if (loading) return <AppLoading />;
  if (!session) {
    const next = encodeURIComponent(location.pathname + location.search);
    return <RouterNavigate to={`/login?next=${next}`} replace />;
  }
  return <AppShell />;
}

function HomeRedirect() {
  return <Navigate to="/projects" replace />;
}

function LoginRoute() {
  const { session } = useAuth();
  const [params] = useSearchParams();
  if (session) {
    const next = params.get("next");
    return <Navigate to={next && next.startsWith("/") ? next : "/projects"} replace />;
  }
  return <LoginPage />;
}

function AppRoutes() {
  return (
    <Routes>
      <Route path="/login" element={<LoginRoute />} />
      <Route element={<RequireAuth />}>
        <Route path="/" element={<HomeRedirect />} />
        <Route path="/projects" element={<ProjectsPage />} />
        <Route path="/projects/:projectId" element={<ProjectLayout />}>
          <Route index element={<ProjectOverview />} />
          <Route path="builds" element={<BuildsPage />} />
          <Route path="runs" element={<RunsPage />} />
          <Route path="runs/:runId" element={<ReportPage />} />
          <Route path="runs/:runId/findings/:findingId" element={<FindingPage />} />
          <Route path="findings/:findingId" element={<FindingPage />} />
          <Route path="compare" element={<ComparePage />} />
          <Route path="settings" element={<ProjectSettingsPage />} />
        </Route>
        <Route path="/runs" element={<RunsIndexPage />} />
        <Route path="/settings" element={<SettingsPage />} />
        <Route path="/admin" element={<AdminPage />} />
        <Route path="*" element={<Navigate to="/projects" replace />} />
      </Route>
    </Routes>
  );
}

export function App() {
  return <AppRoutes />;
}

const container = document.getElementById("root");
if (!container) throw new Error("root container missing");

createRoot(container).render(
  <StrictMode>
    <BrowserRouter>
      <AuthProvider>
        <ToastProvider>
          <App />
        </ToastProvider>
      </AuthProvider>
    </BrowserRouter>
  </StrictMode>,
);

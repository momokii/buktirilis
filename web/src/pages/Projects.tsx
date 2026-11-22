import { useState } from "react";
import { Link } from "react-router-dom";
import { useApi, useAuth } from "../auth";
import type { Project } from "../api";
import { Button, EmptyState, ErrorState, Loading, ModeBadge, PageHeader, RelativeTime } from "../ui";
import { ProjectDialog } from "../components/ProjectDialog";

export function ProjectsPage() {
  const { session } = useAuth();
  const { data, error, loading, refresh } = useApi<{ items: Project[] }>("/api/projects");
  const isAdmin = session?.user.is_admin ?? false;
  const [createOpen, setCreateOpen] = useState(false);

  if (loading && !data) return <Loading label="Loading projects" />;
  if (error) return <ErrorState message="Projects are unavailable." onRetry={refresh} />;

  const projects = data?.items ?? [];
  return (
    <>
      <PageHeader
        title="Projects"
        description="Approved staging scopes, their builds, and the evidence recorded against them."
        meta={<span>{projects.length} project(s) visible to your account</span>}
        actions={
          isAdmin ? (
            <Button variant="primary" onClick={() => setCreateOpen(true)}>
              New project
            </Button>
          ) : undefined
        }
      />
      {!isAdmin ? (
        <p className="muted small" style={{ margin: "-0.35rem 0 0.9rem" }}>
          Only an installation administrator can create a project. Ask an administrator to add
          your account to the right project scope.
        </p>
      ) : null}
      {projects.length === 0 ? (
        <EmptyState
          title="No projects yet"
          action={
            isAdmin ? (
              <Button variant="primary" onClick={() => setCreateOpen(true)}>
                Create a project
              </Button>
            ) : undefined
          }
        >
          An administrator registers the approved staging scope before any run can be requested.
          Scoped developers, operators, and viewers then see only the projects they belong to.
        </EmptyState>
      ) : (
        <div className="project-grid">
          {projects.map((project) => (
            <Link key={project.id} to={`/projects/${project.id}`} className="project-card">
              <div className="spread">
                <h2>{project.name}</h2>
                <span className="badge badge-neutral">{project.role}</span>
              </div>
              <p className="desc">{project.description || "No description recorded."}</p>
              <div className="row">
                {project.target ? (
                  <>
                    <span className="badge badge-neutral">{project.target.environment_label}</span>
                    <code className="mono">{project.target.base_url}</code>
                  </>
                ) : (
                  <span className="badge badge-warn">No approved target</span>
                )}
                {project.last_run ? <ModeBadge mode={project.last_run.mode} /> : null}
              </div>
              <div className="foot">
                <span className="count-pill">
                  <strong>{project.counts.builds}</strong> builds
                </span>
                <span className="count-pill">
                  <strong>{project.counts.runs}</strong> runs
                </span>
                <span className="count-pill">
                  <strong>{project.counts.open_findings}</strong> open findings
                </span>
                {project.last_run ? (
                  <span>Last run {<RelativeTime value={project.last_run.created_at} />}</span>
                ) : (
                  <span>No runs yet</span>
                )}
              </div>
            </Link>
          ))}
        </div>
      )}
      <ProjectDialog
        open={createOpen}
        onClose={() => setCreateOpen(false)}
        onCreated={() => {
          refresh();
          setCreateOpen(false);
        }}
      />
    </>
  );
}

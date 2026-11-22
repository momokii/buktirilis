import { Button, Select } from "../ui";

export interface MembershipDraft {
  project_id: string;
  role: string;
}

export function MembershipEditor({
  projects,
  values,
  onChange,
  label = "Project access",
}: {
  projects: { id: string; name: string }[];
  values: MembershipDraft[];
  onChange: (values: MembershipDraft[]) => void;
  label?: string;
}) {
  const selected = new Set(values.map((membership) => membership.project_id).filter(Boolean));
  const update = (index: number, patch: Partial<MembershipDraft>) => {
    onChange(
      values.map((membership, itemIndex) =>
        itemIndex === index ? { ...membership, ...patch } : membership,
      ),
    );
  };
  return (
    <fieldset className="membership-editor">
      <legend>{label}</legend>
      <p className="field-hint">
        Add one row per project. A user can have a different role in each project.
      </p>
      {values.length === 0 ? (
        <p className="muted small">No project membership. The account can sign in but sees no projects.</p>
      ) : null}
      <div className="membership-rows">
        {values.map((membership, index) => (
          <div className="membership-row" key={`${membership.project_id || "new"}-${index}`}>
            <label className="visually-hidden" htmlFor={`membership-project-${index}`}>
              Project for membership {index + 1}
            </label>
            <Select
              id={`membership-project-${index}`}
              value={membership.project_id}
              onChange={(event) => update(index, { project_id: event.target.value })}
            >
              <option value="">Select a project</option>
              {projects.map((project) => (
                <option
                  key={project.id}
                  value={project.id}
                  disabled={selected.has(project.id) && project.id !== membership.project_id}
                >
                  {project.name}
                </option>
              ))}
            </Select>
            <label className="visually-hidden" htmlFor={`membership-role-${index}`}>
              Role for membership {index + 1}
            </label>
            <Select
              id={`membership-role-${index}`}
              value={membership.role}
              onChange={(event) => update(index, { role: event.target.value })}
            >
              <option value="viewer">Viewer</option>
              <option value="developer">Developer</option>
              <option value="operator">Operator</option>
            </Select>
            <Button
              type="button"
              size="sm"
              aria-label={`Remove membership ${index + 1}`}
              onClick={() => onChange(values.filter((_, itemIndex) => itemIndex !== index))}
            >
              Remove
            </Button>
          </div>
        ))}
      </div>
      <Button
        type="button"
        size="sm"
        variant="secondary"
        disabled={projects.length === 0}
        onClick={() => onChange([...values, { project_id: "", role: "developer" }])}
      >
        Add project access
      </Button>
    </fieldset>
  );
}

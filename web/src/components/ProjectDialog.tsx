import { useState } from "react";
import { api, errorMessage } from "../api";
import type { Project } from "../api";
import { Button, Dialog, Field, Notice, TextInput, useToast } from "../ui";
import { StringListField } from "./StringListField";

export function ProjectDialog({
  open,
  onClose,
  onCreated,
}: {
  open: boolean;
  onClose: () => void;
  onCreated: (project: Project) => void;
}) {
  const { notify } = useToast();
  const [name, setName] = useState("");
  const [slug, setSlug] = useState("");
  const [description, setDescription] = useState("");
  const [baseUrl, setBaseUrl] = useState("");
  const [origins, setOrigins] = useState<string[]>([]);
  const [prefixes, setPrefixes] = useState<string[]>(["/"]);
  const [environment, setEnvironment] = useState("staging");
  const [scopeOwner, setScopeOwner] = useState("");
  const [authorization, setAuthorization] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const reset = () => {
    setName("");
    setSlug("");
    setDescription("");
    setBaseUrl("");
    setOrigins([]);
    setPrefixes(["/"]);
    setEnvironment("staging");
    setScopeOwner("");
    setAuthorization("");
    setError(null);
  };

  const close = () => {
    reset();
    onClose();
  };

  const createProject = async () => {
    setBusy(true);
    setError(null);
    try {
      const response = await api<Project>("/api/projects", {
        method: "POST",
        body: JSON.stringify({
          name,
          slug: slug || null,
          description,
          target: {
            base_url: baseUrl.trim(),
            allowed_origins: origins.map((origin) => origin.trim()).filter(Boolean),
            path_prefixes: prefixes.map((prefix) => prefix.trim()).filter(Boolean),
            environment_label: environment,
            scope_owner: scopeOwner,
            authorization_reference: authorization,
            run_limits: { max_depth: "standard", max_replay_checks: 20, max_runs_per_day: 8 },
          },
        }),
      });
      notify("success", "Project registered with its first approved target revision.");
      onCreated(response);
      close();
    } catch (caught) {
      setError(errorMessage(caught));
    } finally {
      setBusy(false);
    }
  };

  return (
    <Dialog
      open={open}
      onClose={close}
      wide
      title="Register an approved project"
      description="The first target policy revision is created with the project. Runs can only target destinations inside it."
      footer={
        <>
          <Button onClick={close}>Cancel</Button>
          <Button
            variant="primary"
            busy={busy}
            onClick={() => void createProject()}
            disabled={!name.trim() || !baseUrl.trim()}
          >
            Create project
          </Button>
        </>
      }
    >
      <div className="grid-2">
        <Field label="Project name" htmlFor="project-name">
          <TextInput
            id="project-name"
            value={name}
            onChange={(event) => setName(event.target.value)}
          />
        </Field>
        <Field label="Slug (optional)" htmlFor="project-slug">
          <TextInput
            id="project-slug"
            value={slug}
            onChange={(event) => setSlug(event.target.value)}
          />
        </Field>
      </div>
      <Field label="Description" htmlFor="project-description">
        <TextInput
          id="project-description"
          value={description}
          onChange={(event) => setDescription(event.target.value)}
        />
      </Field>
      <Field label="Approved base URL" htmlFor="project-base">
        <TextInput
          id="project-base"
          value={baseUrl}
          onChange={(event) => setBaseUrl(event.target.value)}
          placeholder="https://staging.example.internal"
        />
      </Field>
      <StringListField
        id="project-origin"
        label="Approved origins"
        hint="Origin only: scheme://host:port. Leave empty to use the base URL."
        values={origins}
        onChange={setOrigins}
        addLabel="Add origin"
        placeholder="https://staging.example.internal"
      />
      <StringListField
        id="project-prefix"
        label="Path restrictions"
        hint="Absolute path prefixes. Leave one entry with / to allow the whole origin."
        values={prefixes}
        onChange={setPrefixes}
        addLabel="Add path restriction"
        placeholder="/deployments"
      />
      <div className="grid-2">
        <Field label="Environment label" htmlFor="project-env">
          <TextInput
            id="project-env"
            value={environment}
            onChange={(event) => setEnvironment(event.target.value)}
          />
        </Field>
        <Field label="Scope owner" htmlFor="project-owner">
          <TextInput
            id="project-owner"
            value={scopeOwner}
            onChange={(event) => setScopeOwner(event.target.value)}
          />
        </Field>
      </div>
      <Field label="Authorization reference" htmlFor="project-auth">
        <TextInput
          id="project-auth"
          value={authorization}
          onChange={(event) => setAuthorization(event.target.value)}
        />
      </Field>
      {error ? <Notice tone="error">{error}</Notice> : null}
    </Dialog>
  );
}

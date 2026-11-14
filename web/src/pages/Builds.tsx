import { useState } from "react";
import { useParams } from "react-router-dom";
import { useApi } from "../auth";
import { api, errorMessage } from "../api";
import type { Build } from "../api";
import { useProject } from "./Project";
import {
  Button,
  Dialog,
  ErrorState,
  Field,
  Loading,
  Notice,
  PageHeader,
  RelativeTime,
  TableWrap,
  TextInput,
  useToast,
} from "../ui";

export function BuildsPage() {
  const { project } = useProject();
  const { projectId } = useParams();
  const builds = useApi<{ items: Build[] }>(`/api/projects/${projectId}/builds`);
  const { notify } = useToast();
  const [registerOpen, setRegisterOpen] = useState(false);
  const [attesting, setAttesting] = useState<Build | null>(null);
  const [label, setLabel] = useState("");
  const [targetUrl, setTargetUrl] = useState(project.target?.base_url ?? "");
  const [commitSha, setCommitSha] = useState("");
  const [expectedIdentity, setExpectedIdentity] = useState("");
  const [attestValue, setAttestValue] = useState("");
  const [attestNote, setAttestNote] = useState("");
  const [busy, setBusy] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);

  const canOperate = project.capabilities?.can_operate ?? false;

  const register = async () => {
    setBusy(true);
    setFormError(null);
    try {
      await api(`/api/projects/${project.id}/builds`, {
        method: "POST",
        body: JSON.stringify({
          label,
          target_url: targetUrl,
          commit_sha: commitSha || null,
          expected_identity: expectedIdentity || null,
          build_metadata: { source: "ui" },
        }),
      });
      notify("success", "Build registered. Its approved target and identity are now recorded.");
      setRegisterOpen(false);
      setLabel("");
      setCommitSha("");
      setExpectedIdentity("");
      builds.refresh();
    } catch (caught) {
      setFormError(errorMessage(caught));
    } finally {
      setBusy(false);
    }
  };

  const attest = async () => {
    if (!attesting) return;
    setBusy(true);
    setFormError(null);
    try {
      await api(`/api/projects/${project.id}/builds/${attesting.id}/attest`, {
        method: "POST",
        body: JSON.stringify({ observed_identity: attestValue, note: attestNote }),
      });
      notify("success", "Deployed build identity attested. Replays now compare against it.");
      setAttesting(null);
      setAttestValue("");
      setAttestNote("");
      builds.refresh();
    } catch (caught) {
      setFormError(errorMessage(caught));
    } finally {
      setBusy(false);
    }
  };

  return (
    <>
      <PageHeader
        title="Builds"
        description="Each build binds its own approved destination, optional OpenAPI revision, and the identity the deployment is expected to expose."
        actions={
          canOperate ? (
            <Button variant="primary" onClick={() => setRegisterOpen(true)}>
              Register build
            </Button>
          ) : null
        }
      />
      {builds.loading && !builds.data ? <Loading label="Loading builds" /> : null}
      {builds.error ? (
        <ErrorState message="Builds could not be loaded." onRetry={builds.refresh} />
      ) : null}
      {builds.data ? (
        <TableWrap label="Builds">
          <table>
            <thead>
              <tr>
                <th scope="col">Build</th>
                <th scope="col">Destination</th>
                <th scope="col">Identity</th>
                <th scope="col">OpenAPI</th>
                <th scope="col">Runs</th>
                <th scope="col">Recorded</th>
                <th scope="col">
                  <span className="visually-hidden">Actions</span>
                </th>
              </tr>
            </thead>
            <tbody>
              {builds.data.items.map((build) => (
                <tr key={build.id}>
                  <td>
                    <span className="cell-title">{build.label}</span>
                    {build.commit_sha ? (
                      <div className="cell-sub">
                        commit <code className="mono">{build.commit_sha}</code>
                      </div>
                    ) : null}
                  </td>
                  <td>
                    <code className="mono">{build.target_url}</code>
                  </td>
                  <td>
                    {build.identity.expected ? (
                      <>
                        <code className="mono">{build.identity.expected}</code>
                        <div className="cell-sub">
                          {build.identity.source === "operator_attested"
                            ? "operator-attested"
                            : build.identity.observed
                              ? "observed"
                              : "recorded, not yet observed"}
                        </div>
                      </>
                    ) : (
                      <span className="badge badge-warn">Identity not recorded</span>
                    )}
                  </td>
                  <td>
                    {build.openapi ? (
                      <>
                        <span>{build.openapi.filename}</span>
                        <div className="cell-sub">{build.openapi.operations} operations</div>
                      </>
                    ) : (
                      <span className="muted">No spec</span>
                    )}
                  </td>
                  <td>{build.run_count}</td>
                  <td>
                    <RelativeTime value={build.created_at} />
                  </td>
                  <td className="actions">
                    {canOperate && !build.identity.expected ? (
                      <Button size="sm" onClick={() => setAttesting(build)}>
                        Attest identity
                      </Button>
                    ) : null}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </TableWrap>
      ) : null}

      <Dialog
        open={registerOpen}
        onClose={() => setRegisterOpen(false)}
        title="Register an approved build"
        description="A redeploy that changes the tested artifact needs a new build record, even when the URL is unchanged."
        footer={
          <>
            <Button onClick={() => setRegisterOpen(false)}>Cancel</Button>
            <Button variant="primary" busy={busy} onClick={() => void register()} disabled={!label || !targetUrl}>
              Register build
            </Button>
          </>
        }
      >
        <Field label="Build label" htmlFor="build-label" hint="Use the release or build number.">
          <TextInput
            id="build-label"
            value={label}
            onChange={(event) => setLabel(event.target.value)}
            placeholder="2024.11.0"
          />
        </Field>
        <Field
          label="Approved destination"
          htmlFor="build-url"
          hint="Must be inside the project origin allowlist and path restrictions."
        >
          <TextInput
            id="build-url"
            value={targetUrl}
            onChange={(event) => setTargetUrl(event.target.value)}
          />
        </Field>
        <div className="grid-2">
          <Field label="Commit SHA (optional)" htmlFor="build-commit">
            <TextInput
              id="build-commit"
              value={commitSha}
              onChange={(event) => setCommitSha(event.target.value)}
            />
          </Field>
          <Field
            label="Expected build identity (optional)"
            htmlFor="build-identity"
            hint="The deployment's reported build value. Required before a run is dispatched."
          >
            <TextInput
              id="build-identity"
              value={expectedIdentity}
              onChange={(event) => setExpectedIdentity(event.target.value)}
            />
          </Field>
        </div>
        {formError ? (
          <Notice tone="error" title="Build rejected">
            {formError}
          </Notice>
        ) : null}
      </Dialog>

      <Dialog
        open={attesting !== null}
        onClose={() => setAttesting(null)}
        title={`Attest the deployed identity${attesting ? ` for ${attesting.label}` : ""}`}
        description="Use this only when the deployment cannot expose its identity. The attestation is recorded separately from an observed identity."
        footer={
          <>
            <Button onClick={() => setAttesting(null)}>Cancel</Button>
            <Button variant="primary" busy={busy} onClick={() => void attest()} disabled={!attestValue}>
              Record attestation
            </Button>
          </>
        }
      >
        <Field label="Deployed build identity" htmlFor="attest-value">
          <TextInput
            id="attest-value"
            value={attestValue}
            onChange={(event) => setAttestValue(event.target.value)}
            placeholder={attesting?.label}
          />
        </Field>
        <Field label="Attestation note" htmlFor="attest-note">
          <TextInput
            id="attest-note"
            value={attestNote}
            onChange={(event) => setAttestNote(event.target.value)}
            placeholder="Checked the deployment page at 09:15 UTC"
          />
        </Field>
        {formError ? <Notice tone="error">{formError}</Notice> : null}
      </Dialog>
    </>
  );
}

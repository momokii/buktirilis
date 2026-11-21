# Research note — next move for the single-VM ("monodeploy") live pilot

Date: 2026-11-18. Scope: what to do after live run `69cbc6dc-a42b-4822-aac6-914b64f9073f`.
Read-only research; no code, config, or deployment changed. Claims are marked with `[E#]`
into the evidence table at the end. Recommendations are marked **Recommendation**.

## Verdict

**Harden the boundary first — but the minimal, honest version of it: get the root-equivalent
Docker socket off this multi-tenant host, or gate live dispatch off until it is off.** Nothing
else in this list has a catastrophic failure mode; that one does. The host runs a dozen other
Compose stacks next to the socket-bearing worker `[E9]`, so a misled agent inside the
sandbox is a host root incident, not a bad scan.

After that, in order: close the **one** real coverage gap with a manual two-request replay (no
engine), reclassify the other six gaps as bookkeeping rather than untested surfaces, and only
then run the profile against a target that actually has two actors — **the synthetic lab**, not
`:8501` `[E23][E25]`. `:8501` is documented as "Free, no account" `[E41]`: it offers no subject
for API1 and no privilege distinction for API5, and the `:3100` run already tested for a hidden
privileged plane and found none `[E36]`.

The npm audit cannot be cleared by any available upgrade: no patched `picomatch` exists and Vite
8 depends on the same range `[E28][E30]`. A documented dev-only deferral is the honest choice;
making `make security` green would mean weakening the gate, which requires explicit approval.

Isolation **is** constrainable on one host, but not by flipping an env var: the one Strix knob
that moves the sandbox network is undocumented `[E16]` and, used alone, disconnects the worker
from the sandbox's Caido proxy `[E3][E12]`. Every viable option needs a compose change **and** a
root-level host firewall action.

## Evidence table

| # | Claim (verified) | Owning source |
|---|---|---|
| E1 | Worker installs Strix `1.7.1`; sandbox image pinned by tag `ghcr.io/usestrix/strix-sandbox:1.4.1` | `compose.mono.yaml`, `backend/Dockerfile:21-23` |
| E2 | Installed wheel's `runtime/docker_client.py` is byte-identical to GitHub tag `v1.7.1` | `<https://raw.githubusercontent.com/usestrix/strix/v1.7.1/strix/runtime/docker_client.py>`; local `/tmp/strix-venv/lib/python3.12/site-packages/strix/runtime/docker_client.py` |
| E3 | `STRIX_DOCKER_SANDBOX_NETWORK` sets `create_kwargs["network"]` and **deletes `ports`** | `docker_client.py:54-66,262` |
| E4 | Sandbox always gets `cap_add NET_ADMIN, NET_RAW` and `host.docker.internal → host-gateway` | `docker_client.py:255-260` |
| E5 | `host-gateway` "resolves to the internal IP address of the host" | <https://docs.docker.com/reference/cli/docker/container/run/> |
| E6 | Sandbox env has no LLM key; `http(s)_proxy`/`ALL_PROXY` point at in-sandbox Caido `127.0.0.1:48080` | `runtime/session_manager.py:317-331` |
| E7 | Model traffic is host-side: `StrixProvider()` + `SandboxRunConfig` in the worker process | `core/runner.py:437-439`, `config/models.py` |
| E8 | 1.7.1 ships exactly one sandbox backend (`docker`); remote backends exist only via `register_backend` | `runtime/backends.py:52,70-95` |
| E9 | Only the worker gets `/var/run/docker.sock`; web/API/lab do not | `compose.mono.yaml:20-45`, `compose.yaml:77-91` |
| E10 | Nothing in the repo sets `STRIX_DOCKER_SANDBOX_NETWORK` today → sandbox is on the default bridge `172.17.0.0/16`, gw `172.17.0.1` | repo grep (no match); `docker network inspect bridge` |
| E11 | `:8501` is published `0.0.0.0`; API/DB/lab are unpublished or loopback-bound. The same daemon hosts ~13 unrelated stacks (waha, relaynest, grafana, boxbox, cve-change-radar, opencode-dashboard, tailscale exit node, …) | `docker ps -a`, `docker network ls` |
| E12 | "containers connected to different bridge networks can only communicate with each other using published ports" | <https://docs.docker.com/engine/network/drivers/bridge/> |
| E13 | Compose `internal: true` creates an "externally isolated network" | <https://docs.docker.com/reference/compose-file/networks/> |
| E14 | Docker routes container traffic in `nat` before `INPUT`/`OUTPUT`, "effectively ignoring" ufw | <https://docs.docker.com/engine/network/packet-filtering-firewalls/> |
| E15 | `DOCKER-USER` is the supported pre-Docker filter; direct-routed packets never reach it (dropped in `raw`) | <https://docs.docker.com/engine/network/firewall-iptables/> |
| E16 | Strix docs list no sandbox-network variable; only execution/connect timeouts | <https://docs.strix.ai/advanced/configuration.md> |
| E17 | Run wall time: job `23:30:41→00:07:47` (37m 6s); engine `run.json` `00:00:10→00:07:43` (7m 33s) → ~29m 30s before the first model turn | DB `runs`; run artifact `run.json` |
| E18 | `coverage.json`: `complete=false`, 5 entries, 7 gaps, `exit_reason=finished_by_tool`, caveat names 2 stopped agents | run artifact `coverage.json` |
| E19 | Gap kinds: 1 `needs_follow_up`, 5 `unrecorded_risk_class`, 1 `agent_recorded_no_coverage` | same |
| E20 | The one substantive gap failed because "every request through the sandbox proxy returned a 9,088-byte Caido error page"; no runtime drift test ran | same, gap 1 `detail` |
| E21 | The report says `/showcase` + privileged sweep "were not completed"; the coverage entry for the same work claims byte counts, 50+ slug variants, and a 111-entry ffuf sweep | `penetration_test_report.md` vs `coverage.json` |
| E22 | App rows for the run: 4 tested, 1 needs-review, 7 not-run — of which 6 have an **empty surface** and 1 duplicates the needs-review surface | DB `run_checks` |
| E23 | Profile v1 requires `required_identities=2` and fixtures (`invoice-object-a`) and targets `/api/invoices/{id}`, `/api/admin/settings`, `/api/exports/{id}/pdf`, `/api/approvals/{id}` | `backend/app/services/profiles.py:16-40,88-190` |
| E24 | The run's `scope_snapshot` has `accounts: []`, depth `quick`, `max_checks: 12` | DB `runs.scope_snapshot` |
| E25 | The lab implements those exact surfaces with 6 accounts / 3 tenants / an expired token / 4 deployments | `lab/app/main.py:20-90` |
| E26 | TASK-003 acceptance requires deny-by-default egress and a refused denied-local probe | `.claude/state/TASK_QUEUE.md:40-50` |
| E27 | `verify-isolation.sh` runs in the **worker** netns (not the sandbox), and probes `host.docker.internal` with no port | `scripts/verify-isolation.sh` |
| E28 | GHSA-fc5q-39xc-vjpf / CVE-2026-112366, `<= 4.0.7`, `first_patched_version: null`, CVSS 7.5, CWE-1333 | <https://github.com/advisories/GHSA-fc5q-39xc-vjpf> |
| E29 | `picomatch` latest = `4.0.7`; `fdir` latest = `6.5.0`; `tinyglobby` latest = `0.2.17` | registry.npmjs.org |
| E30 | Vite `7.3.8` and `8.3.8` both depend on `picomatch ^4.0.7` | registry.npmjs.org |
| E31 | `npm audit`: 4 high; `fixAvailable` = vite `6.2.7`, `isSemVerMajor: true`; `@vitejs/plugin-react@5.0.4` peer allows vite ^4.2–^7 | `npm audit --json`; registry |
| E32 | Production web image is `nginx-unprivileged` serving static `dist`; Node/Vite exist only in the build stage | `web/Dockerfile`, `web/nginx.conf` |
| E33 | Budget stop is `cost >= max_budget_usd`; observed `cost = 0.0` with 7.9M tokens → the USD cap never binds | `core/hooks.py:103`; run `run.json` |
| E34 | OpenCode Go asks clients to "send a stable session ID in `x-opencode-session`" | <https://opencode.ai/docs/go> |
| E35 | DeepSeek V4.1 Flash data retention: 0 days | same page |
| E36 | API1:2023 assumes a "logged-in user"; API5:2023 assumes "anonymous users or regular, non-privileged users" | <https://github.com/OWASP/API-Security/blob/master/editions/2023/en/0xa1-broken-object-level-authorization.md>, `.../0xa5-broken-function-level-authorization.md` |
| E37 | `ArtifactBundle.status` returns `partial` whenever anything is "missing"; a clean 1.7.1 run has no `vulnerabilities.json` | `backend/app/services/ingest.py:99-106` |
| E38 | No leftover sandbox containers after the run; image digest `sha256:c8e70302ba4a…` | `docker ps -a --filter label=strix-run-id`; `docker image inspect` |
| E39 | Host: 12 vCPU, 22 GB RAM (15 GB avail), 35 GB free on `/`, `/dev/kvm` present, `iptables` needs root | host commands |
| E40 | Docker `29.3.1`, firewall backend `iptables` (nf_tables), ufw enabled+active | `docker version`, `docker info`, `systemctl` |
| E41 | BoxBox Replay: "Free, no account, no live-timing subscription"; no `/login` surface (only outbound upstream keys) | `../boxbox-replay/README.md`; `../boxbox-replay/api/main.py` |
| E42 | `standard` = 30 min–1 h, "source-aware mapping and static triage" (white-box); `deep` is not offered by this adapter | <https://docs.strix.ai/usage/scan-modes.md>; `docs/strix-contract.md` |

## Decision matrix

| Option | Access-control signal produced | Risk added | Cost | Verdict |
|---|---|---|---|---|
| A. Live run against `:8501` | **None.** No accounts, no sessions, no ownership `[E41]`; API1 needs an owner, API5 a privilege distinction `[E36]` | Repeats the `:3100` mistake with the same socket exposure; exposes 44 endpoints — 8 AI-related (`/ai/*`, `/coach/ask`, `/session/strategy`) forwarding to a server-held upstream key — to an autonomous agent | ~37 min + tokens `[E17]` | **No** as an access-control run. Legitimate later as an *API4/API10* profile (unauthenticated LLM proxy, upstream consumption) |
| B. Live run against a real authenticated app | Real API1/API5 signal — the only option that produces it | Sends authenticated app content to a third-party model provider `[E34][E35]`; needs short-lived credentials and a scope agreement | Days (target selection, consent, credentials) | **Yes, but last** — after isolation |
| C. Re-run to "complete the 7 gaps" | ~1 real gap + 6 bookkeeping rows re-derived | Same socket exposure; the 6 bookkeeping gaps recur unless agents are told to record per risk class | ~37 min again | **No.** Only gap 1 is a test; the rest are record-keeping `[E19][E22]` |
| D. Manual/API replay for gap 1 | **Yes** — a named control or a two-request counterexample, which is exactly what the hypothesis needs `[E20]` | None: two GETs from an operator workstation | ~15 min | **Yes — do this first after the socket decision** |
| E. Harden isolation (off-host worker) | None directly; unblocks everything else and removes the catastrophic branch | Migration effort; disk is tight (35 GB) `[E39]` | ~0.5–1 day + operator root | **Yes — highest priority** |
| F. Live run against the synthetic lab | **Full profile signal**: 2 identities, owned invoices, a denial + owner positive control, export and two-actor approval `[E23][E25]` | Low: synthetic data, loopback/container network | ~10 min engine work once reachable | **Yes — the correct "next live target"**; it is also what TASK-003 already specified `[E26]` |

**Recommendation:** E → D → (fix the two reporting/state defects) → F → B, with A reframed as a
different profile and C dropped.

## Isolation: what is actually achievable on this host

Today the sandbox runs on the **default bridge with no network restriction** `[E10]`, always has
`NET_ADMIN`/`NET_RAW` (so it can rewrite its own routes, DNS, and craft raw packets) `[E4]`, and
always receives a `host.docker.internal` alias for the host's internal IP `[E4][E5]`. Because
`:8501` is published on `0.0.0.0` `[E11]`, `http://host.docker.internal:8501` is reachable from
inside the sandbox by construction. The worker↔sandbox hop is host→container (allowed); the
sandbox→host hop is container→host (INPUT), which no `DOCKER-USER`/FORWARD rule governs `[E15]`.

| Option | Mechanism | Feasible here? | Blocking dependency |
|---|---|---|---|
| O1 Status quo | default bridge + socket | Trivially | Unacceptable on a host with other stacks `[E11]` |
| O2 `STRIX_DOCKER_SANDBOX_NETWORK=<new bridge>` | move sandbox to a user-defined bridge, firewall that subnet | **Partially** | Setting it alone **removes port publishing** `[E3]`; the worker sits on `buktirilis_backend` and cross-bridge traffic is allowed only via published ports `[E12]` → Caido bootstrap would fail. Requires co-attaching the worker to the new network (compose change) **and** root `INPUT`/`FORWARD` rules, because host-published ports are INPUT, not FORWARD `[E15]` |
| O3 `internal: true` sandbox network | no external connectivity at all `[E13]`; attach the target container to it | **Yes, but invasive** | Target must be addressed by container DNS (e.g. `http://lab:8099`) instead of `100.124.184.116:3100` → new target policy revision; requires touching another stack's compose to attach its container |
| O4 Dedicated worker VM (KVM) | move worker+socket off this host; filter FORWARD on that VM | **Yes** `[E39]` | ~10–20 GB disk (only 35 GB free); operator provisioning; model key moves to the VM |
| O5 Allow-listed forward proxy | force sandbox traffic through an ACL proxy | **No, not without patching Strix** | Strix hardcodes the sandbox's proxy env to the in-sandbox Caido `[E6]`; there is no env hook to inject an upstream proxy, and Caido dials out from the sandbox netns |
| O6 `ufw` allowlist | host firewall | **No** | Docker bypasses ufw via the `nat` table `[E14]` |
| O7 Strix remote backend | offload sandbox | **No** | Only `docker` is registered in 1.7.1 `[E8]` |

**Recommendation:** O4 for anything called a pilot; if it must stay on one host this week, O3 for
lab-shaped targets and O2 only with the worker co-attached. Do **not** ship a runbook that says
"set `STRIX_DOCKER_SANDBOX_NETWORK`" without the worker co-attach and the INPUT rules — that
combination fails at the proxy bootstrap and looks like an engine bug.

### The existing probe does not test the sandbox

`scripts/verify-isolation.sh` runs wherever it is invoked — the runbook says "inside the worker
network namespace" `[E27]`. The sandbox is a *different* netns on a *different* bridge `[E10]`.
So the probe can pass while the sandbox reaches `:8501`, the tailnet, and the internet. Two
further weaknesses: the `host.docker.internal` destination has no port (nothing listens on :80,
so "unreachable" is guaranteed), and `169.254.169.254` is unreachable on a bare host regardless
of policy — it proves nothing about egress control.

**Recommendation:** re-point the probe to execute *inside a sandbox-like container*
(`docker run --rm --network <sandbox-net> …`), assert `http://<target>:<port>` is reachable and
`http://host.docker.internal:8501`, `…:8088`, `…:3003` are not, and record the exit code.

## Coverage gaps: what the seven actually are

The artifact answers this directly; the framing in `CURRENT_STATUS.md` does not `[E18][E19]`.

| # | Kind | What it means | Smallest evidence-producing follow-up |
|---|---|---|---|
| 1 | `needs_follow_up` | The **only** genuinely unexecuted test: spec-vs-runtime drift on `/api/v1/*`. It never ran because every proxied request returned a 9,088-byte Caido error page `[E20]` | **Manual replay**: for ~10 ids, compare `GET /api/v1/cves/{id}` (404) with `GET /api/v1/cves/batch?ids=` (populated?). Two requests decide it. Upload the raw pair as a project artifact |
| 2–6 | `unrecorded_risk_class` (×5) | A skill was *assigned* to an agent but no coverage entry was recorded — `authentication_jwt`, `browser_security`, `business_logic`, `idor`, `mass_assignment` | **Not a re-test.** The narrative report describes JWT/role-branch and IDOR work as performed `[E21]`; the gap is that the agent never wrote a `record_coverage` row. Either accept the narrative as partial evidence or run one guided pass that records per class |
| 7 | `agent_recorded_no_coverage` | `Batch Resolution Gap` was stopped before recording anything | Subsumed by #1 (same agent, same hypothesis) |

Two consequences worth stating plainly:

1. **"4 of 12 tested" is not a profile denominator.** The 12 rows are 5 Strix coverage entries +
   7 gaps `[E18]`; the profile's own plan needs matching routes and `required_identities=2` `[E23]`,
   and this run had `accounts: []` `[E24]`. The run therefore did not exercise the access-control
   profile at all — it exercised the engine adapter. That is a real result, but it is a different
   claim than "4/12 access-control checks passed".
2. **Six of the twelve rows have an empty surface** `[E22]`, and the seventh duplicates the
   needs-review surface. An operator reading the report sees "7 not run" as seven untested
   surfaces; it is one untested surface plus six audit-trail holes.

`standard` depth would not fix any of this: it raises turns/budget and turns on white-box source
mapping, which needs local source (`--target ./app`), not a remote URL `[E42]`.

## npm advisory triage

- Advisory: **GHSA-fc5q-39xc-vjpf / CVE-2026-112366**, ReDoS in `picomatch` via single-branch
  repeated extglob patterns, CVSS 7.5 `AV:N/AC:L/PR:N/UI:N/S:U/C:N/I:N/A:H`, CWE-1333,
  vulnerable `<= 4.0.7`, **`first_patched_version: null`** `[E28]`.
- Installed: `picomatch@4.0.7` (also the latest published), `fdir@6.5.0` (latest),
  `tinyglobby@0.2.17` (latest) `[E29]`. There is nothing to upgrade *to*.
- No upgrade path: Vite `8.3.8` still declares `picomatch ^4.0.7` `[E30]`, so a major Vite upgrade
  does not clear the audit and would additionally force `@vitejs/plugin-react` to a v8-only major.
- The only mechanical fix npm offers is a **downgrade** of Vite to `6.2.7` `[E31]` (plugin-react 5
  tolerates it). That trades a build-time ReDoS that requires attacker-controlled glob patterns
  for a two-major toolchain regression.
- Reachability: `vite` is a devDependency; the runtime image is nginx serving a static `dist`, with
  Node present only in the build stage `[E32]`. The vulnerable function is reached while compiling
  a glob pattern; in this repo those come from local config and `npm run build`, not from remote
  input. No Node process exists in production.

**Recommendation:** keep `npm audit --audit-level=high` in `make security` (do not soften the
gate), record a **documented dev-only deferral** with an owner, and set the re-check trigger as
"when `picomatch > 4.0.7` is published" — `^4.0.7` already accepts it, so a plain `npm install`
closes the advisory with no code change. Exit criterion: the deferral is written in
`docs/security-guardrails.md` and `make security` is still reported as **red**, not "passing with
exceptions".

## Recommended ordered actions

| # | Action | Exit criteria |
|---|---|---|
| 0 | **Rotate the OpenCode Go key** used in the pilot (already flagged as exposed; `.env.live` is mode 600 and gitignored, so rotation is operator-only) | New key in `.env.live`; old key revoked at the provider; no key value in any log, artifact, or doc |
| 1 | **Stop dispatching live runs on the shared host.** Either set `LIVE_EXECUTION_ENABLED=false`/stop the worker, or complete O4 | `docker ps` shows no socket-bearing worker on the host that runs other stacks; no live job can be claimed |
| 2 | **Close gap 1 by manual replay** against `http://100.124.184.116:3100` (two GETs per id, ~10 ids). Record result as run-level evidence (the model supports `finding_id=None` + `run_id`; uploaded artifacts are size-bounded and content-sniffed) | Either a finding with the two raw responses, or `ruled_out` with the named control (e.g. "batch applies the same PUBLISHED filter; `missingIds` ≡ detail-404 across all N ids") stored as an artifact |
| 3 | **Fix the report's two accounting defects**: (a) six coverage-gap rows carry no surface and one duplicates the needs-review row `[E22]`; (b) `ingest_state=partial` is structural, not historical — any clean 1.7.1 run lacks `vulnerabilities.json`, so `ArtifactBundle.status` will always return `partial` `[E37]`. Correct the claim in `CURRENT_STATUS.md` that re-ingest will help | Re-ingest is either dropped from the backlog or re-scoped as "change the missing-set rule"; the report no longer presents seven unrun rows as seven untested surfaces |
| 4 | **Make the sandbox boundary real** (O4 preferred; O3 acceptable for lab targets). Co-attach the worker if using O2, add the INPUT rule for host-published ports, and re-point the probe at the sandbox netns | Probe run **inside a sandbox container**: target reachable; `host.docker.internal:{8501,8088,3003}`, `169.254.169.254`, and the Docker socket all refused; output committed to the runbook |
| 5 | **First profile-faithful live run: the synthetic lab** `[E23][E25]`, live mode, standard depth, 2 identities (owner + non-owner of the same invoice), fixtures present | Profile-shaped checks appear (`bola-object-read`, `role-restricted-function`, `cross-tenant-export`) with a denial **and** an owner positive control; at least one finding or an explicit `ruled_out` per scenario; `accounts` non-empty in `scope_snapshot` |
| 6 | **Record the npm deferral** (see above) | Written rationale + trigger + owner; `make security` still reported red |
| 7 | **Then** choose a real authenticated target, with a written scope and short-lived credentials | Credential path documented, provider data-handling accepted (`[E35]`), identity probe green |

Notes for whoever runs #5 and #7: the USD budget is inert unless per-MTok pricing is configured —
observed `cost = 0.0` for 7.9M tokens `[E33]` — so the only effective cap today is
`max_runtime_seconds` (3600). Set `STRIX_LLM_*_COST_PER_MTOK` or state that `--max-budget` is
decorative. Expect ~29 minutes of bring-up before the first model turn on a cold image `[E17]`;
warm-image duration is unknown (see below).

## What is still unverified

- **Cross-bridge isolation on Docker 29.3.1 `[E40]`.** The documented rule is `[E12]`; whether
  worker→sandbox Caido is actually dropped on this exact version was not tested (that needs a
  container create, which this task forbade). Consequence: O2's failure mode is predicted from
  source + docs, not observed. Probe before adopting O2.
- **Whether an `internal` network still exposes the host gateway.** `host-gateway` resolves to a
  host IP `[E5]`, and container→host traffic is INPUT rather than FORWARD `[E15]`; O3 must
  therefore be probed, not assumed.
- **`STRIX_DOCKER_SANDBOX_NETWORK` is undocumented `[E16]`.** It is real in the pinned 1.7.1
  source `[E3]`, but it is not a supported interface; a 1.8 upgrade may rename or drop it.
- **Root cause of the Caido failure** (9,088-byte error page, `[E20]`). Unknown whether it was the
  proxy, the sandbox image, or a configuration interaction. It blocked the highest-value test, so
  it matters: no `http_exchange` evidence can be attached until it works.
- **Whether the app UI can attach an artifact to a *check* rather than a finding.** The data model
  allows run-level evidence, but no route was confirmed; step 2 may need an operator step.
- **`:8501` behaviour was not probed** (read-only task, no scans). Its 44 routes — 8 of them
  AI-related `[E41]` — come from source, not from a live response.
- **Warm-image run duration and real token cost** are unknown: the only data point is a cold run
  with `cost = 0.0`.
- **Sandbox image is pinned by tag, not digest.** The registry digest observed locally is
  `sha256:c8e70302ba4a69b678b4001c909b134d8d0b84625d7b23feed59ece02672c1d2` `[E38]`; recording it
  in the runbook (as `docs/strix-contract.md` already asks) is still outstanding.
- **owasp.org was unreachable** from this environment (timeouts); OWASP claims are cited from the
  project's own reference links `[E23]` and the OWASP GitHub mirror `[E36]`.
- **Docker docs `main`** were used for `[E12][E13][E14][E15]`; they describe current behaviour and
  match `29.3.1`'s documented model, but were not version-pinned to it.

## Post-research verification (parent thread)

The parent thread checked the current loader against the real run artifacts after this note
was drafted:

```text
missing []
unparsed []
status complete
sarif_runs 1
vulns 0
```

So E37's "structural partial" conclusion is outdated for the current code: the clean-SARIF
fix removes `vulnerabilities.json` from the missing set when SARIF contains only coverage
results. The historical run was ingested before that fix and remains `partial`; re-ingest is
now viable. This does not change the recommendation order.

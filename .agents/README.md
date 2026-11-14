# Cross-Tool Agent Setup

## One policy, multiple hosts
The shared source of truth is `.claude/`: AGENT_RULES, CODING_STANDARDS,
SECURITY_STANDARDS, state, procedures, and task checklists. The name is historical;
these policies apply to every model/provider. Root `AGENTS.md` is the portable
startup contract; root `CLAUDE.md` remains the compact project snapshot/command index.
Extend the shared policy once and keep native adapters consistent. Never weaken
shared rules or a native adapter without explicit user approval.

Launch tools from the project root. Until Git exists, some hosts cannot reliably
discover this root when launched in a nested directory. Review/trust this project's
files in each host; do not disable safety controls to avoid a trust prompt.

## Loading and enforcement
| Host | Context loading | Native controls supplied |
|---|---|---|
| Claude Code, any supported model | Root CLAUDE.md and its four imports | Existing `.claude/settings.json`; no permission mode override |
| OpenAI Codex CLI/IDE | AGENTS.md; agent explicitly reads its five required files | Trusted `.codex/config.toml`: workspace-write, on-request approvals, shell network off; `.codex/rules/project.rules` |
| OpenCode, any provider | AGENTS.md plus five explicit `opencode.json` instruction paths | Native ordered permissions; secret-path denies, writes/shell/search review, external-directory approval |
| Pi, any provider | AGENTS.md plus full shared context injected before each run by the trusted extension | `.pi/extensions/project-policy.js`: direct secret-path blocks; approval for mutations, shell, searches, and unknown tools |
| Other AGENTS.md-aware agents | AGENTS.md directs explicit context reads | Use that host's own permissions/isolation; no automatic equivalence claim |
| Custom OpenAI/Anthropic/other API clients | Application must load AGENTS.md and all five required files into authorized instruction context | Application must implement tool authorization, isolation, and safe file access |

An OpenAI/Claude **model** does not discover repository files. The coding **host**
does. Ordinary web chat and raw API calls do not automatically gain this setup.
Instruction discovery can be disabled or superseded by host/global/managed settings;
check effective controls in the tool you actually run.

## Claude Code
Open a fresh session here. Run `/context` (or `/context all`) and `/permissions`.
Verify CLAUDE.md and the four imports, rule sources, and no invalid-rule warnings.
Protected-path handling and the limitations of Bash matching remain documented in
`.claude/README.md`. This adapter was preserved; other adapters do not replace it.

## Codex
Review/trust the project so its `.codex/` config and rules load; restart Codex after
config changes. AGENTS.md instructs the agent to read the common files explicitly,
including again after compaction when needed. Do not assume `@path` expands.
The config does not replace built-in model instructions or select a model/provider.

Workspace-write limits mutations and disables shell-network access by default; it
does **not** make secret files unreadable. Prefix rules cover matching commands on
the host's execution/approval path, not arbitrary file reads, every argument order,
or every command run inside the sandbox. For example `git push origin --force`
matches the push approval rule but not the third-token force-push deny. Shared
policy still forbids it. Use OS isolation/managed read restrictions for secrets.
Check `/permissions` and effective project settings in your installed client.

## OpenCode
**Quit and restart OpenCode** after project configuration changes. The configuration
uses documented V1 `permission`/`command` fields, also accepted as compatibility
fields by the published V2 schema. Do not paste V2 `permissions`/`shell` examples
into a V1 client. On a version upgrade, revalidate against the current schema and
installed client before migrating; never silently drop old restrictions.

Rules are **last matching wins**, unlike Claude's category precedence. Broad ask
rules come first; secret denies come last. Named env variants preserve `.env.example`.
Shell defaults to ask (only status/current-branch inspection is pre-allowed); file
mutations, searches, external access, and unspecified tools require review. Global,
agent-specific, CLI, plugin, or managed settings can alter effective behavior.
No model/provider, API key, global config, or existing security plugin is changed.
Read denies do not guarantee protection from indirect shell readers, recursive
search tools, or external integrations; inspect approval requests and use isolation.

## Pi
Review the extension, grant project trust using Pi's normal trust UI, then restart
or `/reload`. Trust loads executable project resources; it is not a sandbox.
The extension keeps Pi's existing system prompt and appends the five current shared
files before every run, including after resumed/compacted conversation history.
Missing/unsafe context blocks all subsequent tool calls rather than silently proceeding.

Direct safe in-project reads are automatic. Direct secret reads/edits/writes (including
symlink targets and new paths under symlinked directories) are blocked. The example
env template remains usable. Other operations prompt **per call**: edits, writes,
all shell/PowerShell, searches/listings, external reads, and unknown/MCP tools.
Direct recognizable sudo/world-writable/force-push commands are rejected; this is
not a complete shell parser. No UI, rejection, or UI failure means denial.

This gate is an in-process tool hook, **not an OS sandbox**. Approved shell commands
can still indirectly access files; other extensions can run code or mutate tool
inputs. User `!`/`!!` shell commands are outside this agent-tool hook. Trusting an
unfamiliar extension or disabling this one defeats its protection. Do not use
`--no-extensions`/`--no-approve` for normal project work or assume headless auto-approval.
If a resource was declined, report it; do not force trust as a workaround.
For hard separation, run the complete host with only needed resources exposed in
an approved sandbox/container/VM. Production credentials never belong in the host.

## Shared workflows
The portable skills in `.agents/skills/` reference the existing `.claude/commands/`
procedures; their bodies remain authoritative. All hosts can follow natural-language
requests such as "resume this project", "wrap up this task", and "check security".

| Host | Explicit invocation |
|---|---|
| Claude Code | `/resume`, `/wrap-up`, `/security-check` |
| Codex | `$project-resume`, `$project-wrap-up`, `$project-security-check` (or `/skills`) |
| OpenCode | `/project-resume`, `/project-wrap-up`, `/project-security-check` |
| Pi | `/skill:project-resume`, `/skill:project-wrap-up`, `/skill:project-security-check` |

## Verification
Run `python3 .agents/verify.py` for the known-file/import/configuration/hygiene and
actual Git ignore checks (Python 3.11+ and Git required). Add `--native` to check
installed Codex/OpenCode diagnostics in an isolated synthetic project; no AI requests
are made and no user configuration/credentials are loaded into the fixture.
For Pi's native loader check, also pass `--pi-package` with its installed coding-agent
package directory. Without that path, native Pi verification is reported unverified.
`--schemas` additionally requires the already-installed Python `jsonschema` package
and public documentation access; it never installs dependencies. Previously retrieved
official schema JSON can be supplied using `--opencode-schema` and `--codex-schema`
when downloads are unavailable. Check provenance/date before relying on cached schemas.

Run `node --test .agents/tests/pi-policy.test.mjs` for the Pi hook's positive and
negative tests. This is infrastructure verification, not the future application's
test command. Test Codex prefix rules without executing the proposed command:
`codex execpolicy check --rules .codex/rules/project.rules -- sudo true`.
Validate opencode.json against `https://opencode.ai/config.json`, and Codex TOML
against `https://developers.openai.com/codex/config-schema.json` after TOML parsing.
Keep secrets out of validation fixtures and diagnostic output.

Runtime acceptance remains per host: verify loaded instruction sources, project trust,
effective permissions, workflow discovery, and extension activation with synthetic
non-secret fixtures. Native config/rule tests do not prove all UI flows or arbitrary
provider integrations. CLI/API clients without repository access need manual integration.

Bootstrap verification evidence: 34 known files passed static checks; 12 Pi policy
tests passed; installed Codex 0.147.0 discovered AGENTS.md and passed eight execpolicy
cases; installed OpenCode 1.19.5 loaded instruction/workflow configuration with nine
retained-rule fixtures; installed Pi 1.4.0 discovered AGENTS.md and loaded all three
extension hooks. Both native configurations validated against official schemas
retrieved during this task. A subsequent direct schema downloader received HTTP 403;
validation used the already-retrieved copies rather than retrying that access.
Interactive trust/approval UI and real model behavior remain unverified. Claude's
interactive loading/permission check and a dedicated secret scan remain outstanding.

## Sources checked on 2026-11-14
- [Claude context](https://code.claude.com/docs/en/memory) and [permissions](https://code.claude.com/docs/en/permissions)
- [Codex AGENTS.md](https://developers.openai.com/codex/agent-configuration/agents-md), [config](https://developers.openai.com/codex/config-file/config-basic), [rules](https://developers.openai.com/codex/agent-configuration/rules), [skills](https://developers.openai.com/codex/build-skills)
- [OpenCode rules](https://opencode.ai/docs/rules/), [permissions](https://opencode.ai/docs/permissions/), [schema](https://opencode.ai/config.json), [skills](https://opencode.ai/docs/skills/)
- [Pi configuration](https://github.com/earendil-works/pi/blob/main/packages/coding-agent/docs/configuration.md), [extensions](https://github.com/earendil-works/pi/blob/main/packages/coding-agent/docs/extensions.md), [security](https://github.com/earendil-works/pi/blob/main/packages/coding-agent/docs/security.md), [skills](https://github.com/earendil-works/pi/blob/main/packages/coding-agent/docs/skills.md)

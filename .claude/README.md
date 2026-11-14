# Agent Infrastructure

This is a general-purpose project scaffold. Purpose, stack, product requirements,
and deployment targets are not yet defined. Update this overview after the first
working session. Every file starts general by design and evolves with verified facts.
The policies/state here are shared by all project agents. Root `AGENTS.md` and
`.agents/README.md` connect Codex, OpenCode, Pi, and other configurable clients.

## How context loads
Root `CLAUDE.md` is the automatic project entry point, including after context
compaction. It imports exactly `AGENT_RULES.md`, `CODING_STANDARDS.md`,
`SECURITY_STANDARDS.md`, and `state/CURRENT_STATUS.md` from this directory.
Imports are plain-text lines beginning with `@` immediately followed by a relative
path; they are not evaluated inside inline code or fenced blocks.
Imported files load fully and consume context. Other files here, including this
README and `HOW_TO_RESUME.md`, are read on demand through the entry point's pointers.
Run `/context` in a new Claude Code session and inspect **Memory files**; on versions
or layouts that collapse the list, run `/context all`. Confirm the entry point and
four imports are present; read any missing files manually.

## File map
All paths below are relative to `.claude/`.

| File | Purpose |
|---|---|
| `settings.json` | Shared deny/ask/allow permission baseline |
| `README.md` | Orientation, loading model, and limitations |
| `AGENT_RULES.md` | Session, scope, security, and maintenance requirements |
| `CODING_STANDARDS.md` | Universal code and quality conventions to specialize |
| `SECURITY_STANDARDS.md` | Security Gate and mandatory security requirements |
| `ENVIRONMENT_GUIDE.md` | Environment identification and dev/prod configuration |
| `HOW_TO_RESUME.md` | Ordered session-start and task lifecycle protocol |
| `commands/resume.md` | `/resume`: baseline and report, then wait for confirmation |
| `commands/wrap-up.md` | `/wrap-up`: batch state and documentation maintenance |
| `commands/security-check.md` | `/security-check`: review changes without auto-fixing |
| `state/CURRENT_STATUS.md` | Compact current state imported every session |
| `state/TASK_QUEUE.md` | Ordered, dependency-aware backlog and task template |
| `state/DECISIONS_LOG.md` | Decisions, rationale, security implications, and template |
| `state/HISTORY.md` | Append-only session summaries |
| `templates/new_feature.md` | Feature implementation checklist |
| `templates/new_endpoint.md` | API endpoint checklist |
| `templates/new_test.md` | Test design and reliability checklist |
| `templates/bug_fix.md` | Reproduce, diagnose, fix, and regression checklist |

Root `.gitignore` protects local files; `.env.example` documents safe configuration
placeholders. Root `CLAUDE.md` owns the snapshot, essential imports, and command index.

## Permissions: enforcement and limits
- Markdown instructions are context, not enforcement. Claude Code enforces settings;
  hooks, Git hooks, and CI can add checks after approval in TASK-002.
  `.claude/settings.json` targets Claude Code. Native OpenCode/Codex adapters and a
  Pi extension are documented in `.agents/README.md`; verify the active host's controls.
  Loading these docs does not establish that a host enforces another host's settings.
- Rules evaluate **deny, then ask, then allow**; the first matching category wins.
  Deny and ask rules apply across modes (noninteractive modes can refuse instead of
  prompting). No `permissions.defaultMode` is set; the user's chosen/built-in mode applies.
- Allow: Git add/commit and ordinary Compose up/build/ps/logs. Permission to run a
  commit is not user intent: never commit or push unless explicitly requested.
- Ask: pushes, destructive operations, shell downloads, volume deletion/pruning,
  and workflow edits. Deny: named environment files, secret/key stores, sudo,
  world-writable chmod forms, and common force-push forms (including lease variants).
- `.env.*` is deliberately NOT a Read/Edit wildcard deny: it would block
  `.env.example`. Named env files (including common local/test variants) are denied
  instead. Before introducing another secret-bearing filename, add explicit Read
  and Edit denies; do not inspect its contents. The ignore wildcard still applies.
- Read/Edit denies cover built-in file tools, recognized Bash file commands such as
  `cat`, `head`, `tail`, `sed`, `tee`, and redirect targets. They do not cover indirect
  readers such as `grep -r` from a containing directory or scripts opening files.
  Avoid broad searches that might ingest secrets. Evaluate Claude Code's sandboxing
  for OS-level filesystem/network protection; enable it only with user confirmation.
- Bash patterns match command text, not program identity. `Bash(curl *)` does not
  match `/usr/bin/curl` or `sh -c 'curl ...'`; `Bash(git push *)` does not match
  `git -C . push`. These rules are not a security boundary or exhaustive shell filter.
- `docker compose up *` covers the default development command shape. Explicit
  `docker compose -f compose.yaml -f compose.prod.yaml up` does not match the allow
  rule and remains subject to the mode's approval/classifier checks. It is not
  guaranteed to prompt in auto mode: agent policy must always ask if not clearly dev.
  Text matching cannot prove development: check APP_ENV, target daemon/context,
  Compose file selection (including COMPOSE_FILE), and effective configuration without
  printing secrets. Never dump `env` or use an interpolated config dump to identify it.
- No stack-specific package manager, test, or lint commands are pre-allowed. Once
  selected, propose narrow rules and add them only with user confirmation. Never
  use blanket `Bash(*)` or an allow rule as a substitute for environment checks.

## Protected paths and shared/local boundaries
`.claude/` is protected: settings allow rules such as `Edit(.claude/**)` do not
pre-approve writes. Manual/acceptEdits prompt; auto mode routes to the classifier;
dontAsk refuses; bypass skips this protection. Exceptions include Claude's own
`.claude/worktrees/` and its own eligible auto-memory files.
The prompt can offer **allow edits in this project's .claude folder for this session**;
selecting it avoids repeated prompts within that session. Otherwise expect prompts
again. Batch all wrap-up writes into one step, and report any refusal; never work
around protection through a shell, another tool, settings, or bypass mode.
`.pre-commit-config.yaml`, `.husky/`, `.devcontainer/`, and `.mcp.json` are also
protected paths; expected approval/classifier handling applies to their edits.

Shared files here are intended for version control. `CLAUDE.local.md` and
`.claude/settings.local.json` are personal and gitignored; agents must never create
or modify `settings.local.json`. Claude's own auto-memory is machine-local, so put
team-relevant knowledge in these versioned files, never only in auto-memory.

## Evolve and verify
Specialize rules, commands, environment docs, and representative code references as
the stack emerges. Keep imports compact; put deeper details in project docs.
Never weaken AGENT_RULES, SECURITY_STANDARDS, or permissions without explicit approval.

Official documentation checked on 2026-11-14:
- [Memory/imports](https://code.claude.com/docs/en/memory)
- [Permissions and rule syntax](https://code.claude.com/docs/en/permissions)
- [Modes and protected paths](https://code.claude.com/docs/en/permission-modes#protected-paths)
- [Skills and supported legacy command files](https://code.claude.com/docs/en/skills)

The requested `.claude/commands/*.md` format remains supported with `description`
frontmatter. No command grants extra tools or changes models. In current local CLI
versions a custom command can override a same-named built-in: this project's `/resume`
is the startup protocol, not the session picker; use `claude --resume` for that picker.
Check the `/` menu on your installed surface/version for command-name resolution.
All rule shapes were checked against the docs. Interactive `/permissions` inspection
has not been performed by the bootstrap harness. In Claude Code, open `/permissions`,
verify each rule and source is recognized with no invalid-rule warnings, and confirm
effective settings alongside any user/managed rules. Check `/context` as above.
Application tests, audits, and CI are not configured until foundation tasks are approved.

# Project Scaffold

Purpose and application stack are not yet defined. This repository currently holds
a security-first, stack-neutral infrastructure for iterative AI-assisted development.

## Agent entry points
- **Claude Code:** `CLAUDE.md` imports the four compact shared policy/state documents.
- **OpenAI Codex, OpenCode, and Pi:** `AGENTS.md` establishes the same required context.
- **Other tools and custom API clients:** configure `AGENTS.md` as the instruction
  entry point and load its required documents; model names alone do not load files.

Read [the cross-tool setup guide](.agents/README.md) for discovery, native controls,
workflow invocation, trust/restart requirements, and verification commands.
Read [the shared infrastructure map](.claude/README.md) for canonical policies and state.

Start with the first project task: confirm purpose, stack, and a local development
target. TASK-001 configures application tooling; TASK-002 adds approved security
automation. Native adapter defaults do not establish application/production readiness.

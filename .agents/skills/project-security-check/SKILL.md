---
name: project-security-check
description: Review this project's current changes against its Security Gate without automatically fixing findings.
---

# Project Security Check
Resolve the project root three directories above this skill directory. Read root
`AGENTS.md`, then `.claude/commands/security-check.md` from that root and execute its body.
Review only safe authorized paths; cite findings by severity and location without
printing secrets. Distinguish executed scans from manual review. Ask before fixes.

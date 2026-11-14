---
description: Run the project resume protocol through baseline checks and report readiness.
disable-model-invocation: true
---

Read `.claude/HOW_TO_RESUME.md` and execute steps 1–7 only. Confirm root CLAUDE.md
and its four imports, read TASK_QUEUE, identify the environment before commands,
check Git without disturbing changes, read relevant docs, and verify documented
health/test baselines only where the environment and permissions permit.

Do not install tooling, bootstrap the stack, or treat unavailable checks as passes.
If Git/app commands do not yet exist, report that. Preserve secret-file protections.
Report in fewer than 15 lines: current state, next eligible task and dependencies,
environment/target confidence, health and baseline test results, and blockers.
Stop and wait for user confirmation before starting implementation.

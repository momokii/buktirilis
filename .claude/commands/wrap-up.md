---
description: Batch task-boundary state and instruction updates and summarize saved progress.
disable-model-invocation: true
---

Read `.claude/AGENT_RULES.md` Wrap-Up and current state files. Gather actual task
outcomes and verification evidence; distinguish pass, fail, N/A, and unverified.
Update CURRENT_STATUS (under about 80 lines), TASK_QUEUE, significant DECISIONS_LOG
entries, and append HISTORY without rewriting earlier summaries. Update affected
standards, environment/resume docs, root CLAUDE.md Snapshot/Commands, and README
when verified facts changed. Preserve existing work and the no-weakening guardrail.

Perform all writes together in one edit step: `.claude/` is protected. If refused,
report the refusal and pending updates; never switch tools or change permissions
to work around it. Never touch settings.local.json. Never commit or push implicitly.
Print a short summary of saved files, next task, blockers, and any unverified checks.

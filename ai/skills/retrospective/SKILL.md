---
name: retrospective
description: "Post-work close-out for any change in this repository: verify the full CI mirror passed, sync REQUIREMENTS.md, consult the mentor before writing memory, file refactoring debt, fix framework drift, and check hygiene. Use BEFORE finalizing any task that changed files."
allowed-tools: Read, Grep, Glob, Edit, Write, Bash
---

# Retrospective — after work, before finalizing

Phase 2 of the mandatory lifecycle. Run every step. This is what makes the framework improve
itself instead of repeating its mistakes.

## 1. Tests — run the CI mirror, not a subset

Use the `verify-build` skill. In short: `./scripts/run_tests.sh` (add `--all` when an
emulator or device is attached), read the printed gate summary, and name every `⊘ SKIPPED`
gate in your task summary as an accepted risk.

Bare `pytest` or `gradlew testDebugUnitTest` is a strict subset of what CI enforces and is
**not** sufficient evidence.

**If the task is not done, the task is not done.** Never push a speculative fix and let CI
adjudicate it — a chain of `fix(ci)` / `fix(test)` commits on a branch is the anti-pattern
this step exists to prevent.

## 2. Requirements

Did observable behaviour change? Then the owning product's `REQUIREMENTS.md` changes in the
same commit. Use the `sync-requirements` skill — it covers what counts as observable, which
file owns which rule, and the workflow-parity obligation.

## 3. Reflect, then consult the mentor

Reflect on the task honestly:

- What failed on the first attempt?
- What took longest, and why?
- What surprised you — an assumption the codebase did not honour?

Draft candidate memories from that, then **consult `@shared-mentor-agent`** with the task
summary, the diff, and your candidates. The mentor is a fresh-context reviewer: it dedupes
against existing memory, rejects task-diary noise, routes each candidate to the right home,
and writes the final wording.

**Do not write to `ai/memory/` or to a playbook without this gate.** Working agents are
biased toward memorizing their own struggle; the two-phase commit is what keeps memory sharp.

In tools without subagents, adopt `ai/agents/shared-mentor-agent.md` as a role in a separate
reflection pass, or file candidates tagged `[PROPOSED]`.

If nothing at all was learned you may skip the consult — but say so explicitly in your summary.

## 4. Lessons

What the mentor approves gets written via the `record-lesson` skill, which owns the file
routing, the dated `Learning`/`Action` format, and the dedupe rules.

## 5. Cross-product propagation

Three independent products ship from this repository, and a lesson or fix recorded for one
does not reach the others by itself — agents read `ai/memory/` for the product they are
already working in.

For every behaviour change and every approved lesson, ask: **does this apply to the other two
products?** Interaction patterns and performance fixes count, not only features. Record the
answer in `docs/shared/FEATURE_PARITY.md` — *including* "not applicable, because…" — and file
a task for anything that should be ported. Never port by copying code: each product gets its
own implementation in its own stack (`ai/ROUTING.md`, the separation rule).

An unrecorded "I checked and it does not apply" is indistinguishable from never having looked.

## 6. Refactoring candidates

Saw debt you could not fix in scope — duplication, dead code, pattern violations, oversized
functions? Add a backlog entry to `ai/memory/code_health.md` with file paths and rationale.
**Do not silently drop it.**

Large refactorings (multi-file, cross-module) are not retro side effects. File them and let
`@shared-code-health-agent` schedule them as dedicated tasks.

## 7. Framework drift

If any agent instruction, scope, skill or routing rule was wrong or stale during this task,
fix it now at the canonical source under `ai/` and regenerate what depends on it. Use the
`sync-framework` skill — it owns the regeneration and validation steps.

A stale instruction you noticed and did not fix will cost the next agent the same time it
cost you.

## 8. Playbook

Is this task type likely to recur? Use the `create-playbook` skill to record the efficient
path, or to improve the playbook you followed. Playbooks must get better every time they are
used.

## 9. Hygiene

No scratch files, report dumps, or PR-description drafts staged for commit. Benchmarks belong
in `products/desktop/benchmarks/`, never in the repository root. The `guard-paths` hook blocks
most of these at write time, but check `git status` before you finish.

## Checklist

```
[ ] 1. ./scripts/run_tests.sh passed; skipped gates named in the summary
[ ] 2. REQUIREMENTS.md synced (or: behaviour did not change)
[ ] 3. Reflected; mentor consulted (or: nothing learned, stated explicitly)
[ ] 4. Approved lessons written via record-lesson
[ ] 5. Cross-product propagation evaluated; decision recorded in FEATURE_PARITY.md
[ ] 6. Out-of-scope debt filed in ai/memory/code_health.md
[ ] 7. Framework drift fixed at source and validated
[ ] 8. Playbook created or improved (or: task type will not recur)
[ ] 9. git status clean of scratch artifacts
```

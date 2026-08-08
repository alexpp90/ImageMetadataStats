---
name: record-lesson
description: "Write an approved lesson into ai/memory/ (bolt=performance, palette=UI/a11y, sentinel=security, code_health=debt) in the dated Learning/Action format, after the mandatory shared-mentor-agent gate. Use when a task produced a generalizable lesson worth keeping."
allowed-tools: Read, Grep, Edit
---

# Record a lesson

`ai/memory/` is the project's long-term memory. Its value is inversely proportional to its
size: a small, sharp file gets read; a bloated one gets skipped. Everything here exists to
keep it small and sharp.

## The gate comes first

**Do not write to `ai/memory/` without the `@shared-mentor-agent` consult** described in the
`retrospective` skill, step 3. The working agent proposes; the mentor decides what is
recorded, where, and in what wording.

In a tool without subagents: adopt `ai/agents/shared-mentor-agent.md` as a role in a separate
reflection pass, or write the entry tagged `[PROPOSED]` for a later mentor pass.

`[PROPOSED]` is a fallback for hosts without subagents, and it needs an exit or it silently
becomes a second, unreviewed memory file. **Any mentor consult adjudicates every `[PROPOSED]`
entry it finds in a file it touches**, approving, merging or deleting each one and removing
the tag. A `[PROPOSED]` entry must never reach `main`.

## Which file

| File | Scope |
|---|---|
| `ai/memory/bolt.md` | performance: threading, caching, I/O, image loading, scan throughput |
| `ai/memory/palette.md` | UI and accessibility: layout, theming, contrast, gestures, semantics |
| `ai/memory/sentinel.md` | security and privacy: archives, URLs, user input, OAuth scopes, permissions |
| `ai/memory/code_health.md` | structure and debt — also holds the refactoring backlog |

If a lesson fits two files, it is probably two lessons, or it is too vague.

## Format

Newest entries at the top. Always use the real current date.

```markdown
## YYYY-MM-DD - Short title
**Learning:** What was discovered and why it matters.
**Action:** The concrete rule future agents should follow.
```

`code_health.md` backlog items additionally carry `[OPEN]` / `[DONE]` status and file paths.

## What makes a lesson worth keeping

A lesson is **generalizable**: it changes what a future agent does in a situation that will
recur.

| Keep | Drop |
|---|---|
| "An unknown input to a GitHub Action is a warning, not an error — the fix silently never applied. Check `action.yml` for the tag in use before adding an input." | "The CI run failed and I fixed it." |
| "`ImageTk.PhotoImage` must be constructed on the main thread; load PIL in the worker and convert during `<Configure>`." | "Threading was tricky in this file." |

The **Action** line is the test. If you cannot write a concrete rule, there is no lesson —
there is a task diary, and task diaries are what make memory unreadable.

## Before appending

1. **Skim the target file.** Most candidate lessons duplicate or slightly vary something
   already recorded. Extend the existing entry instead of adding a near-twin.
2. **Check whether it is procedural rather than propositional.** A lesson shaped like "do
   these steps in this order" belongs in a playbook — use the `create-playbook` skill.
3. **Check it is not really a framework fix.** If the lesson is "the agent instructions were
   wrong", fix the instructions via `sync-framework`; do not memorize a workaround for a
   file you could have corrected.

## Consolidation

`@shared-code-health-agent` periodically merges duplicates, deletes lessons invalidated by
code changes, promotes procedure-shaped lessons into playbooks, and prunes stale playbooks.
Write with that pass in mind: one entry, one lesson.

# Agent Instructions

This is the entry point for every AI coding agent working in this repository. It is
deliberately short: the framework itself lives in [`ai/`](ai/README.md), and the product
documentation lives in [`docs/`](docs/README.md).

**Read in this order:**

1. This file — the rules below are non-negotiable and apply to every task.
2. [`ai/ROUTING.md`](ai/ROUTING.md) — identify the target product, then your agent.
3. `ai/agents/<your-agent>.md` — your scope and role.
4. `docs/products/<product>/REQUIREMENTS.md` — what the product you are touching must do.

## The three products

The repository ships **three independent products**. Identifying which one a task targets is
the first action of every task.

| Product | Code | Tech | Target |
|---|---|---|---|
| **Desktop** | `products/desktop/src/photo_selector_toolbox/` | Python + Tkinter | macOS, Linux, Windows |
| **Android Desktop** | `products/android/android-desktop/` (`:android-desktop`) | Kotlin, Compose, Room, OpenCV, Vico | Samsung DeX, tablets ≥ 840 dp |
| **PhotoTok** | `products/android/phototok/` (`:phototok`) | Kotlin, Compose, DataStore | Phones < 600 dp, gesture-first |

They share photographic *concepts* — the EXIF contract, score semantics, what "Selection"
means — and nothing else. The only shared implementation is `products/android/core/` (`:core`), which
holds the EXIF model and readers used by both Android products. Everything else is
independent by design: do not copy code between products, and do not force identical
structures where the platform does not want them.

Canonical names and the mapping to modules and packages: [`docs/GLOSSARY.md`](docs/GLOSSARY.md).

## Rules

1. **Identify the product first, and stay inside it.** Files under `products/desktop/src/` and `products/desktop/tests/` are
   Desktop; `products/android/android-desktop/` is Android Desktop; `products/android/phototok/` is PhotoTok;
   `products/android/core/` affects both Android products and needs both core agents to review.
   Leaking code between products is a defect, not reuse. In Claude Code this is enforced
   mechanically: every product agent carries an `ai/hooks/guard_scope.py` frontmatter hook
   that blocks writes into the other products' source trees.
2. **Mandatory task lifecycle.** Every task, in every tool, starts with the
   [`task-lifecycle`](ai/skills/task-lifecycle/SKILL.md) skill and ends with the
   [`retrospective`](ai/skills/retrospective/SKILL.md) skill (including generating a mandatory Agent Report table in the task summary). This is not optional; in Claude Code and Antigravity a `Stop` hook checks it.
3. **Requirements follow behaviour, in the same commit.** Each product owns
   `docs/products/<product>/REQUIREMENTS.md`; rules holding for more than one product live in
   [`docs/shared/`](docs/shared/). The [`sync-requirements`](ai/skills/sync-requirements/SKILL.md)
   skill decides what counts and where it goes. There is no repository-root `REQUIREMENTS.md`.
4. **Write and run tests for every feature, fix or logic change.** Tests must be executed and
   verify correctness before the task is complete.
5. **Verify against the CI mirror, not a subset.** `./scripts/run_tests.sh` (add `--all` with a
   device attached) reproduces every gate CI enforces; `pytest` and `gradlew testDebugUnitTest`
   do not. Gates reported `⊘ SKIPPED` are accepted risks that must be named in your task
   summary. **Never push a speculative fix and let CI adjudicate it.** Changing a gate in
   `.github/workflows/` obliges you to mirror it in `scripts/run_tests.sh` and
   `docs/build/CI_PARITY.md` in the same commit. Details:
   [`verify-build`](ai/skills/verify-build/SKILL.md).
6. **No scratch files in the repo.** Never commit temporary or working artifacts
   (`scratch*.py`, `pr_desc.txt`, lint/analysis report dumps, debug scripts). Benchmarks belong
   in `products/desktop/benchmarks/`, never in the repository root. Enforced by the
   `guard_paths.py` and `guard_commit.py` hooks, which block the write and the commit.
7. **Single source of truth.** Everything under `ai/` is canonical; `.claude/`, `.gemini/` and
   `.agents/` are symlinks into it and `.gemini/settings.json` is generated. Edit through `ai/`,
   then run [`sync-framework`](ai/skills/sync-framework/SKILL.md) — writes through the mirrored
   directories are blocked.
8. **Memory is mentor-gated.** Lessons go to `ai/memory/` via
   [`record-lesson`](ai/skills/record-lesson/SKILL.md), and only after the
   `@shared-mentor-agent` consult. Recurring task types become playbooks via
   [`create-playbook`](ai/skills/create-playbook/SKILL.md).

## Where things live

Every product owns one directory under `products/`, and every product directory has the
same shape: `src/` for sources, `tests/` for tests, its own build configuration, its own
`README.md`. Nothing product-specific lives at the repository root.

```
products/
  desktop/            Desktop product (Python)      — src/ tests/ benchmarks/ scripts/ pyproject.toml
  android/            The Android platform group    — one Gradle build for both Android products
    android-desktop/  Android Desktop product       — src/ tests/ res/ AndroidManifest.xml
    phototok/         PhotoTok product              — src/ tests/ res/ AndroidManifest.xml
    core/             The only code the two Android products share — src/
docs/                 Product documentation, organised per product  -> docs/README.md
ai/                   Agent framework: routing, agents, skills, hooks, commands,
                      rules, memory -> ai/README.md
scripts/              Cross-product tooling — run_tests.sh (the local CI mirror)
assets/               Shared branding used by the README and the desktop icons
Formula/  Casks/      Homebrew tap definitions — MUST stay at the repository root
```

The Android modules override Gradle's default source-set convention so that
they match the other products: sources in `src/`, unit tests in `tests/unit/`,
instrumented tests in `tests/instrumented/`. The overriding `sourceSets` block is in each
module's `build.gradle.kts` — keep the three copies in sync.

Full framework documentation: [`ai/README.md`](ai/README.md).
Documentation map: [`docs/README.md`](docs/README.md).

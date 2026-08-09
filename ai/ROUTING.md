# Agent Routing

How the coordinator decides who does the work. Read [`README.md`](README.md) first for how the
framework is wired; this file is only about *who owns what*.

## Step 1 — identify the product

This repository ships **three independent products**. Determining which one a task targets is
the first action of every task, before any file is opened.

| Product | Code | Tech | Target | Documentation |
|---|---|---|---|---|
| **Desktop** | `products/desktop/src/photo_selector_toolbox/`, `products/desktop/tests/`, `products/desktop/benchmarks/` | Python + Tkinter | macOS, Linux, Windows workstations | [`docs/products/desktop/`](../docs/products/desktop/) |
| **Android Desktop** | `products/android/android-desktop/` (`:android-desktop`, `com.photoselectortoolbox`) | Kotlin, Compose, Room, OpenCV, Vico | Samsung DeX, tablets ≥ 840 dp, Chromebooks | [`docs/products/android-desktop/`](../docs/products/android-desktop/) |
| **PhotoTok** | `products/android/phototok/` (`:phototok`, `com.phototok`) | Kotlin, Compose, DataStore | Phones < 600 dp, portrait, gesture-first | [`docs/products/phototok/`](../docs/products/phototok/) |

Shared code is deliberately minimal and lives in exactly two places:

| Shared surface | What it is |
|---|---|
| `products/android/core/` (`:core`, `com.photoselector.core`) | The only Kotlin both Android products share: the EXIF model and readers, and storage detection. Admission rule is stated in `products/android/core/build.gradle.kts`. |
| [`docs/shared/`](../docs/shared/) | Requirements and policies that must hold for more than one product. |

Canonical names, slugs and the mapping to Gradle modules and package names:
[`docs/GLOSSARY.md`](../docs/GLOSSARY.md). Use those names in commits, docs and agent output —
"the Android app" is ambiguous and therefore wrong.

**The separation rule.** The three products share photographic *concepts* (the EXIF contract,
score semantics, the meaning of "Selection") and nothing else. They do not share
implementations, layouts or UX models. When a feature is wanted in more than one product, split
it into one independent subtask per product and tailor each to its stack — never force identical
code where it does not fit. Copying a file from one product into another is a defect.

## Step 2 — route to the agent

### Desktop

| Change | Agent |
|---|---|
| Core algorithms, models, EXIF reading, caching, config, CLI, plotting — `products/desktop/src/photo_selector_toolbox/{core,exif,tools}/`, `cli.py` | `@desktop-backend-agent` |
| Tkinter UI, controllers, threading — `products/desktop/src/photo_selector_toolbox/gui/` | `@desktop-gui-agent` |
| Tests and benchmarks — `products/desktop/tests/`, `products/desktop/benchmarks/` | `@desktop-test-agent` |
| Build, packaging, desktop CI — `products/desktop/scripts/` (build tooling), `scripts/run_tests.sh` (the cross-product CI mirror), `.github/workflows/desktop.yml`, `Formula/`, `Casks/`, `products/desktop/pyproject.toml`, `products/desktop/poetry.lock` | `@desktop-build-agent` |

### Android Desktop (`:android-desktop`)

| Change | Agent |
|---|---|
| Compose UI, NavigationRail, comparison layouts, DeX input — `products/android/android-desktop/src/com/photoselectortoolbox/{ui,viewmodel}/` | `@android-desktop-ui-agent` |
| Room cache, OpenCV analysis, repositories, use cases, SAF source — `products/android/android-desktop/src/com/photoselectortoolbox/{data,domain,di}/` | `@android-desktop-core-agent` |

### PhotoTok (`:phototok`)

| Change | Agent |
|---|---|
| Gesture feed, viewer, overlays, bottom sheets — `products/android/phototok/src/com/phototok/{ui,viewmodel}/` | `@phototok-ui-agent` |
| DataStore settings, SAF discovery, pure domain logic — `products/android/phototok/src/com/phototok/{data,domain,di}/` | `@phototok-core-agent` |

### Both Android products

| Change | Agent |
|---|---|
| Gradle files, version catalog, `:core` module, R8/ProGuard, signing, `.github/workflows/android.yml` | `@android-shared-build-agent` |

A change inside `products/android/core/` affects both products by definition. It requires the owning core
agent of **both** products to review, and it must satisfy the admission rule: a file belongs in
`:core` only if it is identical for both products *and would stay identical* if either product
evolved independently.

### Cross-product consultants

| Situation | Agent |
|---|---|
| Photographic science, image-quality metrics, metadata standards, vague requirements | `@shared-photo-researcher-agent` |
| UX flows, ergonomics, wireframes, visual styling (always state the target product) | `@shared-ux-agent` |
| Google Play compliance, OAuth scopes, privacy policy, Impressum, Data Safety, store metadata, anything changing what data the app accesses or transmits | `@shared-publish-agent` |
| Refactoring, tech debt, retrospective follow-ups, framework maintenance | `@shared-code-health-agent` |
| End-of-task reflection and anything to be memorised (`ai/memory/`, playbooks) | `@shared-mentor-agent` — mandatory gate |

## Step 3 — the coordinator's own duties

Routing is this file's job; the procedures below belong to skills, which own their detail.

- **Multi-product tasks:** split into one subtask per product; delegate each separately; do not
  let one product's implementation leak into another's subtask. This is the one duty that is
  purely the coordinator's.
- **Numbers in briefs:** anything a subagent is handed arrives as a premise, not as advice.
  Label every quantity **measured** (name the command and device), **computed** (state the model
  and call it a prediction to check) or **assumed** — and where the subagent can measure cheaply,
  brief the measurement rather than the answer. See `ai/memory/code_health.md` 2026-08-08.
- **Lifecycle:** every delegated subtask starts with `task-lifecycle` and ends with
  `retrospective`.
- **Requirements maintenance:** `sync-requirements`.
- **Verification before finishing:** `verify-build`.
- **Feature parity:** evaluated at the end of every task by the `retrospective` skill, step 5,
  against [`docs/shared/FEATURE_PARITY.md`](../docs/shared/FEATURE_PARITY.md). The coordinator's
  own duty is only to route a *decided* port as one subtask per product.

## Shared skills

Skills live in [`skills/`](skills/) and apply to every product. Each loads when its moment
arrives rather than being read up front.

| Skill | Use when |
|---|---|
| [`task-lifecycle`](skills/task-lifecycle/SKILL.md) | starting any task — **mandatory** |
| [`retrospective`](skills/retrospective/SKILL.md) | before finalising any task that changed files — **mandatory** |
| [`verify-build`](skills/verify-build/SKILL.md) | proving a change passes what CI enforces |
| [`sync-requirements`](skills/sync-requirements/SKILL.md) | behaviour changed and the docs must follow |
| [`record-lesson`](skills/record-lesson/SKILL.md) | writing a mentor-approved lesson to `ai/memory/` |
| [`create-playbook`](skills/create-playbook/SKILL.md) | a task type will recur, or a playbook was followed |
| [`sync-framework`](skills/sync-framework/SKILL.md) | `ai/agents/` or `ai/skills/` was edited |
| [`release-compliance`](skills/release-compliance/SKILL.md) | permissions, endpoints, SDKs, data flow, or a release |
| [`refactoring-guide`](skills/refactoring-guide/SKILL.md) | any refactoring — centralised constants, controller/view separation, thread-pool sizing, image-loading safety, the EXIF data contract, error handling |
| [`playbook-port-pattern-across-products`](skills/playbook-port-pattern-across-products/SKILL.md) | adapting an interaction or performance pattern proven in one product into another |
| [`playbook-verify-android-desktop-on-reference-device`](skills/playbook-verify-android-desktop-on-reference-device/SKILL.md) | running the `:android-desktop` instrumented suite at the 1480×924 dp reference tablet geometry |
| `playbook-*` | a learned procedure matches the task type (template: `skills/playbook-template/`) |

## Commands

Live in [`commands/`](commands/); available as `/name` in Claude Code and as Antigravity
workflows.

| Command | Does |
|---|---|
| `/route` | names the target product, owning agent, requirements sections, memory file and playbook for a path or feature |
| `/verify` | runs the CI mirror and reports failed and skipped gates |
| `/retro` | runs the retrospective against the current diff |
| `/sync-framework` | regenerates `.gemini/settings.json` and validates the framework |

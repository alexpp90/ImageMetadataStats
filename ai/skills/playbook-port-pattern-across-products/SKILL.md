---
name: playbook-port-pattern-across-products
description: "Adapt an interaction, guidance or performance pattern proven in one product into another — Desktop, Android Desktop or PhotoTok. Covers reading the source lesson, grepping the target for the anti-pattern, sequencing the core-then-UI delegation, and the flow-contract trap. Use when a retrospective or the user identifies a pattern worth propagating."
last_validated: 2026-08-08
---

# Playbook: Port a Pattern Across Products

Makes "PhotoTok does X well, Android Desktop should too" a reliable diff instead of a
rewrite. Applies to all three products in both directions.

## When to use

- The `retrospective` skill's step 5 (cross-product propagation) decides a pattern should port.
- A `docs/shared/FEATURE_PARITY.md` § 6 row moves from `⬜ evaluate` to a decision.
- The user says some version of "product A does this better, bring it to product B".

Not for features that need designing from scratch — that is a normal product task. This
playbook is for a pattern that has already been proven somewhere in this repository.

## Steps (the efficient path)

1. **Name the source and the target product, in that order, before opening any code.** Read
   *both* products' `docs/products/<product>/REQUIREMENTS.md`. The port is to the **target's**
   UX model, never the source's implementation: PhotoTok is a gesture-first phone feed, Android
   Desktop is a keyboard-first three-frame comparison on a tablet. A pattern that is right in
   both will look different in each. **Copying a file across products is a defect**
   (`ai/ROUTING.md`, the separation rule) — read the source for its shape, then write the
   target's own version.

2. **Read the source product's `ai/memory/` file, then grep the target for the anti-pattern the
   lesson names — by symbol, not by concept.** This is the step that turns a lesson into a diff,
   and it is where the surprises are. `ai/memory/bolt.md` (2026-07-31) names
   `DocumentFile.listFiles()`; grepping Android Desktop for it found the exact anti-pattern the
   lesson describes, still present a week later, *plus* a per-file `openInputStream` the lesson
   does not cover. Assume the target has drifted further than the lesson describes.

3. **Sequence data/domain before UI, as two separate delegations.** Per `ai/ROUTING.md`, the
   `{data,domain,di}/` agent and the `{ui,viewmodel}/` agent are different specialists with
   enforced scopes. The UI pass cannot start until the core pass's contracts (flow emission
   shape, result types, DI qualifiers) are settled. Hand the UI agent the exact new API
   signatures in its prompt — it should not have to rediscover them.

4. **Give the core pass the pure-logic obligation explicitly.** Pattern ports almost always
   carry index arithmetic, rollback or state transitions. Those belong in `domain/` as
   Android-free, JVM-testable objects, not inside a ViewModel or composable — see
   `ai/memory/code_health.md` (2026-08-07) on `:android-desktop` having no JVM-testable layout
   layer. Adapt the *invariants*, not the source's class: PhotoTok's `OptimisticFeed` carries
   dual filtered/unfiltered lists that Android Desktop does not have.

5. **Update `docs/shared/FEATURE_PARITY.md` § 6** with the pattern row, and both products'
   `REQUIREMENTS.md` if observable behaviour changed in either.

Commands: `./scripts/run_tests.sh --android` after each Android pass (it runs
`assembleDebugAndroidTest`, the only task that compiles instrumented sources), then the full
`./scripts/run_tests.sh` before finishing.

## Traps

- **Changing a flow's emission shape silently breaks every collector.** The single worst trap
  here: making discovery progressive turned two unrelated ViewModels' `.first()` calls into
  "the first 24 photos", compiling clean and failing no test. See `ai/memory/bolt.md`
  (2026-08-08, *Making a Flow Progressive Is a Breaking Change to Every Collector*). **Grep every
  collector of the flow before changing its producer**, and hand the list to the UI pass.
- **The source product's copy is written for the source product's user.** Wording derived from
  settings (`SwipeLabels`, `FirstRunHintText`) must be re-derived from the *target's* settings
  objects, or the port ships a hint describing a gesture the target does not have.
- **Porting the whole set is usually wrong.** PhotoTok raises seven first-run hints because
  every gesture's effect is invisible; Android Desktop's controls are labelled, so only three
  earn their place. Ask what the target's user cannot already see.
- **A guidance overlay must consume the layout's own solver**, not re-derive its geometry —
  `ai/memory/palette.md` (2026-08-08).

## Definition of done

- `docs/shared/FEATURE_PARITY.md` § 6 row updated with the decision and date.
- Both products' `REQUIREMENTS.md` synced where behaviour changed; the source product's
  requirements are **unchanged** unless the port genuinely altered it.
- No file copied between `products/` subtrees — check the diff for identical blocks.
- `./scripts/run_tests.sh` run in full, with every `⊘ SKIPPED` gate named in the summary.

---
Maintenance: every use must either improve this file or bump `last_validated` — see the `create-playbook` skill. `@shared-code-health-agent` prunes playbooks that go stale or reference deleted files.

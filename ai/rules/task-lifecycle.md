# Photo Selector Toolbox — always-on rule

Set this rule's activation to **Always On** in the Antigravity Customizations panel.

Full instructions: `@/AGENTS.md`. Framework: `@/ai/README.md`. Routing: `@/ai/ROUTING.md`.

## Non-negotiable

1. **Identify the product first, and stay inside it.** Three independent products —
   Desktop (`products/desktop/`), Android Desktop (`products/android/android-desktop/`),
   PhotoTok (`products/android/phototok/`). `products/android/core/` affects both Android
   products. Copying code between products is a defect, not reuse.

2. **Start with the `task-lifecycle` skill.** Read the target product's
   `docs/products/<product>/REQUIREMENTS.md`, the matching `ai/memory/` lesson file, the
   owning agent config in `ai/agents/`, and any matching `ai/skills/playbook-*`.

3. **Adopt the owning agent's role.** `ai/ROUTING.md` maps paths to agents; read that agent's
   `ai/agents/*.md` file and work within its stated scope.

4. **Verify with `./scripts/run_tests.sh`**, not a subset. `pytest` and
   `gradlew testDebugUnitTest` miss gates CI enforces. Never push a speculative fix and let
   CI adjudicate it.

5. **Finish with the `retrospective` skill.** Requirements synced, mentor consulted before
   any `ai/memory/` write, debt filed, framework drift fixed, no scratch files committed, and
   an **Agent Report** table included in the final task summary.

6. **Edit canonical files only.** Everything under `ai/` is canonical; `.agents/`, `.claude/`
   and `.gemini/` are symlinks to it. Edit through `ai/`.

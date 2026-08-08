# Shared — Feature Parity & Sync Policy

> How a feature added to one product is evaluated for the other two.
> The at-a-glance matrix lives in the root [`README.md`](../../README.md);
> this file holds the policy and the permanent exclusions.

## Feature Sync Policy

Sync is **bidirectional**. A feature or pattern proven in any of the three products is
evaluated for the other two — Desktop → Android is the common direction, but PhotoTok and
Android Desktop originate work too, and it must travel back. The evaluation is a step of the
`retrospective` skill, not an optional courtesy.

When a new feature is added to any product, it must be evaluated for inclusion in the others:
*   **Tablet/DeX mode:** Should include the feature if technically feasible on Android.
*   **PhotoTok:** Should include the feature if it works well on small screens; may omit with documented rationale.
*   **Excluded features** (Ollama VLM, CLI, ExifTool, SMB paths) are permanently excluded regardless of desktop changes.
*   Feature sync evaluations are documented in the mapping table below, and the resulting
    behaviour in the owning product's `docs/products/<product>/REQUIREMENTS.md`.

## 5. Feature Mapping: Desktop → Android

| Desktop Feature | Android Tablet/DeX | PhotoTok | Notes |
|----------------|-------------------|---------------|-------|
| Photo Selector (review & cull) | ✅ Full | ✅ Simplified | Phone uses swipe gestures instead of prev/next panels |
| Focus Mode (comparison) | ✅ Side-by-side | ❌ Omitted | Not practical on phone screens; tablet gets swipe-between comparison |
| Fullscreen Viewer | ✅ Full + gestures | ✅ Full + gestures | Pinch-to-zoom, swipe to navigate, double-tap zoom |
| Sharpness Analysis | ✅ Full | ✅ Full | Same algorithm, WorkManager for long scans |
| Noise Analysis | ✅ Full | ✅ Full | |
| Highlight/Shadow Clipping | ✅ Full | ✅ Full | |
| Image Library Statistics | ✅ Full charts | ✅ Simplified charts | Phone shows single-column scrollable charts |
| Duplicate Finder | ✅ Full | ✅ Grid view | Phone uses compact grid with batch select |
| Move/Copy to Selection | ✅ Full | ✅ Full | SAF-based folder selection |
| Collection Sorting (RAW/JPEG) | ✅ Full | ✅ Full | |
| Image Grouping (similarity) | ✅ Full | ✅ Time-only default | Phone defaults to fast time+filename grouping |
| Persistent Score Cache | ✅ Room DB | ✅ Room DB | Same 10,000 MRU limit |
| Local AI (Ollama VLM) | ❌ Excluded | ❌ Excluded | Battery/compute constraints |
| CLI | ❌ N/A | ❌ N/A | Android has no CLI equivalent |
| Homebrew Distribution | ❌ N/A | ❌ N/A | Distributed via APK/Play Store |
| SMB Path Resolution | ❌ Excluded | ❌ Excluded | Android handles network shares via SAF providers |
| ExifTool (bundled) | ❌ Excluded | ❌ Excluded | Replaced by AndroidX ExifInterface |

## 6. Pattern Parity: Interaction & Performance

Features are not the only thing that ports. A pattern proven in any product — an interaction
model, a data-access fix, a guidance approach — is evaluated for the other two and the
decision recorded here, including a decision not to port.

Ported means **reimplemented in the target's own stack and UX model**. Copying a file between
products is a defect (`ai/ROUTING.md`, the separation rule).

| Pattern | Source | Desktop | Android Desktop | PhotoTok | Decided |
|---|---|---|---|---|---|
| Progressive SAF enumeration (cursor per directory, batched emission) | PhotoTok 2026-07-31 | ❌ N/A — local filesystem, no binder cost | ✅ ported 2026-08-08 | ✅ origin | 2026-08-08 |
| Optimistic filing + deferred deletion with undo | PhotoTok 2026-07-31 | ◐ partial — async delete only | ✅ ported 2026-08-08 | ✅ origin | 2026-08-08 |
| Coach marks in place, replacing a shortcut list | PhotoTok 2026-07-31 | ❌ solved differently | ✅ ported 2026-08-08 | ✅ origin | 2026-08-08 |
| First-run explanations derived from live settings | PhotoTok 2026-07-24 | ❌ solved differently — log pane | ✅ ported 2026-08-08 | ✅ origin | 2026-08-08 |
| Symmetric queuing of conflicting long passes | Desktop 2026-07-24 | ✅ origin | ✅ ported 2026-08-08 | ❌ N/A — no long passes | 2026-08-08 |
| Neighbour image prefetch | Desktop (`preload_next_candidates`) | ✅ origin | ✅ ported 2026-08-08 | ✅ independent | 2026-08-08 |
| Filing wording names the *configured* Selection folder, never the literal | Android Desktop 2026-08-08 | ◐ gap — buttons and shortcut list say "Move to Selection" while `selection_folder` is configurable; the log lines already print the real path | ✅ origin | ◐ gap — `selection_folder_name` is a setting, wording not checked against it | 2026-08-08 |
| Chrome is priced against the binding axis, and a filmstrip is a column not a bar | Android Desktop 2026-08-08 | ❌ N/A — no filmstrip; the Tk window is resizable and not aspect-bound, so no axis is scarce by construction | ✅ origin | ❌ N/A — one photograph fills a portrait phone; there is no slack on either axis and no filmstrip | 2026-08-08 |
| Chrome that hides its own escape hatch is a one-way door | Android Desktop 2026-08-08 | ⬜ evaluate — panels are toggled from a persistent menu bar, which cannot hide itself | ✅ origin | ⬜ evaluate — overlays are gesture-dismissed, no persistent toggle to strand | 2026-08-08 |
| A background pass merges the field it computed, never the item | Android Desktop 2026-08-08 | ⬜ evaluate — analysis results are written into a dict keyed by path, no list snapshot | ✅ origin | ◐ gap — check `optimistic copy/move` and DataStore reads for the same snapshot-merge shape | 2026-08-08 |
| No second cloud source: SAF already mounts the providers | PhotoTok (policy, `REQUIREMENTS.md` §No Dedicated Cloud Integration) | ❌ N/A — desktop mounts are the OS's job | ✅ ported 2026-08-08 | ✅ origin | 2026-08-08 |

Rationale for the negatives, so a future agent does not re-open a settled question:

- **Escape-hatch rule → PhotoTok / Desktop:** both are `⬜` deliberately. The Android Desktop
  failure needed three ingredients — a toggle that hides a panel, the toggle living *inside*
  that panel, and no keyboard binding for it. Neither sibling obviously has all three, but
  neither has been walked control by control, and asserting "safe" without doing that is the
  unrecorded check this table exists to prevent.
- **Snackbar merge shape → PhotoTok** is flagged `◐` rather than `⬜` because the shape is
  known to exist there: `phototok` does optimistic copy/move against a list it also re-reads
  from discovery. Whether it merges items or fields has not been read. File before closing.
- **Optimistic filing → Desktop** is a genuine gap, not a rejection. `execute_delete` already
  updates the UI first and trashes on a background thread, but `execute_move_to_selection` /
  `execute_copy_to_selection` still call `f.rename` / `shutil.copy2` on the Tk main thread for
  the image and every RAW/JPEG/XMP sibling. Tracked as `[OPEN] 2026-07-24` in
  `ai/memory/code_health.md`; that entry is the work item, this row is the pointer.
- **Coach marks → Desktop:** the discoverability problem is real there but was solved in 2024
  by appending the shortcut to the button text ("Copy to Selection (C)" —
  `ai/memory/palette.md` 2024-05-18). Every Desktop action is a permanently labelled button in
  a visible panel, and Tk has no scrim/overlay idiom that would not fight the window manager.
- **First-run explanations → Desktop:** the log pane already reports the effect of every action
  in words, continuously rather than once, and names the destination path. A one-shot card
  would repeat what the user can already read.
- **Prefetch → PhotoTok:** already present independently (`PhoneModeViewer` enqueues around the
  pager). Listing Android Desktop as the origin in an earlier draft of this table was wrong —
  both siblings had it and only Android Desktop did not, which is precisely the propagation
  failure recorded in `ai/memory/code_health.md` (2026-08-08).

`⬜ evaluate` is the honest state for a pattern nobody has ruled on yet, and it is the point of
the table: an open question is visible here, where an unrecorded one is indistinguishable from
never having looked. A row must not sit at `⬜` across two retrospectives — resolve it or file it.

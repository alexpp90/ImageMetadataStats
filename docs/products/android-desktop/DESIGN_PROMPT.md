# Photo Selector Toolbox — Android Desktop (Tablet / DeX) Design Prompt

Source of truth extracted from this product's `REQUIREMENTS.md`, `ARCHITECTURE.md` and
`products/android/android-desktop/src/com/photoselectortoolbox/ui/`. Where this file and
[`DESIGN.md`](DESIGN.md) disagree, `DESIGN.md` wins.

**How to use this file**

- **Claude Design / any conversational design tool:** paste Part 1 (Master Brief) as the first message, then Part 3 screen by screen.
- **Google Stitch:** paste Part 1 once to set context, then paste one Part 3 block per generation. Stitch works best with a single screen at a time plus explicit device framing — each block already carries its own framing line.

---

# PART 1 — MASTER BRIEF

Paste this first. It is the shared context for every screen.

```
You are designing a visual refresh of "Photo Selector Toolbox", a professional
photo-culling application for Android large-screen devices.

## Product in one sentence
A photographer dumps a shoot folder onto the device, the app analyses every
image for technical quality (sharpness, noise, highlight/shadow clipping, and an
optional on-device AI aesthetic score), and the photographer rapidly compares
neighbouring frames side by side to decide which ones to keep, copy, move, or
delete.

## Who uses it and how
Enthusiast and professional photographers reviewing 200–2000 frames from a
single shoot, mostly bursts of near-identical images. The core loop is:
look at three consecutive frames → decide which is sharpest / best → act →
advance. This loop repeats hundreds of times per session, so every millimetre of
image area and every avoided tap compounds. The user is seated, holding a large
tablet in landscape or working at a desk with a keyboard and mouse.

## Target devices — design for these exact frames
- PRIMARY: Samsung Galaxy Tab S11 Ultra, landscape. ~1480 × 924 dp logical
  (2960 × 1848 px @2x), aspect ratio 16:10.
- Samsung DeX / Chromebook desktop window: resizable, default 1024 × 768 dp,
  minimum 800 × 600 dp. Hardware keyboard and mouse present.
- SECONDARY: tablet portrait, 600–840 dp wide.
- TERTIARY: phone, <600 dp wide (a stripped-down variant; see its own block).

## The content is 4:3 photographs
Almost every image is 4:3 (landscape or portrait orientation). The device is
16:10. This mismatch is the single most important layout fact in this product:
a 4:3 image fitted to a 16:10 frame always leaves empty side columns. Those
columns are where chrome belongs. Chrome must never steal vertical space from
the photograph, and must never overlay the photograph.

## Design principles (non-negotiable)
1. THE PHOTOGRAPH IS THE INTERFACE. Maximise pixel area given to images.
   Chrome lives in the letterbox dead space the aspect-ratio mismatch creates.
2. NO OVERLAYS ON IMAGES. No floating action buttons, no scrims, no controls
   sitting on top of a photo. The only exception is the one-time first-run
   navigation hint. Two interactive controls may never share screen bounds.
3. ONE CONTROL, ONE HOME. Each control belongs to exactly one control group.
   Nothing free-floats between layouts.
4. TOUCH FIRST, KEYBOARD FAST. Every interactive target ≥ 48 dp. Every frequent
   action also has a keyboard shortcut, shown as a subtle key hint on hover.
5. DARK, QUIET, NEUTRAL. The UI must not colour-cast the photographs. Greys and
   a single indigo accent only. No gradients behind or beside images, no
   coloured glows, no translucent blur panels over image areas.
6. NUMBERS MUST BE READABLE. A quality score is never a bare number: it is
   icon + short label + formatted value, and its legend is one tap away.
7. DENSITY WITHOUT CLUTTER. This is a professional tool. Prefer compact
   type and tight spacing over generous consumer padding — but keep touch
   targets full size.

## Visual identity — use these tokens exactly
Dark theme only. Material 3 (`darkColorScheme`). Zinc greys + Indigo accent.

  background / surface     #18181B   (Zinc-900)  base canvas
  surfaceVariant           #27272A   (Zinc-800)  cards, panels, rails
  outline                  #3F3F46   (Zinc-700)  borders, dividers, grid lines
  onSurface                #FAFAFA   (Zinc-50)   primary text
  onSurfaceVariant         #A1A1AA   (Zinc-400)  secondary text, icons at rest
  primary                  #6366F1   (Indigo-500) accent, selection, active nav
  onPrimary                #FFFFFF
  primaryContainer         #4F46E5   (Indigo-600) pressed / hovered accent
  secondary                #A1A1AA   (Zinc-400)

Semantic accents (use sparingly, only for score direction and destructive acts):
  good / pass              #34D399   (Emerald-400)
  warning                  #FBBF24   (Amber-400)
  bad / destructive        #F87171   (Red-400)

Type: Roboto / Inter. Material 3 type scale. Metadata and score chips use
labelSmall–labelMedium (11–13 sp). Filenames use bodyMedium (14 sp) with
middle-ellipsis. Numeric values are tabular-figure so columns of scores align.

Shape: 8 dp corner radius on cards and chips, 12 dp on sheets and dialogs.
Images themselves have 4 dp radius, or 0 dp — never more; rounded photos read
as consumer-app styling.

Elevation: avoid drop shadows. Separate surfaces with the #3F3F46 1 dp outline
and the #18181B / #27272A value step instead. Dark themes read better with
borders than with shadows.

Motion: 150–200 ms, standard easing. Image transitions crossfade only — no
slide, no scale, no parallax. The user is judging sharpness; movement lies.

## Iconography
Material Symbols (Rounded, weight 400). Key icons:
  Selector = photo_camera · Statistics = bar_chart · Duplicates = content_copy
  Settings = settings · Move = drive_file_move · Copy = content_copy
  Delete = delete · Fullscreen = fullscreen · Details = info
  Filmstrip = view_carousel · Layout toggle = view_column / view_agenda
  Sharpness = center_focus_strong · Noise = grain
  Highlight clipping = brightness_high · Shadow clipping = brightness_low
  Aesthetic = auto_awesome

## What the app is NOT
Not a photo editor. Not a gallery. Not a social/consumer app. No filters, no
stickers, no likes, no bottom sheets full of emoji. It is closer to Lightroom's
Library module or Photo Mechanic than to Google Photos.

## Creative latitude
You may rethink layout composition, hierarchy, information density, empty
states, and visual polish. You may NOT change: the dark Zinc/Indigo palette, the
"photograph is the interface" and "no overlays" principles, or the four-
destination navigation model. The three-image comparison view is the heart of
the product — treat it as the hero screen and give it the most design effort.
```

---

# PART 2 — INFORMATION ARCHITECTURE

Paste this alongside Part 1 if the tool accepts long context.

```
## Four top-level destinations (persistent NavigationRail, left edge)
1. Selector    — the culling workspace. Default destination. 95% of session time.
2. Statistics  — EXIF distribution charts for the loaded folder.
3. Duplicates  — byte-identical file finder (SHA-256), with batch delete.
4. Settings    — storage, analysis, display, cache, about.

## Objects the UI shows
IMAGE ITEM
  filename, thumbnail, full-resolution image, orientation (4:3 landscape or
  portrait), position in folder (e.g. "127 / 842"), selection state.

EXIF DATA (loaded asynchronously for current image and its two neighbours)
  Shutter speed (rendered "1/250s" or "2s"), Aperture ("f/2.8"),
  Focal length ("35mm"), 35mm-equivalent focal length, ISO ("ISO 400"),
  Lens name. Any field may be "Unknown". A fallback flag exists when full EXIF
  could not be read — show it as a subtle "limited metadata" marker.

QUALITY SCORES (produced by a scan; any subset may be absent)
  Sharpness           short label "Sharp"  format %.1f   higher is better
  Noise               short label "Noise"  format %.1f   lower is better
  Highlight clipping  short label "Highl"  format %.1f%% lower is better
  Shadow clipping     short label "Shad"   format %.1f%% lower is better
  Aesthetic (beta)    short label "Aesth"  format %.1f   higher is better, 1–10

  RENDERING RULE: a score chip is icon + short label + value. The label may be
  dropped ONLY on thumbnail overlays where space genuinely does not exist.
  Encode direction visually — e.g. a thin bar or dot that fills toward "good" —
  so the user can compare three frames without reading digits. Decimal
  separator is always a period (Locale.US).

## Primary actions on the current image
  Move to Selection · Copy to Selection · Delete · Open Fullscreen
"Selection" is a destination subfolder (default name "Selection", configurable)
created inside the source folder. Deletion goes to the Android trash and is
undoable via a 30-second Snackbar.

## Session-level actions
  Open Folder (system folder picker) ·
  Scan Images (opens scan configuration) · Cancel Scan · Clear Scores ·
  Group Similar Series · Score legend ("What the scan icons mean")

## Persistent state to reflect in the design
  - Chosen comparison layout is remembered across launches.
  - Filmstrip visible/hidden is a user toggle.
  - Photo-details panel visible/hidden is a user toggle.
  - First-run navigation hint shows once, then never again.
```

---

# PART 3 — SCREEN PROMPTS

## 3.1 — HERO SCREEN: Three-Column Comparison (Expanded ≥ 840 dp)

> This is the most important screen in the product. Generate it first and iterate on it most.

```
Design the SELECTOR screen, THREE-COLUMN COMPARISON LAYOUT, for a
1480 × 924 dp landscape tablet (Samsung Galaxy Tab S11 Ultra), dark theme.

## Goal
Show three consecutive photographs — Previous, Current, Next — simultaneously,
each 4:3, each rendered as large as the display physically allows, so the
photographer can judge which of three near-identical frames is the keeper.

## The layout maths — obey this, it drives everything
Three 4:3 images in a row across ~1480 dp of width means each image is width-
constrained, not height-constrained:
    usable width  = 1480 − (nav rail) − (outer padding) − (2 × column gap)
    image width   = usable width / 3        →  roughly 450–470 dp
    image height  = image width × 3/4       →  roughly 340–350 dp
    usable height ≈ 850 dp after system insets

CONSEQUENCE: horizontal pixels are the scarce resource and vertical pixels are
abundant. Therefore:
  - Strip horizontal chrome to the bone. The navigation rail must collapse to
    its narrowest form (72–80 dp) or be hidden entirely in this layout with a
    single menu affordance to bring it back. Outer horizontal padding ≤ 8 dp.
    Column gaps 8 dp. Do not put any side panel, metadata rail, or inspector
    column next to the three images.
  - Spend the leftover vertical space generously: put each image's filename,
    EXIF line, and score chips in a caption block DIRECTLY BELOW its own image,
    not in a shared side panel. Put the action row below that.
  - Every image is exactly the same size. Previous, Current and Next must be
    visually identical in dimensions — the whole point is a fair comparison.
    Never enlarge the current image relative to its neighbours in this layout.

## Column anatomy (identical for all three columns)
  1. Column header: "Previous" / "Current" / "Next" in labelSmall, Zinc-400,
     uppercase-tracking. The CURRENT column's header is Indigo-500.
  2. The image, 4:3, letterboxed inside a Zinc-800 tile with a 1 dp Zinc-700
     border. The CURRENT column's tile gets a 2 dp Indigo-500 border — that
     border is the ONLY thing marking which column is active. No scrim, no
     glow, no dimming of the neighbours. The neighbours must render at full
     brightness or the comparison is worthless.
  3. Filename, bodyMedium, middle-ellipsis, one line.
  4. Compact EXIF line, labelSmall, Zinc-400, dot-separated:
     "1/250s · f/2.8 · 35mm · ISO 400"
  5. Score chip row: up to five chips, wrapping to two lines if needed.
     Each chip = icon + short label + value, on a Zinc-800 pill with a 1 dp
     Zinc-700 border. Include a direction indicator (a 2 dp bar under the chip
     that fills toward "good", tinted emerald→amber→red) so three columns can
     be compared at a glance without reading digits.
  6. Portrait-orientation images: keep the tile footprint identical and pillarbox
     the image inside it. The grid must never reflow when orientation changes.

## Interaction
  - Tapping the Previous or Next column advances the whole triptych by one
    frame. Show a hand cursor on hover (mouse/DeX). The neighbour columns are
    the navigation — there are no arrow buttons over the images.
  - Long-press any image → context menu (Move, Copy, Delete, Info, Fullscreen).

## Action row — below the three columns, one shared row, centred
  A single horizontal group of ≥ 48 dp controls acting on the CURRENT image:
     [Move to Selection] [Copy to Selection] [Delete] | [Fullscreen]
     ... then a divider, then the view controls:
     [Layout toggle: switch to focused view] [Details] [Filmstrip]
  The layout toggle LIVES HERE in this layout — it must not float anywhere
  else. Move/Copy are filled-tonal buttons; Delete is text/outlined with the
  red accent reserved for its icon; the view controls are icon toggle buttons.
  Show keyboard hints (M, C, Del, F) as small Zinc-400 superscript labels.

## Top app bar (compact, ≤ 56 dp)
  Left: folder name + "127 / 842" position counter.
  Right: [Scan Images] [Group Similar Series] [Score legend (info)] [overflow].
  If a scan is running, replace the bar's lower edge with a 2 dp indeterminate
  or determinate Indigo progress line plus an inline "Scanning 412 / 842 · Cancel".

## Filmstrip (collapsible, bottom edge, ~72 dp tall when shown)
  Horizontally scrolling row of thumbnails for the whole folder. Current item
  outlined in Indigo. Each thumbnail may carry ONE tiny score dot; no text.
  Collapsed by default state is remembered.

## Do not
  Do not add a side inspector panel. Do not shrink the neighbour images.
  Do not overlay arrows, buttons or gradients on the photographs. Do not use
  drop shadows. Do not round the image corners more than 4 dp.
```

---

## 3.2 — Selector: Focused (Stacked) Layout — DEFAULT on Expanded/Medium

```
Design the SELECTOR screen, FOCUSED LAYOUT, for a 1480 × 924 dp landscape
tablet, dark theme. This is the DEFAULT comparison layout; the three-column
layout is the alternative, reached via the layout toggle.

## Goal
One large current image with its two neighbours as smaller reference tiles
beneath it — for when the user wants detail on one frame rather than an
even three-way comparison.

## The layout maths — obey this
A 4:3 image fitted into a full-width 16:10 region is HEIGHT-limited and leaves
a wide empty column on each side. Put the controls in those dead columns:
  - LEFT vertical rail, 56 dp wide: Previous button, Next button, and the
    "127 / 842" position counter stacked vertically.
  - RIGHT vertical rail, 56 dp wide: Move, Copy, Delete, Fullscreen, then a
    divider, then Layout toggle, Details toggle, Filmstrip toggle.
  Both rails are flush with the image region's vertical extent. They consume
  ZERO vertical space and never cover the photo.
  Outer padding ≤ 6 dp.

## Vertical budget
  Current image  ≈ 72% of the free height (≈ 80% when the window is short).
  Previous / Next tiles share the remaining height, side by side below the
  current image, each half-width, each 4:3, each labelled "Previous"/"Next"
  with its filename.
  Filmstrip (if shown) sits below that.

## Current image block
  4:3 image in a Zinc-800 tile, 1 dp Zinc-700 border, 4 dp radius.
  Directly beneath it (or in a collapsible details overlay panel that docks
  BELOW the image, never on top of it): filename, full EXIF line, and the
  score chip row with direction bars.

## First-run only
  On the very first launch, show translucent left/right chevron affordances on
  the image edges with a one-line caption "Tap either side to browse". Persist a
  seen-flag and never show them again. This is the ONLY permitted image overlay.

## Empty and loading states
  No folder: centred card, camera icon, "Select a Folder",
  "Select a folder to start reviewing and culling your photos.",
  primary button [Open Folder]. There is no second source — SAF already mounts cloud providers as directories.
  Folder open but unscanned: images visible, score chip rows replaced by a
  single ghost chip reading "Not scanned", with [Scan Images] in the app bar
  visually emphasised.

## Same top app bar and filmstrip as the three-column layout.
## The layout toggle lives in the RIGHT rail here — nowhere else.
```

---

## 3.3 — Fullscreen Viewer

```
Design the FULLSCREEN IMAGE VIEWER for a 1480 × 924 dp landscape tablet, dark.

Pure black or Zinc-900 canvas, image fitted to the window. Chrome auto-hides
after 3 seconds of inactivity and returns on tap or pointer movement.

When chrome is visible:
  - Top: close (X), filename, "127 / 842", and a single-line EXIF summary
    ("1/250s | f/2.8 | 35mm | ISO 400"), all on a minimal Zinc-900 bar at 90%
    opacity — a bar, not a gradient scrim.
  - Bottom (only if "Show Fullscreen Action Buttons" is enabled in Settings):
    [Move to Selection] [Copy to Selection] [Delete], ≥ 48 dp, centred.
  - Score chip row, bottom-left, compact.

Gestures to communicate visually (via a dismissible one-time hint card):
  pinch to zoom · double-tap toggles fit ↔ 100% · horizontal swipe navigates ·
  swipe down dismisses · Escape exits · arrow keys navigate.

When zoomed beyond fit, show a small navigator thumbnail in the bottom-right
corner indicating which part of the frame is visible.
```

---

## 3.4 — Scan Configuration

```
Design the SCAN CONFIGURATION surface. On tablet/DeX render it as a right-side
sheet 400 dp wide (not a centred modal — the user should still see the photos);
on phone, a bottom sheet. Dark theme, Zinc-800 surface, 12 dp radius.

Title: "Scan Configuration"
Section "Analysis Types" — Material 3 switches, each with a name and a one-line
plain-language explanation:
  Sharpness            "Detect focus quality via Laplacian variance"
  Noise Level          "Estimate sensor noise via median absolute deviation"
  Highlight Clipping   "Detect overexposed (blown-out) areas"
  Shadow Clipping      "Detect underexposed (crushed black) areas"
  AI Aesthetic Score (beta)  "On-device aesthetic rating; runs only on sharp images"
    → mark with a "BETA" pill and a small battery-impact note.

Show an estimated-duration line that updates with the selected options,
e.g. "842 images · about 3 min · 612 already cached and will be skipped".

Footer: [Cancel] (text) and [Start Scan] (filled Indigo).
```

---

## 3.5 — Score Legend Sheet

```
Design the SCORE LEGEND sheet, opened from the info icon in the Selector app
bar. Title: "What the scan icons mean".

One row per metric: the actual chip as it appears in the UI, the full display
name, a direction badge ("higher is better" / "lower is better"), and the plain-
language description:

  Sharp  — Sharpness — higher is better
    "Edge contrast in the sharpest part of the frame. Low values usually mean
     motion blur or a missed focus."
  Noise  — Noise — lower is better
    "Estimated sensor noise in flat areas of the image. Rises with high ISO."
  Highl  — Highlight clipping — lower is better
    "Share of pixels blown out to pure white — detail that cannot be recovered."
  Shad   — Shadow clipping — lower is better
    "Share of pixels crushed to pure black — detail that cannot be recovered."
  Aesth  — Aesthetic score — higher is better
    "On-device AI rating of overall appeal, on a 1–10 scale."

Include a small worked example showing three chips side by side with their
direction bars, captioned "Compare the bars, not the numbers."
```

---

## 3.6 — Statistics

```
Design the STATISTICS screen for a 1480 × 924 dp landscape tablet, dark theme.
EXIF distribution charts for the currently loaded folder.

Header summary strip: four stat tiles — Images (count), Lenses (unique count),
Focal Range ("24mm - 200mm"), and one more of your choosing derived from the
data below.

Chart cards, responsive grid, 2–3 per row on Expanded, 1 per row on Compact:
  Focal Length Distribution   (histogram)
  Aperture Distribution       (histogram)
  ISO Distribution            (histogram)
  Shutter Speed Distribution  (histogram)
  Lens Usage                  (horizontal bar / ranked list)

Chart styling: Indigo-500 (#6366F1) bars, Zinc-400 axis labels, Zinc-700 grid
lines, Zinc-800 card background, 1 dp Zinc-700 card border, 8 dp radius, card
title in titleSmall. No legends where a single series makes them redundant.

Empty state: "No Folder Selected" /
"Select a folder containing photos to view EXIF statistics." / [Select Folder].
```

---

## 3.7 — Duplicate Finder

```
Design the DUPLICATE FINDER screen for a 1480 × 924 dp landscape tablet, dark.
Finds byte-identical files by SHA-256 hash and lets the user batch-delete copies.

States to design:
  1. No folder — "No Folder Selected" / "Select a folder to scan for duplicate
     images." / [Select Folder].
  2. Ready — "Ready to Scan", folder name, [Start Scan].
  3. Scanning — determinate progress with file counter and [Cancel].
  4. Results — see below.

Results: a vertical list of duplicate GROUPS. Each group is a card:
  Header: "Group (3 files)" + a [Select All But First] text action.
  Body: a horizontal row of thumbnails, one per file. The first file carries an
  "Original" badge (Indigo outline). Files marked for deletion get a red-tinted
  border, a checked checkbox, and a "Selected for deletion" caption. Below each
  thumbnail: filename, file size, folder path (ellipsised from the left).

Persistent bottom action bar when anything is selected:
  "12 selected"  ............................  [Delete Selected (12)]
Delete opens a confirmation dialog: "Delete Selected Files" /
"Delete 12 file(s)? This action cannot be undone." / [Cancel] [Delete].
```

---

## 3.8 — Settings

```
Design the SETTINGS screen for a 1480 × 924 dp landscape tablet, dark theme.
On Expanded width use a two-pane layout: section list on the left (280 dp),
section content on the right. On Compact, a single scrolling list.

Sections and items (labels are final — use them verbatim):

STORAGE
  Selection Subfolder Name        value "Selection", editable, helper
                                  "Created inside the source folder by default"
  Custom Selection Location       "Default: subfolder in source folder" /
                                  "Using custom folder" when set
  File Sorting                    switch — "Sort RAW and JPEG files into
                                  separate subfolders"

ANALYSIS
  Analysis Threads                slider 1–4, current value shown numerically
  Group Similar Series            switch — "Group photos shot in close succession"
  Grouping Level                  segmented control, 3 options:
    "Time & Filename"        — "Group by capture time and filename similarity"
    "Time + Fast Similarity" — "Group by time with fast perceptual hash comparison"
    "Detailed Similarity"    — "Full similarity analysis (slower, more accurate)"

DISPLAY / FULLSCREEN VIEWER
  Double-Tap Gesture Action       choice: "Move to Selection" / "Copy to Selection"
  Show Fullscreen Action Buttons  switch — "Display delete, copy, and move
                                  buttons in fullscreen mode"

CACHE
  Cached Scores                   "1,204 analysis results stored"
  Clear Cache                     destructive action — "Remove all cached
                                  analysis scores", opens a confirm dialog

ABOUT
  Photo Selector Toolbox · Version 1.4.2
  Source Code — "View on GitHub"

Style: Zinc-800 grouped cards on a Zinc-900 canvas, 1 dp Zinc-700 borders,
section headers in labelLarge Indigo-500, item titles bodyLarge Zinc-50,
supporting text bodySmall Zinc-400, controls right-aligned. Destructive items
use the red accent for their icon and label only.
```

---

## 3.9 — Medium Breakpoint (600–840 dp, tablet portrait)

```
Adapt the SELECTOR screen to a 720 × 1100 dp portrait tablet, dark theme.

  - NavigationRail persists but icon-only, 72 dp.
  - Default to the FOCUSED layout. The three-column layout is still available
    via the toggle but at this width each 4:3 image would be ~200 dp wide — if
    the user selects it, warn nothing, just render it honestly with the same
    equal-thirds rule.
  - In focused layout, the 56 dp side rails still apply; if width falls below
    700 dp, collapse the LEFT rail's controls into the RIGHT rail and rely on
    tapping the Previous/Next tiles for navigation.
  - Metadata and score chips collapse below the current image, and the details
    panel becomes a collapsible expander rather than an always-visible block.
  - Filmstrip remains a horizontal scrolling row.
```

---

## 3.10 — Compact Breakpoint (< 600 dp, phone variant of the Toolbox)

```
Adapt the SELECTOR screen to a 400 × 880 dp phone, dark theme, portrait.

  - BottomNavigation replaces the NavigationRail: Selector, Statistics,
    Duplicates, Settings.
  - Single full-width swipeable image viewer (horizontal pager). No comparison
    layout — it is omitted at this width.
  - Below the image: a single-line filename, then a horizontally scrollable
    score chip row (icons + values; labels may be dropped here).
  - Detailed EXIF is behind a tap-to-expand row, not always visible.
  - Two always-visible quick actions: [Select] and [Delete], full-width,
    ≥ 48 dp.
  - Statistics: single-column scrollable charts.
  - Duplicates: compact grid with checkboxes instead of the detailed group rows.
```

---

# PART 4 — CROSS-CUTTING SPECS

Paste this when asking the tool to produce a component sheet or design-system page.

```
Produce a COMPONENT SHEET for the design system, dark theme, Zinc/Indigo.

1. ScoreChip — five variants (Sharp, Noise, Highl, Shad, Aesth) × three states
   (good, neutral, poor) × two sizes (full = icon+label+value, compact =
   icon+value for thumbnail overlays). Show the direction bar treatment.
2. ScoreChipRow — wrapping row of up to five chips at column width ~450 dp.
3. ImageTile — 4:3 tile with letterbox/pillarbox behaviour, resting state,
   current/active state (2 dp Indigo border), hovered state (Zinc-600 border),
   and loading state (Zinc-800 with a subtle shimmer, no spinner).
4. Vertical control rail — 56 dp wide, icon buttons at 48 dp with 4 dp gaps,
   divider treatment, and a disabled state ("No Previous" / "No Next").
5. Action row buttons — filled-tonal (Move, Copy), outlined destructive
   (Delete), icon toggle (layout, details, filmstrip) in on and off states,
   each with its keyboard-hint superscript.
6. Top app bar — resting, scan-in-progress (with inline progress + Cancel), and
   selection-count variants.
7. Filmstrip thumbnail — resting, current, and marked states, 64 dp tall.
8. Snackbar with Undo — "Moved to Selection" / "Copied to Selection" /
   "1 image deleted", each with a 30 s Undo action and a thin countdown line.
9. Empty-state card — icon, title, one-line body, primary + secondary button.
10. Confirmation dialog — destructive variant.
11. Metadata panel — labelled key/value rows for Shutter Speed, Aperture,
    Focal Length, 35mm Equiv., ISO, Lens; "Unknown" treatment for missing
    fields; a "limited metadata" marker for fallback reads.
12. Keyboard shortcut hint — the small key-cap style used on hover.

Accessibility requirements to reflect:
  - All text ≥ 4.5:1 contrast against its surface; Zinc-400 on Zinc-900 passes,
    Zinc-500 does not — do not go darker than #A1A1AA for body text.
  - Score direction must be conveyed by more than colour (bar length + label).
  - Every icon-only control needs a visible tooltip on hover and a full
    accessibility label carrying name, value and direction.
  - Focus rings: 2 dp Indigo-500 with a 2 dp offset, visible on every
    interactive element for keyboard/DeX navigation.

Keyboard map to document on the sheet:
  ← / →  previous / next          Delete / Backspace  delete (confirm)
  M      move to Selection        C   copy to Selection
  F      fullscreen               Esc exit fullscreen / comparison
  Space  toggle comparison layout
```

---

# PART 5 — QUICK REFERENCE FOR ITERATION

Short follow-up prompts to steer a generated design back on track.

| Problem in output | Correction prompt |
|---|---|
| Controls floating on the photo | "Remove every control that sits on top of an image. Move them into the 56 dp side rails or the action row below." |
| Current image enlarged in 3-column view | "All three images must be identical in size. The active image is marked only by a 2 dp Indigo border." |
| Neighbours dimmed or scrimmed | "Render Previous and Next at full brightness. Dimming defeats the comparison." |
| Images too small in 3-column view | "Reduce horizontal chrome: collapse the nav rail, drop outer padding to 8 dp, remove any side panel. Each image should be roughly one third of the full window width." |
| Consumer-app styling | "This is a professional tool, closer to Lightroom's Library module than Google Photos. Remove gradients, large radii, drop shadows, and decorative colour." |
| Bare numeric scores | "Every score is icon + short label + value, with a direction bar. Never a bare number." |
| Light theme or coloured background | "Dark theme only. Canvas #18181B, panels #27272A. Nothing may colour-cast the photographs." |
| Layout toggle in two places | "The layout toggle appears exactly once, inside the current layout's own control group — the right rail in focused view, the action row in three-column view." |
```

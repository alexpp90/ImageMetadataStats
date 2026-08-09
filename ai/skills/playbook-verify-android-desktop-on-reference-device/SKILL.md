---
name: playbook-verify-android-desktop-on-reference-device
description: "Run the :android-desktop instrumented suite at the reference tablet geometry (1480x924 dp, the Galaxy Tab S11 Ultra in landscape) and read the result honestly: configure the AVD, confirm the rotation, baseline against unmodified HEAD before believing any failure. Use whenever an instrumented test fails, a layout or frame-size change needs proving, or a task touches ui/selector/."
last_validated: 2026-08-08
---

# Playbook: Verify Android Desktop on the Reference Device

`connectedDebugAndroidTest` is the gate nobody runs locally, so it decays to red and then
gets ignored. This is how to run it at the geometry the product is actually designed for and
get an answer you can trust.

## When to use

- An instrumented test fails, or you are about to add one.
- A change touches `products/android/android-desktop/src/com/photoselectortoolbox/ui/selector/`
  — especially frame sizing, chrome placement or any overlay that aligns to the frames.
- Someone reports "the images look small", or a layout figure in
  `docs/products/android-desktop/REQUIREMENTS.md` needs proving.

## The reference geometry

The user's primary device is a **Galaxy Tab S11 Ultra in landscape**: 2960×1848 px at 320 dpi
= **1480×924 dp**. That is the same "reference device" quoted throughout `REQUIREMENTS.md` § 2
and `ui/selector/FrameGeometry.kt`. Any other window size is a different question.

## Steps

```bash
# 1. Pick an AVD (any tablet image; the geometry is overridden below).
~/Library/Android/sdk/emulator/emulator -list-avds

# 2. Boot it, in the background.
~/Library/Android/sdk/emulator/emulator -avd <avd> -no-snapshot-save -no-boot-anim

# 3. Wait for boot rather than sleeping a guess.
until [ "$(adb shell getprop sys.boot_completed 2>/dev/null | tr -d '\r')" = "1" ]; do sleep 5; done

# 4. Force the reference geometry.
adb shell wm size 2960x1848
adb shell wm density 320

# 5. CONFIRM the orientation — do not assume it (see Traps).
adb shell dumpsys window | grep -o "w[0-9]*dp h[0-9]*dp" | head -1
#   must print: w1480dp h924dp     ← width > height, i.e. landscape
#   if it prints w924dp h1480dp:   adb shell settings put system user_rotation 0

# 6. Run. NOTE the gradlew lives under products/android, not the repo root.
cd products/android && ./gradlew :android-desktop:connectedDebugAndroidTest
```

**Expected: 38/38 passing** at this geometry (2026-08-08). A different total means tests were
added or removed — update this number when that happens.

Reading the results without scrolling a wall of Gradle output:

```bash
python3 - <<'PY'
import re, glob
for f in glob.glob('products/android/android-desktop/build/outputs/'
                   'androidTest-results/connected/**/*.xml', recursive=True):
    s = open(f).read()
    print(len(re.findall(r'<testcase ', s)), "tests")
    for m in re.finditer(r'<testcase name="([^"]+)".*?</testcase>', s, re.S):
        if '<failure' in m.group(0):
            print("FAIL:", m.group(1), "|",
                  " ".join(re.sub(r'<[^>]+>', '', m.group(0)).split())[:180])
PY
```

Restore the device afterwards: `adb shell wm size reset && adb shell wm density reset`.

## Traps

- **Confirm the rotation; never infer it.** `user_rotation 1` is *not* "landscape" — it is 90°
  from the AVD's natural orientation, and tablet AVDs are often natively landscape, so `1`
  rotates them **into portrait**. Getting this wrong once produced a "frame is 7 % of the
  window" finding that was pure misconfiguration. Step 5 exists because the dp readout is the
  only trustworthy check.
- **Baseline before believing any failure.** The suite has been red at `HEAD` before, so a
  failure is not evidence until you have run the same subset on unmodified `HEAD`:

  ```bash
  git worktree add /tmp/psb HEAD
  cd /tmp/psb/products/android && ./gradlew :android-desktop:connectedDebugAndroidTest
  # compare, then:  git worktree remove /tmp/psb --force
  ```

  A worktree, not `git stash` — stashing a large change to run a build is a needless risk.
  Compare the two result sets **symmetrically with one parser**; a regex that under-counts one
  side invents or hides a regression.
- **A run at non-reference geometry may say "smaller than the product targets"; it may never be
  read as a defect.** A frame ratio measured on a 1280×800 dp emulator says nothing about the
  product, and the *same* wrong ratio on a second small device is one artefact seen twice, not
  corroboration.
- **Check the fixture's aspect ratio before diagnosing a layout.** `SelectorScreenTest`'s
  default images are 1920×1080 (16:9), and at 16:9 the bottom row is *width*-bound — the frame
  is smaller than a 3:2 frame by geometry, not by a bug. A percentage-of-window assertion
  cannot tell that ceiling from a real leak. See `ai/memory/palette.md` (2026-08-08).
- **Measure before theorising about missing height.** Arithmetic that reasons backwards from a
  frame size to "N dp is being consumed" reproduces whatever the model assumed. A temporary
  instrumented probe printing the real region bounds settles it in minutes — see
  `ai/memory/code_health.md` (2026-08-08) on unmeasured numbers becoming established facts.
- Instrumented sources are only compiled by `assembleDebugAndroidTest`; `./scripts/run_tests.sh`
  runs that, so a compile break is caught without a device. The corollary bites: a green
  `run_tests.sh` is **not** evidence for a layout change, because it never ran a layout
  assertion. Boot the AVD.
- **`emulator -list-avds` may offer a phone image.** `medium_tablet` is the one to pick; a
  phone AVD resolves to the compact layout, where most selector tests early-return and the
  suite goes green without asserting anything. Step 5's dp readout catches this too.

## Definition of done

- The dp readout in step 5 showed `w1480dp h924dp` before the run.
- Every failure was either fixed or shown to be present on unmodified `HEAD`, with the baseline
  command and result quoted in the task summary.
- New assertions derive their expected value from the measured window through
  `FrameGeometry.threeUpLayout`, and any absolute dp floor is gated on the window being
  reference-class — never a bare percentage.
- The emulator geometry was reset.

---
Maintenance: every use must either improve this file or bump `last_validated` — see the `create-playbook` skill. `@shared-code-health-agent` prunes playbooks that go stale or reference deleted files.

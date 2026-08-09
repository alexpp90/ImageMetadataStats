package com.photoselectortoolbox.ui.selector

import androidx.compose.ui.unit.Dp
import androidx.compose.ui.unit.DpSize
import androidx.compose.ui.unit.dp

/**
 * How large the three frames are, and why that is the number it is.
 *
 * ## The one calculation this screen is built on
 *
 * Three equal 4:3 frames have to fit in the window. There are two arrangements
 * that keep them equal, and they are not close:
 *
 * ```
 * three in a row:   3w ≤ W  →  w ≤ 493 dp,  h = 370   (width binds; 554 dp of height wasted)
 * one over two:     2h ≤ H  →  h ≤ 462 dp,  w = 616   (height binds; 124 dp of width spare)
 * ```
 *
 * On a 1480 × 924 dp tablet the row arrangement is width-bound and abandons 60 %
 * of the display's height *by construction* — no amount of trimming chrome
 * fixes it. One over two is height-bound and uses all of it, for 56 % more area
 * per frame before any chrome is considered.
 *
 * The consequence is the layout rule for the whole screen: **height is the
 * scarce axis, width is surplus.** Anything that consumes height costs 2 dp of
 * frame height for every 3 dp it occupies, on all three frames at once. Anything
 * that consumes width, up to the slack, is free. That is why the readouts and
 * the controls flank the current frame instead of stacking above and below it,
 * why the sidebar can afford words, and why there is no app bar.
 *
 * ## Which axis binds depends on the photograph
 *
 * "Height is scarce" is true of the *window*, not of every frame in it. Measured
 * on the reference device at 1480 × 924 dp, with no filmstrip in the vertical
 * stack:
 *
 * ```
 * 4:3   600 × 450   height binds   (2 × 450 + 8 = 908, the whole region)
 * 3:2   675 × 450   height binds   (two abreast need 1358 of 1376 — 18 dp spare)
 * 16:9  684 × 385   WIDTH binds    (two abreast want 1464, only 1376 exists)
 * ```
 *
 * Past 3:2 the bottom row runs out of width before the column runs out of
 * height, and a 16:9 frame caps at 385 dp however much height is freed. That is
 * the ceiling of the display, not a leak, and it is why the height floor below
 * is asserted for 3:2 rather than for whatever happens to be on screen.
 *
 * ## Why this is a solver and not an `aspectRatio` modifier
 *
 * `Modifier.fillMaxHeight().aspectRatio(4f / 3f)` inside a weighted `Row`
 * resolves the *width* constraint first by default, so each tile derives its own
 * height and a wide frame ends up taller than a narrow one. The difference is
 * small enough to survive code review and eyeballing while quietly defeating the
 * comparison the screen exists for — that is the 2026-07-27 lesson in
 * `ai/memory/palette.md`. Computing one [DpSize] here and handing the same value
 * to all three tiles removes the constraint-order question entirely.
 */
object FrameGeometry {

    /** Gap between the two neighbour frames, and between the rows. */
    val Gap: Dp = 8.dp

    /** Padding around the whole image region. */
    val OuterPadding: Dp = 8.dp

    /** Width of the readout block and of the control block flanking the current frame. */
    val FlankWidth: Dp = 388.dp

    /** Minimum width required for flank blocks (readout and control block). */
    val MinimumFlankWidth: Dp = 260.dp

    /**
     * Width of the filmstrip, which is a **vertical** strip down the outer edge
     * of the control flank rather than a bar across the bottom (DESIGN §7.8).
     *
     * The number is a measurement, not a taste. On the reference device a 3:2
     * frame is height-bound at 675 × 450, which leaves each flank 342.5 dp
     * where the control block needs [MinimumFlankWidth] — 82.5 dp of slack. A
     * strip of 72 dp plus the 8 dp [Gap] is 80 dp of that, so the frames do not
     * move at all when the strip is toggled; a unit test asserts exactly that.
     * Anything above 74.5 dp would start taking height off all three frames,
     * because the flank would then push the top row's fit below what the
     * bottom row can carry.
     */
    val FilmstripWidth: Dp = 72.dp

    /**
     * The narrowest the control block may be squeezed: its row of four 48 dp
     * view toggles and the 6 dp gaps between them, plus the block's padding.
     */
    val MinimumControlBlockWidth: Dp = 212.dp

    /**
     * Minimum flank width when the readouts are off but the filmstrip is on.
     *
     * The strip shares the control flank, so with the readouts hidden the flank
     * still has to hold both — otherwise the toggle silently does nothing, or
     * the strip arrives on top of the view toggles. It is width, so on the
     * reference device it is still free; see the class comment.
     */
    val MinimumFilmstripFlankWidth: Dp = MinimumControlBlockWidth + Gap + FilmstripWidth

    /** Width of a neighbour's value overlay. */
    val OverlayWidth: Dp = 148.dp

    /**
     * Free width beside a neighbour at which its values move out of the frame.
     *
     * A measurement rather than a hard-coded choice: on the reference tablet the
     * bottom row leaves 84 dp per side so the values overlay the photograph, but
     * in a wide DeX window or tablet portrait they sit outside it, and the same
     * code decides both.
     */
    val OverlayOutsideThreshold: Dp = OverlayWidth + 8.dp

    /** Standard camera aspect ratio is 3:2; legacy default 4:3; portrait frames are the reciprocal. */
    const val DefaultLandscapeAspect: Float = 1.5f
    const val LandscapeAspect: Float = 4f / 3f
    const val PortraitAspect: Float = 3f / 4f

    /**
     * The size all three frames share, for a region of [regionWidth] ×
     * [regionHeight] and a frame aspect of [aspect].
     *
     * Both constraints are evaluated and the binding one wins — which one that
     * is depends on the window, and assuming either is how this screen broke
     * before. In the maximised state ([rows] = 1, [columns] = 1) the same
     * function gives the single-frame size, so there is one geometry rule for
     * both states rather than two that can disagree.
     */
    fun frameSize(
        regionWidth: Dp,
        regionHeight: Dp,
        aspect: Float = LandscapeAspect,
        rows: Int = 2,
        columns: Int = 2,
    ): DpSize {
        val availableWidth = (regionWidth - Gap * (columns - 1)).coerceAtLeast(0.dp)
        val availableHeight = (regionHeight - Gap * (rows - 1)).coerceAtLeast(0.dp)

        val widthBound = availableWidth / columns
        val heightBound = availableHeight / rows

        // The frame is the smaller of "as wide as the columns allow" and "as
        // wide as the row height allows once the aspect ratio is applied".
        val width = minOf(widthBound, heightBound * aspect)
        val height = width / aspect

        return DpSize(width.coerceAtLeast(0.dp), height.coerceAtLeast(0.dp))
    }

    /**
     * The whole three-up arrangement for one region: one frame size, one flank
     * width, one answer about where the neighbour values go.
     *
     * Extracted because there are now two composables that have to agree about
     * it exactly — the layout itself and the coach-mark overlay, which reserves
     * the real geometry so its callouts land in the slack and never over a
     * frame. Two copies of this arithmetic is an overlay that drifts one dp at a
     * time until it is covering the photographs it was drawn to point at.
     */
    fun threeUpLayout(
        regionWidth: Dp,
        regionHeight: Dp,
        aspect: Float = DefaultLandscapeAspect,
        detailsVisible: Boolean = true,
        filmstripVisible: Boolean = false,
    ): ThreeUpLayout {
        val stripSpace = if (filmstripVisible) FilmstripWidth + Gap else 0.dp

        // A flank is always reserved, even with every panel switched off, because
        // the control block is not optional chrome — it holds the only route back
        // to the details and filmstrip toggles themselves.
        //
        // Returning 0 dp here did not merely hide the controls, it stranded the
        // photographer: no key is bound to the details toggle, so the control that
        // would undo the choice went with the ones it was switched off with. It
        // also un-centred the screen. The current frame is centred *by
        // arithmetic* — flank | frame | flank, all three consuming the region —
        // and with both flanks at zero the row's default `Arrangement.Start` drew
        // the frame hard against the left edge while the neighbour row below,
        // which centres explicitly, stayed put. One collapsed number, and the
        // screen reads as "the picture is on the left and the controls are gone".
        val requestedFlank = if (detailsVisible) {
            MinimumFlankWidth + stripSpace
        } else {
            MinimumControlBlockWidth + stripSpace
        }

        // A flank may never claim more than a quarter of the region, so the two
        // together never claim more than half. Without the cap a window narrow
        // enough that the minima do not fit — tablet portrait at 700 dp, which
        // is still Medium and still gets this layout — resolves to a frame of a
        // few dp, or of none at all, rather than to small frames. Chrome that
        // squeezes the photographs out of existence is the failure this whole
        // file exists to prevent.
        val maxFlank = ((regionWidth - Gap * 2) / 4).coerceAtLeast(0.dp)
        val minFlank = minOf(requestedFlank, maxFlank)

        // The top row must fit the current frame *between* two flanks; the
        // bottom row must fit two frames abreast. The binding one wins — which
        // one that is depends on the window, and assuming either is how this
        // screen broke before.
        val topRowFit = frameSize(
            regionWidth = regionWidth - minFlank * 2 - Gap * 2,
            regionHeight = regionHeight,
            aspect = aspect,
            columns = 1,
            rows = 2,
        )
        val bottomRowFit = frameSize(
            regionWidth = regionWidth,
            regionHeight = regionHeight,
            aspect = aspect,
            columns = 2,
            rows = 2,
        )
        val frame = if (bottomRowFit.width < topRowFit.width) bottomRowFit else topRowFit

        val flankWidth = ((regionWidth - frame.width - Gap * 2) / 2).coerceAtLeast(minFlank)

        // The strip is drawn down the outer edge of the control flank, so what
        // it gets is what the flank has left once the controls have their
        // minimum. On any window this product targets that is the full 72 dp;
        // squeezed below it the strip narrows rather than pushing the controls
        // out of the flank or on top of the photographs.
        val filmstripWidth = if (filmstripVisible) {
            FilmstripWidth.coerceAtMost((flankWidth - MinimumControlBlockWidth - Gap))
                .coerceAtLeast(0.dp)
        } else {
            0.dp
        }

        return ThreeUpLayout(
            frame = frame,
            flankWidth = flankWidth,
            filmstripWidth = filmstripWidth,
            overlayOutside = overlayFitsOutside(regionWidth, frame.width),
        )
    }

    /**
     * The size of a frame filling the whole region, for the maximised state.
     *
     * On the reference tablet this is 1211 × 908 dp against 600 × 450 in
     * three-up — 4.1× the area — which is what "as large as possible" means once
     * the other two frames are off screen.
     */
    fun maximisedFrameSize(
        regionWidth: Dp,
        regionHeight: Dp,
        aspect: Float = LandscapeAspect,
    ): DpSize = frameSize(regionWidth, regionHeight, aspect, rows = 1, columns = 1)

    /**
     * Whether a neighbour's values fit beside its frame rather than on it.
     *
     * [rowWidth] is the full width available to the bottom row and [frameWidth]
     * the width the two frames actually take; what is left over is split between
     * them.
     */
    fun overlayFitsOutside(rowWidth: Dp, frameWidth: Dp): Boolean {
        val leftover = rowWidth - (frameWidth * 2) - Gap
        return leftover / 2 >= OverlayOutsideThreshold
    }

    /**
     * The image region a window of this size must hand to the solver.
     *
     * This is the whole permitted chrome budget, written once:
     *
     * ```
     * width  = window − sidebar 88 − outer padding 8 × 2
     * height = window            − outer padding 8 × 2
     * ```
     *
     * Nothing else may appear in the vertical stack — no app bar, no bottom
     * action row, no horizontal filmstrip (REQUIREMENTS §2). An instrumented
     * test measures the window, calls this, calls [threeUpLayout], and asserts
     * the frames that were actually drawn are the ones that answer implies. Any
     * new chrome above or below the frames therefore fails the build instead of
     * being noticed, two revisions later, as "the images look small".
     *
     * Measured against the reference device on 2026-08-08, with the strip both
     * off and on: window 1480 × 924, region 1392 × 924, frames 675 × 450 at
     * 3:2. The system bars are drawn *through* under `enableEdgeToEdge()` and
     * consume none of it, which is why they do not appear in this arithmetic —
     * the screen pads for the horizontal insets only, and that is a priced
     * decision recorded in [SelectorScreen].
     */
    fun imageRegion(windowWidth: Dp, windowHeight: Dp, sidebarWidth: Dp): DpSize = DpSize(
        (windowWidth - sidebarWidth - OuterPadding * 2).coerceAtLeast(0.dp),
        (windowHeight - OuterPadding * 2).coerceAtLeast(0.dp),
    )

    /**
     * The window height at or above which the reference floor is meaningful.
     *
     * A 1280 × 800 dp CI emulator is simply a smaller window than this product
     * targets; asserting the reference floor there would report a defect that is
     * really "this display is smaller than a Tab S11 Ultra".
     */
    val ReferenceWindowHeight: Dp = 900.dp

    /**
     * The minimum frame height the reference device must produce.
     *
     * Asserted by a UI test, on a reference-class window and for a 3:2 frame —
     * the standard camera ratio, and the one the 450 dp figure in REQUIREMENTS
     * §2 is quoted for. A layout change that quietly reintroduces a top bar, a
     * bottom action row or a full-width filmstrip drops below it, and the point
     * is that it fails the build rather than waiting to be noticed by eye — the
     * previous two revisions of this screen were both shipped with frames far
     * smaller than the display allowed.
     *
     * It is deliberately *not* asserted for every aspect ratio. A 16:9 frame at
     * 1480 × 924 is width-bound at 684 × 385 — two abreast need 1376 dp and that
     * is all there is — so 385 dp is the maximum the display allows, not a
     * shortfall. Confusing the two is what made this look like a height leak.
     */
    val MinimumReferenceFrameHeight: Dp = 440.dp
}

/**
 * One resolved three-up arrangement: the size every frame shares, the width of
 * each flank, and whether a neighbour's values fit beside its frame.
 *
 * Returned as one value rather than computed three times, so the layout and the
 * coach-mark overlay cannot disagree about any of the three.
 */
data class ThreeUpLayout(
    val frame: DpSize,
    val flankWidth: Dp,
    /**
     * Width of the vertical filmstrip inside the control flank, or zero when it
     * is switched off. Part of the solved layout rather than a constant read at
     * the draw site, so the coach-mark overlay reserves the same column the
     * strip is actually drawn in.
     */
    val filmstripWidth: Dp,
    val overlayOutside: Boolean,
)

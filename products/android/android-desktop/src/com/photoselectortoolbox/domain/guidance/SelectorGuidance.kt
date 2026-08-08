package com.photoselectortoolbox.domain.guidance

/**
 * Which slack the one-time explanation card is allowed to occupy.
 *
 * There is exactly one legal answer and one refusal, because there is exactly
 * one place on this screen with room: the flank left of the current frame,
 * under the readout block. Everything else is either a photograph or is already
 * occupied — the bottom centre belongs to the snackbar, which is showing the
 * confirmation of the very action the card is explaining.
 */
enum class HintSlot {
    /** Below the readout block, inside the left flank. */
    READOUT_FLANK,

    /** No slack wide enough; the card is not drawn and the hint stays unspent. */
    NONE,
}

/**
 * When a one-time explanation fires, and where it is allowed to go.
 *
 * These are decisions, not drawing, so they live here rather than as `if`
 * branches inside a composable — the same reason `FrameGeometry` owns the frame
 * arithmetic (`ai/memory/code_health.md`, `[OPEN] 2026-08-07`). Every rule below
 * is a pure function with a JVM test.
 */
object SelectorGuidance {

    /**
     * The hints that are rendered as a card, in the order they are met.
     *
     * Deliberately three, not five. This layout labels its controls, so a hint
     * only earns its place where the *effect* is invisible:
     *
     * - [SelectorHint.FILING] — the photograph left the frame and nothing says
     *   where it went. This is the important one.
     * - [SelectorHint.DELETE_UNDO] — that the deletion is deferred and can be
     *   taken back.
     * - [SelectorHint.MAXIMISE] — that there is a way back to three-up.
     *
     * [SelectorHint.SCORES] is defined and worded but deliberately **not**
     * raised: the scores appear on the frames as they are computed and the
     * Legend item appears in the sidebar at the same moment, so the effect is
     * visible and a card would be explaining something the user is looking at.
     * [SelectorHint.TOUR] is the overlay, not a card.
     */
    val CARD_HINTS: List<SelectorHint> = listOf(
        SelectorHint.FILING,
        SelectorHint.DELETE_UNDO,
        SelectorHint.MAXIMISE,
    )

    /** Narrowest flank that can carry the card without squeezing it into a column of words. */
    const val MIN_CARD_WIDTH_DP: Float = 240f

    /**
     * The hint to show after [candidate] was triggered, or null.
     *
     * A hint already dismissed never returns, and a hint that is not a card
     * hint is never raised as one. A newly triggered hint replaces one still on
     * screen: the user just did something else, and the explanation of what
     * they did most recently is the useful one.
     */
    fun nextHint(
        candidate: SelectorHint,
        seen: Set<SelectorHint>,
        current: SelectorHint?,
    ): SelectorHint? = when {
        candidate !in CARD_HINTS -> current
        candidate in seen -> current
        else -> candidate
    }

    /**
     * The hint that survives a change to the seen set.
     *
     * *Reset guidance* and the persistence of a dismissal both arrive as a new
     * set, and a card whose hint has just been recorded as seen must go with it.
     */
    fun retainPending(current: SelectorHint?, seen: Set<SelectorHint>): SelectorHint? =
        current?.takeIf { it !in seen }

    /**
     * Whether the first-launch guide should open by itself.
     *
     * Gated on there being photographs: an overlay that labels a readout block,
     * three frames and a filmstrip which are not on screen yet is a diagram of
     * somewhere else.
     */
    fun shouldShowTour(seen: Set<SelectorHint>, hasImages: Boolean): Boolean =
        hasImages && SelectorHint.TOUR !in seen

    /**
     * Where the card goes, given the flank the layout resolved.
     *
     * Returns [HintSlot.NONE] rather than falling back to the image region: the
     * card must never cover a frame, so when there is no slack the honest
     * outcome is not to show it — and, because the hint is then not marked seen,
     * to show it the next time there is room.
     */
    fun slotFor(flankWidthDp: Float, detailsVisible: Boolean): HintSlot = when {
        !detailsVisible -> HintSlot.NONE
        flankWidthDp < MIN_CARD_WIDTH_DP -> HintSlot.NONE
        else -> HintSlot.READOUT_FLANK
    }

    /**
     * Whether the card is drawn at all.
     *
     * Suppressed while the coach-mark guide is up: the guide is already
     * explaining this screen, and a card fading in over it would be two
     * explanations of the same thing competing for the same attention.
     */
    fun cardVisible(pending: SelectorHint?, guideOpen: Boolean, slot: HintSlot): Boolean =
        pending != null && !guideOpen && slot != HintSlot.NONE
}

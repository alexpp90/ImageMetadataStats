package com.photoselectortoolbox.domain.curation

/**
 * A deletion the photographer can still take back.
 *
 * The frame is out of the list immediately, but nothing has touched the disk
 * yet — which is what makes the undo trustworthy: reverting is a list insertion,
 * not a hope that the file system will cooperate. The files are removed for real
 * when the window closes, when the next action arrives, or when the screen is
 * left.
 */
data class PendingDeletion(
    /** What was removed, and from where. Ascending by index. */
    val slots: List<ImageSlot>,
    /** When the deletion was applied, in `System.currentTimeMillis()` terms. */
    val requestedAtMillis: Long,
) {
    /** The URIs that must actually be deleted when this is committed. */
    val uris: List<String> get() = slots.map { it.uri }

    /** How much of the undo window is left at [nowMillis]; never negative. */
    fun remainingMillis(nowMillis: Long): Long =
        (requestedAtMillis + DeferredDeletion.UNDO_WINDOW_MILLIS - nowMillis)
            .coerceAtLeast(0L)

    /** Whether the window is still open at [nowMillis]. */
    fun isRevertable(nowMillis: Long): Boolean = remainingMillis(nowMillis) > 0L
}

/**
 * Pure state transitions for the deferred-delete undo window.
 *
 * The selector's snackbar has drawn a 30-second countdown line since the
 * refresh, next to an `onUndo` wired to null, because nothing below the UI could
 * reverse an action (`ai/memory/code_health.md`,
 * `[OPEN] 2026-07-27 - No Repository-Level Undo`). This is the half of that fix
 * that has no Android in it.
 */
object DeferredDeletion {

    /**
     * How long the photographer has to take a deletion back.
     *
     * Declared once, here, because the snackbar's countdown line and the timer
     * that commits the deletion are the same 30 seconds — REQUIREMENTS §2
     * "Action Feedback". Two copies of this number is a countdown that lies.
     */
    const val UNDO_WINDOW_MILLIS = 30_000L

    /**
     * Remove [uris] from the list and hold them pending.
     *
     * Returns null when nothing matched, so a caller cannot end up with an empty
     * pending deletion whose snackbar offers an undo for nothing.
     */
    fun begin(
        state: SelectorListState,
        uris: List<String>,
        nowMillis: Long,
    ): Pair<SelectorListState, PendingDeletion>? {
        val edit = OptimisticEdits.apply(state, CurationAction.DELETE, uris)
        if (edit.slots.isEmpty()) return null
        return edit.state to PendingDeletion(edit.slots, nowMillis)
    }

    /** Remove the frame on screen and hold it pending. */
    fun beginForCurrent(
        state: SelectorListState,
        nowMillis: Long,
    ): Pair<SelectorListState, PendingDeletion>? {
        val uri = state.currentUri ?: return null
        return begin(state, listOf(uri), nowMillis)
    }

    /**
     * Take the deletion back: the frames return to their original slots and the
     * photographer stays on the frame they are looking at.
     *
     * No file operation is involved — that is the entire point of deferring.
     */
    fun revert(
        state: SelectorListState,
        pending: PendingDeletion,
    ): SelectorListState = OptimisticEdits.restore(state, pending.slots)
}

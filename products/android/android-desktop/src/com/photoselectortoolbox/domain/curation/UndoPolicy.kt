package com.photoselectortoolbox.domain.curation

/**
 * What, if anything, can genuinely be undone about an action that has happened.
 *
 * The rule this type exists to enforce: **an UNDO that silently does nothing is
 * worse than no UNDO at all.** The selector snackbar takes `onUndo` from
 * [UndoPolicy], and a null here means the affordance is simply not drawn.
 */
sealed interface UndoableOperation {

    /** The list slots to restore. Restoring the list is always possible. */
    val slots: List<ImageSlot>

    /**
     * A deletion still inside its window. Nothing has been deleted on disk, so
     * undoing is a list insertion and a cancelled timer.
     */
    data class RevertPendingDelete(
        val pending: PendingDeletion,
    ) : UndoableOperation {
        override val slots: List<ImageSlot> get() = pending.slots
    }

    /**
     * A deletion already committed to a backend that trashes rather than
     * destroys (Google Drive). The file comes back out of the trash.
     */
    data class RestoreFromTrash(
        override val slots: List<ImageSlot>,
        val uris: List<String>,
    ) : UndoableOperation

    /**
     * A completed move. The file exists at [destinationUri] and can be moved
     * back into the folder the photographer opened.
     */
    data class ReverseMove(
        override val slots: List<ImageSlot>,
        val sourceUri: String,
        val destinationUri: String,
    ) : UndoableOperation
}

/**
 * Decides whether an action is reversible, and how.
 *
 * Pure and Android-free: the caller supplies the facts (was the delete deferred,
 * does this backend trash, did the move report a destination) and gets back
 * either an operation to run or null.
 */
object UndoPolicy {

    /**
     * Undo for a deletion that is still deferred — nothing on disk has changed
     * yet, which is the strongest form of undo available.
     */
    fun forPendingDelete(pending: PendingDeletion?): UndoableOperation? {
        if (pending == null || pending.slots.isEmpty()) return null
        return UndoableOperation.RevertPendingDelete(pending)
    }

    /**
     * Undo for a deletion that has already been committed to disk.
     *
     * Only offered where the backend trashes rather than destroys. A SAF delete
     * is an unlink with nothing behind it, so this returns null and the snackbar
     * shows no UNDO — the honest outcome.
     */
    fun forCommittedDelete(
        slots: List<ImageSlot>,
        canTrash: Boolean,
    ): UndoableOperation? {
        if (slots.isEmpty() || !canTrash) return null
        return UndoableOperation.RestoreFromTrash(slots, slots.map { it.uri })
    }

    /**
     * Undo for a filing action.
     *
     * - **Move** is reversible when the repository reported where the file went;
     *   without a destination URI the file cannot be found again, so no UNDO.
     * - **Copy** is deliberately *not* offered. Undoing a copy means deleting a
     *   file the photographer just created, and an undo must never be the thing
     *   that destroys data. The original was never touched, so there is nothing
     *   to restore either.
     */
    fun forFiling(
        action: CurationAction,
        slots: List<ImageSlot>,
        sourceUri: String,
        destinationUri: String?,
    ): UndoableOperation? {
        if (action != CurationAction.MOVE) return null
        if (destinationUri == null) return null
        return UndoableOperation.ReverseMove(slots, sourceUri, destinationUri)
    }
}

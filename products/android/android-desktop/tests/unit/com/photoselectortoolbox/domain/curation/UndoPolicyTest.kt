package com.photoselectortoolbox.domain.curation

import com.photoselectortoolbox.data.model.ImageItem
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

/**
 * An UNDO that silently does nothing is worse than no UNDO at all.
 *
 * So the snackbar's `onUndo` is non-null only for the operations this policy
 * says are genuinely reversible, and null everywhere else.
 */
class UndoPolicyTest {

    private val image = ImageItem(
        uri = "content://tree/a.jpg",
        fileName = "a.jpg",
        fileSize = 1L,
        lastModified = 0L,
        mimeType = "image/jpeg",
    )
    private val slots = listOf(ImageSlot(image, 0))

    @Test
    fun `a deferred delete is always reversible`() {
        val pending = PendingDeletion(slots, requestedAtMillis = 0L)

        val undo = UndoPolicy.forPendingDelete(pending)

        assertTrue(undo is UndoableOperation.RevertPendingDelete)
        assertEquals(slots, undo!!.slots)
    }

    @Test
    fun `no pending deletion means no undo`() {
        assertNull(UndoPolicy.forPendingDelete(null))
        assertNull(UndoPolicy.forPendingDelete(PendingDeletion(emptyList(), 0L)))
    }

    @Test
    fun `a committed delete is reversible only where the backend trashes`() {
        val trashed = UndoPolicy.forCommittedDelete(slots, canTrash = true)
        assertTrue(trashed is UndoableOperation.RestoreFromTrash)
        assertEquals(listOf(image.uri), (trashed as UndoableOperation.RestoreFromTrash).uris)

        // A SAF delete is an unlink with nothing behind it. Offer nothing.
        assertNull(UndoPolicy.forCommittedDelete(slots, canTrash = false))
    }

    @Test
    fun `a move is reversible once the repository reports where the file went`() {
        val undo = UndoPolicy.forFiling(
            action = CurationAction.MOVE,
            slots = slots,
            sourceUri = image.uri,
            destinationUri = "content://tree/Selection/a.jpg",
        )

        assertTrue(undo is UndoableOperation.ReverseMove)
        assertEquals("content://tree/Selection/a.jpg", (undo as UndoableOperation.ReverseMove).destinationUri)
    }

    @Test
    fun `a move with no destination uri offers no undo`() {
        // This is exactly what the Boolean-returning repository used to force:
        // the file is somewhere, and nothing below the UI can find it again.
        assertNull(
            UndoPolicy.forFiling(CurationAction.MOVE, slots, image.uri, destinationUri = null),
        )
    }

    @Test
    fun `a copy offers no undo, because undoing it would delete a file`() {
        // The original was never touched, so there is nothing to restore; the
        // only thing an "undo" could do is destroy the copy the photographer
        // just asked for. An undo must never be the destructive action.
        assertNull(
            UndoPolicy.forFiling(
                CurationAction.COPY,
                slots,
                image.uri,
                destinationUri = "content://tree/Selection/a.jpg",
            ),
        )
    }
}

package com.photoselectortoolbox.domain.curation

import com.photoselectortoolbox.data.model.ImageItem
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

/**
 * A delete the photographer can still take back.
 *
 * The selector has drawn a 30-second countdown next to a null `onUndo` since the
 * refresh (`ai/memory/code_health.md`,
 * `[OPEN] 2026-07-27 - No Repository-Level Undo`). These are the list mechanics
 * that make the countdown mean something.
 */
class DeferredDeletionTest {

    private fun image(name: String) = ImageItem(
        uri = "content://tree/$name",
        fileName = name,
        fileSize = 1_000L,
        lastModified = 0L,
        mimeType = "image/jpeg",
    )

    private fun stateOf(vararg names: String, currentIndex: Int = 0) =
        SelectorListState(names.map(::image), currentIndex)

    @Test
    fun `the frame leaves the list at once and the files are held back`() {
        val (state, pending) = DeferredDeletion.beginForCurrent(
            stateOf("a.jpg", "b.jpg", "c.jpg", currentIndex = 1),
            nowMillis = 0L,
        )!!

        assertEquals(listOf("a.jpg", "c.jpg"), state.images.map { it.fileName })
        assertEquals(listOf("content://tree/b.jpg"), pending.uris)
    }

    @Test
    fun `revert puts the frame back in its original slot`() {
        val original = stateOf("a.jpg", "b.jpg", "c.jpg", currentIndex = 1)
        val (afterDelete, pending) = DeferredDeletion.beginForCurrent(original, 0L)!!

        val reverted = DeferredDeletion.revert(afterDelete, pending)

        assertEquals(listOf("a.jpg", "b.jpg", "c.jpg"), reverted.images.map { it.fileName })
        // Still on c.jpg: the frame on screen must not change under the user
        // just because an earlier one came back.
        assertEquals("c.jpg", reverted.images[reverted.currentIndex].fileName)
    }

    @Test
    fun `reverting the last frame in a folder shows it again`() {
        val (afterDelete, pending) = DeferredDeletion.beginForCurrent(stateOf("only.jpg"), 0L)!!
        assertTrue(afterDelete.images.isEmpty())

        val reverted = DeferredDeletion.revert(afterDelete, pending)

        assertEquals(listOf("only.jpg"), reverted.images.map { it.fileName })
        assertEquals(0, reverted.currentIndex)
    }

    @Test
    fun `deleting nothing yields no pending deletion`() {
        assertNull(DeferredDeletion.beginForCurrent(SelectorListState(emptyList(), 0), 0L))
        assertNull(DeferredDeletion.begin(stateOf("a.jpg"), listOf("content://ghost"), 0L))
    }

    @Test
    fun `the undo window is one declared number`() {
        // The snackbar's countdown line and the timer that commits the deletion
        // are the same 30 seconds (REQUIREMENTS §2, "Action Feedback"). Two
        // copies of this constant is a countdown that lies.
        assertEquals(30_000L, DeferredDeletion.UNDO_WINDOW_MILLIS)
    }

    @Test
    fun `the window drains and then closes`() {
        val (_, pending) = DeferredDeletion.beginForCurrent(stateOf("a.jpg"), 1_000L)!!

        assertEquals(30_000L, pending.remainingMillis(1_000L))
        assertEquals(20_000L, pending.remainingMillis(11_000L))
        assertTrue(pending.isRevertable(30_999L))
        assertFalse(pending.isRevertable(31_000L))
        // Never negative: a countdown line reads this as a fraction.
        assertEquals(0L, pending.remainingMillis(99_000L))
    }

    @Test
    fun `several frames deleted together all come back`() {
        val original = stateOf("a.jpg", "b.jpg", "c.jpg", "d.jpg", currentIndex = 3)
        val (afterDelete, pending) = DeferredDeletion.begin(
            original,
            listOf("content://tree/c.jpg", "content://tree/a.jpg"),
            0L,
        )!!
        assertEquals(listOf("b.jpg", "d.jpg"), afterDelete.images.map { it.fileName })

        val reverted = DeferredDeletion.revert(afterDelete, pending)

        assertEquals(
            listOf("a.jpg", "b.jpg", "c.jpg", "d.jpg"),
            reverted.images.map { it.fileName },
        )
        assertEquals("d.jpg", reverted.images[reverted.currentIndex].fileName)
    }
}

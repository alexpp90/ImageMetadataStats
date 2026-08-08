package com.photoselectortoolbox.domain.curation

import com.photoselectortoolbox.data.model.ImageItem
import org.junit.Assert.assertEquals
import org.junit.Assert.assertSame
import org.junit.Assert.assertTrue
import org.junit.Test

/**
 * The list runs ahead of the file system, so the rollback is where the bugs are.
 *
 * Every case here is a rule from the 2026-07-31 entry in `ai/memory/palette.md`
 * ("An Optimistic Action Owns Its Rollback, and the Rollback Must Be Keyed by
 * Identity") applied to this product's single list plus `currentIndex`.
 */
class OptimisticEditsTest {

    private fun image(name: String) = ImageItem(
        uri = "content://tree/$name",
        fileName = name,
        fileSize = 1_000L,
        lastModified = 0L,
        mimeType = "image/jpeg",
    )

    private fun stateOf(vararg names: String, currentIndex: Int = 0) =
        SelectorListState(names.map(::image), currentIndex)

    private fun uriOf(name: String) = "content://tree/$name"

    // ── Optimistic removal ────────────────────────────────────────────────

    @Test
    fun `a move takes the frame out of the list immediately`() {
        val state = stateOf("a.jpg", "b.jpg", "c.jpg", currentIndex = 1)

        val edit = OptimisticEdits.applyToCurrent(state, CurationAction.MOVE)

        assertEquals(listOf("a.jpg", "c.jpg"), edit.state.images.map { it.fileName })
        // The frame that slid up into the freed slot is the one now on screen.
        assertEquals("c.jpg", edit.state.images[edit.state.currentIndex].fileName)
    }

    @Test
    fun `a copy leaves the list alone`() {
        val state = stateOf("a.jpg", "b.jpg", "c.jpg", currentIndex = 1)

        val edit = OptimisticEdits.applyToCurrent(state, CurationAction.COPY)

        assertSame(state, edit.state)
        assertTrue(edit.slots.isEmpty())
    }

    @Test
    fun `removing the last frame steps back rather than off the end`() {
        val state = stateOf("a.jpg", "b.jpg", currentIndex = 1)

        val edit = OptimisticEdits.applyToCurrent(state, CurationAction.MOVE)

        assertEquals(0, edit.state.currentIndex)
        assertEquals("a.jpg", edit.state.images[edit.state.currentIndex].fileName)
    }

    @Test
    fun `removing the only frame leaves an empty list at index zero`() {
        val edit = OptimisticEdits.applyToCurrent(stateOf("only.jpg"), CurationAction.MOVE)

        assertTrue(edit.state.images.isEmpty())
        assertEquals(0, edit.state.currentIndex)
    }

    @Test
    fun `slots record the position the frame was removed from`() {
        val state = stateOf("a.jpg", "b.jpg", "c.jpg", currentIndex = 2)

        val edit = OptimisticEdits.applyToCurrent(state, CurationAction.DELETE)

        assertEquals(listOf(2), edit.slots.map { it.index })
        assertEquals(listOf("c.jpg"), edit.slots.map { it.image.fileName })
    }

    // ── Rollback ──────────────────────────────────────────────────────────

    @Test
    fun `a failed move puts the frame back in its own slot`() {
        val state = stateOf("a.jpg", "b.jpg", "c.jpg", currentIndex = 1)
        val edit = OptimisticEdits.applyToCurrent(state, CurationAction.MOVE)

        val rolledBack = OptimisticEdits.rollback(edit.state, edit)

        assertEquals(
            listOf("a.jpg", "b.jpg", "c.jpg"),
            rolledBack.images.map { it.fileName },
        )
    }

    @Test
    fun `rollback keeps the photographer on the frame they are looking at`() {
        // b is moved; c slides into slot 1 and is now on screen. Restoring b at
        // slot 1 pushes c to slot 2 — the index must follow c, not stay at 1.
        val state = stateOf("a.jpg", "b.jpg", "c.jpg", currentIndex = 1)
        val edit = OptimisticEdits.applyToCurrent(state, CurationAction.MOVE)
        assertEquals("c.jpg", edit.state.images[edit.state.currentIndex].fileName)

        val rolledBack = OptimisticEdits.rollback(edit.state, edit)

        assertEquals("c.jpg", rolledBack.images[rolledBack.currentIndex].fileName)
        assertEquals(2, rolledBack.currentIndex)
    }

    @Test
    fun `a failed copy does not rewind the list`() {
        // The source file never left the folder, so the frame never left the
        // list. Re-inserting here would show the same photograph twice.
        val state = stateOf("a.jpg", "b.jpg", "c.jpg", currentIndex = 1)
        val edit = OptimisticEdits.applyToCurrent(state, CurationAction.COPY)

        val rolledBack = OptimisticEdits.rollback(edit.state, edit)

        assertEquals(listOf("a.jpg", "b.jpg", "c.jpg"), rolledBack.images.map { it.fileName })
        assertEquals(1, rolledBack.currentIndex)
        // And even if a caller hands over slots anyway, copy still rewinds nothing.
        val forced = OptimisticEdits.rollback(
            edit.state,
            CurationAction.COPY,
            OptimisticEdits.slotsOf(state, listOf(uriOf("b.jpg"))),
        )
        assertEquals(3, forced.images.size)
    }

    @Test
    fun `asymmetry is declared on the action, not rediscovered at call sites`() {
        assertTrue(CurationAction.MOVE.rewindsOnFailure)
        assertTrue(CurationAction.DELETE.rewindsOnFailure)
        assertTrue(!CurationAction.COPY.rewindsOnFailure)
    }

    @Test
    fun `several frames are re-inserted in ascending index order`() {
        // Descending insertion would put d.jpg at index 3 of a list that has not
        // regained b.jpg yet, landing it one slot too early.
        val state = stateOf("a.jpg", "b.jpg", "c.jpg", "d.jpg", "e.jpg", currentIndex = 4)
        val edit = OptimisticEdits.apply(
            state,
            CurationAction.MOVE,
            listOf(uriOf("d.jpg"), uriOf("b.jpg")),
        )
        assertEquals(listOf("a.jpg", "c.jpg", "e.jpg"), edit.state.images.map { it.fileName })

        val rolledBack = OptimisticEdits.rollback(edit.state, edit)

        assertEquals(
            listOf("a.jpg", "b.jpg", "c.jpg", "d.jpg", "e.jpg"),
            rolledBack.images.map { it.fileName },
        )
        assertEquals("e.jpg", rolledBack.images[rolledBack.currentIndex].fileName)
    }

    @Test
    fun `rollback into an emptied list shows the restored frame`() {
        val state = stateOf("only.jpg")
        val edit = OptimisticEdits.applyToCurrent(state, CurationAction.MOVE)

        val rolledBack = OptimisticEdits.rollback(edit.state, edit)

        assertEquals(listOf("only.jpg"), rolledBack.images.map { it.fileName })
        assertEquals(0, rolledBack.currentIndex)
    }

    @Test
    fun `restoring a frame that is already present does not duplicate it`() {
        // Belt and braces: a late rollback after the folder was re-discovered
        // must not add a second copy of the same URI.
        val state = stateOf("a.jpg", "b.jpg", currentIndex = 0)
        val slots = OptimisticEdits.slotsOf(state, listOf(uriOf("b.jpg")))

        val restored = OptimisticEdits.restore(state, slots)

        assertEquals(listOf("a.jpg", "b.jpg"), restored.images.map { it.fileName })
    }

    @Test
    fun `slots for unknown uris are dropped rather than faked`() {
        val state = stateOf("a.jpg")

        val slots = OptimisticEdits.slotsOf(state, listOf(uriOf("ghost.jpg")))

        assertTrue(slots.isEmpty())
    }

    // ── Index identity ────────────────────────────────────────────────────

    @Test
    fun `focusedOn re-derives the index from the uri`() {
        val state = stateOf("a.jpg", "b.jpg", "c.jpg", currentIndex = 0)

        assertEquals(2, state.focusedOn(uriOf("c.jpg")).currentIndex)
    }

    @Test
    fun `focusedOn on a vanished uri clamps instead of throwing`() {
        val state = stateOf("a.jpg", "b.jpg", currentIndex = 5)

        assertEquals(1, state.focusedOn(uriOf("ghost.jpg")).currentIndex)
        assertEquals(0, SelectorListState(emptyList(), 3).focusedOn(null).currentIndex)
    }
}

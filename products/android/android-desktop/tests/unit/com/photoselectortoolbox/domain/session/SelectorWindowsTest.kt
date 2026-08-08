package com.photoselectortoolbox.domain.session

import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test

/** The I/O windows around the current frame: what gets read, and in what order. */
class SelectorWindowsTest {

    @Test
    fun `the visible window is the three frames the layout draws`() {
        assertEquals(listOf(5, 6, 4), SelectorWindows.visibleIndices(currentIndex = 5, size = 20))
    }

    @Test
    fun `the visible window clamps at the folder edges rather than wrapping`() {
        assertEquals(listOf(0, 1), SelectorWindows.visibleIndices(currentIndex = 0, size = 20))
        assertEquals(listOf(19, 18), SelectorWindows.visibleIndices(currentIndex = 19, size = 20))
    }

    @Test
    fun `prefetch starts beyond the frames already being decoded`() {
        // Enqueueing the visible three again competes with the decode the user
        // is actually waiting on.
        val prefetch = SelectorWindows.prefetchIndices(currentIndex = 10, size = 100)
        val visible = SelectorWindows.visibleIndices(currentIndex = 10, size = 100)

        assertTrue(prefetch.none { it in visible })
        assertEquals(listOf(12, 8, 13, 7), prefetch)
    }

    @Test
    fun `prefetch is nearest-first and forward-biased`() {
        val prefetch = SelectorWindows.prefetchIndices(currentIndex = 50, size = 100)
        assertEquals(52, prefetch.first())
        assertTrue(prefetch.indexOf(52) < prefetch.indexOf(53))
    }

    @Test
    fun `prefetch stays inside the folder near its start and end`() {
        assertEquals(listOf(2, 3), SelectorWindows.prefetchIndices(currentIndex = 0, size = 4))
        assertEquals(listOf(1, 0), SelectorWindows.prefetchIndices(currentIndex = 3, size = 4))
        assertTrue(SelectorWindows.prefetchIndices(currentIndex = 0, size = 0).isEmpty())
    }

    @Test
    fun `prefetch is bounded, so it cannot compete with the visible decode`() {
        val prefetch = SelectorWindows.prefetchIndices(currentIndex = 500, size = 1000)
        assertEquals(SelectorWindows.PREFETCH_RADIUS * 2, prefetch.size)
    }

    @Test
    fun `the metadata window covers the filmstrip either side`() {
        val window = SelectorWindows.metadataIndices(currentIndex = 40, size = 100)
        assertEquals(SelectorWindows.FILMSTRIP_RADIUS * 2 + 1, window.size)
        assertTrue(window.contains(40 - SelectorWindows.FILMSTRIP_RADIUS))
        assertTrue(window.contains(40 + SelectorWindows.FILMSTRIP_RADIUS))
    }

    @Test
    fun `dimension backfill walks outwards from the current frame`() {
        val order = SelectorWindows.dimensionOrder(currentIndex = 2, size = 5)
        assertEquals(listOf(2, 1, 3, 0, 4), order)
    }

    @Test
    fun `dimension backfill covers every frame exactly once`() {
        val order = SelectorWindows.dimensionOrder(currentIndex = 7, size = 30)
        assertEquals(30, order.size)
        assertEquals(30, order.toSet().size)
        assertEquals((0 until 30).toSet(), order.toSet())
    }

    @Test
    fun `an empty folder asks for nothing`() {
        assertTrue(SelectorWindows.visibleIndices(0, 0).isEmpty())
        assertTrue(SelectorWindows.metadataIndices(0, 0).isEmpty())
        assertTrue(SelectorWindows.dimensionOrder(0, 0).isEmpty())
    }
}

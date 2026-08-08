package com.photoselectortoolbox.domain.session

import com.photoselectortoolbox.data.model.ImageItem
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

/**
 * The merge that keeps a streaming folder from moving under the photographer.
 *
 * Every case here is a failure the naive consumer (`images = batch` on every
 * emission) actually produces.
 */
class ProgressiveMergeTest {

    private fun image(name: String) = ImageItem(
        uri = "content://photos/$name",
        fileName = name,
        fileSize = 1,
        lastModified = 1,
        mimeType = "image/jpeg",
    )

    private fun uris(items: List<ImageItem>) = items.map { it.fileName }

    @Test
    fun `first batch establishes the list and starts at the first frame`() {
        val batch = listOf(image("a"), image("b"), image("c"))

        val result = ProgressiveMerge.append(
            current = emptyList(),
            currentIndex = 0,
            batch = batch,
            published = emptySet(),
            isFirstBatch = true,
        )

        assertEquals(listOf("a", "b", "c"), uris(result.images))
        assertEquals(0, result.currentIndex)
        assertEquals(3, result.added.size)
    }

    @Test
    fun `a later batch appends and leaves the photographer where they are`() {
        // The regression this exists for: `currentIndex = 0` on every emission
        // drags the user back to frame 1 every time another chunk enumerates.
        val first = listOf(image("a"), image("b"), image("c"))
        val cumulative = first + listOf(image("d"), image("e"))

        val result = ProgressiveMerge.append(
            current = first,
            currentIndex = 2,
            batch = cumulative,
            published = first.map { it.uri }.toSet(),
            isFirstBatch = false,
        )

        assertEquals(listOf("a", "b", "c", "d", "e"), uris(result.images))
        assertEquals(2, result.currentIndex)
        assertEquals(listOf("d", "e"), uris(result.added))
    }

    @Test
    fun `a photo the user removed is not resurrected by the next batch`() {
        // Emissions are cumulative, so "b" is in every one of them. It must not
        // come back after being moved to the Selection.
        val discovered = listOf(image("a"), image("b"), image("c"))
        val visible = listOf(image("a"), image("c"))

        val result = ProgressiveMerge.append(
            current = visible,
            currentIndex = 1,
            batch = discovered + image("d"),
            published = discovered.map { it.uri }.toSet(),
            isFirstBatch = false,
        )

        assertEquals(listOf("a", "c", "d"), uris(result.images))
        assertFalse(result.images.any { it.fileName == "b" })
    }

    @Test
    fun `the visible list is never reordered`() {
        // A batch arriving out of alphabetical order still appends. Re-sorting
        // would move photographs out from under someone mid-cull.
        val visible = listOf(image("m"), image("n"))

        val result = ProgressiveMerge.append(
            current = visible,
            currentIndex = 0,
            batch = visible + listOf(image("a"), image("z")),
            published = visible.map { it.uri }.toSet(),
            isFirstBatch = false,
        )

        assertEquals(listOf("m", "n", "a", "z"), uris(result.images))
    }

    @Test
    fun `a batch with nothing new is a no-op`() {
        val visible = listOf(image("a"), image("b"))

        val result = ProgressiveMerge.append(
            current = visible,
            currentIndex = 1,
            batch = visible,
            published = visible.map { it.uri }.toSet(),
            isFirstBatch = false,
        )

        assertTrue(result.isNoOp)
        assertEquals(visible, result.images)
        assertEquals(1, result.currentIndex)
    }

    @Test
    fun `duplicates inside one batch are collapsed`() {
        val result = ProgressiveMerge.newItems(
            batch = listOf(image("a"), image("a"), image("b")),
            published = emptySet(),
        )
        assertEquals(listOf("a", "b"), uris(result))
    }

    @Test
    fun `an index past the end of a shrunken list is coerced, never negative`() {
        val result = ProgressiveMerge.append(
            current = emptyList(),
            currentIndex = 7,
            batch = emptyList(),
            published = setOf("content://photos/a"),
            isFirstBatch = false,
        )
        assertEquals(0, result.currentIndex)
        assertTrue(result.images.isEmpty())
    }
}

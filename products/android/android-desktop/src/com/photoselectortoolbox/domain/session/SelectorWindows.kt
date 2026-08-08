package com.photoselectortoolbox.domain.session

import kotlin.math.abs

/**
 * Which frames around the current one are worth spending I/O on, and in what
 * order.
 *
 * Three different appetites, deliberately different sizes:
 *
 * - **Visible** — the three frames actually drawn (current ± 1). Their
 *   dimensions decide the shared frame size, so they are resolved first and
 *   synchronously with navigation.
 * - **Metadata** — the visible three plus the filmstrip thumbnails either side,
 *   which is what EXIF and dimension backfill target next.
 * - **Prefetch** — frames the photographer is *about* to reach, decoded ahead of
 *   them. Deliberately narrow: every prefetched frame competes for the same Coil
 *   memory cache and the same decode threads as the three the user is looking
 *   at, and a prefetch that slows the visible decode has made things worse.
 *
 * Pure index arithmetic so the ranges are unit-tested rather than eyeballed
 * against a running app.
 */
object SelectorWindows {

    /** The three-up layout draws the current frame and one neighbour each side. */
    const val VISIBLE_RADIUS = 1

    /** Thumbnails either side of the current one that the filmstrip typically shows. */
    const val FILMSTRIP_RADIUS = 8

    /**
     * How far *beyond* the visible three to warm frames.
     *
     * Two each way: four extra decodes at roughly 5 MB apiece against the three
     * visible frames' ~15 MB, inside a memory cache sized at 30 % of app memory
     * (see `PhotoSelectorApp`). Wider starts evicting a neighbour between two
     * comparisons of the same pair, which is the one thing this screen must
     * never do.
     */
    const val PREFETCH_RADIUS = 2

    /** The frames on screen, nearest first. */
    fun visibleIndices(currentIndex: Int, size: Int): List<Int> =
        radiusAround(currentIndex, size, VISIBLE_RADIUS)

    /** The visible frames plus the filmstrip's neighbourhood, nearest first. */
    fun metadataIndices(currentIndex: Int, size: Int): List<Int> =
        radiusAround(currentIndex, size, FILMSTRIP_RADIUS)

    /**
     * The frames to warm, nearest first and forward-biased at equal distance.
     *
     * Excludes the visible three: those are being decoded for display already,
     * and enqueueing them again only competes with that decode.
     */
    fun prefetchIndices(currentIndex: Int, size: Int): List<Int> {
        if (size <= 0) return emptyList()
        val result = ArrayList<Int>(PREFETCH_RADIUS * 2)
        for (distance in (VISIBLE_RADIUS + 1)..(VISIBLE_RADIUS + PREFETCH_RADIUS)) {
            val forward = currentIndex + distance
            if (forward in 0 until size) result += forward
            val backward = currentIndex - distance
            if (backward in 0 until size) result += backward
        }
        return result
    }

    /**
     * Every frame, nearest to [currentIndex] first — the order dimension
     * backfill walks the folder in, so the photographs closest to the
     * photographer stop being 3:2 guesses first.
     */
    fun dimensionOrder(currentIndex: Int, size: Int): List<Int> {
        if (size <= 0) return emptyList()
        return (0 until size).sortedWith(
            compareBy({ abs(it - currentIndex) }, { it })
        )
    }

    private fun radiusAround(currentIndex: Int, size: Int, radius: Int): List<Int> {
        if (size <= 0) return emptyList()
        val result = ArrayList<Int>(radius * 2 + 1)
        if (currentIndex in 0 until size) result += currentIndex
        for (distance in 1..radius) {
            val forward = currentIndex + distance
            if (forward in 0 until size) result += forward
            val backward = currentIndex - distance
            if (backward in 0 until size) result += backward
        }
        return result
    }
}

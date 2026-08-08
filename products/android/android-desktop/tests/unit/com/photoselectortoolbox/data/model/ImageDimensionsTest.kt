package com.photoselectortoolbox.data.model

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

/**
 * Unknown dimensions are a state the app spends real time in, now that headers
 * are read after enumeration rather than during it. They must therefore be safe
 * rather than exceptional.
 */
class ImageDimensionsTest {

    @Test
    fun `a 3 by 2 camera frame reports its ratio`() {
        val dimensions = ImageDimensions.of(6192, 4128)

        assertTrue(dimensions.isKnown)
        assertTrue(dimensions.isLandscape)
        assertEquals(1.5f, dimensions.aspectRatio!!, 1e-4f)
    }

    @Test
    fun `unknown dimensions have no ratio, so the caller can default`() {
        // Null is what selects FrameGeometry.DefaultLandscapeAspect (3:2). A
        // zero or a 1.0 here would silently draw every unmeasured frame square.
        assertNull(ImageDimensions.UNKNOWN.aspectRatio)
        assertFalse(ImageDimensions.UNKNOWN.isKnown)
        assertFalse(ImageDimensions.UNKNOWN.isLandscape)
    }

    @Test
    fun `an unreadable header collapses to unknown`() {
        // BitmapFactory reports -1 for a file it cannot parse.
        assertEquals(ImageDimensions.UNKNOWN, ImageDimensions.of(-1, -1))
        assertEquals(ImageDimensions.UNKNOWN, ImageDimensions.of(4000, 0))
        assertEquals(ImageDimensions.UNKNOWN, ImageDimensions.of(0, 3000))
    }

    @Test
    fun `a portrait frame is not landscape`() {
        val portrait = ImageDimensions.of(4128, 6192)

        assertFalse(portrait.isLandscape)
        assertEquals(2f / 3f, portrait.aspectRatio!!, 1e-4f)
    }
}

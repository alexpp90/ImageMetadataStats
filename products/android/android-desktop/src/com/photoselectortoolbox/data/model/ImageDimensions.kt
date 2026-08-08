package com.photoselectortoolbox.data.model

/**
 * The pixel size of one image, or the explicit statement that it is not known yet.
 *
 * Dimensions used to be read during folder enumeration, which meant opening and
 * header-decoding every photograph before the first one could be shown. They are
 * now resolved separately and lazily (see
 * [com.photoselectortoolbox.data.source.LocalImageSource.resolveDimensions]), so
 * "not known yet" is a state the app spends real time in rather than an error.
 *
 * That is why [UNKNOWN] is a first-class value and [aspectRatio] is nullable:
 * the selector's frame solver defaults to 3:2 until the true ratio arrives
 * (`FrameGeometry.DefaultLandscapeAspect`), and a null here is what selects that
 * default. Absent dimensions must never block a frame from being drawn.
 */
data class ImageDimensions(
    val width: Int,
    val height: Int,
) {
    /** True once both edges are positive — i.e. an actual header was read. */
    val isKnown: Boolean
        get() = width > 0 && height > 0

    /** Width / height, or null while the dimensions are still unknown. */
    val aspectRatio: Float?
        get() = if (isKnown) width.toFloat() / height.toFloat() else null

    /** True when the image is wider than it is tall. Meaningless while unknown. */
    val isLandscape: Boolean
        get() = isKnown && width > height

    companion object {
        /** Not read yet, or unreadable. Both are the same thing to a caller. */
        val UNKNOWN = ImageDimensions(0, 0)

        /**
         * Coerce a raw decode result. Negative values (what `BitmapFactory`
         * reports for a file it cannot parse) collapse to [UNKNOWN] so callers
         * never see a nonsensical ratio.
         */
        fun of(width: Int, height: Int): ImageDimensions =
            if (width > 0 && height > 0) ImageDimensions(width, height) else UNKNOWN
    }
}

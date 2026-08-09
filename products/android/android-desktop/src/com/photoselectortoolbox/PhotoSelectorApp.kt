package com.photoselectortoolbox

import android.app.Application
import android.util.Log
import coil.Coil
import coil.ImageLoader
import coil.disk.DiskCache
import coil.memory.MemoryCache
import dagger.hilt.android.HiltAndroidApp
import org.opencv.android.OpenCVLoader

@HiltAndroidApp
class PhotoSelectorApp : Application() {

    companion object {
        private const val TAG = "PhotoSelectorApp"
    }

    override fun onCreate() {
        super.onCreate()
        initOpenCV()
        initCoil()
    }

    private fun initOpenCV() {
        if (OpenCVLoader.initLocal()) {
            Log.i(TAG, "OpenCV loaded successfully")
        } else {
            Log.e(TAG, "OpenCV initialization failed")
        }
    }

    /**
     * Configure Coil for a screen that holds three large frames at once.
     *
     * The numbers are derived from what this app actually draws, not picked:
     *
     * - Three equal frames of up to 675×450dp render at ~1350×900px on a 2×
     *   density tablet — about 4.9 MB each in `ARGB_8888`, so ~15 MB just for
     *   what is on screen.
     * - A maximised frame is 1211×908dp ≈ 2422×1816px ≈ 17.6 MB on its own.
     * - Neighbour prefetch means several more frames either side are decoded
     *   ahead of the photographer, who typically scrubs back and forth over the
     *   same burst.
     *
     * 30 % of the app's available memory gives roughly 75 MB on a 256 MB heap —
     * enough for the visible three, a maximised frame and a prefetch window,
     * while leaving headroom for the OpenCV analysis bitmaps (2048px, decoded on
     * the analysis path and released immediately). Higher would start competing
     * with the scan; lower would evict a neighbour between two comparisons of
     * the same pair, which is the one thing this screen must never do.
     *
     * The disk cache holds Coil's *decoded, downsampled* frames, which is a
     * different thing from the originals: a 45 MP RAW re-read and re-downsampled
     * costs far more than reading back the 1350x900 result, and a culling
     * session scrubs over the same frames repeatedly. 512 MB holds a full
     * session's worth. Source images are immutable once written, so cache
     * headers are ignored rather than re-validated.
     */
    private fun initCoil() {
        val imageLoader = ImageLoader.Builder(this)
            .memoryCache {
                MemoryCache.Builder(this)
                    .maxSizePercent(0.30)
                    .build()
            }
            .diskCache {
                DiskCache.Builder()
                    .directory(cacheDir.resolve("image_cache"))
                    .maxSizeBytes(512L * 1024 * 1024)
                    .build()
            }
            .respectCacheHeaders(false)
            .build()
        Coil.setImageLoader(imageLoader)
    }
}

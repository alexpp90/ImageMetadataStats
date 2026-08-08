package com.photoselectortoolbox.domain.usecase

import android.content.Context
import android.net.Uri
import androidx.documentfile.provider.DocumentFile
import com.photoselectortoolbox.data.model.ImageItem
import com.photoselectortoolbox.data.repository.FileOperationResult
import com.photoselectortoolbox.data.repository.ImageRepository
import dagger.hilt.android.qualifiers.ApplicationContext
import javax.inject.Inject
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.async
import kotlinx.coroutines.awaitAll
import kotlinx.coroutines.ensureActive
import kotlinx.coroutines.withContext

/**
 * Result of a move/copy operation for a single image.
 *
 * This was the first result shape in the product to carry the destination URI,
 * and it is now *the* shape: [ImageRepository.moveImage]/`copyImage` return the
 * same type instead of a `Boolean` that discarded where the file went. Kept as
 * an alias rather than a second data class so there is one result to reason
 * about, and so existing call sites and tests are untouched.
 */
typealias MoveResult = FileOperationResult

/**
 * Handles moving or copying images into a Selection folder structure.
 * Organizes files into subfolders by type:
 * - RAW files -> "RAW" subfolder
 * - JPEG files -> "JPEG" subfolder
 * - XMP sidecars follow their parent image's subfolder
 * - Lightroom edit files (*-Edit.*) -> "RAW" subfolder
 */
class MoveToSelectionUseCase @Inject constructor(
    @ApplicationContext private val context: Context
) {

    companion object {
        private const val SELECTION_FOLDER_NAME = "Selection"
        private const val RAW_SUBFOLDER = "RAW"
        private const val JPEG_SUBFOLDER = "JPEG"

        private val RAW_EXTENSIONS = setOf(
            "arw", "cr2", "cr3", "nef", "nrw", "orf", "raf", "rw2",
            "pef", "srw", "dng", "raw", "3fr", "ari", "bay", "cap",
            "iiq", "eip", "erf", "fff", "mef", "mdc", "mos", "mrw",
            "obm", "ptx", "pxn", "rwl", "rwz", "sr2", "srf", "x3f"
        )

        private val JPEG_EXTENSIONS = setOf("jpg", "jpeg")

        private const val XMP_EXTENSION = "xmp"
        private const val EDIT_SUFFIX = "-Edit"
    }

    /**
     * Move or copy a list of images to the Selection folder within the given
     * parent directory.
     *
     * @param images The images to move/copy.
     * @param parentDirUri The URI of the parent directory where "Selection" will be created.
     * @param copy If true, copy files instead of moving.
     * @return List of results for each image operation.
     */
    suspend fun invoke(
        images: List<ImageItem>,
        parentDirUri: Uri,
        copy: Boolean = false
    ): List<MoveResult> = withContext(Dispatchers.IO) {
        val parentDir = DocumentFile.fromTreeUri(context, parentDirUri)
            ?: return@withContext images.map { image ->
                MoveResult(image.uri, null, false, "Cannot access parent directory")
            }

        // Create or get Selection folder
        val selectionDir = parentDir.findFile(SELECTION_FOLDER_NAME)
            ?: parentDir.createDirectory(SELECTION_FOLDER_NAME)
            ?: return@withContext images.map { image ->
                MoveResult(image.uri, null, false, "Cannot create Selection folder")
            }

        // Create subfolders
        val rawDir = selectionDir.findFile(RAW_SUBFOLDER)
            ?: selectionDir.createDirectory(RAW_SUBFOLDER)
        val jpegDir = selectionDir.findFile(JPEG_SUBFOLDER)
            ?: selectionDir.createDirectory(JPEG_SUBFOLDER)

        val results = images.map { image ->
            async {
                ensureActive()
                processImage(image, selectionDir, rawDir, jpegDir, copy)
            }
        }.awaitAll()

        results
    }

    /**
     * Process a single image: determine its target subfolder and copy/move it.
     */
    private suspend fun processImage(
        image: ImageItem,
        selectionDir: DocumentFile,
        rawDir: DocumentFile?,
        jpegDir: DocumentFile?,
        copy: Boolean
    ): MoveResult = withContext(Dispatchers.IO) {
        try {
            val targetDir = determineTargetFolder(image.fileName, selectionDir, rawDir, jpegDir)
                ?: return@withContext MoveResult(image.uri, null, false, "Cannot determine target folder")

            val sourceUri = Uri.parse(image.uri)
            val mimeType = image.mimeType ?: "application/octet-stream"

            // Create destination file
            val destFile = targetDir.createFile(mimeType, image.fileName)
                ?: return@withContext MoveResult(image.uri, null, false, "Cannot create destination file")

            // Copy content
            context.contentResolver.openInputStream(sourceUri)?.use { input ->
                context.contentResolver.openOutputStream(destFile.uri)?.use { output ->
                    input.copyTo(output)
                }
            } ?: return@withContext MoveResult(image.uri, null, false, "Cannot read source file")

            // If moving (not copying), delete the source
            if (!copy) {
                try {
                    val sourceDoc = DocumentFile.fromSingleUri(context, sourceUri)
                    sourceDoc?.delete()
                } catch (e: Exception) {
                    // Source deletion failure is non-fatal for the copy operation
                }
            }

            MoveResult(
                sourceUri = image.uri,
                destinationUri = destFile.uri.toString(),
                success = true
            )
        } catch (e: Exception) {
            MoveResult(image.uri, null, false, e.message)
        }
    }

    /**
     * Determine which subfolder an image belongs in based on its filename and extension.
     *
     * Rules:
     * - RAW extensions -> RAW subfolder
     * - JPEG extensions -> JPEG subfolder
     * - Lightroom edit files (*-Edit.*) -> RAW subfolder
     * - XMP sidecars -> follow their parent image's subfolder
     * - Everything else -> Selection root
     */
    private fun determineTargetFolder(
        fileName: String,
        selectionDir: DocumentFile,
        rawDir: DocumentFile?,
        jpegDir: DocumentFile?
    ): DocumentFile? {
        val extension = fileName.substringAfterLast('.', "").lowercase()
        val stem = fileName.substringBeforeLast('.')

        return when {
            // Lightroom edit files (*-Edit.tif, *-Edit.jpg, etc.) go to RAW subfolder
            stem.endsWith(EDIT_SUFFIX) -> rawDir ?: selectionDir

            // RAW files go to RAW subfolder
            extension in RAW_EXTENSIONS -> rawDir ?: selectionDir

            // JPEG files go to JPEG subfolder
            extension in JPEG_EXTENSIONS -> jpegDir ?: selectionDir

            // XMP sidecar files follow their parent image
            extension == XMP_EXTENSION -> {
                // XMP sidecar name matches parent: "IMG_001.ARW" -> "IMG_001.xmp"
                // Check if the parent would be a RAW file
                val parentExtension = guessParentExtension(stem)
                if (parentExtension != null && parentExtension.lowercase() in RAW_EXTENSIONS) {
                    rawDir ?: selectionDir
                } else {
                    // Default XMP to selection root if parent type is unknown
                    selectionDir
                }
            }

            // Everything else goes to Selection root
            else -> selectionDir
        }
    }

    /**
     * For an XMP sidecar, try to guess the parent file's extension.
     * Some XMP filenames include the parent extension: "IMG_001.ARW.xmp"
     * In that case the stem is "IMG_001.ARW" and we can extract "ARW".
     */
    private fun guessParentExtension(xmpStem: String): String? {
        val dotIndex = xmpStem.lastIndexOf('.')
        return if (dotIndex > 0) {
            xmpStem.substring(dotIndex + 1)
        } else {
            null
        }
    }
}

package com.photoselectortoolbox.data.repository

import android.content.Context
import android.net.Uri
import android.util.Log
import androidx.documentfile.provider.DocumentFile
import com.photoselector.core.model.ExifData
import com.photoselector.core.reader.AndroidExifReader
import com.photoselector.core.reader.MediaStoreReader
import com.photoselectortoolbox.data.model.ImageDimensions
import com.photoselectortoolbox.data.model.ImageItem
import com.photoselectortoolbox.data.source.LocalImageSource
import com.photoselectortoolbox.data.source.googledrive.GoogleDriveClient
import com.photoselectortoolbox.data.source.googledrive.GoogleDriveImageSource
import javax.inject.Inject
import javax.inject.Singleton
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.ensureActive
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.lastOrNull
import kotlinx.coroutines.withContext

@Singleton
class ImageRepositoryImpl @Inject constructor(
    private val localImageSource: LocalImageSource,
    private val androidExifReader: AndroidExifReader,
    private val mediaStoreReader: MediaStoreReader,
    private val driveImageSource: GoogleDriveImageSource,
    private val driveClient: GoogleDriveClient,
) : ImageRepository {

    companion object {
        private const val TAG = "ImageRepositoryImpl"
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

    override fun discoverImages(folderUri: Uri): Flow<List<ImageItem>> {
        if (GoogleDriveImageSource.isDriveUri(folderUri)) {
            val folderId = GoogleDriveImageSource.extractId(folderUri) ?: return localImageSource.discoverImages(folderUri)
            return driveImageSource.discoverImages(folderId)
        }
        return localImageSource.discoverImages(folderUri)
    }

    /**
     * The last emission is the complete folder by contract, so collecting to it
     * is the whole implementation — and it keeps the "progressive discovery
     * exists" knowledge in one place rather than at each one-shot call site.
     */
    override suspend fun discoverAllImages(folderUri: Uri): List<ImageItem> =
        withContext(Dispatchers.IO) { discoverImages(folderUri).lastOrNull().orEmpty() }

    override suspend fun getExifData(context: Context, uri: Uri): ExifData? {
        // For Drive URIs, download to cache first then read EXIF from local file
        if (GoogleDriveImageSource.isDriveUri(uri)) {
            val fileId = GoogleDriveImageSource.extractId(uri) ?: return null
            val cached = driveImageSource.ensureCached(fileId, fileId)
                ?: return null
            val localUri = Uri.fromFile(cached)
            return androidExifReader.readExif(context, localUri)
        }

        // Try the primary ExifInterface reader first
        val exifData = androidExifReader.readExif(context, uri)
        if (exifData != null) return exifData

        // Fall back to MediaStore reader
        return mediaStoreReader.readExif(context, uri)
    }

    override fun canTrash(uri: Uri): Boolean =
        GoogleDriveImageSource.isDriveUri(uri)

    /**
     * Untrash a Drive file. SAF deletes are unlinks with no trash behind them,
     * so for a local URI this returns false and the UI offers no UNDO — which is
     * the honest answer, and better than an UNDO that silently does nothing.
     */
    override suspend fun restoreFromTrash(context: Context, uri: Uri): Boolean =
        withContext(Dispatchers.IO) {
            if (!GoogleDriveImageSource.isDriveUri(uri)) return@withContext false
            val fileId = GoogleDriveImageSource.extractId(uri) ?: return@withContext false
            driveClient.untrashFile(fileId)
        }

    override suspend fun deleteImage(context: Context, uri: Uri): Boolean =
        withContext(Dispatchers.IO) {
            if (GoogleDriveImageSource.isDriveUri(uri)) {
                val fileId = GoogleDriveImageSource.extractId(uri) ?: return@withContext false
                return@withContext driveClient.trashFile(fileId)
            }
            try {
                val docFile = DocumentFile.fromSingleUri(context, uri)
                docFile?.delete() ?: false
            } catch (e: Exception) {
                Log.e(TAG, "Failed to delete image: $uri", e)
                false
            }
        }

    override suspend fun moveImage(
        context: Context,
        sourceUri: Uri,
        destFolderUri: Uri,
        sorting: Boolean
    ): FileOperationResult = withContext(Dispatchers.IO) {
        val source = sourceUri.toString()
        // Drive → Drive move
        if (GoogleDriveImageSource.isDriveUri(sourceUri) && GoogleDriveImageSource.isDriveUri(destFolderUri)) {
            return@withContext driveMoveCopy(sourceUri, destFolderUri, sorting, move = true)
        }
        try {
            val destination = copyImageInternal(context, sourceUri, destFolderUri, sorting)
                ?: return@withContext FileOperationResult.failure(source, "Copy step failed")
            if (deleteImage(context, sourceUri)) {
                FileOperationResult.success(source, destination)
            } else {
                // The copy landed but the original is still there. Report the
                // destination anyway: the caller has two files now and needs the
                // URI to clean one of them up.
                FileOperationResult(
                    sourceUri = source,
                    destinationUri = destination,
                    success = false,
                    error = "Copied, but the original could not be removed",
                )
            }
        } catch (e: Exception) {
            Log.e(TAG, "Failed to move image: $sourceUri", e)
            FileOperationResult.failure(source, e.message)
        }
    }

    override suspend fun copyImage(
        context: Context,
        sourceUri: Uri,
        destFolderUri: Uri,
        sorting: Boolean
    ): FileOperationResult = withContext(Dispatchers.IO) {
        val source = sourceUri.toString()
        // Drive → Drive copy
        if (GoogleDriveImageSource.isDriveUri(sourceUri) && GoogleDriveImageSource.isDriveUri(destFolderUri)) {
            return@withContext driveMoveCopy(sourceUri, destFolderUri, sorting, move = false)
        }
        try {
            val destination = copyImageInternal(context, sourceUri, destFolderUri, sorting)
            if (destination != null) {
                FileOperationResult.success(source, destination)
            } else {
                FileOperationResult.failure(source, "Could not write to the Selection folder")
            }
        } catch (e: Exception) {
            Log.e(TAG, "Failed to copy image: $sourceUri", e)
            FileOperationResult.failure(source, e.message)
        }
    }

    /**
     * Take a filed photograph back out of the Selection.
     *
     * Implemented as an unsorted move in the opposite direction, so it works for
     * both backends without a second code path. See [ImageRepository.undoMove]
     * for the parent-folder limitation.
     */
    override suspend fun undoMove(
        context: Context,
        movedTo: Uri,
        restoreFolderUri: Uri,
    ): FileOperationResult = moveImage(
        context = context,
        sourceUri = movedTo,
        destFolderUri = restoreFolderUri,
        sorting = false,
    )

    /**
     * Handle move/copy between Google Drive locations.
     * Creates Selection/RAW/JPEG subfolders on Drive when sorting is enabled.
     *
     * A move costs one extra round trip — [GoogleDriveClient.parentsOf] — and
     * **fails outright if that read fails**. There is deliberately no fallback:
     * guessing the old parent is what produced a move that silently left the
     * file in place, and a reported failure the optimistic list can roll back is
     * strictly better than a success the file system did not honour.
     */
    private suspend fun driveMoveCopy(
        sourceUri: Uri,
        destFolderUri: Uri,
        sorting: Boolean,
        move: Boolean,
    ): FileOperationResult {
        val source = sourceUri.toString()
        val fileId = GoogleDriveImageSource.extractId(sourceUri)
            ?: return FileOperationResult.failure(source, "Not a Drive file")
        val destFolderId = GoogleDriveImageSource.extractId(destFolderUri)
            ?: return FileOperationResult.failure(source, "Not a Drive folder")

        // Determine target folder (with optional sorting subfolders)
        val targetFolderId = if (sorting) {
            val selectionId = driveClient.findOrCreateFolder(destFolderId, SELECTION_FOLDER_NAME)
                ?: return FileOperationResult.failure(source, "Cannot create Selection on Drive")
            // We need the filename to determine the subfolder
            // For simplicity, copy/move directly into Selection (subfolder sorting
            // would need a filename lookup — skip for Drive for now)
            selectionId
        } else {
            destFolderId
        }

        return if (move) {
            // Drive move = update parents; the file keeps its id, so the
            // destination URI is the source URI at a new location.
            //
            // The parents to remove are the file's *real* current ones, read
            // back from Drive. Passing the destination folder here — which this
            // did until 2026-08-08 — makes Drive remove a parent the file does
            // not have, so the file gains the Selection folder while staying in
            // the source folder: a move that is really a link. Since the
            // selector removes the frame from the list optimistically, that
            // reports success, empties the frame and leaves the file where it
            // was.
            val currentParents = driveClient.parentsOf(fileId)
                ?: return FileOperationResult.failure(
                    source,
                    "Could not read the file's folder on Drive",
                )

            when {
                // Already exactly where it is being moved to. Drive rejects a
                // PATCH that adds and removes the same parent, and there is
                // nothing to do.
                currentParents == listOf(targetFolderId) ->
                    return FileOperationResult.success(source, source)

                // An orphan or a shared-with-me file: nothing to remove, and
                // adding the destination still leaves it in exactly one folder,
                // so the move is honest.
                currentParents.isEmpty() ->
                    Log.i(TAG, "Drive file $fileId has no parent; move adds one")

                // Legacy multi-parenting. Every current parent is removed, not
                // just the first: a file left in any of them would still be in
                // the photographer's folder after a "move".
                currentParents.size > 1 ->
                    Log.i(TAG, "Drive file $fileId has ${currentParents.size} parents; removing all")
            }

            if (driveClient.moveFile(fileId, currentParents, targetFolderId)) {
                FileOperationResult.success(source, source)
            } else {
                FileOperationResult.failure(source, "Drive move failed")
            }
        } else {
            val copiedId = driveClient.copyFile(fileId, targetFolderId)
            if (copiedId != null) {
                FileOperationResult.success(
                    source,
                    GoogleDriveImageSource.buildUri(copiedId).toString(),
                )
            } else {
                FileOperationResult.failure(source, "Drive copy failed")
            }
        }
    }

    /** Copy the file and return the destination URI, or null if it did not land. */
    private fun copyImageInternal(
        context: Context,
        sourceUri: Uri,
        destFolderUri: Uri,
        sorting: Boolean
    ): String? {
        val sourceDoc = DocumentFile.fromSingleUri(context, sourceUri) ?: return null
        val fileName = sourceDoc.name ?: return null
        val mimeType = sourceDoc.type ?: "application/octet-stream"

        val destFolder = DocumentFile.fromTreeUri(context, destFolderUri) ?: return null

        val targetFolder = if (sorting) {
            // Create Selection folder
            val selectionDir = destFolder.findFile(SELECTION_FOLDER_NAME)
                ?: destFolder.createDirectory(SELECTION_FOLDER_NAME)
                ?: return null

            // Determine the correct subfolder based on file extension
            determineTargetFolder(fileName, selectionDir)
        } else {
            destFolder
        }

        val destFile = targetFolder.createFile(mimeType, fileName) ?: return null

        try {
            context.contentResolver.openInputStream(sourceUri)?.use { input ->
                context.contentResolver.openOutputStream(destFile.uri)?.use { output ->
                    input.copyTo(output)
                    return destFile.uri.toString()
                }
            }
        } catch (e: Exception) {
            // Never leave a half-written file in the Selection: a truncated
            // photograph that looks filed is worse than a failed move.
            cleanUpFailedCopy(destFile)
            throw e
        }

        // Streams could not be opened — remove the empty placeholder file.
        cleanUpFailedCopy(destFile)
        return null
    }

    private fun cleanUpFailedCopy(destFile: DocumentFile) {
        try {
            destFile.delete()
        } catch (e: Exception) {
            Log.w(TAG, "Could not clean up failed copy: ${destFile.uri}", e)
        }
    }

    /**
     * Determine which subfolder a file belongs in based on its extension.
     * RAW files → RAW subfolder, JPEG → JPEG subfolder,
     * Lightroom edits → RAW subfolder, XMP sidecars → follow parent type.
     */
    private fun determineTargetFolder(
        fileName: String,
        selectionDir: DocumentFile
    ): DocumentFile {
        val extension = fileName.substringAfterLast('.', "").lowercase()
        val stem = fileName.substringBeforeLast('.')

        val rawDir by lazy {
            selectionDir.findFile(RAW_SUBFOLDER)
                ?: selectionDir.createDirectory(RAW_SUBFOLDER)
        }
        val jpegDir by lazy {
            selectionDir.findFile(JPEG_SUBFOLDER)
                ?: selectionDir.createDirectory(JPEG_SUBFOLDER)
        }

        return when {
            extension in RAW_EXTENSIONS -> rawDir ?: selectionDir
            extension in JPEG_EXTENSIONS -> jpegDir ?: selectionDir
            stem.endsWith(EDIT_SUFFIX) -> rawDir ?: selectionDir
            extension == XMP_EXTENSION -> {
                val dotIndex = stem.lastIndexOf('.')
                val parentExt = if (dotIndex > 0) stem.substring(dotIndex + 1).lowercase() else null
                if (parentExt != null && parentExt in RAW_EXTENSIONS) {
                    rawDir ?: selectionDir
                } else {
                    selectionDir
                }
            }
            else -> selectionDir
        }
    }

    override suspend fun getImageDimensions(context: Context, uri: Uri): Pair<Int, Int> {
        if (GoogleDriveImageSource.isDriveUri(uri)) {
            val fileId = GoogleDriveImageSource.extractId(uri) ?: return Pair(0, 0)
            val cached = driveImageSource.ensureCached(fileId, fileId) ?: return Pair(0, 0)
            return localImageSource.getImageDimensions(Uri.fromFile(cached))
        }
        return localImageSource.getImageDimensions(uri)
    }

    /**
     * Resolve a batch of dimensions, routing each URI to its backend.
     *
     * Local URIs go to the source in one call so its memoisation does the work;
     * Drive URIs must be downloaded to the cache first, so they are resolved one
     * at a time and a failed download simply yields
     * [ImageDimensions.UNKNOWN] rather than aborting the batch — a frame with no
     * known ratio still draws at the 3:2 default.
     */
    override suspend fun resolveDimensions(
        context: Context,
        uris: Collection<String>,
    ): Map<String, ImageDimensions> = withContext(Dispatchers.IO) {
        val (driveUris, localUris) = uris.partition { GoogleDriveImageSource.isDriveUri(it) }

        val resolved = LinkedHashMap<String, ImageDimensions>(uris.size)
        if (localUris.isNotEmpty()) {
            resolved.putAll(localImageSource.resolveDimensions(localUris))
        }
        for (driveUri in driveUris) {
            ensureActive()
            resolved[driveUri] = resolveDriveDimensions(driveUri)
        }
        resolved
    }

    private suspend fun resolveDriveDimensions(uriString: String): ImageDimensions {
        val fileId = GoogleDriveImageSource.extractId(Uri.parse(uriString))
            ?: return ImageDimensions.UNKNOWN
        val cached = try {
            driveImageSource.ensureCached(fileId, fileId)
        } catch (e: Exception) {
            Log.w(TAG, "Cannot cache Drive file $fileId for dimensions", e)
            null
        } ?: return ImageDimensions.UNKNOWN
        val (width, height) = localImageSource.getImageDimensions(Uri.fromFile(cached))
        return ImageDimensions.of(width, height)
    }
}

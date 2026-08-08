package com.photoselectortoolbox.data.repository

import android.content.Context
import android.net.Uri
import com.photoselector.core.model.ExifData
import com.photoselectortoolbox.data.model.ImageDimensions
import com.photoselectortoolbox.data.model.ImageItem
import kotlinx.coroutines.flow.Flow

/**
 * Everything the selector needs from storage, with the storage backend hidden.
 *
 * Callers above this interface must never branch on a URI scheme: whether a
 * photograph lives behind SAF or in Google Drive decides which source runs, and
 * that decision belongs here rather than in a ViewModel.
 */
interface ImageRepository {
    /**
     * Progressive folder discovery. Emissions are cumulative and append-only —
     * a consumer merges by appending and must not re-sort what is already
     * visible.
     */
    fun discoverImages(folderUri: Uri): Flow<List<ImageItem>>

    /**
     * The complete folder, once.
     *
     * For consumers that cannot use a photograph until they have all of them —
     * duplicate detection, statistics. **Use this instead of
     * `discoverImages(uri).first()`**: since discovery became progressive, the
     * first emission is a batch of
     * [com.photoselectortoolbox.data.source.LocalImageSourceImpl.FIRST_BATCH_SIZE]
     * images, not the folder, so `first()` would silently analyse 24 photographs
     * and report the answer for the whole folder.
     */
    suspend fun discoverAllImages(folderUri: Uri): List<ImageItem>

    suspend fun getExifData(context: Context, uri: Uri): ExifData?

    suspend fun deleteImage(context: Context, uri: Uri): Boolean

    /** Returns true if the image can be moved to trash (recoverable) rather than permanently deleted. */
    fun canTrash(uri: Uri): Boolean

    /**
     * Bring a trashed file back. Only meaningful where [canTrash] is true; for
     * every other backend a delete is final and this returns false, which is the
     * signal to offer no UNDO at all rather than one that quietly fails.
     */
    suspend fun restoreFromTrash(context: Context, uri: Uri): Boolean

    /**
     * Move one image into the Selection of [destFolderUri].
     *
     * Returns the destination URI so the move can be reversed by
     * [undoMove]; a `Boolean` here is what previously made repository-level
     * undo impossible.
     */
    suspend fun moveImage(
        context: Context,
        sourceUri: Uri,
        destFolderUri: Uri,
        sorting: Boolean,
    ): FileOperationResult

    /** Copy one image into the Selection of [destFolderUri]. The source stays put. */
    suspend fun copyImage(
        context: Context,
        sourceUri: Uri,
        destFolderUri: Uri,
        sorting: Boolean,
    ): FileOperationResult

    /**
     * Reverse a completed move: take the file back out of the Selection and
     * return it to [restoreFolderUri].
     *
     * **Known limitation, stated rather than hidden:** SAF exposes no way to ask
     * a document for its parent, so the file returns to the root of the folder
     * the user opened, not to the sub-folder it was originally in. It reappears
     * in the list either way, because discovery is recursive over that folder.
     * Sorting is deliberately off — putting it back through the RAW/JPEG sorter
     * would be a second filing decision, not an undo.
     */
    suspend fun undoMove(
        context: Context,
        movedTo: Uri,
        restoreFolderUri: Uri,
    ): FileOperationResult

    suspend fun getImageDimensions(context: Context, uri: Uri): Pair<Int, Int>

    /**
     * Header-only dimensions for a set of images, keyed by URI string.
     *
     * Enumeration no longer reads dimensions (that cost one stream open per
     * photograph before the folder could be shown), so the caller drives this:
     * resolve the visible range first, then backfill the rest off the main
     * thread. Each URI is read at most once per process. Images whose header
     * cannot be parsed map to [ImageDimensions.UNKNOWN] — an absent ratio is a
     * safe state the frame solver already handles, never a failure.
     */
    suspend fun resolveDimensions(
        context: Context,
        uris: Collection<String>,
    ): Map<String, ImageDimensions>
}

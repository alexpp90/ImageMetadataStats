package com.photoselectortoolbox.data.repository

import android.content.Context
import android.net.Uri
import androidx.test.core.app.ApplicationProvider
import com.photoselector.core.reader.AndroidExifReader
import com.photoselector.core.reader.MediaStoreReader
import com.photoselectortoolbox.data.source.LocalImageSource
import com.photoselectortoolbox.data.source.googledrive.GoogleDriveClient
import com.photoselectortoolbox.data.source.googledrive.GoogleDriveImageSource
import io.mockk.coEvery
import io.mockk.coVerify
import io.mockk.mockk
import io.mockk.slot
import kotlinx.coroutines.test.runTest
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner
import org.robolectric.annotation.Config

/**
 * A Drive move must actually move the file.
 *
 * It did not. `driveMoveCopy` passed the **destination** folder as the parent to
 * remove, so Drive removed a parent the file never had and `addParents` simply
 * linked the photograph into the Selection while it stayed in the shoot folder.
 * The selector removes the frame from the list optimistically, so the failure
 * was invisible from inside the app: the snackbar said "Moved", the frame went
 * away, and the file was still where it started — the "feed is ahead of the file
 * system" defect in `ai/memory/palette.md` (2026-07-31), except here the file
 * operation itself did the wrong thing.
 *
 * These tests hold the fake client's [GoogleDriveClient.moveFile] arguments up
 * against the parents the file actually has, because that is the one assertion
 * the shipped code would have failed.
 *
 * Robolectric rather than an emulator: the only Android surface involved is
 * `Uri.parse`.
 */
@RunWith(RobolectricTestRunner::class)
@Config(sdk = [34])
class ImageRepositoryDriveMoveTest {

    private companion object {
        const val FILE_ID = "photo-1"
        const val SOURCE_FOLDER_ID = "shoot-folder"
        const val DEST_FOLDER_ID = "selection-folder"
    }

    private val driveClient: GoogleDriveClient = mockk(relaxed = true)

    private val repository = ImageRepositoryImpl(
        localImageSource = mockk<LocalImageSource>(relaxed = true),
        androidExifReader = mockk<AndroidExifReader>(relaxed = true),
        mediaStoreReader = mockk<MediaStoreReader>(relaxed = true),
        driveImageSource = mockk<GoogleDriveImageSource>(relaxed = true),
        driveClient = driveClient,
    )

    private val context: Context get() = ApplicationProvider.getApplicationContext()

    private fun fileUri() = Uri.parse("gdrive://$FILE_ID")
    private fun destUri() = Uri.parse("gdrive://$DEST_FOLDER_ID")

    private suspend fun move() = repository.moveImage(
        context = context,
        sourceUri = fileUri(),
        destFolderUri = destUri(),
        sorting = false,
    )

    @Test
    fun `the parent removed is the folder the file was in, not the destination`() = runTest {
        coEvery { driveClient.parentsOf(FILE_ID) } returns listOf(SOURCE_FOLDER_ID)
        val removed = slot<Collection<String>>()
        coEvery { driveClient.moveFile(FILE_ID, capture(removed), DEST_FOLDER_ID) } returns true

        val result = move()

        assertTrue(result.success)
        assertEquals(listOf(SOURCE_FOLDER_ID), removed.captured.toList())
        assertFalse(
            "the destination folder must never be the parent being removed",
            removed.captured.contains(DEST_FOLDER_ID),
        )
    }

    @Test
    fun `every parent of a multi-parented file is removed`() = runTest {
        // Legacy Drive multi-parenting: leaving the file in any of its folders
        // would keep it in the photographer's shoot after a "move".
        val parents = listOf(SOURCE_FOLDER_ID, "second-folder", "third-folder")
        coEvery { driveClient.parentsOf(FILE_ID) } returns parents
        val removed = slot<Collection<String>>()
        coEvery { driveClient.moveFile(FILE_ID, capture(removed), DEST_FOLDER_ID) } returns true

        val result = move()

        assertTrue(result.success)
        assertEquals(parents, removed.captured.toList())
    }

    @Test
    fun `a file with no parent is still moved, with nothing to remove`() = runTest {
        // An orphan or a shared-with-me file. Adding the destination leaves it
        // in exactly one folder, so the move is honest and must not fail.
        coEvery { driveClient.parentsOf(FILE_ID) } returns emptyList()
        val removed = slot<Collection<String>>()
        coEvery { driveClient.moveFile(FILE_ID, capture(removed), DEST_FOLDER_ID) } returns true

        val result = move()

        assertTrue(result.success)
        assertTrue(removed.captured.isEmpty())
    }

    @Test
    fun `a file already in the destination is a no-op, not a rejected PATCH`() = runTest {
        // Drive rejects a request that both adds and removes the same parent.
        coEvery { driveClient.parentsOf(FILE_ID) } returns listOf(DEST_FOLDER_ID)

        val result = move()

        assertTrue(result.success)
        coVerify(exactly = 0) { driveClient.moveFile(any(), any(), any()) }
    }

    @Test
    fun `an unreadable parent list fails the move instead of guessing`() = runTest {
        // The whole point of the fix: no fallback. A half-move the optimistic
        // list has already committed to is worse than a failure it rolls back.
        coEvery { driveClient.parentsOf(FILE_ID) } returns null

        val result = move()

        assertFalse(result.success)
        assertEquals("Could not read the file's folder on Drive", result.error)
        coVerify(exactly = 0) { driveClient.moveFile(any(), any(), any()) }
    }

    @Test
    fun `a rejected move is reported as a failure`() = runTest {
        coEvery { driveClient.parentsOf(FILE_ID) } returns listOf(SOURCE_FOLDER_ID)
        coEvery { driveClient.moveFile(FILE_ID, any(), DEST_FOLDER_ID) } returns false

        val result = move()

        assertFalse(result.success)
        assertEquals("Drive move failed", result.error)
    }

    @Test
    fun `a copy never asks for parents and never touches them`() = runTest {
        coEvery { driveClient.copyFile(FILE_ID, DEST_FOLDER_ID, any()) } returns "copied-id"

        val result = repository.copyImage(
            context = context,
            sourceUri = fileUri(),
            destFolderUri = destUri(),
            sorting = false,
        )

        assertTrue(result.success)
        assertEquals("gdrive://copied-id", result.destinationUri)
        coVerify(exactly = 0) { driveClient.parentsOf(any()) }
        coVerify(exactly = 0) { driveClient.moveFile(any(), any(), any()) }
    }
}

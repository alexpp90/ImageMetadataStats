package com.photoselectortoolbox.viewmodel

import android.net.Uri
import androidx.test.core.app.ApplicationProvider
import com.photoselectortoolbox.data.cache.ScoreDao
import kotlinx.coroutines.yield
import com.photoselectortoolbox.domain.usecase.ScanProgress
import com.photoselectortoolbox.data.model.ScanResult
import com.photoselectortoolbox.data.cache.ScoreEntity
import com.photoselector.core.model.ExifData
import com.photoselectortoolbox.data.model.ImageDimensions
import com.photoselectortoolbox.data.model.ImageItem
import com.photoselectortoolbox.data.repository.CacheRepository
import com.photoselectortoolbox.data.repository.FileOperationResult
import com.photoselectortoolbox.data.repository.ImageRepository
import com.photoselectortoolbox.data.repository.SettingsRepository
import com.photoselectortoolbox.domain.curation.UndoableOperation
import com.photoselectortoolbox.domain.grouping.GroupingLevel
import com.photoselectortoolbox.domain.interaction.FilingAction
import com.photoselectortoolbox.domain.usecase.MoveToSelectionUseCase
import com.photoselectortoolbox.domain.usecase.ScanImagesUseCase
import io.mockk.coEvery
import io.mockk.coVerify
import io.mockk.every
import io.mockk.mockk
import kotlinx.coroutines.CompletableDeferred
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.cancel
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.ExperimentalCoroutinesApi
import kotlinx.coroutines.flow.MutableSharedFlow
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.flowOf
import kotlinx.coroutines.test.UnconfinedTestDispatcher
import kotlinx.coroutines.test.advanceUntilIdle
import kotlinx.coroutines.test.resetMain
import kotlinx.coroutines.test.runTest
import kotlinx.coroutines.test.setMain
import org.junit.After
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Before
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner
import org.robolectric.annotation.Config

/**
 * The selector's session behaviour: progressive loading, optimistic filing,
 * deferred deletion and the undo that follows from them.
 *
 * Robolectric rather than an emulator because everything under test here is
 * state transition — the Android surface actually needed is `Uri.parse` and a
 * `Context`. Folders are opened through [ImageRepository.openFolder], which is
 * the seam that keeps SAF's `DocumentFile` dance behind the repository — so a
 * stubbed folder name is all it takes to exercise the real discovery, merge and
 * filing code.
 */
@OptIn(ExperimentalCoroutinesApi::class)
@RunWith(RobolectricTestRunner::class)
@Config(sdk = [34])
class SelectorViewModelTest {

    private val testDispatcher = UnconfinedTestDispatcher()

    /**
     * The application scope the ViewModel files and deletes on.
     *
     * Held by the test rather than created per ViewModel so [tearDown] can cancel
     * it. It outlives `viewModelScope` by design — that is what lets a filing
     * operation survive the screen going away — so work left running on it would
     * otherwise still be dispatching while `resetMain` swaps the dispatcher out.
     */
    private val appScope = CoroutineScope(testDispatcher)

    private val groupingEnabledFlow = MutableStateFlow(false)
    private val groupingLevelFlow = MutableStateFlow(GroupingLevel.TIME_FILENAME)
    private val sortingEnabledFlow = MutableStateFlow(true)
    private val lastFolderUriFlow = MutableStateFlow<String?>(null)
    private val filingActionFlow = MutableStateFlow(FilingAction.COPY)
    private val fullscreenButtonsFlow = MutableStateFlow(true)
    private val overlayValuesFlow = MutableStateFlow(true)
    private val filmstripVisibleFlow = MutableStateFlow(true)
    private val detailsVisibleFlow = MutableStateFlow(true)
    private val seenFullscreenHintFlow = MutableStateFlow(true)
    private val seenNavHintFlow = MutableStateFlow(true)
    private val selectionFolderNameFlow = MutableStateFlow(FilingAction.DEFAULT_SELECTION_FOLDER)

    /** Discovery batches, pushed by the test to imitate progressive enumeration. */
    private val discovery = MutableSharedFlow<List<ImageItem>>(replay = 1)

    private companion object {
        const val FOLDER_URI = "content://test/folder"
        const val OTHER_FOLDER_URI = "content://test/other"
    }

    private val settingsRepository: SettingsRepository = mockk(relaxed = true) {
        every { groupingEnabled } returns groupingEnabledFlow
        every { groupingLevel } returns groupingLevelFlow
        every { sortingEnabled } returns sortingEnabledFlow
        every { lastFolderUri } returns lastFolderUriFlow
        every { filingAction } returns filingActionFlow
        every { fullscreenButtonsEnabled } returns fullscreenButtonsFlow
        every { overlayValuesVisible } returns overlayValuesFlow
        every { filmstripVisible } returns filmstripVisibleFlow
        every { detailsVisible } returns detailsVisibleFlow
        every { hasSeenFullscreenGestureHint } returns seenFullscreenHintFlow
        every { hasSeenNavHint } returns seenNavHintFlow
        every { selectionFolderName } returns selectionFolderNameFlow
    }

    private val imageRepository: ImageRepository = mockk(relaxed = true) {
        coEvery { openFolder(any(), any()) } returns "Test Shoot"
        every { discoverImages(any()) } returns discovery
        every { canTrash(any()) } returns false
        coEvery { getExifData(any(), any()) } returns null
        coEvery { resolveDimensions(any(), any()) } returns emptyMap<String, ImageDimensions>()
        coEvery { deleteImage(any(), any()) } returns true
    }

    private val scanImagesUseCase: ScanImagesUseCase = mockk(relaxed = true)

    private val scoreDao: ScoreDao = mockk(relaxed = true) {
        coEvery { getScore(any()) } returns null
    }

    private fun image(name: String) = ImageItem(
        uri = "content://test/folder/$name",
        fileName = name,
        fileSize = 1,
        lastModified = 1,
        mimeType = "image/jpeg",
    )

    private fun buildViewModel() = SelectorViewModel(
        imageRepository = imageRepository,
        scanImagesUseCase = scanImagesUseCase,
        moveToSelectionUseCase = mockk<MoveToSelectionUseCase>(relaxed = true),
        cacheRepository = mockk<CacheRepository>(relaxed = true),
        settingsRepository = settingsRepository,
        scoreDao = scoreDao,
        appScope = appScope,
        context = ApplicationProvider.getApplicationContext(),
    )

    private suspend fun loadFolder(vararg images: ImageItem): SelectorViewModel {
        val viewModel = buildViewModel()
        viewModel.selectFolder(Uri.parse(FOLDER_URI))
        discovery.emit(images.toList())
        return viewModel
    }

    @Before
    fun setUp() {
        Dispatchers.setMain(testDispatcher)
    }

    @After
    fun tearDown() {
        appScope.cancel()
        Dispatchers.resetMain()
        discovery.resetReplayCache()
    }

    // ── Progressive loading ──────────────────────────────────────────────

    @Test
    fun `a later batch appends without moving the photographer`() = runTest {
        val viewModel = loadFolder(image("a"), image("b"), image("c"))
        viewModel.navigateToImage(2)

        // Cumulative emission: the first three are in it again.
        discovery.emit(listOf(image("a"), image("b"), image("c"), image("d"), image("e")))

        val state = viewModel.uiState.value
        assertEquals(listOf("a", "b", "c", "d", "e"), state.images.map { it.fileName })
        assertEquals("c", state.currentImage?.fileName)
    }

    @Test
    fun `a frame filed away is not resurrected by the next batch`() = runTest {
        coEvery { imageRepository.moveImage(any(), any(), any(), any()) } returns
            FileOperationResult.success("content://test/folder/a", "content://test/selection/a")

        val viewModel = loadFolder(image("a"), image("b"))
        viewModel.moveToSelection()
        assertEquals(listOf("b"), viewModel.uiState.value.images.map { it.fileName })

        discovery.emit(listOf(image("a"), image("b"), image("c")))

        assertEquals(listOf("b", "c"), viewModel.uiState.value.images.map { it.fileName })
    }

    @Test
    fun `enumeration is flagged while the folder is still growing`() = runTest {
        // What puts the `+` on `127 / 842+`. The total is a running total until
        // the discovery flow completes.
        val streaming = loadFolder(image("a"), image("b"))
        assertTrue(streaming.uiState.value.isEnumerating)
        assertFalse(streaming.uiState.value.isLoading)
    }

    @Test
    fun `enumeration stops being flagged once discovery completes`() = runTest {
        every { imageRepository.discoverImages(any()) } returns
            flowOf(listOf(image("a"), image("b")))

        val settled = buildViewModel()
        settled.selectFolder(Uri.parse(FOLDER_URI))

        assertFalse(settled.uiState.value.isEnumerating)
        assertEquals(2, settled.uiState.value.images.size)
    }

    @Test
    fun `selecting a new folder clears the published set so the folder is not empty`() = runTest {
        val viewModel = loadFolder(image("a"), image("b"))
        assertEquals(2, viewModel.uiState.value.images.size)

        // Same URIs, different folder. A surviving published set would
        // de-duplicate them all away and leave a silently empty screen.
        viewModel.selectFolder(Uri.parse(OTHER_FOLDER_URI))
        discovery.emit(listOf(image("a"), image("b")))

        assertEquals(2, viewModel.uiState.value.images.size)
        assertEquals(0, viewModel.uiState.value.currentIndex)
    }

    // ── Optimistic filing ────────────────────────────────────────────────

    @Test
    fun `a move leaves the list before the transfer completes`() = runTest {
        // The point of the change: gate the repository on a deferred and assert
        // the list has already advanced. A test that only checks the settled
        // state cannot tell optimistic from blocking.
        val transfer = CompletableDeferred<FileOperationResult>()
        coEvery { imageRepository.moveImage(any(), any(), any(), any()) } coAnswers {
            transfer.await()
        }

        val viewModel = loadFolder(image("a"), image("b"), image("c"))
        viewModel.moveToSelection()

        assertFalse(transfer.isCompleted)
        assertEquals(listOf("b", "c"), viewModel.uiState.value.images.map { it.fileName })
        assertEquals("b", viewModel.uiState.value.currentImage?.fileName)
        assertFalse("no spinner for a filing action", viewModel.uiState.value.isLoading)
        assertEquals("Moved to Selection", viewModel.uiState.value.snackbarMessage)

        transfer.complete(FileOperationResult.success("content://test/folder/a", "content://test/sel/a"))
        assertEquals(listOf("b", "c"), viewModel.uiState.value.images.map { it.fileName })
    }

    @Test
    fun `the confirmation names the folder the photographer configured`() = runTest {
        // Guards the wiring, not the wording: SelectionActionLabels is already
        // unit-tested with a renamed folder, but every other assertion in this
        // file uses the default name, so passing a constant instead of the
        // configured value would satisfy all of them. Only a renamed folder
        // reaching the snackbar proves the ViewModel actually threads it.
        selectionFolderNameFlow.value = "Picks"
        coEvery { imageRepository.moveImage(any(), any(), any(), any()) } returns
            FileOperationResult.success("content://test/folder/a", "content://test/sel/a")

        val viewModel = loadFolder(image("a"), image("b"))
        viewModel.moveToSelection()

        assertEquals("Moved to Picks", viewModel.uiState.value.snackbarMessage)
    }

    @Test
    fun `a copy keeps the frame on screen and confirms it`() = runTest {
        val transfer = CompletableDeferred<FileOperationResult>()
        coEvery { imageRepository.copyImage(any(), any(), any(), any()) } coAnswers {
            transfer.await()
        }

        val viewModel = loadFolder(image("a"), image("b"))
        viewModel.copyToSelection()

        assertEquals(listOf("a", "b"), viewModel.uiState.value.images.map { it.fileName })
        assertEquals("Copied to Selection", viewModel.uiState.value.snackbarMessage)
        transfer.complete(FileOperationResult.success("content://test/folder/a", "content://test/sel/a"))
    }

    @Test
    fun `a failed move puts the frame back where it was`() = runTest {
        coEvery { imageRepository.moveImage(any(), any(), any(), any()) } returns
            FileOperationResult.failure("content://test/folder/b", "disk full")

        val viewModel = loadFolder(image("a"), image("b"), image("c"))
        viewModel.navigateToImage(1)
        viewModel.moveToSelection()

        val state = viewModel.uiState.value
        assertEquals(listOf("a", "b", "c"), state.images.map { it.fileName })
        assertNotNull(state.error)
        assertNull(state.undoOperation)
    }

    @Test
    fun `a failed copy rewinds nothing, because the source never left`() = runTest {
        coEvery { imageRepository.copyImage(any(), any(), any(), any()) } returns
            FileOperationResult.failure("content://test/folder/a", "disk full")

        val viewModel = loadFolder(image("a"), image("b"))
        viewModel.copyToSelection()

        assertEquals(listOf("a", "b"), viewModel.uiState.value.images.map { it.fileName })
    }

    // ── Undo availability ────────────────────────────────────────────────

    @Test
    fun `a completed move offers an undo, a copy never does`() = runTest {
        coEvery { imageRepository.moveImage(any(), any(), any(), any()) } returns
            FileOperationResult.success("content://test/folder/a", "content://test/sel/a")
        coEvery { imageRepository.copyImage(any(), any(), any(), any()) } returns
            FileOperationResult.success("content://test/folder/a", "content://test/sel/a")

        val moved = loadFolder(image("a"), image("b"))
        moved.moveToSelection()
        assertTrue(moved.uiState.value.undoOperation is UndoableOperation.ReverseMove)

        val copied = loadFolder(image("a"), image("b"))
        copied.copyToSelection()
        // Undoing a copy could only mean deleting the file just created.
        assertNull(copied.uiState.value.undoOperation)
    }

    @Test
    fun `a move with no destination URI offers no undo`() = runTest {
        coEvery { imageRepository.moveImage(any(), any(), any(), any()) } returns
            FileOperationResult.success("content://test/folder/a", null)

        val viewModel = loadFolder(image("a"), image("b"))
        viewModel.moveToSelection()

        assertNull(viewModel.uiState.value.undoOperation)
    }

    // ── Deferred deletion ────────────────────────────────────────────────

    @Test
    fun `a delete leaves the list at once and touches no file yet`() = runTest {
        val viewModel = loadFolder(image("a"), image("b"), image("c"))
        viewModel.deleteCurrentImage()

        val state = viewModel.uiState.value
        assertEquals(listOf("b", "c"), state.images.map { it.fileName })
        assertEquals("1 image deleted", state.snackbarMessage)
        assertNotNull(state.pendingDeletion)
        assertTrue(state.undoOperation is UndoableOperation.RevertPendingDelete)
        coVerify(exactly = 0) { imageRepository.deleteImage(any(), any()) }
    }

    @Test
    fun `undoing a pending delete restores the frame and never deletes it`() = runTest {
        val viewModel = loadFolder(image("a"), image("b"), image("c"))
        viewModel.navigateToImage(1)
        viewModel.deleteCurrentImage()
        viewModel.undoLastOperation()

        val state = viewModel.uiState.value
        assertEquals(listOf("a", "b", "c"), state.images.map { it.fileName })
        assertNull(state.pendingDeletion)
        assertNull(state.undoOperation)
        assertNull(state.snackbarMessage)
        coVerify(exactly = 0) { imageRepository.deleteImage(any(), any()) }
    }

    @Test
    fun `a second destructive action commits the first deletion to disk`() = runTest {
        val viewModel = loadFolder(image("a"), image("b"), image("c"))
        viewModel.deleteCurrentImage()
        viewModel.deleteCurrentImage()

        coVerify(exactly = 1) {
            imageRepository.deleteImage(any(), match { it.toString().endsWith("/a") })
        }
        assertEquals(listOf("c"), viewModel.uiState.value.images.map { it.fileName })
    }

    @Test
    fun `leaving the screen commits the deletion rather than dropping it`() = runTest {
        val viewModel = loadFolder(image("a"), image("b"))
        viewModel.deleteCurrentImage()

        // Reaching onCleared through a folder change would also do it; this is
        // the path where viewModelScope dies, which is why the commit is on the
        // application scope.
        viewModel.selectFolder(Uri.parse(OTHER_FOLDER_URI))

        coVerify(exactly = 1) {
            imageRepository.deleteImage(any(), match { it.toString().endsWith("/a") })
        }
    }

    @Test
    fun `delete is confirmed by dialog only where the file cannot be trashed`() = runTest {
        every { imageRepository.canTrash(any()) } returns false
        val saf = loadFolder(image("a"), image("b"))
        saf.requestDelete()
        assertTrue(saf.uiState.value.showDeleteConfirmation)
        assertEquals(2, saf.uiState.value.images.size)

        every { imageRepository.canTrash(any()) } returns true
        val trashing = loadFolder(image("a"), image("b"))
        trashing.requestDelete()
        assertFalse(trashing.uiState.value.showDeleteConfirmation)
        assertEquals(1, trashing.uiState.value.images.size)
    }

    // ── Snackbar ownership ───────────────────────────────────────────────

    @Test
    fun `dismissing the snackbar takes its undo with it`() = runTest {
        val viewModel = loadFolder(image("a"), image("b"))
        viewModel.deleteCurrentImage()
        assertNotNull(viewModel.uiState.value.undoOperation)

        viewModel.dismissSnackbar()

        assertNull(viewModel.uiState.value.snackbarMessage)
        assertNull(viewModel.uiState.value.undoOperation)
    }

    @Test
    fun `an error reaches the photographer through the snackbar with no undo`() = runTest {
        val viewModel = loadFolder(image("a"))
        viewModel.setError("Could not read the folder")

        assertEquals("Could not read the folder", viewModel.uiState.value.snackbarMessage)
        assertNull(viewModel.uiState.value.undoOperation)
    }

    // ── Background merges must not roll back what landed while they ran ──

    @Test
    fun `a scan does not roll back the EXIF already on screen`() = runTest {
        val exif = ExifData(iso = 800, aperture = 4.0)
        coEvery { imageRepository.getExifData(any(), any()) } returns exif
        val progress = MutableSharedFlow<ScanProgress>(replay = 1)
        every { scanImagesUseCase(any(), any()) } returns progress

        val viewModel = loadFolder(image("a"))
        assertEquals(exif, viewModel.uiState.value.currentImage?.exifData)

        viewModel.startScan()
        progress.emit(
            ScanProgress(
                processed = 1,
                total = 1,
                currentFile = "a",
                results = mapOf(
                    "content://test/folder/a" to ScanResult(
                        filePath = "content://test/folder/a",
                        sharpnessScore = 70.0,
                    )
                ),
            )
        )

        val current = viewModel.uiState.value.currentImage
        assertEquals("the scan rolled EXIF back", exif, current?.exifData)
        assertEquals(70.0, current?.scanResult?.sharpnessScore!!, 0.01)
    }
}

package com.photoselectortoolbox.viewmodel

import android.content.Context
import android.net.Uri
import android.util.Log
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import coil.Coil
import coil.request.Disposable
import coil.request.ImageRequest
import coil.size.Precision
import coil.size.Scale
import com.photoselector.core.model.ExifData
import com.photoselectortoolbox.data.cache.ScoreDao
import com.photoselectortoolbox.data.model.ImageDimensions
import com.photoselectortoolbox.data.model.ImageItem
import com.photoselectortoolbox.data.model.ScanResult
import com.photoselectortoolbox.data.repository.CacheRepository
import com.photoselectortoolbox.data.repository.ImageRepository
import com.photoselectortoolbox.data.repository.SettingsRepository
import com.photoselectortoolbox.di.ApplicationScope
import com.photoselectortoolbox.domain.curation.CurationAction
import com.photoselectortoolbox.domain.curation.DeferredDeletion
import com.photoselectortoolbox.domain.curation.ImageSlot
import com.photoselectortoolbox.domain.curation.OptimisticEdits
import com.photoselectortoolbox.domain.curation.PendingDeletion
import com.photoselectortoolbox.domain.curation.SelectorListState
import com.photoselectortoolbox.domain.curation.UndoPolicy
import com.photoselectortoolbox.domain.curation.UndoableOperation
import com.photoselectortoolbox.domain.format.SelectorLabels
import com.photoselectortoolbox.domain.grouping.GroupingLevel
import com.photoselectortoolbox.domain.guidance.SelectorGuidance
import com.photoselectortoolbox.domain.guidance.SelectorHint
import com.photoselectortoolbox.domain.guidance.SelectorHintText
import com.photoselectortoolbox.domain.grouping.ImageGrouper
import com.photoselectortoolbox.domain.format.SelectionActionLabels
import com.photoselectortoolbox.domain.interaction.FilingAction
import com.photoselectortoolbox.domain.session.ProgressiveMerge
import com.photoselectortoolbox.domain.session.ScoreMerge
import com.photoselectortoolbox.domain.session.SelectorWindows
import com.photoselectortoolbox.domain.session.SelectorWork
import com.photoselectortoolbox.domain.session.SelectorWorkQueue
import com.photoselectortoolbox.domain.session.WorkDecision
import com.photoselectortoolbox.domain.session.WorkQueueState
import com.photoselectortoolbox.domain.usecase.MoveToSelectionUseCase
import com.photoselectortoolbox.domain.usecase.ScanImagesUseCase
import dagger.hilt.android.lifecycle.HiltViewModel
import dagger.hilt.android.qualifiers.ApplicationContext
import javax.inject.Inject
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.Job
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.combine
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext

/**
 * Which of the three frames on screen a control refers to.
 *
 * Named rather than passed as an index because "1" and "the previous frame" are
 * different things: the index shifts every time the user advances, and every
 * bug in this area has come from an index that outlived the mutation it was
 * read before.
 */
enum class SelectorFrame { PREVIOUS, CURRENT, NEXT }

data class SelectorUiState(
    val images: List<ImageItem> = emptyList(),
    val currentIndex: Int = 0,
    val isLoading: Boolean = false,
    /**
     * Whether folder enumeration is still producing photographs.
     *
     * Distinct from [isLoading], which covers only the wait for the *first*
     * batch. Discovery streams, so the folder keeps growing behind a fully
     * usable screen; this is what puts the `+` on `127 / 842+`.
     */
    val isEnumerating: Boolean = false,
    val isScanRunning: Boolean = false,
    /** Whether Group Similar Series is currently rebuilding the bursts. */
    val isGroupingRunning: Boolean = false,
    /**
     * The pass that has been asked for and is waiting for the running one.
     *
     * Never a disabled control: the sidebar shows this as a queued state with a
     * Cancel, per `ai/memory/palette.md` (2026-07-24).
     */
    val queuedWork: SelectorWork? = null,
    val scanProgress: Float = 0f,
    val scanStatusText: String = "",
    val folderUri: String? = null,
    val folderName: String = "",
    val error: String? = null,
    /**
     * The snackbar line, owned here rather than in the composable so it survives
     * recomposition and always matches the operation [undoOperation] describes.
     */
    val snackbarMessage: String? = null,
    /**
     * What, if anything, the snackbar's UNDO would actually reverse.
     *
     * Null means no UNDO is drawn. `UndoPolicy` decides — a button that silently
     * does nothing is worse than no button (REQUIREMENTS §2).
     */
    val undoOperation: UndoableOperation? = null,
    /** A deletion removed from the list but not yet committed to disk. */
    val pendingDeletion: PendingDeletion? = null,
    val showDeleteConfirmation: Boolean = false,
    val groupingEnabled: Boolean = false,
    val groups: List<List<Int>> = emptyList(),
    val fullscreenButtonsEnabled: Boolean = true,
    /** Which of Copy and Move is the emphasised filing control (persisted). */
    val filingAction: FilingAction = FilingAction.DEFAULT,
    /** Whether the one-time on-image nav arrows have already been shown. */
    val hasSeenNavHint: Boolean = false,
    /** Whether the filmstrip along the bottom edge is shown (persisted). */
    val filmstripVisible: Boolean = true,
    /** Whether the readout block beside the current frame is shown (persisted). */
    val detailsVisible: Boolean = true,
    /** Whether Previous and Next carry their value overlay (persisted). */
    val overlayValuesVisible: Boolean = true,
    /**
     * Which frame, if any, is currently filling the image region.
     *
     * Null is the normal three-up state. Maximise is transient view state, not
     * a preference: it is a thing you do to look closer at one frame, and it
     * should not survive a relaunch the way a layout choice would.
     */
    val maximisedFrame: SelectorFrame? = null,
    /** Whether the one-time fullscreen gesture hint has already been dismissed. */
    val hasSeenFullscreenHint: Boolean = false,
    /** Every one-time explanation the photographer has already dismissed. */
    val seenHints: Set<SelectorHint> = emptySet(),
    /**
     * The explanation waiting to be shown, if any.
     *
     * Raised by the action whose *effect* is invisible — filing, deferred
     * deletion, maximise — and cleared when it is dismissed or auto-dismissed.
     * `SelectorGuidance` decides; this field only carries the answer.
     */
    val pendingHint: SelectorHint? = null,
    /** The destination folder name, so the filing hint can name it (persisted). */
    val selectionFolderName: String = FilingAction.DEFAULT_SELECTION_FOLDER,
    /** Whether RAW and JPEG are filed into subfolders (persisted). */
    val sortingEnabled: Boolean = true,
) {
    /** The frame being judged, or null when no folder is loaded. */
    val currentImage: ImageItem?
        get() = images.getOrNull(currentIndex)

    /** The frame before the current one, or null at the start of the folder. */
    val previousImage: ImageItem?
        get() = images.getOrNull(currentIndex - 1)

    /** The frame after the current one, or null at the end of the folder. */
    val nextImage: ImageItem?
        get() = images.getOrNull(currentIndex + 1)

    /** Human-readable position, 1-based, as shown in the app bar and rails. */
    val position: Int
        get() = if (images.isEmpty()) 0 else currentIndex + 1

    /** True once at least one frame carries scores, which is what reveals the legend. */
    val hasAnyScores: Boolean
        get() = images.any { it.scanResult != null }

    /** The list and the index as one value, for the pure `domain/curation` logic. */
    val listState: SelectorListState
        get() = SelectorListState(images, currentIndex)

    /**
     * Whether the coach-mark guide opens by itself, this being a first launch.
     *
     * Derived rather than stored: it is a function of the persisted hint set and
     * whether there is anything on screen to label, and a second copy of it
     * would be one more thing to keep in step with *Reset guidance*.
     */
    val showIntroTour: Boolean
        get() = SelectorGuidance.shouldShowTour(seenHints, images.isNotEmpty())

    /**
     * The pending explanation with its wording resolved from the current
     * settings, ready for the card to draw.
     *
     * Built here rather than in the composable so no default verb, folder name
     * or key can be hard-coded next to a `Text`.
     */
    val pendingHintText: SelectorHintUi?
        get() = pendingHint?.let { hint ->
            SelectorHintUi(
                hint = hint,
                title = SelectorHintText.title(hint, filingAction, selectionFolderName),
                message = SelectorHintText.message(
                    hint = hint,
                    filingAction = filingAction,
                    selectionFolderName = selectionFolderName,
                    sortingEnabled = sortingEnabled,
                ),
            )
        }
}

/** One resolved explanation: which hint it is, and the words for it. */
data class SelectorHintUi(
    val hint: SelectorHint,
    val title: String,
    val message: String,
)

@HiltViewModel
class SelectorViewModel @Inject constructor(
    private val imageRepository: ImageRepository,
    private val scanImagesUseCase: ScanImagesUseCase,
    private val moveToSelectionUseCase: MoveToSelectionUseCase,
    private val cacheRepository: CacheRepository,
    private val settingsRepository: SettingsRepository,
    private val scoreDao: ScoreDao,
    @ApplicationScope private val appScope: CoroutineScope,
    @ApplicationContext private val context: Context
) : ViewModel() {

    private val _uiState = MutableStateFlow(SelectorUiState())
    val uiState: StateFlow<SelectorUiState> = _uiState.asStateFlow()

    // ── Session state ────────────────────────────────────────────────────
    //
    // Everything below belongs to "the folder currently open" and is cleared in
    // exactly one place ([resetSession]). A stale `publishedUris` makes a new
    // folder look empty, and scattered resets are how one gets forgotten — the
    // same trap recorded against PhotoTok's feed loader in
    // `ai/memory/code_health.md`.

    private var discoveryJob: Job? = null
    private var visibleDimensionsJob: Job? = null
    private var backfillDimensionsJob: Job? = null
    private var scoreRestoreJob: Job? = null
    private var scanJob: Job? = null
    private var groupingJob: Job? = null
    private var deletionTimerJob: Job? = null

    /**
     * Every URI ever published for this folder, including ones the photographer
     * has since moved or deleted. Discovery emits cumulatively, so "not in the
     * list" must never be read as "newly found".
     */
    private val publishedUris = mutableSetOf<String>()

    /**
     * URIs whose header has been read, so no URI costs a second open —
     * unreadable ones included, because a negative result is still an answer.
     *
     * Concurrent because the visible-range pass and the background backfill
     * touch it from different dispatchers.
     */
    private val dimensionsResolved: MutableSet<String> =
        java.util.Collections.newSetFromMap(java.util.concurrent.ConcurrentHashMap())

    /** Coil prefetch requests in flight, keyed by URI so they can be superseded. */
    private val prefetchRequests = mutableMapOf<String, Disposable>()

    private var workQueue = WorkQueueState()
    private var pendingScanAesthetic = false
    private var pendingGroupingLevel: GroupingLevel = GroupingLevel.TIME_FILENAME

    private val imageGrouper = ImageGrouper(context)

    init {
        viewModelScope.launch {
            combine(
                settingsRepository.groupingEnabled,
                settingsRepository.groupingLevel
            ) { enabled, level ->
                Pair(enabled, level)
            }.collect { (enabled, level) ->
                _uiState.update { it.copy(groupingEnabled = enabled) }
                if (_uiState.value.images.isEmpty()) return@collect
                if (enabled) {
                    requestGrouping(level)
                } else {
                    cancelGroupingWork()
                    _uiState.update { it.copy(groups = emptyList()) }
                }
            }
        }

        viewModelScope.launch {
            settingsRepository.fullscreenButtonsEnabled.collect { enabled ->
                _uiState.update { it.copy(fullscreenButtonsEnabled = enabled) }
            }
        }

        viewModelScope.launch {
            settingsRepository.filingAction.collect { action ->
                _uiState.update { it.copy(filingAction = action) }
            }
        }

        viewModelScope.launch {
            settingsRepository.overlayValuesVisible.collect { visible ->
                _uiState.update { it.copy(overlayValuesVisible = visible) }
            }
        }

        viewModelScope.launch {
            settingsRepository.filmstripVisible.collect { visible ->
                _uiState.update { it.copy(filmstripVisible = visible) }
            }
        }

        viewModelScope.launch {
            settingsRepository.detailsVisible.collect { visible ->
                _uiState.update { it.copy(detailsVisible = visible) }
            }
        }

        viewModelScope.launch {
            settingsRepository.hasSeenFullscreenGestureHint.collect { seen ->
                _uiState.update { it.copy(hasSeenFullscreenHint = seen) }
            }
        }

        viewModelScope.launch {
            settingsRepository.hasSeenNavHint.collect { seen ->
                _uiState.update { it.copy(hasSeenNavHint = seen) }
            }
        }

        // A card whose hint has just been recorded as seen goes with it, and
        // "Reset guidance" arrives through the same flow — so the reset brings
        // the explanations back without any second code path.
        viewModelScope.launch {
            settingsRepository.seenHints.collect { seen ->
                _uiState.update {
                    it.copy(
                        seenHints = seen,
                        pendingHint = SelectorGuidance.retainPending(it.pendingHint, seen),
                    )
                }
            }
        }

        // Both are read by the filing explanation, which names the folder the
        // photograph is actually in rather than the default one.
        viewModelScope.launch {
            settingsRepository.selectionFolderName.collect { name ->
                _uiState.update { it.copy(selectionFolderName = name) }
            }
        }

        viewModelScope.launch {
            settingsRepository.sortingEnabled.collect { enabled ->
                _uiState.update { it.copy(sortingEnabled = enabled) }
            }
        }

        viewModelScope.launch {
            settingsRepository.lastFolderUri.collect { uri ->
                if (uri != null && _uiState.value.folderUri == null) {
                    selectFolder(Uri.parse(uri))
                }
            }
        }
    }

    // ── Folder selection and progressive loading ─────────────────────────

    /**
     * Reset everything that belongs to the folder being left.
     *
     * One function, called from every path that changes folder, because the
     * failure mode of forgetting one field is silent: a surviving
     * [publishedUris] de-duplicates the *new* folder's first batch against the
     * old folder's URIs and the screen stays empty with no error anywhere.
     */
    private fun resetSession() {
        commitPendingDeletion()
        discoveryJob?.cancel()
        visibleDimensionsJob?.cancel()
        backfillDimensionsJob?.cancel()
        scoreRestoreJob?.cancel()
        scanJob?.cancel()
        groupingJob?.cancel()
        discoveryJob = null
        visibleDimensionsJob = null
        backfillDimensionsJob = null
        scoreRestoreJob = null
        scanJob = null
        groupingJob = null
        publishedUris.clear()
        dimensionsResolved.clear()
        cancelAllPrefetch()
        loadedExifCache.clear()
        workQueue = SelectorWorkQueue.reset()
        pendingScanAesthetic = false
        _uiState.update {
            it.copy(
                images = emptyList(),
                currentIndex = 0,
                groups = emptyList(),
                isScanRunning = false,
                isGroupingRunning = false,
                queuedWork = null,
                scanProgress = 0f,
                scanStatusText = "",
                snackbarMessage = null,
                undoOperation = null,
                pendingDeletion = null,
            )
        }
    }

    fun selectFolder(uri: Uri) {
        resetSession()
        discoveryJob = viewModelScope.launch {
            _uiState.update {
                it.copy(
                    isLoading = true,
                    isEnumerating = true,
                    error = null,
                    folderUri = uri.toString()
                )
            }

            // Claiming the folder — persisting the grant and confirming it is
            // still there — belongs to the repository, not here. See
            // [ImageRepository.openFolder].
            val folderName = imageRepository.openFolder(context, uri)
            if (folderName == null) {
                _uiState.update { it.copy(isLoading = false, isEnumerating = false) }
                reportError("Failed to load folder: permission revoked or directory deleted.")
                settingsRepository.setLastFolderUri(null)
                return@launch
            }

            _uiState.update { it.copy(folderName = folderName) }

            settingsRepository.setLastFolderUri(uri.toString())

            collectDiscovery(uri, "images") { e ->
                if (e is SecurityException) settingsRepository.setLastFolderUri(null)
            }
        }
    }

    /**
     * The shared tail of folder selection: stream, merge append-only, publish.
     *
     * Emissions are cumulative, so each one is merged against [publishedUris]
     * rather than replacing the list. Three things deliberately do **not** run
     * per batch:
     *
     * - `currentIndex = 0`, which would drag the photographer back to frame 1
     *   every time another 250 files finished enumerating.
     * - grouping, which rebuilds the candidate list they are looking at.
     * - the cached-score restore, which is a per-image cache read over the whole
     *   list; it is debounced onto the settled list instead.
     */
    private suspend fun collectDiscovery(
        folderUri: Uri,
        errorLabel: String,
        onError: suspend (Throwable) -> Unit = {},
    ) {
        try {
            imageRepository.discoverImages(folderUri).collect { batch ->
                publishBatch(batch)
            }
            _uiState.update { it.copy(isLoading = false, isEnumerating = false) }
            // Enumeration has settled: restore scores over the complete list and
            // pick up the tail of the dimensions nobody has asked for yet.
            scheduleScoreRestore(immediate = true)
            startDimensionBackfill(force = true)
            if (_uiState.value.groupingEnabled && _uiState.value.images.isNotEmpty()) {
                requestGrouping(settingsRepository.groupingLevel.first())
            }
        } catch (e: CancellationException) {
            // A newer discovery owns the state now — do not touch it.
            throw e
        } catch (e: Exception) {
            Log.e("SelectorViewModel", "Failed to discover images in $folderUri", e)
            _uiState.update { it.copy(isLoading = false, isEnumerating = false) }
            reportError("Failed to load $errorLabel: ${e.message}")
            onError(e)
        }
    }

    /** Merge one cumulative batch into the visible list, append-only. */
    private fun publishBatch(batch: List<ImageItem>) {
        val isFirstBatch = publishedUris.isEmpty()
        val fresh = ProgressiveMerge.newItems(batch, publishedUris)
        if (fresh.isEmpty() && !isFirstBatch) {
            _uiState.update { it.copy(isLoading = false) }
            return
        }
        publishedUris += fresh.map { it.uri }

        // Merged *inside* the update rather than from a snapshot read before it:
        // the dimension backfill publishes from `Dispatchers.IO`, so a snapshot
        // taken out here could be stale by the time it is written back, silently
        // dropping the aspect ratios that had just arrived. `fresh` is already
        // de-duplicated, so the append itself is pure and safe to retry.
        _uiState.update { current ->
            val merged = ProgressiveMerge.append(
                current = current.images,
                currentIndex = current.currentIndex,
                batch = fresh,
                published = emptySet(),
                isFirstBatch = isFirstBatch,
            )
            current.copy(
                images = merged.images,
                currentIndex = merged.currentIndex,
                isLoading = false,
            )
        }

        if (isFirstBatch) {
            loadMetadataForActiveRange()
            resolveVisibleDimensions()
            prefetchNeighbours()
        }
        startDimensionBackfill()
        scheduleScoreRestore()
    }

    // ── Navigation ───────────────────────────────────────────────────────

    fun navigateToImage(index: Int) {
        val images = _uiState.value.images
        if (index in images.indices) {
            _uiState.update { it.copy(currentIndex = index) }
            onFrameChanged()
        }
    }

    fun navigateNext() {
        val state = _uiState.value
        if (state.currentIndex < state.images.size - 1) {
            _uiState.update { it.copy(currentIndex = state.currentIndex + 1) }
            onFrameChanged()
        }
    }

    fun navigatePrevious() {
        val state = _uiState.value
        if (state.currentIndex > 0) {
            _uiState.update { it.copy(currentIndex = state.currentIndex - 1) }
            onFrameChanged()
        }
    }

    /** Everything the frame under judgement changing implies. */
    private fun onFrameChanged() {
        loadMetadataForActiveRange()
        resolveVisibleDimensions()
        prefetchNeighbours()
    }

    // ── Scanning, grouping, and the queue between them ───────────────────

    fun startScan(aestheticEnabled: Boolean = false) {
        if (_uiState.value.images.isEmpty()) return
        pendingScanAesthetic = aestheticEnabled
        applyWorkDecision(SelectorWorkQueue.request(workQueue, SelectorWork.SCAN))
    }

    private fun requestGrouping(level: GroupingLevel) {
        pendingGroupingLevel = level
        applyWorkDecision(SelectorWorkQueue.request(workQueue, SelectorWork.GROUPING))
    }

    private fun applyWorkDecision(outcome: Pair<WorkQueueState, WorkDecision>) {
        workQueue = outcome.first
        publishWorkState()
        when (val decision = outcome.second) {
            is WorkDecision.Start -> when (decision.work) {
                SelectorWork.SCAN -> runScan(pendingScanAesthetic)
                SelectorWork.GROUPING -> runGrouping(pendingGroupingLevel)
            }
            is WorkDecision.Queue, WorkDecision.Idle -> Unit
        }
    }

    private fun publishWorkState() {
        _uiState.update {
            it.copy(
                isScanRunning = workQueue.isScanning,
                isGroupingRunning = workQueue.isGrouping,
                queuedWork = workQueue.queued,
            )
        }
    }

    /** The waiting request is dropped; whatever is running carries on. */
    fun cancelQueuedWork() {
        workQueue = SelectorWorkQueue.cancelQueued(workQueue)
        publishWorkState()
    }

    private fun finishWork(work: SelectorWork) {
        applyWorkDecision(SelectorWorkQueue.finish(workQueue, work))
    }

    private fun runScan(aestheticEnabled: Boolean) {
        val images = _uiState.value.images
        if (images.isEmpty()) {
            finishWork(SelectorWork.SCAN)
            return
        }

        scanJob?.cancel()
        scanJob = viewModelScope.launch {
            _uiState.update {
                it.copy(
                    scanProgress = 0f,
                    scanStatusText = SelectorLabels.scanProgress(0, images.size),
                    error = null,
                )
            }

            var analysed = 0
            try {
                scanImagesUseCase(images, aestheticEnabled).collect { progress ->
                    val fraction = if (progress.total > 0) {
                        progress.processed.toFloat() / progress.total.toFloat()
                    } else {
                        0f
                    }
                    analysed = progress.processed

                    // Merged *inside* the update, against the state as it is at
                    // that moment. Building the new list from a snapshot read
                    // beforehand loses whatever landed in between — the EXIF and
                    // dimension loads run on their own coroutines and a scan is
                    // long.
                    _uiState.update { state ->
                        val merged = ScoreMerge.apply(state.images, progress.results)
                        state.copy(
                            scanProgress = fraction,
                            scanStatusText = SelectorLabels.scanProgress(
                                progress.processed,
                                progress.total,
                            ),
                            images = merged,
                        )
                    }
                }

                _uiState.update {
                    it.copy(
                        scanProgress = 1f,
                        scanStatusText = "",
                        snackbarMessage = SelectorLabels.scanCompleteMessage(analysed),
                        undoOperation = null,
                    )
                }
            } catch (e: CancellationException) {
                throw e
            } catch (e: Exception) {
                _uiState.update { it.copy(scanProgress = 0f, scanStatusText = "") }
                reportError("Scan failed: ${e.message}")
            } finally {
                finishWork(SelectorWork.SCAN)
            }
        }
    }

    fun cancelScan() {
        scanJob?.cancel()
        scanJob = null
        _uiState.update { it.copy(scanProgress = 0f, scanStatusText = "") }
        finishWork(SelectorWork.SCAN)
    }

    private fun runGrouping(level: GroupingLevel) {
        val images = _uiState.value.images
        if (images.isEmpty()) {
            _uiState.update { it.copy(groups = emptyList()) }
            finishWork(SelectorWork.GROUPING)
            return
        }

        groupingJob?.cancel()
        groupingJob = viewModelScope.launch {
            try {
                val groupedImages = imageGrouper.groupImages(images, level)
                val indexByUri = images.withIndex().associate { (i, img) -> img.uri to i }
                val indexGroups = groupedImages.map { group ->
                    group.mapNotNull { grouped -> indexByUri[grouped.uri] }
                }.filter { it.isNotEmpty() }

                _uiState.update { it.copy(groups = indexGroups, groupingEnabled = true) }
            } catch (e: CancellationException) {
                throw e
            } catch (e: Exception) {
                reportError("Grouping failed: ${e.message}")
            } finally {
                finishWork(SelectorWork.GROUPING)
            }
        }
    }

    /** Stop a grouping pass that is running or waiting. */
    private fun cancelGroupingWork() {
        groupingJob?.cancel()
        groupingJob = null
        if (workQueue.queued == SelectorWork.GROUPING) cancelQueuedWork()
        if (workQueue.isGrouping) finishWork(SelectorWork.GROUPING)
    }

    fun toggleGrouping() {
        viewModelScope.launch {
            val current = settingsRepository.groupingEnabled.first()
            settingsRepository.setGroupingEnabled(!current)
        }
    }

    fun setGroupingLevel(level: GroupingLevel) {
        viewModelScope.launch {
            settingsRepository.setGroupingLevel(level)
        }
    }

    // ── Deletion (deferred) ──────────────────────────────────────────────

    fun showDeleteConfirmation() {
        _uiState.update { it.copy(showDeleteConfirmation = true) }
    }

    fun dismissDeleteConfirmation() {
        _uiState.update { it.copy(showDeleteConfirmation = false) }
    }

    /**
     * Delete the current frame, skipping the dialog only when the file can be
     * recovered from the system trash.
     *
     * Called from the labelled Delete control, the `Del` key and the context
     * menu — never from a swipe. A swipe used to invoke this on the phone
     * layout, which made the same horizontal gesture mean "next frame" in the
     * viewer and "destroy this file" in the feed; that binding is gone.
     */
    fun requestDelete() {
        val state = _uiState.value
        if (state.images.isEmpty()) return

        val currentImage = state.images[state.currentIndex]
        val uri = Uri.parse(currentImage.uri)

        if (imageRepository.canTrash(uri)) {
            deleteCurrentImage()
        } else {
            showDeleteConfirmation()
        }
    }

    /**
     * Remove the current frame from the list now and delete it from disk when
     * the undo window closes.
     *
     * Nothing touches the file system here, which is what makes the UNDO
     * trustworthy: reverting is a list insertion, so it cannot fail. The commit
     * runs on [appScope] — a deletion that vanishes because the photographer
     * backed out of the screen is a data-integrity bug, not a cancelled task.
     */
    fun deleteCurrentImage() {
        // Another destructive action arriving closes the previous window.
        commitPendingDeletion()

        val state = _uiState.value
        val (listState, pending) =
            DeferredDeletion.beginForCurrent(state.listState, System.currentTimeMillis())
                ?: run {
                    _uiState.update { it.copy(showDeleteConfirmation = false) }
                    return
                }

        _uiState.update {
            it.copy(
                images = listState.images,
                currentIndex = listState.currentIndex,
                showDeleteConfirmation = false,
                pendingDeletion = pending,
                snackbarMessage = SelectorLabels.deletedMessage(pending.slots.size),
                undoOperation = UndoPolicy.forPendingDelete(pending),
            )
        }
        onFrameChanged()
        // The frame is gone from the list and nothing has touched the disk. That
        // second half is invisible, so it is said once.
        raiseHint(SelectorHint.DELETE_UNDO)

        deletionTimerJob?.cancel()
        deletionTimerJob = appScope.launch {
            delay(DeferredDeletion.UNDO_WINDOW_MILLIS)
            commitPendingDeletion()
        }
    }

    /**
     * Write the pending deletion to disk.
     *
     * Triggered by the window closing, by another destructive or filing action,
     * by a folder change, and by the screen being left ([onCleared]).
     */
    private fun commitPendingDeletion() {
        val pending = _uiState.value.pendingDeletion ?: return
        deletionTimerJob?.cancel()
        deletionTimerJob = null
        _uiState.update { it.copy(pendingDeletion = null) }

        val canTrash = pending.uris.all { imageRepository.canTrash(Uri.parse(it)) }

        appScope.launch {
            var failures = 0
            pending.uris.forEach { uri ->
                val deleted = try {
                    imageRepository.deleteImage(context, Uri.parse(uri))
                } catch (e: Exception) {
                    Log.e("SelectorViewModel", "Delete failed for $uri", e)
                    false
                }
                if (!deleted) failures++
            }

            _uiState.update { state ->
                val offered = state.undoOperation
                // Only this deletion's own UNDO is rewritten. Once on disk, the
                // list restore is honest only where the backend kept the file:
                // a SAF delete is an unlink with nothing behind it, so the
                // affordance disappears rather than lying about what it does.
                if (offered is UndoableOperation.RevertPendingDelete &&
                    offered.pending == pending
                ) {
                    state.copy(
                        undoOperation = UndoPolicy.forCommittedDelete(pending.slots, canTrash),
                    )
                } else {
                    state
                }
            }

            if (failures > 0) {
                reportError(
                    if (failures == 1) "1 image could not be deleted"
                    else "$failures images could not be deleted"
                )
            }
        }
    }

    // ── Filing (optimistic) ──────────────────────────────────────────────

    fun moveToSelection() = performFiling(CurationAction.MOVE)

    fun copyToSelection() = performFiling(CurationAction.COPY)

    /**
     * Apply the filing action to the list immediately and transfer behind it.
     *
     * No spinner and no `isLoading`: the whole point is that filing a frame
     * costs the photographer nothing, and a 60 MB raw copied over SAF is exactly
     * the moment the app must not stall. The transfer runs on [appScope] so it
     * finishes even if the selector is left mid-copy.
     *
     * On failure the list rewinds through [OptimisticEdits.rollback], which
     * re-derives the index from the URI on screen rather than a stored integer —
     * and rewinds **nothing** for a copy, because the source file never left.
     */
    private fun performFiling(action: CurationAction) {
        val state = _uiState.value
        val folderUri = state.folderUri ?: return
        if (state.images.isEmpty()) return

        // A filing action is the next action: it closes any open undo window.
        commitPendingDeletion()

        val before = _uiState.value.listState
        val sourceUri = before.currentUri ?: return
        val edit = OptimisticEdits.applyToCurrent(before, action)

        _uiState.update {
            it.copy(
                images = edit.state.images,
                currentIndex = edit.state.currentIndex,
                // One sentence, one source: the hint card heading is generated by
                // this same call, so the card and the snackbar beside it cannot
                // disagree about the verb or name a folder the user renamed away.
                snackbarMessage = SelectionActionLabels.confirmation(
                    action = if (action == CurationAction.MOVE) {
                        FilingAction.MOVE
                    } else {
                        FilingAction.COPY
                    },
                    selectionFolderName = state.selectionFolderName,
                ),
                // Populated once the transfer reports where the file went; a
                // move with no destination URI is not reversible.
                undoOperation = null,
            )
        }
        onFrameChanged()
        // The photograph left the centre of the screen and nothing on it says
        // where it went. This is the explanation that matters most.
        raiseHint(SelectorHint.FILING)

        appScope.launch {
            val result = try {
                val sorting = settingsRepository.sortingEnabled.first()
                val destination = Uri.parse(folderUri)
                val source = Uri.parse(sourceUri)
                if (action == CurationAction.COPY) {
                    imageRepository.copyImage(context, source, destination, sorting)
                } else {
                    imageRepository.moveImage(context, source, destination, sorting)
                }
            } catch (e: Exception) {
                Log.e("SelectorViewModel", "${action.name} failed for $sourceUri", e)
                null
            }

            if (result != null && result.success) {
                val undo = UndoPolicy.forFiling(
                    action = action,
                    slots = edit.slots,
                    sourceUri = sourceUri,
                    destinationUri = result.destinationUri,
                )
                _uiState.update { current ->
                    // Only attach the undo if this action still owns the
                    // snackbar; a later action must not inherit it.
                    if (current.undoOperation == null && current.snackbarMessage != null) {
                        current.copy(undoOperation = undo)
                    } else {
                        current
                    }
                }
            } else {
                rollbackFiling(edit.action, edit.slots)
                val verb = if (action == CurationAction.COPY) "Copy" else "Move"
                reportError("$verb failed: ${result?.error ?: "the file could not be transferred"}")
            }
        }
    }

    private fun rollbackFiling(action: CurationAction, slots: List<ImageSlot>) {
        _uiState.update { state ->
            val restored = OptimisticEdits.rollback(state.listState, action, slots)
            state.copy(
                images = restored.images,
                currentIndex = restored.currentIndex,
                undoOperation = null,
            )
        }
    }

    // ── Undo ─────────────────────────────────────────────────────────────

    /**
     * Reverse the last action, where `UndoPolicy` said that was possible.
     *
     * The three cases are genuinely different operations, not one operation with
     * flags: a pending delete is a list insertion, a committed delete is a trash
     * restore, and a move is a file operation back into the opened folder.
     */
    fun undoLastOperation() {
        val state = _uiState.value
        when (val operation = state.undoOperation) {
            null -> return

            is UndoableOperation.RevertPendingDelete -> {
                deletionTimerJob?.cancel()
                deletionTimerJob = null
                val restored = DeferredDeletion.revert(state.listState, operation.pending)
                _uiState.update {
                    it.copy(
                        images = restored.images,
                        currentIndex = restored.currentIndex,
                        pendingDeletion = null,
                        undoOperation = null,
                        snackbarMessage = null,
                    )
                }
                onFrameChanged()
            }

            is UndoableOperation.RestoreFromTrash -> {
                val restored = OptimisticEdits.restore(state.listState, operation.slots)
                _uiState.update {
                    it.copy(
                        images = restored.images,
                        currentIndex = restored.currentIndex,
                        undoOperation = null,
                        snackbarMessage = null,
                    )
                }
                onFrameChanged()
                appScope.launch {
                    operation.uris.forEach { uri ->
                        val ok = try {
                            imageRepository.restoreFromTrash(context, Uri.parse(uri))
                        } catch (e: Exception) {
                            Log.e("SelectorViewModel", "Restore from trash failed for $uri", e)
                            false
                        }
                        if (!ok) reportError("Could not restore the deleted image")
                    }
                }
            }

            is UndoableOperation.ReverseMove -> {
                val folderUri = state.folderUri ?: return
                val restored = OptimisticEdits.restore(state.listState, operation.slots)
                _uiState.update {
                    it.copy(
                        images = restored.images,
                        currentIndex = restored.currentIndex,
                        undoOperation = null,
                        snackbarMessage = null,
                    )
                }
                onFrameChanged()
                appScope.launch {
                    val result = try {
                        imageRepository.undoMove(
                            context,
                            Uri.parse(operation.destinationUri),
                            Uri.parse(folderUri),
                        )
                    } catch (e: Exception) {
                        Log.e("SelectorViewModel", "Undo move failed", e)
                        null
                    }
                    if (result == null || !result.success) {
                        reportError("Could not move the image back")
                    }
                }
            }
        }
    }

    /** The snackbar has timed out or been dismissed; its undo goes with it. */
    fun dismissSnackbar() {
        _uiState.update { it.copy(snackbarMessage = null, undoOperation = null) }
    }

    // ── Misc actions ─────────────────────────────────────────────────────

    fun clearScores() {
        viewModelScope.launch {
            try {
                cacheRepository.clearAll()

                val clearedImages = _uiState.value.images.map { image ->
                    image.copy(scanResult = null)
                }
                _uiState.update { it.copy(images = clearedImages) }
            } catch (e: Exception) {
                reportError("Failed to clear cache: ${e.message}")
            }
        }
    }

    /**
     * Fill the image region with one frame, or return to three-up.
     *
     * Passing the frame that is already maximised toggles back out, so the same
     * control and the same key both open and close it.
     */
    fun toggleMaximised(frame: SelectorFrame) {
        val entering = _uiState.value.maximisedFrame != frame
        _uiState.update {
            it.copy(maximisedFrame = if (it.maximisedFrame == frame) null else frame)
        }
        // Nothing on the maximised screen says how to get back out, so it is
        // said once, on the way in.
        if (entering) raiseHint(SelectorHint.MAXIMISE)
    }

    /** Leave the maximised state, if in it. Bound to Escape. */
    fun clearMaximised() {
        if (_uiState.value.maximisedFrame != null) {
            _uiState.update { it.copy(maximisedFrame = null) }
        }
    }

    /** Persist that the one-time on-image navigation arrows have now been shown. */
    fun markNavHintSeen() {
        viewModelScope.launch {
            if (!settingsRepository.hasSeenNavHint.first()) {
                settingsRepository.setHasSeenNavHint(true)
            }
        }
    }

    /** Show or hide the filmstrip; the choice survives relaunch. */
    fun toggleFilmstrip() {
        viewModelScope.launch {
            settingsRepository.setFilmstripVisible(!settingsRepository.filmstripVisible.first())
        }
    }

    /** Show or hide the readout block; the choice survives relaunch. */
    fun toggleDetails() {
        viewModelScope.launch {
            settingsRepository.setDetailsVisible(!settingsRepository.detailsVisible.first())
        }
    }

    /** Show or hide the neighbour value overlays; the choice survives relaunch. */
    fun toggleOverlayValues() {
        viewModelScope.launch {
            settingsRepository.setOverlayValuesVisible(
                !settingsRepository.overlayValuesVisible.first()
            )
        }
    }

    // ── One-time guidance ────────────────────────────────────────────────

    /**
     * Offer an explanation, if this one has not been given before.
     *
     * The decision is [SelectorGuidance.nextHint]'s, not this method's: whether
     * a hint is a card at all, whether it has been seen, and what happens to one
     * already on screen are policy, and policy that lives in a ViewModel method
     * is policy no JVM test can reach.
     */
    private fun raiseHint(hint: SelectorHint) {
        _uiState.update {
            it.copy(
                pendingHint = SelectorGuidance.nextHint(
                    candidate = hint,
                    seen = it.seenHints,
                    current = it.pendingHint,
                )
            )
        }
    }

    /**
     * The explanation has been read, dismissed, or has timed out.
     *
     * Persisted rather than merely cleared: it fires exactly once, ever, until
     * *Reset guidance*. Clearing the field locally as well means the card goes
     * immediately rather than on the DataStore round trip.
     */
    fun dismissHint() {
        val hint = _uiState.value.pendingHint ?: return
        _uiState.update { it.copy(pendingHint = null) }
        viewModelScope.launch { settingsRepository.markHintSeen(hint) }
    }

    /** Persist that the coach-mark guide has been seen, so it stops opening itself. */
    fun markGuideSeen() {
        if (SelectorHint.TOUR in _uiState.value.seenHints) return
        viewModelScope.launch { settingsRepository.markHintSeen(SelectorHint.TOUR) }
    }

    /** Persist that the fullscreen gesture hint has been dismissed. */
    fun markFullscreenHintSeen() {
        viewModelScope.launch {
            if (!settingsRepository.hasSeenFullscreenGestureHint.first()) {
                settingsRepository.setHasSeenFullscreenGestureHint(true)
            }
        }
    }

    fun clearError() {
        _uiState.update { it.copy(error = null) }
    }

    fun setError(message: String) = reportError(message)

    /** Errors reach the photographer through the same snackbar as everything else. */
    private fun reportError(message: String) {
        _uiState.update {
            it.copy(error = message, snackbarMessage = message, undoOperation = null)
        }
    }

    // ── EXIF, dimensions, prefetch ───────────────────────────────────────

    private val loadedExifCache = object : LinkedHashMap<String, ExifData>(64, 0.75f, true) {
        override fun removeEldestEntry(eldest: MutableMap.MutableEntry<String, ExifData>?): Boolean {
            return size > MAX_EXIF_CACHE_SIZE
        }
    }

    private fun loadMetadataForActiveRange() {
        val state = _uiState.value
        val images = state.images
        if (images.isEmpty()) return

        val indicesToLoad = SelectorWindows.visibleIndices(state.currentIndex, images.size)

        viewModelScope.launch {
            indicesToLoad.forEach { index ->
                val image = images.getOrNull(index) ?: return@forEach
                if (image.exifData == null) {
                    val cachedExif = loadedExifCache[image.uri]
                    if (cachedExif != null) {
                        updateImageExif(image.uri, cachedExif)
                    } else {
                        val exif = imageRepository.getExifData(context, Uri.parse(image.uri))
                        if (exif != null) {
                            loadedExifCache[image.uri] = exif
                            updateImageExif(image.uri, exif)
                        }
                    }
                }
            }
        }
    }

    private fun updateImageExif(uri: String, exif: ExifData) {
        _uiState.update { state ->
            val updatedImages = state.images.map { img ->
                if (img.uri == uri) img.copy(exifData = exif) else img
            }
            state.copy(images = updatedImages)
        }
    }

    /**
     * Resolve dimensions for the frames actually on screen.
     *
     * Enumeration no longer reads image headers — that is why folders open fast
     * — so the aspect ratio the frame solver wants arrives here instead. This is
     * a progressive-enhancement path and never a blocking one: until it lands,
     * `FrameGeometry` uses its documented 3:2 default and the frames are drawn
     * anyway (REQUIREMENTS §7, "Dimensions Are Resolved Off the Enumeration
     * Path").
     *
     * Restarted on navigation, unlike [startDimensionBackfill], because it is at
     * most a handful of URIs and the photographer is waiting on precisely these.
     */
    private fun resolveVisibleDimensions() {
        val state = _uiState.value
        if (state.images.isEmpty()) return

        val wanted = SelectorWindows.metadataIndices(state.currentIndex, state.images.size)
            .mapNotNull { state.images.getOrNull(it) }
            .filter { it.aspectRatio == null && it.uri !in dimensionsResolved }
            .map { it.uri }
        if (wanted.isEmpty()) return

        visibleDimensionsJob?.cancel()
        visibleDimensionsJob = viewModelScope.launch {
            val resolved = try {
                imageRepository.resolveDimensions(context, wanted)
            } catch (e: CancellationException) {
                throw e
            } catch (e: Exception) {
                Log.e("SelectorViewModel", "Dimension resolution failed", e)
                emptyMap()
            }
            // Marked only once the read has actually happened, so a cancelled
            // pass does not leave URIs permanently claimed and unresolved.
            dimensionsResolved += resolved.keys
            applyDimensions(resolved)
        }
    }

    /**
     * Fill in the dimensions of everything else, nearest to the photographer
     * first.
     *
     * Results are applied in batches of [DIMENSION_BATCH_SIZE] rather than per
     * image: a per-image state update in an 842-frame folder is 842
     * recompositions of the whole selector for information almost none of the
     * frames on screen needed.
     *
     * Deliberately **not** restarted per navigation or per discovery batch —
     * cancelling and re-sorting each time would throw away in-flight work and
     * re-read headers already read. [dimensionsResolved] makes each URI cost one
     * open, ever, including the ones that turn out to be unreadable.
     */
    private fun startDimensionBackfill(force: Boolean = false) {
        if (!force && backfillDimensionsJob?.isActive == true) return
        backfillDimensionsJob?.cancel()
        backfillDimensionsJob = viewModelScope.launch(Dispatchers.IO) {
            val state = _uiState.value
            val images = state.images
            if (images.isEmpty()) return@launch

            val pending = SelectorWindows.dimensionOrder(state.currentIndex, images.size)
                .mapNotNull { images.getOrNull(it) }
                .filter { it.aspectRatio == null && it.uri !in dimensionsResolved }
                .map { it.uri }

            pending.chunked(DIMENSION_BATCH_SIZE).forEach { chunk ->
                val remaining = chunk.filterNot { it in dimensionsResolved }
                if (remaining.isEmpty()) return@forEach
                val resolved = try {
                    imageRepository.resolveDimensions(context, remaining)
                } catch (e: CancellationException) {
                    throw e
                } catch (e: Exception) {
                    Log.e("SelectorViewModel", "Dimension backfill failed", e)
                    emptyMap()
                }
                dimensionsResolved += resolved.keys
                applyDimensions(resolved)
            }
        }
    }

    /** One state update per batch, so recomposition stays bounded. */
    private fun applyDimensions(dimensions: Map<String, ImageDimensions>) {
        val known = dimensions.filterValues { it.isKnown }
        if (known.isEmpty()) return
        _uiState.update { state ->
            state.copy(
                images = state.images.map { image ->
                    val dims = known[image.uri] ?: return@map image
                    if (image.imageWidth == dims.width && image.imageHeight == dims.height) {
                        image
                    } else {
                        image.copy(imageWidth = dims.width, imageHeight = dims.height)
                    }
                }
            )
        }
    }

    /**
     * Warm the frames the photographer is about to reach.
     *
     * The three-up layout already decodes current ± 1, so this covers what is
     * beyond that — the desktop product's `preload_next_candidates`, in Coil
     * terms. Requests are sized to a frame rather than to the original, because
     * decoding a 6192 × 4128 raw to fill a 675 dp tile spends memory and time on
     * pixels nobody will see.
     *
     * Stale requests are disposed rather than left running: on a fast scrub
     * through a burst the frames enqueued three navigations ago are competing
     * with the ones on screen. Requests still inside the window are left alone,
     * so a scrub does not restart work already half done.
     */
    private fun prefetchNeighbours() {
        val state = _uiState.value
        if (state.images.isEmpty()) return

        val wanted = SelectorWindows.prefetchIndices(state.currentIndex, state.images.size)
            .mapNotNull { state.images.getOrNull(it)?.uri }
            .toSet()

        prefetchRequests.keys.toList().forEach { uri ->
            if (uri !in wanted) {
                prefetchRequests.remove(uri)?.dispose()
            }
        }

        // Prefetch is an optimisation, never a requirement: any failure to warm
        // a frame must leave the visible decode exactly as it was.
        try {
            val loader = Coil.imageLoader(context)
            wanted.forEach { uri ->
                if (prefetchRequests[uri]?.isDisposed == false) return@forEach
                val request = ImageRequest.Builder(context)
                    .data(uri)
                    .size(PREFETCH_WIDTH_PX, PREFETCH_HEIGHT_PX)
                    .scale(Scale.FIT)
                    .precision(Precision.INEXACT)
                    .build()
                prefetchRequests[uri] = loader.enqueue(request)
            }
        } catch (e: Exception) {
            Log.w("SelectorViewModel", "Neighbour prefetch unavailable", e)
        }
    }

    private fun cancelAllPrefetch() {
        prefetchRequests.values.forEach { it.dispose() }
        prefetchRequests.clear()
    }

    /**
     * Restore cached scan scores from Room.
     *
     * Debounced rather than run per discovery batch: it is a cache read per
     * image over the whole list, and running it on every cumulative emission
     * re-reads the same rows once per batch for no new information.
     */
    private fun scheduleScoreRestore(immediate: Boolean = false) {
        scoreRestoreJob?.cancel()
        scoreRestoreJob = viewModelScope.launch {
            if (!immediate) delay(SCORE_RESTORE_DEBOUNCE_MILLIS)
            restoreCachedScores()
        }
    }

    private suspend fun restoreCachedScores() {
        val images = _uiState.value.images
        if (images.isEmpty()) return

        val updatedImages = withContext(Dispatchers.IO) {
            images.map { image ->
                if (image.scanResult != null) return@map image

                val cached = try {
                    scoreDao.getScore(image.uri)
                } catch (e: Exception) {
                    null
                } ?: return@map image

                // Validate cache entry matches current file
                if (cached.fileSize != image.fileSize || cached.lastModified != image.lastModified) {
                    return@map image
                }

                image.copy(
                    scanResult = ScanResult(
                        filePath = image.uri,
                        sharpnessScore = cached.sharpnessScore,
                        noiseLevel = cached.noiseLevel,
                        highlightClipping = cached.highlightClipping,
                        shadowClipping = cached.shadowClipping
                    )
                )
            }
        }

        // Only the scores travel forward out of the snapshot. See [ScoreMerge]
        // for why merging the items themselves is a rollback rather than a merge.
        val restored = ScoreMerge.scoresOf(updatedImages)
        _uiState.update { state ->
            state.copy(images = ScoreMerge.apply(state.images, restored))
        }
    }

    /**
     * The selector is going away.
     *
     * The pending deletion is committed here rather than dropped: the
     * photographer asked for it, the frame has been gone from the list for up to
     * thirty seconds, and a deletion that silently un-happens because a screen
     * was left is a data-integrity bug. The commit itself runs on [appScope], so
     * cancelling `viewModelScope` a moment later does not take it with it.
     */
    override fun onCleared() {
        super.onCleared()
        commitPendingDeletion()
        cancelAllPrefetch()
    }

    companion object {
        /** Maximum number of EXIF data entries to keep in memory. */
        private const val MAX_EXIF_CACHE_SIZE = 50

        /** Dimension results are applied to the UI state in batches of this size. */
        internal const val DIMENSION_BATCH_SIZE = 24

        /** Quiet period after the last discovery batch before scores are restored. */
        internal const val SCORE_RESTORE_DEBOUNCE_MILLIS = 400L

        /**
         * The size a prefetched frame is decoded at.
         *
         * A three-up frame is at most 675 × 450 dp, which is 1350 × 900 px at
         * the 2× density of the reference tablet. Rounded up once so a slightly
         * denser display still gets a usable cache entry, and no further: the
         * point of prefetching is to have the frame ready, not to have the
         * original in memory.
         */
        internal const val PREFETCH_WIDTH_PX = 1440
        internal const val PREFETCH_HEIGHT_PX = 1080
    }
}

package com.photoselectortoolbox.ui.selector

import android.app.Activity
import android.net.Uri
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.activity.result.contract.ActivityResultContracts.StartActivityForResult
import androidx.compose.foundation.ExperimentalFoundationApi
import androidx.compose.foundation.background
import androidx.compose.foundation.draganddrop.dragAndDropTarget
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.WindowInsets
import androidx.compose.foundation.layout.WindowInsetsSides
import androidx.compose.foundation.layout.fillMaxHeight
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.only
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.safeDrawing
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.layout.windowInsetsPadding
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.PhotoCamera
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.DropdownMenu
import androidx.compose.material3.DropdownMenuItem
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.FilledTonalButton
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.material3.windowsizeclass.WindowSizeClass
import androidx.compose.material3.windowsizeclass.WindowWidthSizeClass
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draganddrop.DragAndDropEvent
import androidx.compose.ui.draganddrop.DragAndDropTarget
import androidx.compose.ui.draganddrop.toAndroidDragEvent
import androidx.compose.ui.focus.FocusRequester
import androidx.compose.ui.focus.focusRequester
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.input.key.Key
import androidx.compose.ui.input.key.KeyEventType
import androidx.compose.ui.input.key.key
import androidx.compose.ui.input.key.onKeyEvent
import androidx.compose.ui.input.key.type
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.unit.IntOffset
import androidx.compose.ui.unit.dp
import androidx.compose.ui.window.Popup
import androidx.hilt.navigation.compose.hiltViewModel
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import com.photoselectortoolbox.domain.format.SelectorLabels
import com.photoselectortoolbox.ui.components.EmptyStateCard
import com.photoselectortoolbox.ui.theme.Zinc800
import com.photoselectortoolbox.ui.theme.Zinc900
import com.photoselectortoolbox.ui.navigation.Screen
import com.photoselectortoolbox.viewmodel.SelectorFrame
import com.photoselectortoolbox.viewmodel.SelectorViewModel

/**
 * The culling workspace.
 *
 * This composable owns orchestration only — folder pickers, dialogs, sheets,
 * keyboard handling and which layout is on screen. The layouts themselves live
 * in [ThreeUpSelectorLayout] and [CompactSelectorLayout], because the geometry
 * of each is intricate enough that mixing it with dialog plumbing is how the
 * two drift apart.
 *
 * There is no app bar. Session controls live in [SelectorSidebar] to the left;
 * everything else that used to sit in a bar — folder name, position, burst chip
 * — now sits beside the photograph it describes. On a layout bound by height
 * (see [FrameGeometry]) a 44dp bar is 29dp off every frame, which is a price
 * this screen does not pay for chrome.
 */
@OptIn(ExperimentalMaterial3Api::class, ExperimentalFoundationApi::class)
@Composable
fun SelectorScreen(
    windowSizeClass: WindowSizeClass,
    currentRoute: String? = null,
    onNavigate: (Screen) -> Unit = {},
    viewModel: SelectorViewModel = hiltViewModel(),
) {
    val uiState by viewModel.uiState.collectAsStateWithLifecycle()
    val context = LocalContext.current
    val focusRequester = remember { FocusRequester() }

    var showScanConfig by remember { mutableStateOf(false) }
    var showFullscreen by remember { mutableStateOf(false) }
    var showMenu by remember { mutableStateOf(false) }
    var showGuide by remember { mutableStateOf(false) }
    var contextMenuAt by remember { mutableStateOf<Offset?>(null) }
    var lastPointerPosition by remember { mutableStateOf(Offset.Zero) }

    val isExpanded = windowSizeClass.widthSizeClass == WindowWidthSizeClass.Expanded
    val isMedium = windowSizeClass.widthSizeClass == WindowWidthSizeClass.Medium
    val useExpandedLayout = isExpanded || isMedium

    // The guide opens by itself once, at first launch, and on demand thereafter.
    // Both routes are the same overlay and the same dismissal, so there is one
    // "seen" fact rather than two that can disagree.
    //
    // Never while a frame is maximised: the overlay reserves the three-up
    // footprints, so over a single filled frame its callouts would land on the
    // photograph — the one thing it exists not to do. Opening it therefore
    // leaves the maximised state first.
    val guideOpen = useExpandedLayout &&
        uiState.images.isNotEmpty() &&
        uiState.maximisedFrame == null &&
        (showGuide || uiState.showIntroTour)

    val openGuide: () -> Unit = {
        viewModel.clearMaximised()
        showGuide = true
    }

    // Any open sheet swallows the shortcuts, so a stray M while configuring a
    // scan cannot move the frame behind the sheet. Esc is the exception — it is
    // what closes the sheet.
    val sheetOpen = showScanConfig || guideOpen ||
        uiState.showDeleteConfirmation

    val dismissGuide: () -> Unit = {
        showGuide = false
        viewModel.markGuideSeen()
    }

    val dragAndDropTarget = remember(context, viewModel) {
        object : DragAndDropTarget {
            override fun onDrop(event: DragAndDropEvent): Boolean {
                val dragEvent = event.toAndroidDragEvent()
                (context as? Activity)?.requestDragAndDropPermissions(dragEvent)
                val clipData = dragEvent.clipData
                if (clipData != null && clipData.itemCount > 0) {
                    clipData.getItemAt(0).uri?.let { uri ->
                        viewModel.selectFolder(uri)
                        return true
                    }
                }
                return false
            }
        }
    }

    val folderPickerLauncher = rememberLauncherForActivityResult(
        contract = ActivityResultContracts.OpenDocumentTree()
    ) { uri: Uri? -> uri?.let { viewModel.selectFolder(it) } }

    // Move and Delete advance to the next frame; Copy stays put. That asymmetry
    // is the culling loop: a moved or deleted frame is finished with, a copied
    // one may still be compared against its neighbours.
    //
    // The confirmation wording no longer lives here. The message and its UNDO
    // are one fact about one operation, so they are decided together in the
    // ViewModel — a message set by the composable could outlive, or disagree
    // with, the operation it claims to describe.
    val actions = SelectorActions(
        onMove = viewModel::moveToSelection,
        onCopy = viewModel::copyToSelection,
        onDelete = { viewModel.requestDelete() },
        onFullscreen = { showFullscreen = true },
        onToggleDetails = viewModel::toggleDetails,
        onToggleFilmstrip = viewModel::toggleFilmstrip,
        onToggleOverlayValues = viewModel::toggleOverlayValues,
        onShowShortcuts = openGuide,
    )

    // Errors already reached the snackbar through the ViewModel; the sticky
    // field is cleared so the same failure does not re-announce itself.
    LaunchedEffect(uiState.error) {
        if (uiState.error != null) viewModel.clearError()
    }

    LaunchedEffect(uiState.images.isNotEmpty()) {
        if (uiState.images.isNotEmpty()) {
            try {
                focusRequester.requestFocus()
            } catch (_: Exception) {
                // The node may not be attached yet; the next state change retries.
            }
        }
    }

    if (uiState.showDeleteConfirmation) {
        AlertDialog(
            onDismissRequest = { viewModel.dismissDeleteConfirmation() },
            title = { Text("Delete Image") },
            text = {
                Text("Delete \"${uiState.currentImage?.fileName ?: ""}\"? This cannot be undone.")
            },
            confirmButton = {
                TextButton(
                    onClick = { viewModel.deleteCurrentImage() },
                    modifier = Modifier.testTag("dialog_confirm_delete"),
                ) {
                    Text("Delete", color = MaterialTheme.colorScheme.error)
                }
            },
            dismissButton = {
                TextButton(onClick = { viewModel.dismissDeleteConfirmation() }) { Text("Cancel") }
            },
            containerColor = Zinc800,
        )
    }



    if (showScanConfig) {
        ScanConfigSheet(
            onStartScan = { config ->
                showScanConfig = false
                viewModel.startScan(config.aesthetic)
            },
            onDismiss = { showScanConfig = false },
            isExpanded = useExpandedLayout,
        )
    }

    if (showFullscreen && uiState.images.isNotEmpty()) {
        FullscreenViewer(
            images = uiState.images,
            initialIndex = uiState.currentIndex,
            onDismiss = { showFullscreen = false },
            onDelete = { index ->
                viewModel.navigateToImage(index)
                viewModel.showDeleteConfirmation()
            },
            onMoveToSelection = { index ->
                viewModel.navigateToImage(index)
                viewModel.moveToSelection()
            },
            onCopyToSelection = { index ->
                viewModel.navigateToImage(index)
                viewModel.copyToSelection()
            },
            windowSizeClass = windowSizeClass,
            onPageSelected = viewModel::navigateToImage,
            fullscreenButtonsEnabled = uiState.fullscreenButtonsEnabled,
            filingAction = uiState.filingAction,
            showGestureHint = !uiState.hasSeenFullscreenHint,
            onGestureHintSeen = viewModel::markFullscreenHintSeen,
        )
    }

    Box(
        modifier = Modifier
            .fillMaxSize()
            .background(Zinc900)
            // Horizontal insets only, and that is a priced decision rather than
            // an omission. A display cutout or a rotated navigation bar clips
            // content on the *width*, which this layout has to spare. The
            // vertical system bars are 36 dp + 32 dp on the reference device
            // (measured); padding for them would cost 34 dp of height on all
            // three frames and put the reference frame at 416 dp, below the
            // documented floor. They are transparent under `enableEdgeToEdge()`
            // and overlay the outer 28 dp / 24 dp of the top and bottom frames;
            // a photographer who wants an unobstructed look has maximise and
            // fullscreen, both of which are already immersive. See
            // REQUIREMENTS §2 Edge-to-Edge and DESIGN §7.2.
            .windowInsetsPadding(WindowInsets.safeDrawing.only(WindowInsetsSides.Horizontal))
            .dragAndDropTarget(
                shouldStartDragAndDrop = { true },
                target = dragAndDropTarget,
            )
            .trackPointerPosition { lastPointerPosition = it }
            .then(
                if (uiState.images.isNotEmpty()) {
                    Modifier
                        .focusRequester(focusRequester)
                        .onKeyEvent { event ->
                            if (event.type != KeyEventType.KeyDown) return@onKeyEvent false
                            handleSelectorKey(
                                key = event.key,
                                sheetOpen = sheetOpen,
                                contextMenuOpen = contextMenuAt != null,
                                fullscreenOpen = showFullscreen,
                                maximised = uiState.maximisedFrame != null,
                                actions = actions,
                                onPrevious = viewModel::navigatePrevious,
                                onNext = viewModel::navigateNext,
                                onMaximise = viewModel::toggleMaximised,
                                onShowShortcuts = openGuide,
                                onCloseOverlays = {
                                    when {
                                        showFullscreen -> showFullscreen = false
                                        contextMenuAt != null -> contextMenuAt = null
                                        showScanConfig -> showScanConfig = false
                                        guideOpen -> dismissGuide()
                                        uiState.maximisedFrame != null -> viewModel.clearMaximised()
                                    }
                                },
                            )
                        }
                } else {
                    Modifier
                }
            ),
    ) {
        // One horizontal band: sidebar, then the frames. Nothing above, nothing
        // below. The 44dp app bar that used to sit here cost 29dp of height on
        // every one of the three frames — see FrameGeometry for why height is
        // the axis that must not be spent.
        Row(modifier = Modifier.fillMaxSize()) {
            if (useExpandedLayout) {
                SelectorSidebar(
                    currentRoute = currentRoute,
                    groupingEnabled = uiState.groupingEnabled,
                    hasImages = uiState.images.isNotEmpty(),
                    isScanning = uiState.isScanRunning,
                    scanStatusText = uiState.scanStatusText,
                    isGrouping = uiState.isGroupingRunning,
                    queuedWork = uiState.queuedWork,
                    onCancelQueued = viewModel::cancelQueuedWork,
                    onOpenFolder = { folderPickerLauncher.launch(null) },
                    onScan = { showScanConfig = true },
                    onCancelScan = viewModel::cancelScan,
                    onToggleGrouping = viewModel::toggleGrouping,
                    onShowLegend = openGuide,
                    onShowMenu = { showMenu = true },
                    onNavigate = onNavigate,
                    overflowContent = {
                        DropdownMenu(
                            expanded = showMenu,
                            onDismissRequest = { showMenu = false },
                        ) {
                            DropdownMenuItem(
                                text = { Text("Scan images") },
                                onClick = { showMenu = false; showScanConfig = true },
                                enabled = uiState.images.isNotEmpty() && !uiState.isScanRunning,
                            )
                            DropdownMenuItem(
                                text = { Text("Open folder") },
                                onClick = { showMenu = false; folderPickerLauncher.launch(null) },
                            )
                            DropdownMenuItem(
                                text = { Text("Clear scores") },
                                onClick = { showMenu = false; viewModel.clearScores() },
                                enabled = uiState.hasAnyScores,
                            )
                            DropdownMenuItem(
                                text = { Text("Shortcuts and guide") },
                                onClick = { showMenu = false; openGuide() },
                            )
                        }
                    },
                )
            }

            Column(modifier = Modifier.weight(1f).fillMaxSize()) {
                if (uiState.folderUri == null || uiState.images.isEmpty()) {
                    EmptySelectorState(
                        onOpenFolder = { folderPickerLauncher.launch(null) },
                    )
                } else {
                    // Tagged because the height budget is the thing this screen
                    // is judged on: a test can measure what the frames were
                    // actually offered, rather than inferring it from the frame
                    // that came out. Two revisions shipped small because the
                    // arithmetic was reasoned about instead of measured.
                    Box(
                        modifier = Modifier
                            .weight(1f)
                            .fillMaxWidth()
                            .testTag("image_region"),
                    ) {
                        if (useExpandedLayout) {
                            ThreeUpSelectorLayout(
                                current = uiState.currentImage,
                                previous = uiState.previousImage,
                                next = uiState.nextImage,
                                currentIndex = uiState.currentIndex,
                                total = uiState.images.size,
                                filingAction = uiState.filingAction,
                                folderName = uiState.folderName,
                                burstLabel = burstLabelFor(uiState.groups, uiState.currentIndex)
                                    .takeIf { uiState.groupingEnabled },
                                detailsVisible = uiState.detailsVisible,
                                filmstripVisible = uiState.filmstripVisible,
                                overlayValuesVisible = uiState.overlayValuesVisible,
                                maximisedFrame = uiState.maximisedFrame,
                                actions = actions,
                                onNavigatePrevious = viewModel::navigatePrevious,
                                onNavigateNext = viewModel::navigateNext,
                                onMaximise = viewModel::toggleMaximised,
                                onLongPressFrame = { contextMenuAt = lastPointerPosition },
                                showFirstRunHint = !uiState.hasSeenNavHint,
                                onDismissFirstRunHint = viewModel::markNavHintSeen,
                                stillEnumerating = uiState.isEnumerating,
                                // Suppressed while the guide is up: the guide is
                                // already explaining this screen, and two
                                // explanations of it at once is neither.
                                pendingHint = uiState.pendingHintText.takeIf { !guideOpen },
                                onDismissHint = viewModel::dismissHint,
                                // Passed as a slot and drawn as a vertical column
                                // at the outer edge of the control flank. It
                                // used to span the bottom of the window, which
                                // measured 38 dp off the height of every frame
                                // on the reference device — see FrameGeometry.
                                // The maximised state does not draw the flanks
                                // at all, so the strip disappears there without
                                // a second condition.
                                filmstrip = {
                                    CandidateStrip(
                                        images = uiState.images,
                                        currentIndex = uiState.currentIndex,
                                        onImageSelected = viewModel::navigateToImage,
                                        groups = if (uiState.groupingEnabled) {
                                            uiState.groups
                                        } else {
                                            null
                                        },
                                        modifier = Modifier.fillMaxHeight(),
                                    )
                                },
                            )
                        } else {
                            CompactSelectorLayout(
                                uiState = uiState,
                                onNavigateToImage = viewModel::navigateToImage,
                                onFullscreen = { showFullscreen = true },
                                onMoveToSelection = actions.onMove,
                                onCopyToSelection = actions.onCopy,
                                onDelete = actions.onDelete,
                                showGestureHint = !uiState.hasSeenFullscreenHint,
                                onDismissGestureHint = viewModel::markFullscreenHintSeen,
                            )
                        }
                    }
                }
            }
        }

        // `onUndo` is non-null only where `UndoPolicy` found something genuinely
        // reversible: a deferred delete, a trashable committed delete, or a move
        // that reported where the file went. A copy gets none — undoing it could
        // only mean deleting the file the photographer just asked for.
        SelectorSnackbar(
            message = uiState.snackbarMessage,
            onUndo = if (uiState.undoOperation != null) viewModel::undoLastOperation else null,
            onDismiss = viewModel::dismissSnackbar,
            modifier = Modifier
                .align(Alignment.BottomCenter)
                .padding(bottom = 96.dp),
        )

        // Last in the Box, so it is above every piece of chrome it labels —
        // that is what makes it a coach mark rather than a diagram. It reserves
        // the real geometry itself (see [SelectorCoachOverlay]), so no callout
        // can land on a frame.
        SelectorCoachOverlay(
            visible = guideOpen,
            filingAction = uiState.filingAction,
            detailsVisible = uiState.detailsVisible,
            filmstripVisible = uiState.filmstripVisible && uiState.maximisedFrame == null,
            aspect = currentFrameAspect(uiState),
            onDismiss = dismissGuide,
        )

        contextMenuAt?.let { offset ->
            Popup(
                offset = IntOffset(offset.x.toInt(), offset.y.toInt()),
                onDismissRequest = { contextMenuAt = null },
            ) {
                SelectorContextMenu(
                    actions = actions,
                    filingAction = uiState.filingAction,
                    onDismissRequest = { contextMenuAt = null },
                )
            }
        }
    }
}

@Composable
private fun EmptySelectorState(
    onOpenFolder: () -> Unit,
) {
    Box(
        modifier = Modifier.fillMaxSize(),
        contentAlignment = Alignment.Center,
    ) {
        EmptyStateCard(
            icon = Icons.Default.PhotoCamera,
            title = "Select a Folder",
            description = "Choose a shoot folder to start comparing and culling frames.",
            actionLabel = "Open Folder",
            onAction = onOpenFolder,
        )
    }
}

/**
 * Keyboard and DeX shortcuts.
 *
 * Extracted as a plain function so the routing — including "shortcuts are
 * suppressed while a sheet is open, except Escape" — can be reasoned about and
 * tested without composing the screen.
 */
internal fun handleSelectorKey(
    key: Key,
    sheetOpen: Boolean,
    contextMenuOpen: Boolean,
    fullscreenOpen: Boolean,
    maximised: Boolean,
    actions: SelectorActions,
    onPrevious: () -> Unit,
    onNext: () -> Unit,
    onMaximise: (SelectorFrame) -> Unit,
    onShowShortcuts: () -> Unit,
    onCloseOverlays: () -> Unit,
): Boolean {
    if (key == Key.Escape) {
        if (sheetOpen || contextMenuOpen || fullscreenOpen || maximised) {
            onCloseOverlays()
            return true
        }
        return false
    }

    if (sheetOpen) return false

    return when (key) {
        Key.DirectionLeft -> { onPrevious(); true }
        Key.DirectionRight -> { onNext(); true }
        Key.M -> { actions.onMove(); true }
        Key.C -> { actions.onCopy(); true }
        Key.Delete, Key.Backspace -> { actions.onDelete(); true }
        Key.F -> { actions.onFullscreen(); true }
        // 1/2/3 maximise the frame in that position, left to right as they
        // appear on screen. Space used to toggle between two comparison
        // layouts; there is only one now, so the key is free and goes to the
        // thing users actually want mid-burst — a closer look at one frame.
        Key.One -> { onMaximise(SelectorFrame.PREVIOUS); true }
        Key.Two -> { onMaximise(SelectorFrame.CURRENT); true }
        Key.Three -> { onMaximise(SelectorFrame.NEXT); true }
        Key.Slash -> { onShowShortcuts(); true }
        else -> false
    }
}

/**
 * The aspect ratio the frame solver is currently using, landscape-normalised.
 *
 * Extracted so the coach-mark overlay reserves the same footprints the layout
 * drew — the solver is shared, so the *input* has to be shared too, or the
 * overlay would reserve 4:3 boxes over 3:2 frames and its callouts would drift
 * onto the photographs.
 */
internal fun currentFrameAspect(uiState: com.photoselectortoolbox.viewmodel.SelectorUiState): Float {
    val active = uiState.currentImage ?: uiState.previousImage ?: uiState.nextImage
    val raw = active?.aspectRatio ?: return FrameGeometry.DefaultLandscapeAspect
    return if (raw < 1f) 1f / raw else raw
}

/**
 * The `burst 3/7` label for the frame at [currentIndex], or null when it is
 * not part of a series.
 */
internal fun burstLabelFor(groups: List<List<Int>>, currentIndex: Int): String? {
    val series = groups.firstOrNull { currentIndex in it } ?: return null
    return SelectorLabels.burstChip(
        indexInSeries = series.indexOf(currentIndex),
        seriesLength = series.size,
    )
}

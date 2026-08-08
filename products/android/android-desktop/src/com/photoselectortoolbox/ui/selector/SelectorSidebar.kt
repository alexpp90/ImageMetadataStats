package com.photoselectortoolbox.ui.selector

import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.hoverable
import androidx.compose.foundation.interaction.MutableInteractionSource
import androidx.compose.foundation.interaction.collectIsHoveredAsState
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.fillMaxHeight
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.BurstMode
import androidx.compose.material.icons.filled.FolderOpen
import androidx.compose.material.icons.filled.MoreVert
import androidx.compose.material.icons.filled.Radar
import androidx.compose.material.icons.outlined.Info
import androidx.compose.material3.Icon
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.remember
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.input.pointer.PointerIcon
import androidx.compose.ui.input.pointer.pointerHoverIcon
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.photoselectortoolbox.domain.format.SelectorLabels
import com.photoselectortoolbox.domain.session.SelectorWork
import com.photoselectortoolbox.ui.navigation.Screen
import com.photoselectortoolbox.ui.theme.Indigo500
import com.photoselectortoolbox.ui.theme.ScoreBad
import com.photoselectortoolbox.ui.theme.TonalIndigo
import com.photoselectortoolbox.ui.theme.TonalIndigoNav
import com.photoselectortoolbox.ui.theme.Zinc400
import com.photoselectortoolbox.ui.theme.Zinc50
import com.photoselectortoolbox.ui.theme.Zinc700
import com.photoselectortoolbox.ui.theme.Zinc800
import com.photoselectortoolbox.ui.theme.Zinc950

/**
 * Width of the sidebar.
 *
 * Wide enough for a word under every glyph, which is the entire reason it
 * exists: the controls it replaces were 34 dp icon buttons in a top bar, below
 * the 48 dp minimum and identifiable only by guessing at the glyph.
 *
 * It is also, on this screen, **free**. The selector is height-bound (see §7.2
 * of `docs/products/android-desktop/DESIGN.md`): the three frames are limited by
 * `2h ≤ screen height`, and there are ~124 dp of horizontal slack per frame that
 * the photographs physically cannot use. Spending 88 dp of that on legibility
 * costs zero dp of frame size, while the 44 dp app bar this replaces was coming
 * straight out of the scarce axis.
 */
val SidebarWidth = 88.dp

/** Height of one sidebar item — comfortably above the 48 dp minimum. */
private val SidebarItemHeight = 72.dp

/**
 * The selector's only chrome: session actions above, app destinations below.
 *
 * There is no top app bar anywhere in this product any more. A 44 dp bar costs
 * 29 dp of height on every one of the three frames, and everything that was in
 * it either belongs here (the controls) or belongs beside the photograph it
 * describes (the folder name, the position counter, the burst chip).
 *
 * Toggles and destinations share one active treatment on purpose. "This screen
 * is open" and "this option is on" are the same statement to a user — *this is
 * currently true* — and giving them two different visual languages would be
 * decoration mistaken for information.
 */
@Composable
fun SelectorSidebar(
    currentRoute: String?,
    groupingEnabled: Boolean,
    hasScores: Boolean,
    hasImages: Boolean,
    isScanning: Boolean,
    scanStatusText: String,
    onOpenFolder: () -> Unit,
    onScan: () -> Unit,
    onCancelScan: () -> Unit,
    onToggleGrouping: () -> Unit,
    onShowLegend: () -> Unit,
    onShowMenu: () -> Unit,
    onNavigate: (Screen) -> Unit,
    modifier: Modifier = Modifier,
    isGrouping: Boolean = false,
    queuedWork: SelectorWork? = null,
    onCancelQueued: () -> Unit = {},
    overflowContent: @Composable () -> Unit = {},
) {
    Column(
        modifier = modifier
            .width(SidebarWidth)
            .fillMaxHeight()
            .background(Zinc950)
            .testTag("selector_sidebar")
            .padding(vertical = 6.dp),
        horizontalAlignment = Alignment.CenterHorizontally,
    ) {
        // ── Session actions — what was in the top app bar ────────────────
        SidebarItem(
            icon = Icons.Default.FolderOpen,
            label = "Folder",
            description = "Open a folder",
            onClick = onOpenFolder,
            modifier = Modifier.testTag("sidebar_open_folder"),
        )

        when {
            // The scan replaces its own button in place rather than opening a
            // dialog: culling continues while it runs, so it must not take the
            // screen — or, here, a second slot in the sidebar.
            isScanning -> BusyItem(
                statusText = scanStatusText.removePrefix("Scanning "),
                description = "$scanStatusText. Tap to cancel the scan.",
                onCancel = onCancelScan,
                testTag = "cancel_scan_button",
                statusTestTag = "scan_progress",
            )
            // A scan asked for while grouping runs waits rather than clobbering
            // it — and says so, with a way out. The control is never disabled:
            // a control that does nothing when tapped reads as a frozen app.
            queuedWork == SelectorWork.SCAN -> BusyItem(
                statusText = SelectorLabels.QUEUED,
                description = "Scan queued until grouping finishes. Tap to cancel it.",
                onCancel = onCancelQueued,
                testTag = "cancel_queued_scan",
                statusTestTag = "queued_scan",
            )
            else -> SidebarItem(
                icon = Icons.Default.Radar,
                label = "Scan",
                description = "Scan images for quality scores",
                emphasised = true,
                enabled = hasImages,
                onClick = onScan,
                modifier = Modifier.testTag("scan_button"),
            )
        }

        when {
            isGrouping -> BusyItem(
                statusText = SelectorLabels.GROUPING,
                description = "Grouping similar series. Tap to cancel.",
                onCancel = onToggleGrouping,
                testTag = "cancel_grouping",
                statusTestTag = "grouping_progress",
            )
            queuedWork == SelectorWork.GROUPING -> BusyItem(
                statusText = SelectorLabels.QUEUED,
                description = "Grouping queued until the scan finishes. Tap to cancel it.",
                onCancel = onCancelQueued,
                testTag = "cancel_queued_grouping",
                statusTestTag = "queued_grouping",
            )
            else -> SidebarItem(
                icon = Icons.Default.BurstMode,
                label = "Bursts",
                description = if (groupingEnabled) {
                    "Group Similar Series, on"
                } else {
                    "Group Similar Series, off"
                },
                active = groupingEnabled,
                enabled = hasImages,
                onClick = onToggleGrouping,
                modifier = Modifier.testTag("grouping_toggle"),
            )
        }

        // Appears only once a scan has produced something to explain. A legend
        // for scores that do not exist yet is a dead control.
        if (hasScores) {
            SidebarItem(
                icon = Icons.Outlined.Info,
                label = "Legend",
                description = "What the scan icons mean",
                onClick = onShowLegend,
                modifier = Modifier.testTag("score_legend_button"),
            )
        }

        Box {
            SidebarItem(
                icon = Icons.Default.MoreVert,
                label = "More",
                description = "More options",
                onClick = onShowMenu,
            )
            overflowContent()
        }

        SidebarDivider()

        // ── App destinations — what was in the NavigationRail ────────────
        Screen.all.forEach { screen ->
            SidebarItem(
                icon = screen.icon,
                label = screen.shortLabel,
                description = screen.label,
                active = currentRoute == screen.route,
                onClick = { onNavigate(screen) },
                modifier = Modifier.testTag("nav_${screen.route}"),
            )
        }
    }
}

/**
 * One sidebar control: glyph over word.
 *
 * [emphasised] is reserved for Scan, the one action that starts long-running
 * work; [active] means "currently true", whether that is a screen being open or
 * a toggle being on.
 */
@Composable
private fun SidebarItem(
    icon: ImageVector,
    label: String,
    description: String,
    onClick: () -> Unit,
    modifier: Modifier = Modifier,
    active: Boolean = false,
    emphasised: Boolean = false,
    enabled: Boolean = true,
) {
    val interactionSource = remember { MutableInteractionSource() }
    val hovered by interactionSource.collectIsHoveredAsState()

    val contentColor = when {
        !enabled -> Zinc700
        active -> Indigo500
        else -> Zinc400
    }
    val background = when {
        !enabled -> Color.Transparent
        emphasised -> TonalIndigo
        active -> TonalIndigoNav
        hovered -> Zinc800
        else -> Color.Transparent
    }

    Column(
        modifier = modifier
            .width(80.dp)
            .height(SidebarItemHeight)
            .padding(vertical = 2.dp)
            .clip(RoundedCornerShape(8.dp))
            .background(background)
            .hoverable(interactionSource, enabled = enabled)
            .then(
                if (enabled) {
                    Modifier
                        .pointerHoverIcon(PointerIcon.Hand)
                        .clickable(onClick = onClick)
                } else {
                    Modifier
                }
            )
            .semantics { contentDescription = description }
            .padding(horizontal = 2.dp),
        horizontalAlignment = Alignment.CenterHorizontally,
        verticalArrangement = Arrangement.Center,
    ) {
        Icon(
            imageVector = icon,
            contentDescription = null,
            modifier = Modifier.size(22.dp),
            tint = contentColor,
        )
        Text(
            text = label,
            fontSize = 11.sp,
            color = contentColor,
            maxLines = 1,
            overflow = TextOverflow.Ellipsis,
            textAlign = TextAlign.Center,
            modifier = Modifier.padding(top = 4.dp),
        )
    }
}

/**
 * A slot whose control is busy or waiting: a status line over a Cancel, in the
 * same 72 dp the button occupied.
 *
 * Deliberately not a progress dialog and never a disabled button. The scan is
 * background work over hundreds of frames and the photographer keeps culling
 * while it runs; the same treatment carries a *queued* request, so "running" and
 * "waiting its turn" read the same way and both offer a way out
 * (`ai/memory/palette.md`, 2026-07-24).
 */
@Composable
private fun BusyItem(
    statusText: String,
    description: String,
    onCancel: () -> Unit,
    testTag: String,
    statusTestTag: String,
) {
    Column(
        modifier = Modifier
            .width(80.dp)
            .height(SidebarItemHeight)
            .padding(vertical = 2.dp)
            .clip(RoundedCornerShape(8.dp))
            .background(TonalIndigo)
            .pointerHoverIcon(PointerIcon.Hand)
            .clickable(onClick = onCancel)
            .semantics { contentDescription = description }
            .testTag(testTag)
            .padding(horizontal = 4.dp),
        horizontalAlignment = Alignment.CenterHorizontally,
        verticalArrangement = Arrangement.Center,
    ) {
        Text(
            text = statusText,
            fontSize = 11.sp,
            fontFamily = FontFamily.Monospace,
            color = Zinc50,
            maxLines = 1,
            overflow = TextOverflow.Ellipsis,
            modifier = Modifier.testTag(statusTestTag),
        )
        Text(
            text = "Cancel",
            fontSize = 11.sp,
            color = ScoreBad,
            modifier = Modifier.padding(top = 4.dp),
        )
    }
}

/** The rule between session actions and app destinations. */
@Composable
private fun SidebarDivider() {
    Box(
        modifier = Modifier
            .padding(vertical = 8.dp)
            .width(40.dp)
            .height(1.dp)
            .background(Zinc800),
    )
}

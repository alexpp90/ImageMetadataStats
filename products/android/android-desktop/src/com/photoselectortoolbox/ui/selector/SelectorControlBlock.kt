package com.photoselectortoolbox.ui.selector

import androidx.compose.animation.animateColorAsState
import androidx.compose.animation.core.tween
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.hoverable
import androidx.compose.foundation.interaction.MutableInteractionSource
import androidx.compose.foundation.interaction.collectIsHoveredAsState
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowBack
import androidx.compose.material.icons.automirrored.filled.ArrowForward
import androidx.compose.material.icons.automirrored.filled.DriveFileMove
import androidx.compose.material.icons.filled.ContentCopy
import androidx.compose.material.icons.filled.Delete
import androidx.compose.material.icons.filled.Fullscreen
import androidx.compose.material.icons.filled.Keyboard
import androidx.compose.material.icons.filled.ViewCarousel
import androidx.compose.material.icons.filled.Visibility
import androidx.compose.material.icons.filled.VisibilityOff
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
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.photoselectortoolbox.domain.format.ActionLabel
import com.photoselectortoolbox.domain.format.SelectionActionLabels
import com.photoselectortoolbox.domain.format.SelectorLabels
import com.photoselectortoolbox.domain.interaction.FilingAction
import com.photoselectortoolbox.ui.theme.Indigo500
import com.photoselectortoolbox.ui.theme.PanelSurface
import com.photoselectortoolbox.ui.theme.ScoreBad
import com.photoselectortoolbox.ui.theme.ScoreGood
import com.photoselectortoolbox.ui.theme.TonalIndigo
import com.photoselectortoolbox.ui.theme.Zinc400
import com.photoselectortoolbox.ui.theme.Zinc50
import com.photoselectortoolbox.ui.theme.Zinc600
import com.photoselectortoolbox.ui.theme.Zinc700
import com.photoselectortoolbox.ui.theme.Zinc800

/**
 * Everything that acts on the current frame, in the letterbox column to its
 * right.
 *
 * A 2 × 3 grid of large worded controls rather than the narrow icon rail this
 * replaces. The width is available — the layout is height-bound, so these 388 dp
 * cost the photographs nothing — and 190 dp per cell is enough to carry the
 * word, which is the point: **a control that changes a file is never
 * icon-only.** The previous rail was 48 dp glyphs with hover-revealed key
 * hints, on a tablet, which has no hover.
 *
 * The two filing verbs come from [SelectionActionLabels], so they say Copy and
 * Move according to the user's setting and can never drift into a euphemism.
 */
@Composable
fun SelectorControlBlock(
    actions: SelectorActions,
    filingAction: FilingAction,
    position: Int,
    total: Int,
    canGoPrevious: Boolean,
    canGoNext: Boolean,
    detailsVisible: Boolean,
    filmstripVisible: Boolean,
    overlayValuesVisible: Boolean,
    onNavigatePrevious: () -> Unit,
    onNavigateNext: () -> Unit,
    modifier: Modifier = Modifier,
    stillEnumerating: Boolean = false,
) {
    Column(
        modifier = modifier.padding(horizontal = 10.dp).testTag("control_block"),
        verticalArrangement = Arrangement.spacedBy(6.dp),
    ) {
        val labels = SelectionActionLabels.both(filingAction)

        Row(horizontalArrangement = Arrangement.spacedBy(6.dp)) {
            labels.forEach { label ->
                FilingButton(
                    label = label,
                    onClick = if (label.action == FilingAction.MOVE) {
                        actions.onMove
                    } else {
                        actions.onCopy
                    },
                    modifier = Modifier
                        .weight(1f)
                        .testTag(
                            if (label.action == FilingAction.MOVE) {
                                "move_button_expanded"
                            } else {
                                "copy_button_expanded"
                            }
                        ),
                )
            }
        }

        Row(horizontalArrangement = Arrangement.spacedBy(6.dp)) {
            // Delete is diagonally opposite the configured filing button, not
            // beside it. The two most-used controls on this screen are "file
            // this" and "destroy this", and they should not be neighbours.
            WordedButton(
                icon = Icons.Default.Delete,
                word = "Delete",
                keyHint = "Del",
                description = "Delete, shortcut Delete",
                contentColor = ScoreBad,
                outlined = true,
                onClick = actions.onDelete,
                modifier = Modifier.weight(1f).testTag("delete_button_expanded"),
            )
            WordedButton(
                icon = Icons.Default.Fullscreen,
                word = "Full",
                keyHint = "F",
                description = "Open fullscreen, shortcut F",
                onClick = actions.onFullscreen,
                modifier = Modifier.weight(1f).testTag("fullscreen_button"),
            )
        }

        Row(horizontalArrangement = Arrangement.spacedBy(6.dp)) {
            WordedButton(
                icon = Icons.AutoMirrored.Filled.ArrowBack,
                word = "Prev",
                keyHint = "←",
                description = "Previous image, shortcut left arrow",
                enabled = canGoPrevious,
                onClick = onNavigatePrevious,
                modifier = Modifier.weight(1f).testTag("rail_previous"),
            )
            WordedButton(
                icon = Icons.AutoMirrored.Filled.ArrowForward,
                word = "Next",
                keyHint = "→",
                description = "Next image, shortcut right arrow",
                enabled = canGoNext,
                onClick = onNavigateNext,
                modifier = Modifier.weight(1f).testTag("rail_next"),
            )
        }

        // View controls. Icon-only is acceptable here and only here: none of
        // these four changes a file, so a mis-tap costs a glance, not a photo.
        Row(
            modifier = Modifier.fillMaxWidth().padding(top = 2.dp),
            horizontalArrangement = Arrangement.spacedBy(6.dp, Alignment.CenterHorizontally),
        ) {
            ViewToggle(
                icon = Icons.Outlined.Info,
                description = if (detailsVisible) "Hide photo details" else "Show photo details",
                active = detailsVisible,
                onClick = actions.onToggleDetails,
                modifier = Modifier.testTag("details_toggle"),
            )
            ViewToggle(
                icon = Icons.Default.ViewCarousel,
                description = if (filmstripVisible) "Hide the filmstrip" else "Show the filmstrip",
                active = filmstripVisible,
                onClick = actions.onToggleFilmstrip,
                modifier = Modifier.testTag("filmstrip_toggle"),
            )
            ViewToggle(
                icon = if (overlayValuesVisible) {
                    Icons.Default.Visibility
                } else {
                    Icons.Default.VisibilityOff
                },
                description = if (overlayValuesVisible) {
                    "Hide the values on Previous and Next"
                } else {
                    "Show the values on Previous and Next"
                },
                active = overlayValuesVisible,
                onClick = actions.onToggleOverlayValues,
                modifier = Modifier.testTag("overlay_values_toggle"),
            )
            ViewToggle(
                icon = Icons.Default.Keyboard,
                description = "Shortcuts and layout guide",
                onClick = actions.onShowShortcuts,
                modifier = Modifier.testTag("shortcuts_button"),
            )
        }

        // `127 / 842+` while the folder is still enumerating. Discovery streams,
        // so the total is a running total for the first seconds of a large
        // shoot; printing it bare would state a folder size nobody has counted.
        Text(
            text = SelectorLabels.position(position, total, stillEnumerating),
            fontSize = 12.sp,
            fontFamily = FontFamily.Monospace,
            color = Zinc400,
            modifier = Modifier
                .fillMaxWidth()
                .padding(top = 2.dp)
                .semantics {
                    contentDescription = if (stillEnumerating) {
                        "Image $position of $total so far, still loading"
                    } else {
                        "Image $position of $total"
                    }
                }
                .testTag("position_counter"),
        )
    }
}

/** A filing control, worded from the setting and tinted by whether it is primary. */
@Composable
private fun FilingButton(
    label: ActionLabel,
    onClick: () -> Unit,
    modifier: Modifier = Modifier,
) = WordedButton(
    icon = if (label.action == FilingAction.MOVE) {
        Icons.AutoMirrored.Filled.DriveFileMove
    } else {
        Icons.Default.ContentCopy
    },
    word = label.verb,
    keyHint = label.shortcut,
    description = label.accessibilityLabel,
    contentColor = if (label.isPrimary) ScoreGood else Zinc50,
    filled = label.isPrimary,
    outlined = !label.isPrimary,
    onClick = onClick,
    modifier = modifier,
)

/**
 * The one button shape on this screen: glyph, word, permanent key cap.
 *
 * The key cap is not hover-revealed. A tablet has no hover, and the lesson
 * recorded on the desktop app (2024-05-18, `ai/memory/palette.md`) is that a
 * shortcut nobody can see is a shortcut nobody uses.
 */
@Composable
private fun WordedButton(
    icon: ImageVector,
    word: String,
    keyHint: String,
    description: String,
    onClick: () -> Unit,
    modifier: Modifier = Modifier,
    contentColor: Color = Zinc50,
    filled: Boolean = false,
    outlined: Boolean = false,
    enabled: Boolean = true,
) {
    val interactionSource = remember { MutableInteractionSource() }
    val hovered by interactionSource.collectIsHoveredAsState()

    val resolvedContent = if (enabled) contentColor else Zinc600
    val background by animateColorAsState(
        targetValue = when {
            !enabled -> Color.Transparent
            filled -> TonalIndigo
            hovered -> Zinc800
            else -> PanelSurface
        },
        animationSpec = tween(150),
        label = "buttonBackground",
    )

    Column(
        modifier = modifier
            .height(80.dp)
            .clip(RoundedCornerShape(8.dp))
            .background(background)
            .then(
                if (outlined) Modifier.border(1.dp, Zinc800, RoundedCornerShape(8.dp))
                else Modifier
            )
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
            .padding(6.dp),
        horizontalAlignment = Alignment.CenterHorizontally,
        verticalArrangement = Arrangement.Center,
    ) {
        Icon(
            imageVector = icon,
            contentDescription = null,
            modifier = Modifier.size(22.dp),
            tint = resolvedContent,
        )
        Row(
            modifier = Modifier.padding(top = 5.dp),
            horizontalArrangement = Arrangement.spacedBy(5.dp),
            verticalAlignment = Alignment.CenterVertically,
        ) {
            Text(text = word, fontSize = 13.sp, color = resolvedContent)
            Text(
                text = keyHint,
                fontSize = 10.sp,
                fontFamily = FontFamily.Monospace,
                color = if (enabled) Zinc600 else Zinc700,
            )
        }
    }
}

/** A 48 dp view control — no file changes hands, so the glyph carries it. */
@Composable
private fun ViewToggle(
    icon: ImageVector,
    description: String,
    onClick: () -> Unit,
    modifier: Modifier = Modifier,
    active: Boolean = false,
) {
    val interactionSource = remember { MutableInteractionSource() }
    val hovered by interactionSource.collectIsHoveredAsState()

    Box(
        modifier = modifier
            .size(48.dp)
            .clip(RoundedCornerShape(8.dp))
            .background(if (hovered) Zinc800 else Color.Transparent)
            .hoverable(interactionSource)
            .pointerHoverIcon(PointerIcon.Hand)
            .clickable(onClick = onClick)
            .semantics { contentDescription = description },
        contentAlignment = Alignment.Center,
    ) {
        Icon(
            imageVector = icon,
            contentDescription = null,
            modifier = Modifier.size(20.dp),
            tint = if (active) Indigo500 else Zinc400,
        )
    }
}

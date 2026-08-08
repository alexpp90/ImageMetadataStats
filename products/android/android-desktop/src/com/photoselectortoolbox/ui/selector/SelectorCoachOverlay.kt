package com.photoselectortoolbox.ui.selector

import androidx.compose.animation.AnimatedVisibility
import androidx.compose.animation.core.tween
import androidx.compose.animation.fadeIn
import androidx.compose.animation.fadeOut
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.interaction.MutableInteractionSource
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.BoxWithConstraints
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxHeight
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.Icon
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.remember
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.input.pointer.PointerIcon
import androidx.compose.ui.input.pointer.pointerHoverIcon
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.photoselectortoolbox.domain.guidance.SelectorHint
import com.photoselectortoolbox.domain.guidance.LegendRow
import com.photoselectortoolbox.ui.navigation.Screen
import com.photoselectortoolbox.domain.guidance.SelectorHintText
import com.photoselectortoolbox.domain.guidance.SelectorTour
import com.photoselectortoolbox.domain.guidance.TourCallout
import com.photoselectortoolbox.domain.guidance.TourRegion
import com.photoselectortoolbox.domain.interaction.FilingAction
import com.photoselectortoolbox.domain.interaction.GestureRow
import com.photoselectortoolbox.ui.theme.Indigo200
import com.photoselectortoolbox.ui.theme.Indigo500
import com.photoselectortoolbox.ui.theme.PanelSurface
import com.photoselectortoolbox.ui.theme.Zinc400
import com.photoselectortoolbox.ui.theme.Zinc50
import com.photoselectortoolbox.ui.theme.Zinc700
import com.photoselectortoolbox.ui.theme.Zinc950

/**
 * The guide: the selector, labelled where it actually is.
 *
 * This replaces a scrolling `ModalBottomSheet` of `input → effect` rows, for the
 * reason recorded in `ai/memory/palette.md` (2026-07-31): *a list of labels is
 * the weakest possible way to explain a control the user can already see*. Every
 * control on this screen that acts on a photograph already carries a permanent
 * word and a permanent mono key cap, so the sheet was reciting what was already
 * legible while answering none of the questions a new user actually has — what
 * is the sidebar for, which frame am I deciding on, what do the two below it
 * mean, why is there a block of numbers beside the picture.
 *
 * Those are spatial questions, so this is a spatial answer:
 *
 * - **The screen is dimmed, not replaced.** The real chrome stays visible
 *   through the scrim, because the point is to label *it*, not a diagram of it.
 * - **The real geometry is reserved.** The sidebar column, the two flanks and
 *   the frame footprints are laid out here at exactly the sizes the layout
 *   resolved — through the same [FrameGeometry.threeUpLayout] the layout itself
 *   calls, with the same `detailsVisible` and `filmstripVisible` inputs — so
 *   every callout lands in the horizontal slack and no callout can cover a
 *   frame. An instrumented test asserts the bounds do not intersect, because
 *   that is a regression otherwise only caught by eye.
 * - **It fits on one screen and does not scroll.** A guide that scrolls is
 *   documenting rather than teaching.
 * - **Nothing is written out.** Every row comes from [SelectorTour], which
 *   generates them from the same declarations the bindings read, and the title
 *   comes from [SelectorHintText]. The sheet this replaces claimed the maximise
 *   control was a `⛱` badge — a glyph this product has never rendered.
 *
 * Reachable by `?`, by the keyboard glyph in the control block and from the
 * overflow menu, and shown once at first launch. `Esc` closes it; shortcuts stay
 * suppressed while it is open (REQUIREMENTS §2).
 */
@Composable
fun SelectorCoachOverlay(
    visible: Boolean,
    filingAction: FilingAction,
    detailsVisible: Boolean,
    filmstripVisible: Boolean,
    aspect: Float,
    onDismiss: () -> Unit,
    modifier: Modifier = Modifier,
) {
    AnimatedVisibility(
        visible = visible,
        // Fades. Nothing on this screen slides: the frames underneath are what
        // the user is judging, and movement lies about sharpness.
        enter = fadeIn(tween(200)),
        exit = fadeOut(tween(150)),
        modifier = modifier,
    ) {
        val callouts = remember(filingAction, detailsVisible, filmstripVisible) {
            SelectorTour.callouts(
                filingAction = filingAction,
                detailsVisible = detailsVisible,
                filmstripVisible = filmstripVisible,
                screenLegend = Screen.all.map { screen ->
                    LegendRow(label = screen.label, meaning = screen.meaning)
                },
            ).associateBy { it.region }
        }

        Box(
            modifier = Modifier
                .fillMaxSize()
                // A scrim, not an opaque sheet: the controls being explained stay
                // visible underneath, which is the whole point of a coach mark.
                .background(Zinc950.copy(alpha = 0.72f))
                .clickable(
                    indication = null,
                    interactionSource = remember { MutableInteractionSource() },
                    onClick = onDismiss,
                )
                .testTag("selector_coach_overlay"),
        ) {
            Row(modifier = Modifier.fillMaxSize()) {
                // ── The sidebar column, at its real width ────────────────
                // Reserved and left empty, exactly like the frame footprints.
                // 88 dp cannot hold a sentence, and covering the glyphs with
                // their own explanation is the one thing a coach mark must not
                // do — so the sidebar's callouts sit in the flank beside it and
                // the real icons stay legible through the scrim.
                Spacer(modifier = Modifier.width(SidebarWidth).fillMaxHeight())

                // ── The image region, at its real bounds ─────────────────
                //
                // No strip beneath it any more: the filmstrip is a vertical
                // column at the outer edge of the control flank, so its callout
                // goes beside it. An overlay that still reserved a bottom strip
                // would push every callout up by 76 dp and start labelling the
                // wrong chrome.
                Box(modifier = Modifier.weight(1f).fillMaxSize()) {
                    ImageRegionCallouts(
                        callouts = callouts,
                        aspect = aspect,
                        detailsVisible = detailsVisible,
                        filmstripVisible = filmstripVisible,
                        onDismiss = onDismiss,
                    )
                }
            }
        }
    }
}

/**
 * The three-up region: two flanks carrying callouts, and frame footprints
 * carrying nothing.
 *
 * The footprints are laid out and left empty on purpose. Reserving them is what
 * pushes every callout into the slack; drawing anything in them would be the
 * defect this overlay exists to avoid.
 */
@Composable
private fun ImageRegionCallouts(
    callouts: Map<TourRegion, TourCallout>,
    aspect: Float,
    detailsVisible: Boolean,
    filmstripVisible: Boolean,
    onDismiss: () -> Unit,
) {
    BoxWithConstraints(
        modifier = Modifier.fillMaxSize().padding(FrameGeometry.OuterPadding),
    ) {
        val layout = FrameGeometry.threeUpLayout(
            regionWidth = maxWidth,
            regionHeight = maxHeight,
            aspect = aspect,
            detailsVisible = detailsVisible,
            filmstripVisible = filmstripVisible,
        )

        Column(
            modifier = Modifier.fillMaxSize(),
            verticalArrangement = Arrangement.spacedBy(FrameGeometry.Gap),
        ) {
            // ── Row 1: readout flank · CURRENT footprint · control flank ─
            // Centred exactly as the layout centres it, or the reserved
            // footprint drifts off the frame it is reserving.
            Row(
                modifier = Modifier.weight(1f).fillMaxWidth(),
                horizontalArrangement = Arrangement.Center,
                verticalAlignment = Alignment.CenterVertically,
            ) {
                // The left flank carries three blocks, spaced apart rather than
                // centred as one. The sidebar's session actions are at the top of
                // the screen and its destinations at the bottom, while the
                // readout sits in the middle — so spacing them to the same three
                // positions lands every explanation level with the thing it
                // explains, which is the whole claim the word "legend" makes.
                Column(
                    modifier = Modifier.width(layout.flankWidth).fillMaxHeight(),
                    verticalArrangement = Arrangement.SpaceBetween,
                    horizontalAlignment = Alignment.End,
                ) {
                    callouts[TourRegion.SIDEBAR_SESSION]?.let { Callout(it) }
                    Column(horizontalAlignment = Alignment.End) {
                        callouts[TourRegion.READOUT]?.let { Callout(it) }
                        callouts[TourRegion.FRAMES]?.let {
                            Spacer(modifier = Modifier.height(10.dp))
                            Callout(it)
                        }
                    }
                    callouts[TourRegion.SIDEBAR_SCREENS]?.let { Callout(it) }
                }

                Spacer(modifier = Modifier.width(FrameGeometry.Gap))
                Spacer(modifier = Modifier.size(layout.frame))
                Spacer(modifier = Modifier.width(FrameGeometry.Gap))

                // The control flank, split exactly as the layout splits it:
                // callouts where the controls are, and the filmstrip's column
                // reserved and left empty at the outer edge so its callout sits
                // beside the strip rather than on top of it.
                Row(
                    modifier = Modifier.width(layout.flankWidth).fillMaxHeight(),
                    verticalAlignment = Alignment.CenterVertically,
                ) {
                    Column(
                        modifier = Modifier.weight(1f),
                        verticalArrangement = Arrangement.Center,
                    ) {
                        Title()
                        Spacer(modifier = Modifier.height(14.dp))
                        callouts[TourRegion.CONTROLS]?.let { Callout(it) }
                        callouts[TourRegion.KEYS]?.let {
                            Spacer(modifier = Modifier.height(14.dp))
                            Callout(it)
                        }
                        callouts[TourRegion.FILMSTRIP]?.let {
                            Spacer(modifier = Modifier.height(14.dp))
                            Callout(it, compact = true)
                        }
                        Spacer(modifier = Modifier.height(16.dp))
                        DismissButton(onDismiss)
                    }

                    if (layout.filmstripWidth > 0.dp) {
                        Spacer(modifier = Modifier.width(FrameGeometry.Gap))
                        Spacer(modifier = Modifier.width(layout.filmstripWidth).fillMaxHeight())
                    }
                }
            }

            // ── Row 2: the two neighbour footprints, reserved and empty ──
            Row(
                modifier = Modifier.weight(1f).fillMaxWidth(),
                horizontalArrangement = Arrangement.spacedBy(
                    FrameGeometry.Gap,
                    Alignment.CenterHorizontally,
                ),
                verticalAlignment = Alignment.CenterVertically,
            ) {
                Spacer(modifier = Modifier.size(layout.frame))
                Spacer(modifier = Modifier.size(layout.frame))
            }
        }
    }
}

/** The guide's own heading, worded by the same object as every hint. */
@Composable
private fun Title() {
    Column(horizontalAlignment = Alignment.End) {
        Text(
            text = SelectorHintText.title(SelectorHint.TOUR, FilingAction.DEFAULT),
            fontSize = 18.sp,
            fontWeight = FontWeight.SemiBold,
            color = Zinc50,
        )
        Text(
            // The message names no verb, so the filing action does not reach it;
            // it is still read from the one text object rather than typed here.
            text = SelectorHintText.message(
                hint = SelectorHint.TOUR,
                filingAction = FilingAction.DEFAULT,
                selectionFolderName = "",
                sortingEnabled = false,
            ),
            fontSize = 12.sp,
            color = Zinc400,
        )
    }
}

/**
 * One coach mark: a leader line, a title, one line of body, and the inputs.
 *
 * [compact] is the sidebar and filmstrip variant: the sidebar's has 88 dp to
 * work in, and the filmstrip's is the last of three callouts stacked in the
 * control flank, so both drop to the title and a short body.
 */
@Composable
private fun Callout(callout: TourCallout, compact: Boolean = false) {
    Column(
        modifier = Modifier
            .then(if (compact) Modifier.fillMaxWidth() else Modifier)
            .clip(RoundedCornerShape(10.dp))
            .background(PanelSurface)
            .border(1.dp, Zinc700, RoundedCornerShape(10.dp))
            .padding(horizontal = 10.dp, vertical = 8.dp)
            .semantics { contentDescription = "${callout.title}. ${callout.body}" }
            .testTag("coach_callout"),
        verticalArrangement = Arrangement.spacedBy(3.dp),
    ) {
        Row(
            horizontalArrangement = Arrangement.spacedBy(6.dp),
            verticalAlignment = Alignment.CenterVertically,
        ) {
            Leader()
            Text(
                text = callout.title,
                fontSize = if (compact) 11.sp else 13.sp,
                fontWeight = FontWeight.Medium,
                color = Zinc50,
            )
        }
        Text(
            text = callout.body,
            fontSize = if (compact) 9.sp else 11.sp,
            color = Zinc400,
        )
        callout.legend.forEach { LegendLine(it, compact = compact) }
        callout.rows.forEach { KeyRow(it, compact = compact) }
    }
}

/**
 * One legend line: the thing's own glyph where it has one, its name, and what
 * it means.
 *
 * The glyph is [ScoreMetricIcon.vector] — the same mapping the readouts and the
 * chips draw from — so the legend cannot teach a symbol this product does not
 * render. It did exactly that until the two mappings were merged: a spotlight
 * for highlight clipping against the sun the frames actually showed.
 */
@Composable
private fun LegendLine(row: LegendRow, compact: Boolean) {
    Row(
        modifier = Modifier.fillMaxWidth().padding(top = 2.dp),
        horizontalArrangement = Arrangement.spacedBy(6.dp),
        verticalAlignment = Alignment.Top,
    ) {
        if (row.metric != null) {
            Icon(
                imageVector = row.metric.icon.vector(),
                contentDescription = null,
                tint = Zinc50,
                modifier = Modifier.size(if (compact) 11.dp else 14.dp),
            )
        }
        Column {
            Text(
                text = row.label,
                fontSize = if (compact) 9.sp else 11.sp,
                fontWeight = FontWeight.Medium,
                color = Zinc50,
            )
            Text(
                text = row.meaning,
                fontSize = if (compact) 8.sp else 10.sp,
                color = Zinc400,
            )
        }
    }
}

/** The short rule that ties a callout to the region it labels. */
@Composable
private fun Leader() {
    Box(
        modifier = Modifier
            .width(10.dp)
            .height(1.dp)
            .background(Indigo500),
    )
}

/** One `input → effect` line, generated — never written out. */
@Composable
private fun KeyRow(row: GestureRow, compact: Boolean) {
    Row(
        modifier = Modifier.fillMaxWidth().padding(top = 1.dp),
        horizontalArrangement = Arrangement.spacedBy(8.dp),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        Text(
            text = row.input,
            fontSize = if (compact) 9.sp else 11.sp,
            fontFamily = FontFamily.Monospace,
            color = Zinc50,
            modifier = Modifier.width(if (compact) 62.dp else 92.dp),
        )
        Text(
            text = row.effect,
            fontSize = if (compact) 9.sp else 11.sp,
            color = Zinc400,
        )
    }
}

/** Closes the guide. `Esc` and a tap anywhere on the scrim do the same. */
@Composable
private fun DismissButton(onDismiss: () -> Unit) {
    Box(
        modifier = Modifier
            .height(48.dp)
            .clip(RoundedCornerShape(8.dp))
            .background(PanelSurface)
            .border(1.dp, Zinc700, RoundedCornerShape(8.dp))
            .pointerHoverIcon(PointerIcon.Hand)
            .clickable(onClick = onDismiss)
            .padding(horizontal = 20.dp)
            .testTag("coach_overlay_dismiss"),
        contentAlignment = Alignment.Center,
    ) {
        Text(
            text = "Got it",
            fontSize = 13.sp,
            fontWeight = FontWeight.Medium,
            color = Indigo200,
        )
    }
}


package com.photoselectortoolbox.domain.guidance

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

/**
 * When an explanation fires, and where it is allowed to sit.
 *
 * All of it is policy, and policy inside a composable is policy no JVM test can
 * reach — the reason `ai/memory/code_health.md` `[OPEN] 2026-08-07` asks for
 * placement predicates outside composables in the first place.
 */
class SelectorGuidanceTest {

    @Test
    fun `only the three invisible-effect actions are explained`() {
        // This layout labels its controls, so a hint earns its place only where
        // the effect cannot be seen. Porting seven of them from a gesture-first
        // product would be explaining what is already written on the buttons.
        assertEquals(
            listOf(SelectorHint.FILING, SelectorHint.DELETE_UNDO, SelectorHint.MAXIMISE),
            SelectorGuidance.CARD_HINTS,
        )
    }

    @Test
    fun `the scores hint is defined but deliberately never raised as a card`() {
        // The bars appear on the frames and the Legend item appears in the
        // sidebar at the same moment. A card would explain what the user is
        // looking at.
        assertFalse(SelectorHint.SCORES in SelectorGuidance.CARD_HINTS)
    }

    @Test
    fun `the guide is not a card`() {
        assertFalse(SelectorHint.TOUR in SelectorGuidance.CARD_HINTS)
    }

    @Test
    fun `a hint fires when it has not been seen`() {
        assertEquals(
            SelectorHint.FILING,
            SelectorGuidance.nextHint(SelectorHint.FILING, emptySet(), null),
        )
    }

    @Test
    fun `a dismissed hint never returns`() {
        assertNull(
            SelectorGuidance.nextHint(
                candidate = SelectorHint.FILING,
                seen = setOf(SelectorHint.FILING),
                current = null,
            )
        )
    }

    @Test
    fun `a hint already on screen survives a repeat of the same action`() {
        assertEquals(
            SelectorHint.FILING,
            SelectorGuidance.nextHint(
                candidate = SelectorHint.FILING,
                seen = setOf(SelectorHint.FILING),
                current = SelectorHint.FILING,
            ),
        )
    }

    @Test
    fun `a newer action replaces the explanation on screen`() {
        // The user has moved on; the explanation of what they just did is the
        // useful one.
        assertEquals(
            SelectorHint.DELETE_UNDO,
            SelectorGuidance.nextHint(
                candidate = SelectorHint.DELETE_UNDO,
                seen = emptySet(),
                current = SelectorHint.FILING,
            ),
        )
    }

    @Test
    fun `a non-card hint is never raised as one`() {
        assertNull(SelectorGuidance.nextHint(SelectorHint.TOUR, emptySet(), null))
        assertNull(SelectorGuidance.nextHint(SelectorHint.SCORES, emptySet(), null))
    }

    @Test
    fun `a card goes when its hint is recorded as seen`() {
        assertNull(
            SelectorGuidance.retainPending(SelectorHint.FILING, setOf(SelectorHint.FILING))
        )
        assertEquals(
            SelectorHint.FILING,
            SelectorGuidance.retainPending(SelectorHint.FILING, setOf(SelectorHint.MAXIMISE)),
        )
    }

    @Test
    fun `the guide opens itself once, and only with photographs on screen`() {
        assertTrue(SelectorGuidance.shouldShowTour(emptySet(), hasImages = true))
        assertFalse(SelectorGuidance.shouldShowTour(emptySet(), hasImages = false))
        assertFalse(
            SelectorGuidance.shouldShowTour(setOf(SelectorHint.TOUR), hasImages = true)
        )
    }

    @Test
    fun `reset guidance brings the guide back`() {
        // resetGuidance clears the whole set, which is what arrives here.
        assertTrue(SelectorGuidance.shouldShowTour(emptySet(), hasImages = true))
    }

    @Test
    fun `the card sits in the readout flank when the flank can carry it`() {
        assertEquals(
            HintSlot.READOUT_FLANK,
            SelectorGuidance.slotFor(flankWidthDp = 388f, detailsVisible = true),
        )
    }

    @Test
    fun `no flank means no card, rather than a card over a photograph`() {
        // The alternative — falling back to the image region — is the one thing
        // this screen does not do. Height is the binding constraint and the
        // frames are what the user is judging.
        assertEquals(
            HintSlot.NONE,
            SelectorGuidance.slotFor(flankWidthDp = 388f, detailsVisible = false),
        )
        assertEquals(
            HintSlot.NONE,
            SelectorGuidance.slotFor(
                flankWidthDp = SelectorGuidance.MIN_CARD_WIDTH_DP - 1f,
                detailsVisible = true,
            ),
        )
    }

    @Test
    fun `the card is suppressed while the guide is open`() {
        assertFalse(
            SelectorGuidance.cardVisible(
                pending = SelectorHint.FILING,
                guideOpen = true,
                slot = HintSlot.READOUT_FLANK,
            )
        )
        assertTrue(
            SelectorGuidance.cardVisible(
                pending = SelectorHint.FILING,
                guideOpen = false,
                slot = HintSlot.READOUT_FLANK,
            )
        )
        assertFalse(
            SelectorGuidance.cardVisible(
                pending = null,
                guideOpen = false,
                slot = HintSlot.READOUT_FLANK,
            )
        )
    }
}

package com.photoselectortoolbox.domain.guidance

import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

/**
 * Hint keys are on users' devices, and hint *wording* is not allowed to live
 * here at all.
 */
class SelectorHintTest {

    @Test
    fun `keys are stable`() {
        // Renaming one of these re-shows a hint the user already dismissed.
        // Add entries; never repurpose them.
        assertEquals(
            setOf(
                "filing_action",
                "delete_undo",
                "maximise_frame",
                "scan_scores",
                "selector_tour",
            ),
            SelectorHint.entries.map { it.key }.toSet(),
        )
    }

    @Test
    fun `keys are distinct`() {
        assertEquals(SelectorHint.entries.size, SelectorHint.entries.map { it.key }.toSet().size)
    }

    @Test
    fun `the filing hint is marked as needing the configured verb`() {
        // Its text has to come from SelectionActionLabels / FilingAction, or it
        // is wrong under one of the two configurations. Flagging it here is what
        // lets the UI assert it never renders a constant.
        assertTrue(SelectorHint.FILING.namesFilingVerb)
    }

    @Test
    fun `no hint carries user-facing wording`() {
        // Keys are lowercase snake_case identifiers, not sentences. A key with a
        // space or a capital is copy that has leaked into the domain enum, which
        // is how "Keep"/"Save"/"Favourite" got shipped before (REQUIREMENTS §2).
        SelectorHint.entries.forEach { hint ->
            assertTrue(hint.key, hint.key.matches(Regex("[a-z0-9_]+")))
        }
    }

    @Test
    fun `round trip through the persisted set`() {
        val hints = setOf(SelectorHint.FILING, SelectorHint.SCORES)

        assertEquals(hints, SelectorHint.decode(SelectorHint.encode(hints)))
    }

    @Test
    fun `an unknown stored key is ignored, not treated as a seen hint`() {
        assertEquals(
            setOf(SelectorHint.DELETE_UNDO),
            SelectorHint.decode(setOf("delete_undo", "written_by_a_newer_build")),
        )
        assertTrue(SelectorHint.decode(null).isEmpty())
        assertNull(SelectorHint.fromKey("nope"))
    }
}

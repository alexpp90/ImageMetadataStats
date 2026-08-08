package com.photoselectortoolbox.domain.session

import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Test

/**
 * Scan and grouping queue for each other, symmetrically.
 *
 * The asymmetry these tests exist to prevent is the one recorded in
 * `ai/memory/palette.md` (2026-07-24): the desktop product queued a scan
 * requested during grouping and *disabled the control* for the mirror case. If
 * A-during-B queues, B-during-A must queue too — so every test below has a twin.
 */
class SelectorWorkQueueTest {

    @Test
    fun `a request with nothing running starts immediately`() {
        listOf(SelectorWork.SCAN, SelectorWork.GROUPING).forEach { work ->
            val (state, decision) = SelectorWorkQueue.request(WorkQueueState(), work)
            assertEquals(WorkDecision.Start(work), decision)
            assertEquals(work, state.running)
            assertNull(state.queued)
        }
    }

    @Test
    fun `grouping requested during a scan is queued, not run`() {
        val running = WorkQueueState(running = SelectorWork.SCAN)

        val (state, decision) = SelectorWorkQueue.request(running, SelectorWork.GROUPING)

        assertEquals(WorkDecision.Queue(SelectorWork.GROUPING), decision)
        assertEquals(SelectorWork.SCAN, state.running)
        assertEquals(SelectorWork.GROUPING, state.queued)
    }

    @Test
    fun `a scan requested during grouping is queued, not run`() {
        val running = WorkQueueState(running = SelectorWork.GROUPING)

        val (state, decision) = SelectorWorkQueue.request(running, SelectorWork.SCAN)

        assertEquals(WorkDecision.Queue(SelectorWork.SCAN), decision)
        assertEquals(SelectorWork.GROUPING, state.running)
        assertEquals(SelectorWork.SCAN, state.queued)
    }

    @Test
    fun `the queued pass starts when the running one finishes — both directions`() {
        val scanFirst = WorkQueueState(SelectorWork.SCAN, SelectorWork.GROUPING)
        val (afterScan, scanDecision) = SelectorWorkQueue.finish(scanFirst, SelectorWork.SCAN)
        assertEquals(WorkDecision.Start(SelectorWork.GROUPING), scanDecision)
        assertEquals(SelectorWork.GROUPING, afterScan.running)
        assertNull(afterScan.queued)

        val groupFirst = WorkQueueState(SelectorWork.GROUPING, SelectorWork.SCAN)
        val (afterGroup, groupDecision) = SelectorWorkQueue.finish(groupFirst, SelectorWork.GROUPING)
        assertEquals(WorkDecision.Start(SelectorWork.SCAN), groupDecision)
        assertEquals(SelectorWork.SCAN, afterGroup.running)
        assertNull(afterGroup.queued)
    }

    @Test
    fun `finishing with nothing queued leaves the queue idle`() {
        val (state, decision) = SelectorWorkQueue.finish(
            WorkQueueState(running = SelectorWork.SCAN),
            SelectorWork.SCAN,
        )
        assertEquals(WorkDecision.Idle, decision)
        assertNull(state.running)
        assertNull(state.queued)
    }

    @Test
    fun `a late finish from a pass that is no longer running changes nothing`() {
        // A cancelled job's `finally` can report after the queue has already
        // promoted the waiting pass. Acting on it would start that pass twice.
        val promoted = WorkQueueState(running = SelectorWork.GROUPING)

        val (state, decision) = SelectorWorkQueue.finish(promoted, SelectorWork.SCAN)

        assertEquals(WorkDecision.Idle, decision)
        assertEquals(promoted, state)
    }

    @Test
    fun `cancelling the queued request leaves the running one alone`() {
        val state = SelectorWorkQueue.cancelQueued(
            WorkQueueState(SelectorWork.SCAN, SelectorWork.GROUPING)
        )
        assertEquals(SelectorWork.SCAN, state.running)
        assertNull(state.queued)
    }

    @Test
    fun `requesting the running pass again queues a re-run rather than swallowing it`() {
        // Two Bursts taps in quick succession: the second must take effect after
        // the first pass ends, not vanish.
        val (state, decision) = SelectorWorkQueue.request(
            WorkQueueState(running = SelectorWork.GROUPING),
            SelectorWork.GROUPING,
        )
        assertEquals(WorkDecision.Queue(SelectorWork.GROUPING), decision)
        assertEquals(SelectorWork.GROUPING, state.queued)
    }

    @Test
    fun `reset forgets both, because a new folder invalidates both passes`() {
        assertEquals(WorkQueueState(), SelectorWorkQueue.reset())
    }

    @Test
    fun `only one request can wait, because only one pass can run`() {
        var state = WorkQueueState(running = SelectorWork.SCAN)
        state = SelectorWorkQueue.request(state, SelectorWork.GROUPING).first
        state = SelectorWorkQueue.request(state, SelectorWork.GROUPING).first
        assertEquals(SelectorWork.GROUPING, state.queued)
        assertEquals(SelectorWork.SCAN, state.running)
    }
}

package com.photoselectortoolbox.domain.session

/**
 * The two long-running passes over a folder that cannot run at the same time.
 *
 * Both rebuild something the other depends on — a scan writes scores onto the
 * items, grouping rebuilds the candidate order from them — so running one while
 * the other is mid-flight rebuilds the list underneath a photographer who is
 * looking at it.
 */
enum class SelectorWork {
    /** Quality analysis over the folder. */
    SCAN,

    /** Group Similar Series: dHash comparison producing the burst grouping. */
    GROUPING,
}

/** What is running, and what has been asked for and is waiting. */
data class WorkQueueState(
    val running: SelectorWork? = null,
    val queued: SelectorWork? = null,
) {
    val isScanning: Boolean get() = running == SelectorWork.SCAN
    val isGrouping: Boolean get() = running == SelectorWork.GROUPING
}

/** What the caller should do about a request. */
sealed interface WorkDecision {
    /** Begin [work] now. */
    data class Start(val work: SelectorWork) : WorkDecision

    /** [work] is waiting; show it as queued, with a way to cancel it. */
    data class Queue(val work: SelectorWork) : WorkDecision

    /** Nothing to do. */
    data object Idle : WorkDecision
}

/**
 * Queueing, not disabling.
 *
 * The rule comes from `ai/memory/palette.md` (2026-07-24): when two long-running
 * passes conflict, **keep both controls enabled and queue the second request
 * with a visible queued state and a cancel affordance** — a control that does
 * nothing when clicked reads as a frozen app. The desktop product already had
 * half of this (`_pending_scan`: a scan requested during grouping is queued) and
 * the mirror case implemented as a hard disable, which is exactly the asymmetry
 * that lesson warns against. Here both directions go through the same three
 * functions, so they cannot diverge.
 *
 * At most one request can be waiting: only one pass runs at a time, so only one
 * other pass can be blocked by it.
 */
object SelectorWorkQueue {

    /**
     * Ask for [work].
     *
     * Nothing running → start. Something else running → queue. The *same* pass
     * already running → queue it too, so a second Bursts tap mid-grouping
     * re-runs afterwards with the new setting rather than being swallowed.
     */
    fun request(state: WorkQueueState, work: SelectorWork): Pair<WorkQueueState, WorkDecision> =
        when (state.running) {
            null -> state.copy(running = work, queued = null) to WorkDecision.Start(work)
            else -> state.copy(queued = work) to WorkDecision.Queue(work)
        }

    /**
     * [work] has finished or been cancelled.
     *
     * Whatever was waiting starts now. A finish reported for a pass that is not
     * the running one is ignored, so a late callback from a cancelled job cannot
     * launch the queued pass twice.
     */
    fun finish(state: WorkQueueState, work: SelectorWork): Pair<WorkQueueState, WorkDecision> {
        if (state.running != work) return state to WorkDecision.Idle
        val next = state.queued
            ?: return WorkQueueState(running = null, queued = null) to WorkDecision.Idle
        return WorkQueueState(running = next, queued = null) to WorkDecision.Start(next)
    }

    /** Drop the waiting request. The running pass is untouched. */
    fun cancelQueued(state: WorkQueueState): WorkQueueState = state.copy(queued = null)

    /** Forget everything: a new folder invalidates both passes. */
    fun reset(): WorkQueueState = WorkQueueState()
}

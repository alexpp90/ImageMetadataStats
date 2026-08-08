package com.photoselectortoolbox.domain.session

import com.photoselectortoolbox.data.model.ImageItem

/**
 * How a progressive discovery batch joins the list the photographer is already
 * looking at.
 *
 * Folder discovery emits **cumulatively** — a first batch of 24, then chunks of
 * 250, then the complete snapshot (REQUIREMENTS §7, "Progressive Folder
 * Discovery"). Consuming that naively, by replacing the list on every emission,
 * re-sorts photographs out from under someone who is mid-cull and resurrects the
 * ones they have already filed or deleted, because a cumulative emission still
 * contains them.
 *
 * So the merge is **append-only and de-duplicated against every URI ever
 * published for this folder** — not against what is currently in the list. That
 * distinction is the whole point: "absent from the list" means "the user removed
 * it", never "newly found". This is the corollary the 2026-07-31 entry in
 * `ai/memory/bolt.md` records for the consumer side of streaming enumeration.
 *
 * Pure and Android-free, because every bug in this area is an index or a set
 * membership question and both are answerable without an emulator.
 */
object ProgressiveMerge {

    /**
     * The outcome of merging one batch.
     *
     * [added] is carried separately so the caller can drive dimension
     * resolution and score restoration over only what is new.
     */
    data class Result(
        val images: List<ImageItem>,
        val currentIndex: Int,
        val added: List<ImageItem>,
    ) {
        /** True when the batch contained nothing the list did not already have. */
        val isNoOp: Boolean get() = added.isEmpty()
    }

    /**
     * The items of [batch] that have never been published for this folder,
     * in batch order and de-duplicated within the batch itself.
     *
     * [published] is every URI this folder has ever emitted, including ones the
     * photographer has since moved or deleted.
     */
    fun newItems(batch: List<ImageItem>, published: Set<String>): List<ImageItem> {
        if (batch.isEmpty()) return emptyList()
        val seen = HashSet(published)
        val fresh = ArrayList<ImageItem>(batch.size)
        for (item in batch) {
            if (seen.add(item.uri)) fresh += item
        }
        return fresh
    }

    /**
     * Append the unseen part of [batch] to [current].
     *
     * [currentIndex] is preserved on every batch but the first: moving the
     * photographer back to frame 1 because another 250 files finished
     * enumerating is the exact failure this function exists to prevent. On the
     * first batch of a new folder the index is 0, because there is nothing yet
     * to preserve.
     */
    fun append(
        current: List<ImageItem>,
        currentIndex: Int,
        batch: List<ImageItem>,
        published: Set<String>,
        isFirstBatch: Boolean,
    ): Result {
        val fresh = newItems(batch, published)
        val images = if (fresh.isEmpty()) current else current + fresh
        val index = when {
            images.isEmpty() -> 0
            isFirstBatch -> 0
            else -> currentIndex.coerceIn(0, images.size - 1)
        }
        return Result(images = images, currentIndex = index, added = fresh)
    }
}

package com.photoselectortoolbox.data.repository

/**
 * The outcome of moving, copying or reversing a move for a single file.
 *
 * `moveImage`/`copyImage` used to return `Boolean`, which discarded the one
 * piece of information an undo needs: **where the file went**. Without the
 * destination URI nothing below the UI could reverse a move, so the selector's
 * snackbar drew a 30-second countdown next to a null `onUndo` (see the
 * `[OPEN] 2026-07-27 - No Repository-Level Undo` entry in
 * `ai/memory/code_health.md`).
 *
 * The shape deliberately matches the `MoveResult` that
 * [com.photoselectortoolbox.domain.usecase.MoveToSelectionUseCase] already
 * returned — that type is now a typealias of this one, so there is exactly one
 * result shape for file operations in this product rather than two that drift.
 *
 * [destinationUri] is null on failure, and also on success for operations that
 * genuinely produce no new file (a reversal that only untrashes, for instance).
 * A caller deciding whether an undo is possible must therefore test the URI, not
 * just [success] — that decision lives in
 * [com.photoselectortoolbox.domain.curation.UndoPolicy].
 */
data class FileOperationResult(
    val sourceUri: String,
    val destinationUri: String?,
    val success: Boolean,
    val error: String? = null,
) {
    companion object {
        fun success(sourceUri: String, destinationUri: String?) =
            FileOperationResult(sourceUri, destinationUri, success = true)

        fun failure(sourceUri: String, error: String?) =
            FileOperationResult(sourceUri, null, success = false, error = error)
    }
}

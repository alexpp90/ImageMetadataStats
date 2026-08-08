package com.photoselectortoolbox.data.repository

import android.content.Context
import androidx.datastore.core.DataStore
import androidx.datastore.preferences.core.Preferences
import androidx.datastore.preferences.core.booleanPreferencesKey
import androidx.datastore.preferences.core.edit
import androidx.datastore.preferences.core.intPreferencesKey
import androidx.datastore.preferences.core.longPreferencesKey
import androidx.datastore.preferences.core.stringPreferencesKey
import androidx.datastore.preferences.core.stringSetPreferencesKey
import androidx.datastore.preferences.preferencesDataStore
import com.photoselectortoolbox.domain.grouping.GroupingLevel
import com.photoselectortoolbox.domain.guidance.SelectorHint
import com.photoselectortoolbox.domain.interaction.FilingAction
import dagger.hilt.android.qualifiers.ApplicationContext
import javax.inject.Inject
import javax.inject.Singleton
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.flow.map

private val Context.dataStore: DataStore<Preferences> by preferencesDataStore(
    name = "photo_selector_settings"
)

@Singleton
class SettingsRepository @Inject constructor(
    @ApplicationContext private val context: Context
) {

    companion object {
        private val KEY_SELECTION_FOLDER_NAME = stringPreferencesKey("selection_folder_name")
        private val KEY_SORTING_ENABLED = booleanPreferencesKey("sorting_enabled")
        private val KEY_GROUPING_ENABLED = booleanPreferencesKey("grouping_enabled")
        private val KEY_GROUPING_LEVEL = stringPreferencesKey("grouping_level")
        private val KEY_LAST_FOLDER_URI = stringPreferencesKey("last_folder_uri")
        private val KEY_ANALYSIS_THREAD_COUNT = intPreferencesKey("analysis_thread_count")

        // Phone-mode settings
        private val KEY_PHONE_COLLECTION_ACTION = stringPreferencesKey("phone_collection_action")
        private val KEY_PHONE_COLLECTION_URI = stringPreferencesKey("phone_collection_uri")
        private val KEY_PHONE_DELETE_CONFIRM = booleanPreferencesKey("phone_delete_confirm")
        private val KEY_PHONE_SORT_BY_ORIENTATION = booleanPreferencesKey("phone_sort_by_orientation")
        private val KEY_PHONE_GESTURE_TUTORIAL_TS = longPreferencesKey("phone_gesture_tutorial_ts")
        private val KEY_PHONE_FORCE_MODE = stringPreferencesKey("phone_force_mode")
        private val KEY_PHONE_FILE_TYPE_FILTER = stringPreferencesKey("phone_file_type_filter")
        private val KEY_FULLSCREEN_BUTTONS_ENABLED = booleanPreferencesKey("fullscreen_buttons_enabled")
        private val KEY_FULLSCREEN_GESTURE_ACTION = stringPreferencesKey("fullscreen_gesture_action")

        // Expanded-layout (tablet/DeX) selector view preferences
        private val KEY_HAS_SEEN_NAV_HINT = booleanPreferencesKey("has_seen_nav_hint")
        private val KEY_OVERLAY_VALUES_VISIBLE = booleanPreferencesKey("overlay_values_visible")
        private val KEY_FILMSTRIP_VISIBLE = booleanPreferencesKey("filmstrip_visible")
        private val KEY_DETAILS_VISIBLE = booleanPreferencesKey("details_visible")
        private val KEY_SEEN_FULLSCREEN_HINT = booleanPreferencesKey("seen_fullscreen_gesture_hint")

        /**
         * Which one-time hints the user has already dismissed.
         *
         * A set rather than one boolean per hint, so adding a hint does not add
         * a preference key and "Reset guidance" is a single removal instead of a
         * list that someone will forget to extend.
         */
        private val KEY_SEEN_HINTS = stringSetPreferencesKey("seen_first_run_hints")

        const val DEFAULT_SELECTION_FOLDER_NAME = "Selection"
        const val DEFAULT_SORTING_ENABLED = true
        const val DEFAULT_GROUPING_ENABLED = false

        /**
         * The filmstrip starts hidden.
         *
         * The compare-and-cull loop is Previous/Next and the two neighbour
         * frames; the strip is random access to the rest of the shoot, which is
         * a second-order need. Starting it off means the screen a photographer
         * first sees is the three photographs and nothing else, and the toggle
         * in the view cluster turns it on for the sessions that want it — the
         * preference is persisted, so that decision is made once.
         */
        const val DEFAULT_FILMSTRIP_VISIBLE = false

        val DEFAULT_GROUPING_LEVEL = GroupingLevel.TIME_FILENAME
        val DEFAULT_ANALYSIS_THREAD_COUNT = Runtime.getRuntime().availableProcessors().coerceIn(1, 4)
    }

    val selectionFolderName: Flow<String> = context.dataStore.data.map { prefs ->
        prefs[KEY_SELECTION_FOLDER_NAME] ?: DEFAULT_SELECTION_FOLDER_NAME
    }

    val sortingEnabled: Flow<Boolean> = context.dataStore.data.map { prefs ->
        prefs[KEY_SORTING_ENABLED] ?: DEFAULT_SORTING_ENABLED
    }

    val groupingEnabled: Flow<Boolean> = context.dataStore.data.map { prefs ->
        prefs[KEY_GROUPING_ENABLED] ?: DEFAULT_GROUPING_ENABLED
    }

    val groupingLevel: Flow<GroupingLevel> = context.dataStore.data.map { prefs ->
        val value = prefs[KEY_GROUPING_LEVEL]
        if (value != null) {
            try {
                GroupingLevel.valueOf(value)
            } catch (_: IllegalArgumentException) {
                DEFAULT_GROUPING_LEVEL
            }
        } else {
            DEFAULT_GROUPING_LEVEL
        }
    }

    val lastFolderUri: Flow<String?> = context.dataStore.data.map { prefs ->
        prefs[KEY_LAST_FOLDER_URI]
    }

    val analysisThreadCount: Flow<Int> = context.dataStore.data.map { prefs ->
        prefs[KEY_ANALYSIS_THREAD_COUNT] ?: DEFAULT_ANALYSIS_THREAD_COUNT
    }

    val fullscreenButtonsEnabled: Flow<Boolean> = context.dataStore.data.map { prefs ->
        prefs[KEY_FULLSCREEN_BUTTONS_ENABLED] ?: true
    }

    /**
     * Which verb the emphasised filing control performs: copy, or move.
     *
     * The DataStore key is still `fullscreen_gesture_action` because it is on
     * users' devices, but the setting no longer has anything to do with a
     * gesture — double-tap files nothing now (see [FilingAction] and the
     * fullscreen viewer). It is surfaced as *Filing Action* in Settings, and it
     * decides which of Copy and Move is the primary control in the selector as
     * well as in fullscreen.
     */
    val filingAction: Flow<FilingAction> = context.dataStore.data.map { prefs ->
        FilingAction.fromStored(prefs[KEY_FULLSCREEN_GESTURE_ACTION])
    }

    suspend fun setSelectionFolderName(name: String) {
        context.dataStore.edit { prefs ->
            prefs[KEY_SELECTION_FOLDER_NAME] = name
        }
    }

    suspend fun setSortingEnabled(enabled: Boolean) {
        context.dataStore.edit { prefs ->
            prefs[KEY_SORTING_ENABLED] = enabled
        }
    }

    suspend fun setGroupingEnabled(enabled: Boolean) {
        context.dataStore.edit { prefs ->
            prefs[KEY_GROUPING_ENABLED] = enabled
        }
    }

    suspend fun setGroupingLevel(level: GroupingLevel) {
        context.dataStore.edit { prefs ->
            prefs[KEY_GROUPING_LEVEL] = level.name
        }
    }

    suspend fun setLastFolderUri(uri: String?) {
        context.dataStore.edit { prefs ->
            if (uri != null) {
                prefs[KEY_LAST_FOLDER_URI] = uri
            } else {
                prefs.remove(KEY_LAST_FOLDER_URI)
            }
        }
    }

    suspend fun setAnalysisThreadCount(count: Int) {
        context.dataStore.edit { prefs ->
            prefs[KEY_ANALYSIS_THREAD_COUNT] = count.coerceIn(1, 4)
        }
    }

    suspend fun setFullscreenButtonsEnabled(enabled: Boolean) {
        context.dataStore.edit { prefs ->
            prefs[KEY_FULLSCREEN_BUTTONS_ENABLED] = enabled
        }
    }

    suspend fun setFilingAction(action: FilingAction) {
        context.dataStore.edit { prefs ->
            prefs[KEY_FULLSCREEN_GESTURE_ACTION] = action.storedValue
        }
    }

    // ── Expanded (tablet/DeX) selector layout ────────────────────────────

    /**
     * Whether the user has already seen the on-image previous/next navigation
     * arrows once. After the first viewing they are suppressed to keep the
     * images unobstructed. Defaults to false (arrows shown on first run).
     */
    val hasSeenNavHint: Flow<Boolean> = context.dataStore.data.map { prefs ->
        prefs[KEY_HAS_SEEN_NAV_HINT] ?: false
    }

    suspend fun setHasSeenNavHint(seen: Boolean) {
        context.dataStore.edit { prefs ->
            prefs[KEY_HAS_SEEN_NAV_HINT] = seen
        }
    }

    /**
     * Whether the vertical filmstrip beside the control block is shown.
     *
     * Persisted because a photographer who has decided either way should not
     * have to decide again next launch. It defaults off — see
     * [DEFAULT_FILMSTRIP_VISIBLE]. Where it sits it costs the frames no height
     * (`FrameGeometry`), so this is a preference about clutter, not a price.
     */
    val filmstripVisible: Flow<Boolean> = context.dataStore.data.map { prefs ->
        prefs[KEY_FILMSTRIP_VISIBLE] ?: DEFAULT_FILMSTRIP_VISIBLE
    }

    /** Whether the readout block beside the current frame is shown. */
    val detailsVisible: Flow<Boolean> = context.dataStore.data.map { prefs ->
        prefs[KEY_DETAILS_VISIBLE] ?: true
    }

    /**
     * Whether Previous and Next carry their value overlay.
     *
     * The overlay covers roughly a quarter of each neighbour's width, which is
     * a real cost on a screen whose entire job is judging photographs. Default
     * on, because a photographer who cannot see the numbers cannot cull; but
     * one control turns them all off for a clean look, and that decision
     * persists so it does not have to be made every launch.
     */
    val overlayValuesVisible: Flow<Boolean> = context.dataStore.data.map { prefs ->
        prefs[KEY_OVERLAY_VALUES_VISIBLE] ?: true
    }

    suspend fun setOverlayValuesVisible(visible: Boolean) {
        context.dataStore.edit { prefs ->
            prefs[KEY_OVERLAY_VALUES_VISIBLE] = visible
        }
    }

    suspend fun setFilmstripVisible(visible: Boolean) {
        context.dataStore.edit { prefs ->
            prefs[KEY_FILMSTRIP_VISIBLE] = visible
        }
    }

    suspend fun setDetailsVisible(visible: Boolean) {
        context.dataStore.edit { prefs ->
            prefs[KEY_DETAILS_VISIBLE] = visible
        }
    }

    /**
     * Whether the fullscreen gesture hint card has been dismissed.
     *
     * Fullscreen has no visible affordance for pinch, double-tap or swipe, so
     * the card is the only place those are taught — but once taught it is pure
     * obstruction over the frame being inspected, so it shows exactly once.
     */
    val hasSeenFullscreenGestureHint: Flow<Boolean> = context.dataStore.data.map { prefs ->
        prefs[KEY_SEEN_FULLSCREEN_HINT] ?: false
    }

    suspend fun setHasSeenFullscreenGestureHint(seen: Boolean) {
        context.dataStore.edit { prefs ->
            prefs[KEY_SEEN_FULLSCREEN_HINT] = seen
        }
    }

    // ── First-run guidance ───────────────────────────────────────────────

    /**
     * The one-time hints already dismissed.
     *
     * Unknown stored keys are dropped by [SelectorHint.decode] rather than
     * failing, so a build that no longer knows a hint simply ignores it.
     */
    val seenHints: Flow<Set<SelectorHint>> = context.dataStore.data.map { prefs ->
        SelectorHint.decode(prefs[KEY_SEEN_HINTS])
    }

    /** Record that [hint] has now been shown. Idempotent. */
    suspend fun markHintSeen(hint: SelectorHint) {
        context.dataStore.edit { prefs ->
            prefs[KEY_SEEN_HINTS] = prefs[KEY_SEEN_HINTS].orEmpty() + hint.key
        }
    }

    /**
     * Show every explanation again.
     *
     * Clears the hint set **and** the two older one-shot flags, which predate it
     * and are stored separately. They are cleared here rather than migrated
     * because both are already on users' devices, and "Reset guidance" that
     * leaves two hints permanently dismissed is not a reset.
     */
    suspend fun resetGuidance() {
        context.dataStore.edit { prefs ->
            prefs.remove(KEY_SEEN_HINTS)
            prefs.remove(KEY_HAS_SEEN_NAV_HINT)
            prefs.remove(KEY_SEEN_FULLSCREEN_HINT)
        }
    }

    // ── Phone-mode settings ──────────────────────────────────────────────

    /** "copy" (default) or "move" */
    val phoneCollectionAction: Flow<String> = context.dataStore.data.map { prefs ->
        prefs[KEY_PHONE_COLLECTION_ACTION] ?: "copy"
    }

    /** Optional custom collection target folder URI. null = use Selection subfolder. */
    val phoneCollectionUri: Flow<String?> = context.dataStore.data.map { prefs ->
        prefs[KEY_PHONE_COLLECTION_URI]
    }

    /** Whether to show delete confirmation dialog (default true). */
    val phoneDeleteConfirmEnabled: Flow<Boolean> = context.dataStore.data.map { prefs ->
        prefs[KEY_PHONE_DELETE_CONFIRM] ?: true
    }

    /** Sort images horizontal-first, then vertical (default true). */
    val phoneSortByOrientation: Flow<Boolean> = context.dataStore.data.map { prefs ->
        prefs[KEY_PHONE_SORT_BY_ORIENTATION] ?: true
    }

    /** Timestamp (millis) when gesture tutorial was last shown. 0 = never. */
    val phoneGestureTutorialTs: Flow<Long> = context.dataStore.data.map { prefs ->
        prefs[KEY_PHONE_GESTURE_TUTORIAL_TS] ?: 0L
    }

    /**
     * Force mode for large-screen devices: "phone", "desktop", or null (auto).
     * On compact devices this is ignored.
     */
    val phoneForcedMode: Flow<String?> = context.dataStore.data.map { prefs ->
        prefs[KEY_PHONE_FORCE_MODE]
    }

    suspend fun setPhoneCollectionAction(action: String) {
        context.dataStore.edit { prefs ->
            prefs[KEY_PHONE_COLLECTION_ACTION] = action
        }
    }

    suspend fun setPhoneCollectionUri(uri: String?) {
        context.dataStore.edit { prefs ->
            if (uri != null) prefs[KEY_PHONE_COLLECTION_URI] = uri
            else prefs.remove(KEY_PHONE_COLLECTION_URI)
        }
    }

    suspend fun setPhoneDeleteConfirmEnabled(enabled: Boolean) {
        context.dataStore.edit { prefs ->
            prefs[KEY_PHONE_DELETE_CONFIRM] = enabled
        }
    }

    suspend fun setPhoneSortByOrientation(enabled: Boolean) {
        context.dataStore.edit { prefs ->
            prefs[KEY_PHONE_SORT_BY_ORIENTATION] = enabled
        }
    }

    suspend fun setPhoneGestureTutorialTs(ts: Long) {
        context.dataStore.edit { prefs ->
            prefs[KEY_PHONE_GESTURE_TUTORIAL_TS] = ts
        }
    }

    suspend fun setPhoneForcedMode(mode: String?) {
        context.dataStore.edit { prefs ->
            if (mode != null) prefs[KEY_PHONE_FORCE_MODE] = mode
            else prefs.remove(KEY_PHONE_FORCE_MODE)
        }
    }

    // ── File type filter ─────────────────────────────────────────────────

    /** "all" (default), "raw", or "jpg" */
    val phoneFileTypeFilter: Flow<String> = context.dataStore.data.map { prefs ->
        prefs[KEY_PHONE_FILE_TYPE_FILTER] ?: "all"
    }

    suspend fun setPhoneFileTypeFilter(filter: String) {
        context.dataStore.edit { prefs ->
            prefs[KEY_PHONE_FILE_TYPE_FILTER] = filter
        }
    }

    // ── Per-folder last position ─────────────────────────────────────────

    /**
     * Persist the last viewed image index for a given folder URI.
     * Key is derived by hashing the URI to keep preference keys short.
     */
    suspend fun setFolderLastPosition(folderUri: String, index: Int) {
        val key = intPreferencesKey("folder_pos_${folderUri.hashCode()}")
        context.dataStore.edit { prefs ->
            prefs[key] = index
        }
    }

    /** Retrieve the last viewed position for a folder. Returns 0 if none stored. */
    suspend fun getFolderLastPosition(folderUri: String): Int {
        val key = intPreferencesKey("folder_pos_${folderUri.hashCode()}")
        return context.dataStore.data.map { prefs -> prefs[key] ?: 0 }.first()
    }
}

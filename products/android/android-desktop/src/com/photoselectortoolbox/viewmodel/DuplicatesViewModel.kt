package com.photoselectortoolbox.viewmodel

import android.content.Context
import android.content.Intent
import android.net.Uri
import android.util.Log
import androidx.documentfile.provider.DocumentFile
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.photoselectortoolbox.data.model.DuplicateGroup
import com.photoselectortoolbox.data.repository.ImageRepository
import com.photoselectortoolbox.domain.usecase.FindDuplicatesUseCase
import dagger.hilt.android.lifecycle.HiltViewModel
import dagger.hilt.android.qualifiers.ApplicationContext
import javax.inject.Inject
import kotlinx.coroutines.Job
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch

data class DuplicatesUiState(
    val isScanning: Boolean = false,
    val scanProgress: Float = 0f,
    val statusText: String = "",
    val folderUri: String? = null,
    val folderName: String = "",
    val duplicateGroups: List<DuplicateGroup> = emptyList(),
    val selectedForDeletion: Set<String> = emptySet(),
    val error: String? = null
)

@HiltViewModel
class DuplicatesViewModel @Inject constructor(
    private val findDuplicatesUseCase: FindDuplicatesUseCase,
    private val imageRepository: ImageRepository,
    @ApplicationContext private val context: Context
) : ViewModel() {

    private val _uiState = MutableStateFlow(DuplicatesUiState())
    val uiState: StateFlow<DuplicatesUiState> = _uiState.asStateFlow()

    private var scanJob: Job? = null

    fun selectFolder(uri: Uri) {
        try {
            val takeFlags = Intent.FLAG_GRANT_READ_URI_PERMISSION or Intent.FLAG_GRANT_WRITE_URI_PERMISSION
            context.contentResolver.takePersistableUriPermission(uri, takeFlags)
        } catch (e: Exception) {
            Log.e("DuplicatesViewModel", "Failed to persist URI permission for $uri", e)
        }

        val folderDoc = try {
            DocumentFile.fromTreeUri(context, uri)
        } catch (e: SecurityException) {
            Log.e("DuplicatesViewModel", "SecurityException loading folder $uri", e)
            null
        }

        val folderName = folderDoc?.name ?: "Unknown"

        _uiState.update {
            it.copy(
                folderUri = uri.toString(),
                folderName = folderName,
                duplicateGroups = emptyList(),
                selectedForDeletion = emptySet(),
                error = if (folderDoc == null || !folderDoc.exists()) {
                    "Failed to load folder: permission revoked or directory deleted."
                } else null
            )
        }
    }

    fun startScan() {
        val folderUri = _uiState.value.folderUri ?: return

        scanJob?.cancel()
        scanJob = viewModelScope.launch {
            _uiState.update {
                it.copy(
                    isScanning = true,
                    scanProgress = 0f,
                    statusText = "Discovering images...",
                    duplicateGroups = emptyList(),
                    selectedForDeletion = emptySet(),
                    error = null
                )
            }

            try {
                val uri = Uri.parse(folderUri)
                // The whole folder, not the first progressive batch — a
                // duplicate set found in 24 of 842 photographs is not a
                // duplicate report, it is a sample.
                val images = imageRepository.discoverAllImages(uri)

                if (images.isEmpty()) {
                    _uiState.update {
                        it.copy(
                            isScanning = false,
                            statusText = "No images found in folder"
                        )
                    }
                    return@launch
                }

                _uiState.update {
                    it.copy(statusText = "Scanning ${images.size} images for duplicates...")
                }

                val uriSizePairs = images.map { image ->
                    Uri.parse(image.uri) to image.fileSize
                }

                findDuplicatesUseCase(uriSizePairs).collect { progress ->
                    val fraction = if (progress.total > 0) {
                        progress.processed.toFloat() / progress.total.toFloat()
                    } else {
                        0f
                    }

                    val statusText = if (progress.total > 0) {
                        "Hashing files: ${progress.processed}/${progress.total}"
                    } else {
                        "Analyzing..."
                    }

                    _uiState.update {
                        it.copy(
                            scanProgress = fraction,
                            statusText = statusText,
                            duplicateGroups = progress.groups
                        )
                    }
                }

                val groups = _uiState.value.duplicateGroups
                val totalDuplicates = groups.sumOf { it.files.size - 1 }

                _uiState.update {
                    it.copy(
                        isScanning = false,
                        scanProgress = 1f,
                        statusText = if (groups.isEmpty()) {
                            "No duplicates found"
                        } else {
                            "Found $totalDuplicates duplicates in ${groups.size} groups"
                        }
                    )
                }
            } catch (e: Exception) {
                _uiState.update {
                    it.copy(
                        isScanning = false,
                        statusText = "",
                        error = "Scan failed: ${e.message}"
                    )
                }
            }
        }
    }

    fun toggleSelection(uri: String) {
        _uiState.update { state ->
            val updated = state.selectedForDeletion.toMutableSet()
            if (uri in updated) {
                updated.remove(uri)
            } else {
                updated.add(uri)
            }
            state.copy(selectedForDeletion = updated)
        }
    }

    fun selectAllButFirst(group: DuplicateGroup) {
        _uiState.update { state ->
            val updated = state.selectedForDeletion.toMutableSet()
            // Keep the first file in the group, select the rest
            group.files.drop(1).forEach { uri ->
                updated.add(uri)
            }
            state.copy(selectedForDeletion = updated)
        }
    }

    fun deleteSelected() {
        val selected = _uiState.value.selectedForDeletion
        if (selected.isEmpty()) return

        viewModelScope.launch {
            _uiState.update {
                it.copy(
                    isScanning = true,
                    statusText = "Deleting ${selected.size} files..."
                )
            }

            var deletedCount = 0
            val failedUris = mutableListOf<String>()

            for (uriString in selected) {
                try {
                    val uri = Uri.parse(uriString)
                    val deleted = imageRepository.deleteImage(context, uri)
                    if (deleted) {
                        deletedCount++
                    } else {
                        failedUris.add(uriString)
                    }
                } catch (e: Exception) {
                    failedUris.add(uriString)
                }
            }

            // Remove deleted files from duplicate groups
            val updatedGroups = _uiState.value.duplicateGroups.mapNotNull { group ->
                val remainingFiles = group.files.filter { it !in selected || it in failedUris }
                if (remainingFiles.size > 1) {
                    group.copy(files = remainingFiles)
                } else {
                    null // Group no longer has duplicates
                }
            }

            _uiState.update {
                it.copy(
                    isScanning = false,
                    duplicateGroups = updatedGroups,
                    selectedForDeletion = failedUris.toSet(),
                    statusText = if (failedUris.isEmpty()) {
                        "Deleted $deletedCount files"
                    } else {
                        "Deleted $deletedCount files, ${failedUris.size} failed"
                    },
                    error = if (failedUris.isNotEmpty()) {
                        "Failed to delete ${failedUris.size} files"
                    } else {
                        null
                    }
                )
            }
        }
    }

    fun clearError() {
        _uiState.update { it.copy(error = null) }
    }
}

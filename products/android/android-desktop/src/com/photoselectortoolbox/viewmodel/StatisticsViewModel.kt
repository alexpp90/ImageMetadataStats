package com.photoselectortoolbox.viewmodel

import android.content.Context
import android.content.Intent
import android.net.Uri
import android.util.Log
import androidx.documentfile.provider.DocumentFile
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.photoselectortoolbox.data.repository.ImageRepository
import dagger.hilt.android.lifecycle.HiltViewModel
import dagger.hilt.android.qualifiers.ApplicationContext
import javax.inject.Inject
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.async
import kotlinx.coroutines.coroutineScope
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch
import kotlinx.coroutines.sync.Semaphore
import kotlinx.coroutines.sync.withPermit
import kotlinx.coroutines.withContext

data class StatisticsUiState(
    val isLoading: Boolean = false,
    val folderUri: String? = null,
    val folderName: String = "",
    val imageCount: Int = 0,
    val shutterSpeedDistribution: Map<String, Int> = emptyMap(),
    val apertureDistribution: Map<String, Int> = emptyMap(),
    val isoDistribution: Map<String, Int> = emptyMap(),
    val focalLengthDistribution: Map<String, Int> = emptyMap(),
    val lensDistribution: Map<String, Int> = emptyMap(),
    val error: String? = null,
    val scanProgress: Float = 0f,
    val progressText: String = "",
)

@HiltViewModel
class StatisticsViewModel @Inject constructor(
    private val imageRepository: ImageRepository,
    @ApplicationContext private val context: Context
) : ViewModel() {

    private val _uiState = MutableStateFlow(StatisticsUiState())
    val uiState: StateFlow<StatisticsUiState> = _uiState.asStateFlow()

    fun selectFolder(uri: Uri) {
        try {
            val takeFlags = Intent.FLAG_GRANT_READ_URI_PERMISSION or Intent.FLAG_GRANT_WRITE_URI_PERMISSION
            context.contentResolver.takePersistableUriPermission(uri, takeFlags)
        } catch (e: Exception) {
            Log.e("StatisticsViewModel", "Failed to persist URI permission for $uri", e)
        }

        val folderDoc = try {
            DocumentFile.fromTreeUri(context, uri)
        } catch (e: SecurityException) {
            Log.e("StatisticsViewModel", "SecurityException loading folder $uri", e)
            null
        }

        val folderName = folderDoc?.name ?: "Unknown"

        _uiState.update {
            it.copy(
                folderUri = uri.toString(),
                folderName = folderName,
                error = if (folderDoc == null || !folderDoc.exists()) {
                    "Failed to load folder: permission revoked or directory deleted."
                } else null
            )
        }

        if (folderDoc != null && folderDoc.exists()) {
            analyzeFolder()
        }
    }

    fun analyzeFolder() {
        val folderUri = _uiState.value.folderUri ?: return

        viewModelScope.launch {
            _uiState.update {
                it.copy(
                    isLoading = true,
                    scanProgress = 0f,
                    progressText = "Discovering files...",
                    error = null,
                    shutterSpeedDistribution = emptyMap(),
                    apertureDistribution = emptyMap(),
                    isoDistribution = emptyMap(),
                    focalLengthDistribution = emptyMap(),
                    lensDistribution = emptyMap()
                )
            }

            try {
                val uri = Uri.parse(folderUri)
                // The whole folder, not the first progressive batch. Discovery
                // emits cumulatively (24, then 250, then the complete snapshot),
                // so `discoverImages(uri).first()` would compute a shoot-wide
                // EXIF distribution from 24 photographs and present it as the
                // answer for 842.
                val images = imageRepository.discoverAllImages(uri)

                _uiState.update {
                    it.copy(
                        imageCount = images.size,
                        progressText = "Preparing analysis..."
                    )
                }

                val processedCount = java.util.concurrent.atomic.AtomicInteger(0)
                val exifDataList = withContext(Dispatchers.IO) {
                    coroutineScope {
                        val semaphore = Semaphore(8)
                        images.map { image ->
                            async {
                                semaphore.withPermit {
                                    val exif = try {
                                        imageRepository.getExifData(context, Uri.parse(image.uri))
                                    } catch (e: Exception) {
                                        null
                                    }
                                    val count = processedCount.incrementAndGet()
                                    val progress = count.toFloat() / images.size.toFloat()
                                    _uiState.update {
                                        it.copy(
                                            scanProgress = progress,
                                            progressText = "Analyzing metadata ($count/${images.size})"
                                        )
                                    }
                                    exif
                                }
                            }
                        }.mapNotNull { it.await() }
                    }
                }

                val shutterSpeeds = mutableMapOf<String, Int>()
                val apertures = mutableMapOf<String, Int>()
                val isoValues = mutableMapOf<String, Int>()
                val focalLengths = mutableMapOf<String, Int>()
                val lenses = mutableMapOf<String, Int>()

                for (exif in exifDataList) {
                    exif.shutterSpeed?.let { speed ->
                        val label = formatShutterSpeed(speed)
                        shutterSpeeds[label] = (shutterSpeeds[label] ?: 0) + 1
                    }

                    exif.aperture?.let { aperture ->
                        val label = "f/%.1f".format(java.util.Locale.US, aperture)
                        apertures[label] = (apertures[label] ?: 0) + 1
                    }

                    exif.iso?.let { iso ->
                        val label = "ISO $iso"
                        isoValues[label] = (isoValues[label] ?: 0) + 1
                    }

                    exif.focalLength?.let { focal ->
                        val label = "${focal.toInt()}mm"
                        focalLengths[label] = (focalLengths[label] ?: 0) + 1
                    }

                    val lensName = exif.lens
                    if (lensName != "Unknown") {
                        lenses[lensName] = (lenses[lensName] ?: 0) + 1
                    }
                }

                _uiState.update {
                    it.copy(
                        isLoading = false,
                        shutterSpeedDistribution = shutterSpeeds.toSortedMap(),
                        apertureDistribution = apertures.toSortedMap(),
                        isoDistribution = isoValues.toSortedMap(),
                        focalLengthDistribution = focalLengths.toSortedMap(),
                        lensDistribution = lenses.toSortedMap()
                    )
                }
            } catch (e: Exception) {
                _uiState.update {
                    it.copy(
                        isLoading = false,
                        error = "Analysis failed: ${e.message}"
                    )
                }
            }
        }
    }

    fun clearError() {
        _uiState.update { it.copy(error = null) }
    }

    /**
     * Format a shutter speed value (in seconds) as a human-readable string.
     * Values < 1 second are displayed as fractions (e.g., "1/250s").
     * Values >= 1 second are displayed with quotes (e.g., "2\"").
     */
    private fun formatShutterSpeed(speed: Double): String {
        return if (speed >= 1.0) {
            if (speed == speed.toLong().toDouble()) {
                "${speed.toLong()}\""
            } else {
                "%.1f\"".format(java.util.Locale.US, speed)
            }
        } else {
            val denominator = (1.0 / speed).toLong()
            "1/${denominator}s"
        }
    }
}

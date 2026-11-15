package com.sitediary.mobile.ui.screens.detail

import androidx.lifecycle.SavedStateHandle
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.sitediary.mobile.data.local.dao.SiteLogWithPhotos
import com.sitediary.mobile.data.media.AudioRecorderController
import com.sitediary.mobile.data.repository.SiteDiaryRepository
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.SharingStarted
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.combine
import kotlinx.coroutines.flow.stateIn
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch
import javax.inject.Inject

data class LogDetailUiState(
    val logWithPhotos: SiteLogWithPhotos? = null,
    val tasksText: String = "",
    val laborCountText: String = "",
    val materialsText: String = "",
    val blockersText: String = "",
    val isPlayingAudio: Boolean = false,
    val isSaving: Boolean = false,
    val isRetryingExtraction: Boolean = false,
    val feedbackMessage: String? = null,
    val errorMessage: String? = null,
    val formInitialized: Boolean = false
)

@HiltViewModel
class LogDetailViewModel @Inject constructor(
    savedStateHandle: SavedStateHandle,
    private val repository: SiteDiaryRepository,
    private val audioRecorder: AudioRecorderController
) : ViewModel() {

    val logId: String = checkNotNull(savedStateHandle["logId"])

    private val _formState = MutableStateFlow(LogDetailUiState())

    val uiState: StateFlow<LogDetailUiState> = combine(
        repository.observeLogDetail(logId),
        _formState,
        audioRecorder.isPlaying
    ) { logWithPhotos, form, isPlaying ->
        if (logWithPhotos != null && !form.formInitialized) {
            val summary = logWithPhotos.log.structuredSummary
            val initialized = form.copy(
                logWithPhotos = logWithPhotos,
                tasksText = summary?.tasksCompleted?.joinToString("\n").orEmpty(),
                laborCountText = summary?.laborCount?.toString().orEmpty(),
                materialsText = summary?.materialDeliveries?.joinToString("\n").orEmpty(),
                blockersText = summary?.blockers?.joinToString("\n").orEmpty(),
                isPlayingAudio = isPlaying,
                formInitialized = true
            )
            _formState.value = initialized
            initialized
        } else {
            form.copy(
                logWithPhotos = logWithPhotos,
                isPlayingAudio = isPlaying
            )
        }
    }.stateIn(
        scope = viewModelScope,
        started = SharingStarted.WhileSubscribed(5_000),
        initialValue = LogDetailUiState()
    )

    fun onTasksChange(value: String) {
        _formState.update { it.copy(tasksText = value, feedbackMessage = null, errorMessage = null) }
    }

    fun onLaborCountChange(value: String) {
        val filtered = value.filter { it.isDigit() }
        _formState.update { it.copy(laborCountText = filtered, feedbackMessage = null, errorMessage = null) }
    }

    fun onMaterialsChange(value: String) {
        _formState.update { it.copy(materialsText = value, feedbackMessage = null, errorMessage = null) }
    }

    fun onBlockersChange(value: String) {
        _formState.update { it.copy(blockersText = value, feedbackMessage = null, errorMessage = null) }
    }

    fun toggleAudioPlayback() {
        val log = uiState.value.logWithPhotos?.log ?: return
        val source = log.audioLocalPath ?: log.audioUrl ?: return
        audioRecorder.togglePlayback(source)
    }

    fun updateNotes(notes: String) {
        viewModelScope.launch {
            _formState.update { it.copy(isSaving = true, errorMessage = null, feedbackMessage = null) }
            runCatching {
                repository.editSiteLogNotesOffline(logId, notes)
            }.onSuccess {
                _formState.update { it.copy(isSaving = false, feedbackMessage = "Notes saved offline & queued for sync") }
            }.onFailure { err ->
                _formState.update { it.copy(isSaving = false, errorMessage = err.message ?: "Failed to update notes") }
            }
        }
    }

    fun deleteLog(onDeleted: () -> Unit) {
        viewModelScope.launch {
            _formState.update { it.copy(isSaving = true, errorMessage = null) }
            runCatching {
                audioRecorder.stopPlayback()
                repository.softDeleteSiteLogOffline(logId)
            }.onSuccess {
                _formState.update { it.copy(isSaving = false) }
                onDeleted()
            }.onFailure { err ->
                _formState.update { it.copy(isSaving = false, errorMessage = err.message ?: "Failed to delete log") }
            }
        }
    }

    fun saveCorrections() {
        val form = _formState.value
        val tasks = parseLines(form.tasksText)
        val materials = parseLines(form.materialsText)
        val blockers = parseLines(form.blockersText)
        val laborCount = form.laborCountText.trim().takeIf { it.isNotEmpty() }?.toIntOrNull()

        viewModelScope.launch {
            _formState.update { it.copy(isSaving = true, errorMessage = null, feedbackMessage = null) }
            runCatching {
                repository.saveHumanSummaryCorrection(
                    logId = logId,
                    tasksCompleted = tasks,
                    laborCount = laborCount,
                    materialDeliveries = materials,
                    blockers = blockers
                )
            }.onSuccess {
                _formState.update {
                    it.copy(
                        isSaving = false,
                        feedbackMessage = "Saved locally — queued for sync"
                    )
                }
            }.onFailure { err ->
                _formState.update {
                    it.copy(
                        isSaving = false,
                        errorMessage = err.message ?: "Failed to save edits"
                    )
                }
            }
        }
    }

    fun retryExtraction() {
        viewModelScope.launch {
            _formState.update { it.copy(isRetryingExtraction = true, errorMessage = null) }
            repository.retryExtraction(logId)
                .onSuccess {
                    _formState.update { it.copy(isRetryingExtraction = false) }
                }
                .onFailure { err ->
                    _formState.update {
                        it.copy(
                            isRetryingExtraction = false,
                            errorMessage = err.message ?: "Unable to queue AI extraction"
                        )
                    }
                }
        }
    }

    private fun parseLines(raw: String): List<String> =
        raw.lines().map { it.trim() }.filter { it.isNotEmpty() }

    override fun onCleared() {
        super.onCleared()
        audioRecorder.stopPlayback()
    }
}

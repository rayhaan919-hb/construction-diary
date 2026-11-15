package com.sitediary.mobile.ui.screens.record

import androidx.lifecycle.SavedStateHandle
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.sitediary.mobile.data.local.entity.ProjectEntity
import com.sitediary.mobile.data.media.AudioRecorderController
import com.sitediary.mobile.data.media.LocalMediaFileManager
import com.sitediary.mobile.data.media.PhotoProcessor
import com.sitediary.mobile.data.repository.CapturedPhotoDraft
import com.sitediary.mobile.data.repository.SiteDiaryRepository
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.SharingStarted
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.combine
import kotlinx.coroutines.flow.stateIn
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import java.io.File
import java.time.Clock
import java.util.UUID
import javax.inject.Inject

data class RecordNoteUiState(
    val project: ProjectEntity? = null,
    val isRecording: Boolean = false,
    val elapsedMs: Long = 0L,
    val recordedFile: File? = null,
    val recordedDurationMs: Int? = null,
    val isPlayingPreview: Boolean = false,
    val photos: List<CapturedPhotoDraft> = emptyList(),
    val notes: String = "",
    val isCameraOpen: Boolean = false,
    val isProcessingPhoto: Boolean = false,
    val isSaving: Boolean = false,
    val errorMessage: String? = null
)

@HiltViewModel
class RecordNoteViewModel @Inject constructor(
    savedStateHandle: SavedStateHandle,
    private val repository: SiteDiaryRepository,
    private val audioRecorder: AudioRecorderController,
    private val photoProcessor: PhotoProcessor,
    private val mediaFileManager: LocalMediaFileManager,
    private val clock: Clock
) : ViewModel() {

    val projectId: String = checkNotNull(savedStateHandle["projectId"])
    private val draftLogId: String = UUID.randomUUID().toString()
    private var savedSuccessfully = false

    private val _localState = MutableStateFlow(RecordNoteUiState())

    @Suppress("UNCHECKED_CAST")
    val uiState: StateFlow<RecordNoteUiState> = combine(
        _localState,
        repository.observeProject(projectId),
        audioRecorder.isRecording,
        audioRecorder.elapsedMs,
        audioRecorder.completedRecording,
        audioRecorder.isPlaying
    ) { values ->
        val local = values[0] as RecordNoteUiState
        val project = values[1] as ProjectEntity?
        val isRecording = values[2] as Boolean
        val elapsedMs = values[3] as Long
        val completed = values[4] as com.sitediary.mobile.data.media.RecordingResult?
        val isPlayingPreview = values[5] as Boolean
        local.copy(
            project = project,
            isRecording = isRecording,
            elapsedMs = if (isRecording) elapsedMs else (completed?.durationMs?.toLong() ?: local.elapsedMs),
            recordedFile = completed?.file ?: local.recordedFile,
            recordedDurationMs = completed?.durationMs ?: local.recordedDurationMs,
            isPlayingPreview = isPlayingPreview
        )
    }.stateIn(
        scope = viewModelScope,
        started = SharingStarted.WhileSubscribed(5_000),
        initialValue = RecordNoteUiState()
    )

    fun startRecording() {
        val file = mediaFileManager.createAudioFile(projectId, draftLogId)
        _localState.update { it.copy(errorMessage = null, recordedFile = null, recordedDurationMs = null) }
        runCatching {
            audioRecorder.startRecording(file)
        }.onFailure { err ->
            _localState.update { it.copy(errorMessage = err.message ?: "Unable to start microphone") }
        }
    }

    fun stopRecording() {
        val result = audioRecorder.stopRecording()
        if (result != null) {
            _localState.update {
                it.copy(
                    recordedFile = result.file,
                    recordedDurationMs = result.durationMs,
                    elapsedMs = result.durationMs.toLong()
                )
            }
        }
    }

    fun deleteRecording() {
        audioRecorder.stopPlayback()
        audioRecorder.stopRecording()
        audioRecorder.clearCompletedRecording()
        _localState.value.recordedFile?.let { mediaFileManager.deleteFileIfExists(it.absolutePath) }
        _localState.update {
            it.copy(
                recordedFile = null,
                recordedDurationMs = null,
                elapsedMs = 0L
            )
        }
    }

    fun togglePreviewPlayback() {
        val path = uiState.value.recordedFile?.absolutePath ?: return
        audioRecorder.togglePlayback(path)
    }

    fun openCamera() {
        _localState.update { it.copy(isCameraOpen = true, errorMessage = null) }
    }

    fun closeCamera() {
        _localState.update { it.copy(isCameraOpen = false) }
    }

    fun createTempPhotoFile(): File = mediaFileManager.createTempCaptureFile("site_photo_")

    fun onPhotoCaptured(tempFile: File) {
        val allowGps = uiState.value.project?.allowPhotoGps == true
        val photoId = UUID.randomUUID().toString()
        val targetFile = mediaFileManager.createPhotoFile(projectId, photoId)
        viewModelScope.launch {
            _localState.update { it.copy(isProcessingPhoto = true, errorMessage = null) }
            val result = withContext(Dispatchers.IO) {
                runCatching {
                    val processed = photoProcessor.processCapturedPhoto(
                        sourceFile = tempFile,
                        targetFile = targetFile,
                        allowPhotoGps = allowGps
                    )
                    tempFile.delete()
                    CapturedPhotoDraft(
                        id = photoId,
                        processed = processed,
                        takenAtIso = clock.instant().toString()
                    )
                }
            }
            result.onSuccess { draft ->
                _localState.update {
                    it.copy(
                        isProcessingPhoto = false,
                        isCameraOpen = false,
                        photos = it.photos + draft
                    )
                }
            }.onFailure { err ->
                tempFile.delete()
                _localState.update {
                    it.copy(
                        isProcessingPhoto = false,
                        errorMessage = err.message ?: "Photo processing failed"
                    )
                }
            }
        }
    }

    fun onCameraError(message: String) {
        _localState.update { it.copy(isProcessingPhoto = false, errorMessage = message) }
    }

    fun removePhoto(photoId: String) {
        val target = _localState.value.photos.find { it.id == photoId }
        target?.let { mediaFileManager.deleteFileIfExists(it.processed.file.absolutePath) }
        _localState.update { state ->
            state.copy(photos = state.photos.filterNot { it.id == photoId })
        }
    }

    fun onNotesChange(value: String) {
        _localState.update { it.copy(notes = value.take(4000), errorMessage = null) }
    }

    fun saveOffline(onSaved: () -> Unit) {
        if (uiState.value.isRecording) {
            stopRecording()
        }
        val state = uiState.value
        if (state.recordedFile == null && state.photos.isEmpty() && state.notes.isBlank()) {
            _localState.update {
                it.copy(errorMessage = "Record audio, take a photo, or enter a note before saving.")
            }
            return
        }

        viewModelScope.launch {
            _localState.update { it.copy(isSaving = true, errorMessage = null) }
            runCatching {
                repository.createSiteLogOffline(
                    logId = draftLogId,
                    projectId = projectId,
                    notes = state.notes,
                    audioFile = state.recordedFile,
                    audioDurationMs = state.recordedDurationMs,
                    photos = state.photos
                )
            }.onSuccess {
                savedSuccessfully = true
                _localState.update { it.copy(isSaving = false) }
                onSaved()
            }.onFailure { err ->
                _localState.update {
                    it.copy(isSaving = false, errorMessage = err.message ?: "Failed to save offline")
                }
            }
        }
    }

    override fun onCleared() {
        super.onCleared()
        audioRecorder.release()
        if (!savedSuccessfully) {
            _localState.value.recordedFile?.let { mediaFileManager.deleteFileIfExists(it.absolutePath) }
            _localState.value.photos.forEach {
                mediaFileManager.deleteFileIfExists(it.processed.file.absolutePath)
            }
        }
    }
}

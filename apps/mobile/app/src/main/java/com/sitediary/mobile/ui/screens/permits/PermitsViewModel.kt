package com.sitediary.mobile.ui.screens.permits

import androidx.lifecycle.SavedStateHandle
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.sitediary.mobile.data.local.entity.ProjectEntity
import com.sitediary.mobile.data.media.LocalMediaFileManager
import com.sitediary.mobile.data.media.PhotoProcessor
import com.sitediary.mobile.data.prefs.AppPreferences
import com.sitediary.mobile.data.repository.SiteDiaryRepository
import com.sitediary.mobile.domain.model.EvaluatedPermit
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.SharingStarted
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.combine
import kotlinx.coroutines.flow.stateIn
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import java.io.File
import java.time.LocalDate
import java.util.UUID
import javax.inject.Inject

data class PermitsUiState(
    val project: ProjectEntity? = null,
    val permits: List<EvaluatedPermit> = emptyList(),
    val isSyncing: Boolean = false,
    val isInitialLoading: Boolean = true,
    val lastSyncError: String? = null,
    val showAddDialog: Boolean = false,
    val draftPermitId: String = UUID.randomUUID().toString(),
    val permitName: String = "",
    val authority: String = "",
    val permitNumber: String = "",
    val issueDate: String = "",
    val expiryDate: String = "",
    val documentFile: File? = null,
    val isCameraOpen: Boolean = false,
    val isSaving: Boolean = false,
    val formError: String? = null
)

@HiltViewModel
class PermitsViewModel @Inject constructor(
    savedStateHandle: SavedStateHandle,
    private val repository: SiteDiaryRepository,
    private val appPreferences: AppPreferences,
    private val photoProcessor: PhotoProcessor,
    private val mediaFileManager: LocalMediaFileManager
) : ViewModel() {

    val projectId: String = checkNotNull(savedStateHandle["projectId"])

    private val _formState = MutableStateFlow(PermitsUiState())

    val uiState: StateFlow<PermitsUiState> = combine(
        repository.observeProject(projectId),
        repository.observeProjectPermits(projectId),
        appPreferences.isSyncing,
        appPreferences.lastSyncError,
        _formState
    ) { project, permits, isSyncing, syncError, form ->
        form.copy(
            project = project,
            permits = permits,
            isSyncing = isSyncing,
            isInitialLoading = permits.isEmpty() && project == null && isSyncing,
            lastSyncError = syncError
        )
    }.stateIn(
        scope = viewModelScope,
        started = SharingStarted.WhileSubscribed(5_000),
        initialValue = PermitsUiState()
    )

    fun syncNow() {
        viewModelScope.launch {
            repository.triggerSync()
        }
    }

    fun openAddDialog() {
        _formState.update {
            it.copy(
                showAddDialog = true,
                draftPermitId = UUID.randomUUID().toString(),
                permitName = "",
                authority = "",
                permitNumber = "",
                issueDate = "",
                expiryDate = "",
                documentFile = null,
                isCameraOpen = false,
                formError = null
            )
        }
    }

    fun closeAddDialog() {
        _formState.value.documentFile?.let { mediaFileManager.deleteFileIfExists(it.absolutePath) }
        _formState.update { it.copy(showAddDialog = false, isCameraOpen = false, documentFile = null) }
    }

    fun onPermitNameChange(v: String) = _formState.update { it.copy(permitName = v, formError = null) }
    fun onAuthorityChange(v: String) = _formState.update { it.copy(authority = v, formError = null) }
    fun onPermitNumberChange(v: String) = _formState.update { it.copy(permitNumber = v) }
    fun onIssueDateChange(v: String) = _formState.update { it.copy(issueDate = v, formError = null) }
    fun onExpiryDateChange(v: String) = _formState.update { it.copy(expiryDate = v, formError = null) }

    fun openDocumentCamera() = _formState.update { it.copy(isCameraOpen = true, formError = null) }
    fun closeDocumentCamera() = _formState.update { it.copy(isCameraOpen = false) }
    fun createTempDocFile(): File = mediaFileManager.createTempCaptureFile("permit_doc_")

    fun onDocumentCaptured(tempFile: File) {
        val form = _formState.value
        val allowGps = uiState.value.project?.allowPhotoGps == true
        val targetFile = mediaFileManager.createPermitDocumentFile(projectId, form.draftPermitId)
        viewModelScope.launch {
            val result = withContext(Dispatchers.IO) {
                runCatching {
                    photoProcessor.processCapturedPhoto(
                        sourceFile = tempFile,
                        targetFile = targetFile,
                        allowPhotoGps = allowGps
                    )
                    tempFile.delete()
                    targetFile
                }
            }
            result.onSuccess { file ->
                _formState.update { it.copy(documentFile = file, isCameraOpen = false) }
            }.onFailure { err ->
                tempFile.delete()
                _formState.update { it.copy(formError = err.message ?: "Failed to process document photo") }
            }
        }
    }

    fun onCameraError(message: String) {
        _formState.update { it.copy(formError = message) }
    }

    fun savePermit() {
        val form = _formState.value
        if (form.permitName.isBlank() || form.authority.isBlank()) {
            _formState.update { it.copy(formError = "Permit name and authority are required.") }
            return
        }
        val parsedExpiry = runCatching { LocalDate.parse(form.expiryDate.trim()) }.getOrNull()
        if (parsedExpiry == null) {
            _formState.update { it.copy(formError = "Expiry date must use YYYY-MM-DD format.") }
            return
        }
        if (form.issueDate.isNotBlank() &&
            runCatching { LocalDate.parse(form.issueDate.trim()) }.isFailure
        ) {
            _formState.update { it.copy(formError = "Issue date must use YYYY-MM-DD format.") }
            return
        }

        viewModelScope.launch {
            _formState.update { it.copy(isSaving = true, formError = null) }
            runCatching {
                repository.createPermitOffline(
                    permitId = form.draftPermitId,
                    projectId = projectId,
                    permitName = form.permitName,
                    authority = form.authority,
                    permitNumber = form.permitNumber,
                    issueDate = form.issueDate,
                    expiryDate = parsedExpiry.toString(),
                    documentFile = form.documentFile
                )
            }.onSuccess {
                _formState.update {
                    it.copy(
                        isSaving = false,
                        showAddDialog = false,
                        isCameraOpen = false,
                        documentFile = null
                    )
                }
            }.onFailure { err ->
                _formState.update {
                    it.copy(isSaving = false, formError = err.message ?: "Failed to save permit")
                }
            }
        }
    }
}

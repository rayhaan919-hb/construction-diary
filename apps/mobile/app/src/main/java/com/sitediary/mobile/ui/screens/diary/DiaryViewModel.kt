package com.sitediary.mobile.ui.screens.diary

import androidx.lifecycle.SavedStateHandle
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.sitediary.mobile.data.local.dao.SiteLogWithPhotos
import com.sitediary.mobile.data.local.entity.ProjectEntity
import com.sitediary.mobile.data.prefs.AppPreferences
import com.sitediary.mobile.data.repository.SiteDiaryRepository
import com.sitediary.mobile.domain.model.PermitBannerSummary
import com.sitediary.mobile.domain.model.PermitStatusCalculator
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.flow.SharingStarted
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.combine
import kotlinx.coroutines.flow.stateIn
import kotlinx.coroutines.launch
import javax.inject.Inject

data class DiaryUiState(
    val project: ProjectEntity? = null,
    val todayDate: String = "",
    val todayLogCount: Int = 0,
    val todayLaborMax: Int? = null,
    val todayBlockersCount: Int = 0,
    val bannerSummary: PermitBannerSummary? = null,
    val logs: List<SiteLogWithPhotos> = emptyList(),
    val isSyncing: Boolean = false,
    val isInitialLoading: Boolean = true,
    val lastSyncError: String? = null
)

@HiltViewModel
class DiaryViewModel @Inject constructor(
    savedStateHandle: SavedStateHandle,
    private val repository: SiteDiaryRepository,
    private val appPreferences: AppPreferences,
    private val permitStatusCalculator: PermitStatusCalculator
) : ViewModel() {

    val projectId: String = checkNotNull(savedStateHandle["projectId"])

    val uiState: StateFlow<DiaryUiState> = combine(
        repository.observeProject(projectId),
        repository.observeProjectPermits(projectId),
        repository.observeProjectLogs(projectId),
        appPreferences.isSyncing,
        appPreferences.lastSyncError
    ) { project, permits, logs, isSyncing, syncError ->
        val timezone = project?.timezone ?: PermitStatusCalculator.DEFAULT_TIMEZONE
        val today = permitStatusCalculator.projectToday(timezone).toString()
        val todayLogs = logs.filter { it.log.logDate == today }
        val laborMax = todayLogs.mapNotNull { it.log.structuredSummary?.laborCount }.maxOrNull()
        val blockersCount = todayLogs
            .flatMap { it.log.structuredSummary?.blockers.orEmpty() }
            .map { it.trim().lowercase() }
            .filter { it.isNotEmpty() }
            .distinct()
            .size

        DiaryUiState(
            project = project,
            todayDate = today,
            todayLogCount = todayLogs.size,
            todayLaborMax = laborMax,
            todayBlockersCount = blockersCount,
            bannerSummary = permitStatusCalculator.computeBannerSummary(permits),
            logs = logs,
            isSyncing = isSyncing,
            isInitialLoading = project == null && isSyncing,
            lastSyncError = syncError
        )
    }.stateIn(
        scope = viewModelScope,
        started = SharingStarted.WhileSubscribed(5_000),
        initialValue = DiaryUiState()
    )

    fun syncNow() {
        viewModelScope.launch {
            repository.triggerSync()
        }
    }
}

package com.sitediary.mobile.ui.screens.projects

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.sitediary.mobile.data.prefs.AppPreferences
import com.sitediary.mobile.data.repository.AuthRepository
import com.sitediary.mobile.data.repository.ProjectCardModel
import com.sitediary.mobile.data.repository.SiteDiaryRepository
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.ExperimentalCoroutinesApi
import kotlinx.coroutines.flow.SharingStarted
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.combine
import kotlinx.coroutines.flow.flatMapLatest
import kotlinx.coroutines.flow.flowOf
import kotlinx.coroutines.flow.stateIn
import kotlinx.coroutines.launch
import javax.inject.Inject

data class ProjectsUiState(
    val userName: String = "",
    val projects: List<ProjectCardModel> = emptyList(),
    val isSyncing: Boolean = false,
    val isInitialLoading: Boolean = true,
    val pendingSyncCount: Int = 0,
    val lastSyncError: String? = null,
    val uploadOnMobileData: Boolean = false,
    val currentLocale: String = "en"
)

@OptIn(ExperimentalCoroutinesApi::class)
@HiltViewModel
class ProjectsViewModel @Inject constructor(
    private val repository: SiteDiaryRepository,
    private val authRepository: AuthRepository,
    private val appPreferences: AppPreferences
) : ViewModel() {

    private val projectsFlow = appPreferences.sessionFlow.flatMapLatest { session ->
        if (session == null) {
            flowOf(emptyList())
        } else {
            repository.observeProjectCards(session.user.id)
        }
    }

    val uiState: StateFlow<ProjectsUiState> = combine(
        appPreferences.sessionFlow,
        projectsFlow,
        appPreferences.isSyncing,
        repository.observeTotalPendingSyncCount(),
        appPreferences.lastSyncError,
        appPreferences.uploadOnMobileData,
        appPreferences.appLocale,
        appPreferences.lastSyncEpochMs
    ) { values ->
        val session = values[0] as com.sitediary.mobile.data.prefs.AuthSession?
        @Suppress("UNCHECKED_CAST")
        val projects = values[1] as List<ProjectCardModel>
        val isSyncing = values[2] as Boolean
        val pendingCount = values[3] as Int
        val lastError = values[4] as String?
        val mobileData = values[5] as Boolean
        val locale = values[6] as String
        val lastSyncMs = values[7] as Long?

        ProjectsUiState(
            userName = session?.user?.fullName ?: "",
            projects = projects,
            isSyncing = isSyncing,
            isInitialLoading = projects.isEmpty() && isSyncing && lastSyncMs == null && lastError == null,
            pendingSyncCount = pendingCount,
            lastSyncError = lastError,
            uploadOnMobileData = mobileData,
            currentLocale = locale
        )
    }.stateIn(
        scope = viewModelScope,
        started = SharingStarted.WhileSubscribed(5_000),
        initialValue = ProjectsUiState()
    )

    fun syncNow() {
        viewModelScope.launch {
            repository.triggerSync()
        }
    }

    fun setUploadOnMobileData(enabled: Boolean) {
        viewModelScope.launch {
            repository.setUploadOnMobileData(enabled)
        }
    }

    fun toggleLocale(locale: String) {
        viewModelScope.launch {
            appPreferences.setAppLocale(locale)
        }
    }

    fun signOut() {
        viewModelScope.launch {
            authRepository.logout()
        }
    }
}

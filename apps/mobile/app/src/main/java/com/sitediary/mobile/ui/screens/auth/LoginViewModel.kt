package com.sitediary.mobile.ui.screens.auth

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.sitediary.mobile.data.prefs.AppPreferences
import com.sitediary.mobile.data.repository.AuthActionResult
import com.sitediary.mobile.data.repository.AuthRepository
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.SharingStarted
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.stateIn
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch
import javax.inject.Inject

data class LoginUiState(
    val email: String = "",
    val password: String = "",
    val isSubmitting: Boolean = false,
    val errorMessage: String? = null
)

@HiltViewModel
class LoginViewModel @Inject constructor(
    private val authRepository: AuthRepository,
    private val appPreferences: AppPreferences
) : ViewModel() {

    private val _uiState = MutableStateFlow(LoginUiState())
    val uiState: StateFlow<LoginUiState> = _uiState.asStateFlow()

    val appLocale: StateFlow<String> = appPreferences.appLocale
        .stateIn(viewModelScope, SharingStarted.WhileSubscribed(5_000), "en")

    fun onEmailChange(value: String) {
        _uiState.update { it.copy(email = value, errorMessage = null) }
    }

    fun onPasswordChange(value: String) {
        _uiState.update { it.copy(password = value, errorMessage = null) }
    }

    fun toggleLocale(locale: String) {
        viewModelScope.launch {
            appPreferences.setAppLocale(locale)
        }
    }

    fun submitLogin(onSuccess: (mustChangePassword: Boolean) -> Unit) {
        val state = _uiState.value
        if (state.email.isBlank() || state.password.length < 8) {
            _uiState.update { it.copy(errorMessage = "Enter a valid email and password (min 8 chars).") }
            return
        }
        viewModelScope.launch {
            _uiState.update { it.copy(isSubmitting = true, errorMessage = null) }
            when (val result = authRepository.login(state.email, state.password)) {
                is AuthActionResult.Success -> {
                    _uiState.update { it.copy(isSubmitting = false) }
                    onSuccess(result.user.mustChangePassword)
                }

                is AuthActionResult.Error -> {
                    _uiState.update { it.copy(isSubmitting = false, errorMessage = result.message) }
                }
            }
        }
    }
}

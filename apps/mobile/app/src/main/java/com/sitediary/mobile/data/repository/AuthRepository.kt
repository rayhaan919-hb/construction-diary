package com.sitediary.mobile.data.repository

import android.os.Build
import com.sitediary.mobile.data.local.SiteDiaryDatabase
import com.sitediary.mobile.data.media.LocalMediaFileManager
import com.sitediary.mobile.data.notifications.FcmTokenManager
import com.sitediary.mobile.data.prefs.AppPreferences
import com.sitediary.mobile.data.prefs.AuthSession
import com.sitediary.mobile.data.remote.JsonProvider
import com.sitediary.mobile.data.remote.SiteDiaryApi
import com.sitediary.mobile.data.remote.dto.ChangePasswordRequestDto
import com.sitediary.mobile.data.remote.dto.LoginRequestDto
import com.sitediary.mobile.data.remote.dto.LogoutRequestDto
import com.sitediary.mobile.data.remote.dto.ProblemDto
import com.sitediary.mobile.data.remote.dto.UserDto
import com.sitediary.mobile.data.sync.SyncScheduler
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.withContext
import java.io.IOException
import javax.inject.Inject
import javax.inject.Singleton

sealed interface AuthActionResult {
    data class Success(val user: UserDto) : AuthActionResult
    data class Error(val message: String, val isNetworkError: Boolean = false) : AuthActionResult
}

@Singleton
class AuthRepository @Inject constructor(
    private val api: SiteDiaryApi,
    private val appPreferences: AppPreferences,
    private val database: SiteDiaryDatabase,
    private val mediaFileManager: LocalMediaFileManager,
    private val fcmTokenManager: FcmTokenManager,
    private val syncScheduler: SyncScheduler
) {
    val sessionFlow: StateFlow<AuthSession?> = appPreferences.sessionFlow

    suspend fun login(email: String, password: String): AuthActionResult {
        val response = try {
            api.login(
                LoginRequestDto(
                    email = email.trim(),
                    password = password,
                    deviceLabel = Build.MODEL
                )
            )
        } catch (_: IOException) {
            return AuthActionResult.Error(
                message = "Cannot reach server. Check your connection.",
                isNetworkError = true
            )
        }

        if (!response.isSuccessful) {
            val detail = parseProblemDetail(response.errorBody()?.string())
                ?: if (response.code() == 401) "Invalid email or password" else "Sign in failed (${response.code()})"
            return AuthActionResult.Error(message = detail)
        }

        val tokenPair = response.body()
            ?: return AuthActionResult.Error(message = "Empty login response")

        appPreferences.saveTokenPair(tokenPair)
        if (tokenPair.user.preferredLocale == "ur") {
            appPreferences.setAppLocale("ur")
        }

        fcmTokenManager.registerCurrentTokenIfAvailable()
        syncScheduler.ensurePeriodicWorkersScheduled()
        val mobileData = appPreferences.uploadOnMobileData.first()
        syncScheduler.scheduleImmediateSync(mobileData)

        return AuthActionResult.Success(tokenPair.user)
    }

    suspend fun changePassword(currentPassword: String, newPassword: String): AuthActionResult {
        val response = try {
            api.changePassword(
                ChangePasswordRequestDto(
                    currentPassword = currentPassword,
                    newPassword = newPassword
                )
            )
        } catch (_: IOException) {
            return AuthActionResult.Error(
                message = "Network error while updating password.",
                isNetworkError = true
            )
        }

        if (!response.isSuccessful) {
            val detail = parseProblemDetail(response.errorBody()?.string())
                ?: "Unable to update password (${response.code()})"
            return AuthActionResult.Error(message = detail)
        }

        appPreferences.markPasswordChanged()
        val user = appPreferences.getCurrentUser()
            ?: return AuthActionResult.Error("Session unavailable")

        val mobileData = appPreferences.uploadOnMobileData.first()
        syncScheduler.scheduleImmediateSync(mobileData)
        return AuthActionResult.Success(user)
    }

    suspend fun logout() {
        fcmTokenManager.unregisterCurrentToken()
        val refreshToken = appPreferences.getRefreshToken()
        if (!refreshToken.isNullOrBlank()) {
            runCatching {
                api.logout(LogoutRequestDto(refreshToken = refreshToken))
            }
        }
        syncScheduler.cancelAllSyncWork()
        appPreferences.clearSession()
        appPreferences.clearAllSettingsOnLogout()
        withContext(Dispatchers.IO) {
            database.clearAllTables()
            mediaFileManager.clearAllMedia()
        }
    }

    private fun parseProblemDetail(raw: String?): String? {
        if (raw.isNullOrBlank()) return null
        return runCatching {
            val problem = JsonProvider.json.decodeFromString(ProblemDto.serializer(), raw)
            problem.detail ?: problem.title
        }.getOrNull()
    }
}

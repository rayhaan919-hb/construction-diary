package com.sitediary.mobile.data.notifications

import android.content.Context
import com.google.firebase.FirebaseApp
import com.google.firebase.messaging.FirebaseMessaging
import com.sitediary.mobile.data.prefs.AppPreferences
import com.sitediary.mobile.data.remote.SiteDiaryApi
import com.sitediary.mobile.data.remote.dto.DeviceTokenRequestDto
import dagger.hilt.android.qualifiers.ApplicationContext
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.launch
import javax.inject.Inject
import javax.inject.Singleton

@Singleton
class FcmTokenManager @Inject constructor(
    @ApplicationContext private val context: Context,
    private val api: SiteDiaryApi,
    private val appPreferences: AppPreferences
) {
    private val scope = CoroutineScope(SupervisorJob() + Dispatchers.IO)

    fun registerCurrentTokenIfAvailable() {
        if (appPreferences.getAccessToken().isNullOrBlank()) return
        val hasFirebase = runCatching { FirebaseApp.getApps(context).isNotEmpty() }.getOrDefault(false)
        if (!hasFirebase) return

        runCatching {
            FirebaseMessaging.getInstance().token.addOnSuccessListener { token ->
                if (!token.isNullOrBlank()) {
                    scope.launch {
                        registerToken(token)
                    }
                }
            }
        }
    }

    suspend fun registerToken(token: String) {
        if (token.isBlank() || appPreferences.getAccessToken().isNullOrBlank()) return
        runCatching {
            api.registerDeviceToken(DeviceTokenRequestDto(fcmToken = token))
        }
    }
}

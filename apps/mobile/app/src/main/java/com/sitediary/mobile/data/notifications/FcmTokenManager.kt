package com.sitediary.mobile.data.notifications

import android.content.Context
import android.util.Log
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
        val hasFirebase = runCatching {
            FirebaseApp.getApps(context).isNotEmpty()
        }.getOrElse { err ->
            Log.w(TAG, "Firebase initialization check failed; skipping FCM registration.", err)
            false
        }
        if (!hasFirebase) {
            Log.w(TAG, "Firebase not initialized (missing google-services.json); skipping FCM registration.")
            return
        }

        runCatching {
            FirebaseMessaging.getInstance().token
                .addOnSuccessListener { token ->
                    if (!token.isNullOrBlank()) {
                        scope.launch {
                            registerToken(token)
                        }
                    }
                }
                .addOnFailureListener { err ->
                    Log.w(TAG, "Failed to obtain FCM token; push alerts disabled.", err)
                }
        }.onFailure { err ->
            Log.w(TAG, "FirebaseMessaging unavailable; skipping FCM registration.", err)
        }
    }

    suspend fun registerToken(token: String) {
        if (token.isBlank() || appPreferences.getAccessToken().isNullOrBlank()) return
        runCatching {
            api.registerDeviceToken(DeviceTokenRequestDto(fcmToken = token))
        }.onFailure { err ->
            Log.w(TAG, "Failed to register FCM token with backend API.", err)
        }
    }

    private companion object {
        const val TAG = "FcmTokenManager"
    }
}

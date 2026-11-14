package com.sitediary.mobile.data.notifications

import android.content.Context
import android.util.Log
import com.google.firebase.FirebaseApp
import com.sitediary.mobile.data.prefs.AppPreferences
import com.sitediary.mobile.data.remote.SiteDiaryApi
import com.sitediary.mobile.data.remote.dto.DeviceTokenRequestDto
import io.mockk.coEvery
import io.mockk.coVerify
import io.mockk.every
import io.mockk.mockk
import io.mockk.mockkStatic
import io.mockk.unmockkStatic
import io.mockk.verify
import kotlinx.coroutines.test.runTest
import org.junit.After
import org.junit.Before
import org.junit.Test
import retrofit2.Response

class FcmTokenManagerTest {

    private lateinit var context: Context
    private lateinit var api: SiteDiaryApi
    private lateinit var appPreferences: AppPreferences
    private lateinit var manager: FcmTokenManager

    @Before
    fun setUp() {
        context = mockk(relaxed = true)
        api = mockk(relaxed = true)
        appPreferences = mockk(relaxed = true)
        manager = FcmTokenManager(context = context, api = api, appPreferences = appPreferences)
        mockkStatic(FirebaseApp::class)
        mockkStatic(Log::class)
        every { Log.w(any<String>(), any<String>()) } returns 0
        every { Log.w(any<String>(), any<String>(), any<Throwable>()) } returns 0
    }

    @After
    fun tearDown() {
        unmockkStatic(FirebaseApp::class)
        unmockkStatic(Log::class)
    }

    @Test
    fun `registerCurrentTokenIfAvailable does nothing when unauthenticated`() {
        every { appPreferences.getAccessToken() } returns null

        manager.registerCurrentTokenIfAvailable()

        verify(exactly = 0) { FirebaseApp.getApps(any()) }
        coVerify(exactly = 0) { api.registerDeviceToken(any()) }
    }

    @Test
    fun `registerCurrentTokenIfAvailable logs warning and returns cleanly when Firebase is uninitialized`() {
        every { appPreferences.getAccessToken() } returns "jwt-access-token"
        every { FirebaseApp.getApps(context) } returns emptyList()

        manager.registerCurrentTokenIfAvailable()

        verify(exactly = 1) {
            Log.w(
                "FcmTokenManager",
                match<String> { it.contains("google-services.json") }
            )
        }
        coVerify(exactly = 0) { api.registerDeviceToken(any()) }
    }

    @Test
    fun `registerCurrentTokenIfAvailable catches Firebase initialization errors with warning log`() {
        every { appPreferences.getAccessToken() } returns "jwt-access-token"
        every { FirebaseApp.getApps(context) } throws IllegalStateException("Default FirebaseApp is not initialized")

        manager.registerCurrentTokenIfAvailable()

        verify(atLeast = 1) { Log.w("FcmTokenManager", any<String>(), any<Throwable>()) }
        coVerify(exactly = 0) { api.registerDeviceToken(any()) }
    }

    @Test
    fun `registerToken sends device token only when token and access token are present`() = runTest {
        every { appPreferences.getAccessToken() } returns "jwt-access-token"
        coEvery { api.registerDeviceToken(any()) } returns Response.success(Unit)

        manager.registerToken("   ")
        coVerify(exactly = 0) { api.registerDeviceToken(any()) }

        manager.registerToken("fcm-device-token-123")
        coVerify(exactly = 1) {
            api.registerDeviceToken(DeviceTokenRequestDto(fcmToken = "fcm-device-token-123"))
        }
    }
}

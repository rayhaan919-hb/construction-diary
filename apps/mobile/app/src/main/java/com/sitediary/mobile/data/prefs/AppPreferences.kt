package com.sitediary.mobile.data.prefs

import android.content.Context
import androidx.datastore.core.DataStore
import androidx.datastore.preferences.core.Preferences
import androidx.datastore.preferences.core.booleanPreferencesKey
import androidx.datastore.preferences.core.edit
import androidx.datastore.preferences.core.longPreferencesKey
import androidx.datastore.preferences.core.stringPreferencesKey
import androidx.datastore.preferences.preferencesDataStore
import com.sitediary.mobile.data.remote.TokenStore
import com.sitediary.mobile.data.remote.dto.TokenPairDto
import com.sitediary.mobile.data.remote.dto.UserDto
import dagger.hilt.android.qualifiers.ApplicationContext
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.map
import kotlinx.serialization.json.Json
import javax.inject.Inject
import javax.inject.Singleton

private val Context.settingsDataStore: DataStore<Preferences> by preferencesDataStore(name = "site_diary_settings")

data class AuthSession(
    val accessToken: String,
    val refreshToken: String,
    val user: UserDto
)

@Singleton
class AppPreferences @Inject constructor(
    @ApplicationContext private val context: Context
) : TokenStore {

    private val authPrefs = context.getSharedPreferences("site_diary_auth", Context.MODE_PRIVATE)
    private val json = Json { ignoreUnknownKeys = true }

    private val _sessionFlow = MutableStateFlow(readSessionFromPrefs())
    val sessionFlow: StateFlow<AuthSession?> = _sessionFlow.asStateFlow()

    val uploadOnMobileData: Flow<Boolean> = context.settingsDataStore.data.map { prefs ->
        prefs[KEY_UPLOAD_ON_MOBILE_DATA] ?: false
    }

    val appLocale: Flow<String> = context.settingsDataStore.data.map { prefs ->
        prefs[KEY_APP_LOCALE] ?: "en"
    }

    val lastSyncEpochMs: Flow<Long?> = context.settingsDataStore.data.map { prefs ->
        prefs[KEY_LAST_SYNC_EPOCH_MS]
    }

    val lastSyncError: Flow<String?> = context.settingsDataStore.data.map { prefs ->
        prefs[KEY_LAST_SYNC_ERROR]
    }

    private val _isSyncing = MutableStateFlow(false)
    val isSyncing: StateFlow<Boolean> = _isSyncing.asStateFlow()

    fun setSyncing(syncing: Boolean) {
        _isSyncing.value = syncing
    }

    override fun getAccessToken(): String? = _sessionFlow.value?.accessToken

    override fun getRefreshToken(): String? = _sessionFlow.value?.refreshToken

    fun getCurrentUser(): UserDto? = _sessionFlow.value?.user

    override fun saveTokenPair(tokenPair: TokenPairDto) {
        val userJson = json.encodeToString(UserDto.serializer(), tokenPair.user)
        authPrefs.edit()
            .putString(PREF_ACCESS_TOKEN, tokenPair.accessToken)
            .putString(PREF_REFRESH_TOKEN, tokenPair.refreshToken)
            .putString(PREF_USER_JSON, userJson)
            .apply()
        _sessionFlow.value = AuthSession(
            accessToken = tokenPair.accessToken,
            refreshToken = tokenPair.refreshToken,
            user = tokenPair.user
        )
    }

    fun markPasswordChanged() {
        val current = _sessionFlow.value ?: return
        val updatedUser = current.user.copy(mustChangePassword = false)
        val userJson = json.encodeToString(UserDto.serializer(), updatedUser)
        authPrefs.edit()
            .putString(PREF_USER_JSON, userJson)
            .apply()
        _sessionFlow.value = current.copy(user = updatedUser)
    }

    override fun clearSession() {
        authPrefs.edit().clear().apply()
        _sessionFlow.value = null
    }

    suspend fun setUploadOnMobileData(enabled: Boolean) {
        context.settingsDataStore.edit { prefs ->
            prefs[KEY_UPLOAD_ON_MOBILE_DATA] = enabled
        }
    }

    suspend fun setAppLocale(localeTag: String) {
        val normalized = if (localeTag == "ur") "ur" else "en"
        context.settingsDataStore.edit { prefs ->
            prefs[KEY_APP_LOCALE] = normalized
        }
    }

    suspend fun recordSyncOutcome(epochMs: Long, error: String?) {
        context.settingsDataStore.edit { prefs ->
            if (error == null) {
                prefs[KEY_LAST_SYNC_EPOCH_MS] = epochMs
                prefs.remove(KEY_LAST_SYNC_ERROR)
            } else {
                prefs[KEY_LAST_SYNC_ERROR] = error
            }
        }
    }

    private fun readSessionFromPrefs(): AuthSession? {
        val access = authPrefs.getString(PREF_ACCESS_TOKEN, null) ?: return null
        val refresh = authPrefs.getString(PREF_REFRESH_TOKEN, null) ?: return null
        val userRaw = authPrefs.getString(PREF_USER_JSON, null) ?: return null
        val user = runCatching { json.decodeFromString(UserDto.serializer(), userRaw) }.getOrNull()
            ?: return null
        return AuthSession(accessToken = access, refreshToken = refresh, user = user)
    }

    companion object {
        private const val PREF_ACCESS_TOKEN = "access_token"
        private const val PREF_REFRESH_TOKEN = "refresh_token"
        private const val PREF_USER_JSON = "user_json"

        private val KEY_UPLOAD_ON_MOBILE_DATA = booleanPreferencesKey("upload_on_mobile_data")
        private val KEY_APP_LOCALE = stringPreferencesKey("app_locale")
        private val KEY_LAST_SYNC_EPOCH_MS = longPreferencesKey("last_sync_epoch_ms")
        private val KEY_LAST_SYNC_ERROR = stringPreferencesKey("last_sync_error")
    }
}

package com.sitediary.mobile.data.prefs

import android.content.Context
import android.os.Build
import android.security.keystore.KeyGenParameterSpec
import android.security.keystore.KeyProperties
import android.util.Base64
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
import java.nio.charset.StandardCharsets
import java.security.KeyStore
import java.security.KeyStoreException
import javax.crypto.Cipher
import javax.crypto.KeyGenerator
import javax.crypto.SecretKey
import javax.crypto.spec.GCMParameterSpec
import javax.inject.Inject
import javax.inject.Singleton

private val Context.settingsDataStore: DataStore<Preferences> by preferencesDataStore(name = "site_diary_settings")

data class AuthSession(
    val accessToken: String,
    val refreshToken: String,
    val user: UserDto
)

/**
 * Encrypts session credentials via AndroidKeyStore AES-256-GCM on device.
 * Falls back to UTF-8 encoding ONLY when running under pure JVM unit tests (no Android runtime).
 */
internal object SessionCrypto {
    private const val KEYSTORE_PROVIDER = "AndroidKeyStore"
    private const val KEY_ALIAS = "site_diary_session_aes_v1"
    private const val TRANSFORMATION = "AES/GCM/NoPadding"
    private const val GCM_TAG_BITS = 128
    private const val GCM_IV_BYTES = 12
    private const val PREFIX_GCM = "gcm1:"

    private fun getOrCreateKey(): SecretKey {
        val ks = KeyStore.getInstance(KEYSTORE_PROVIDER).apply { load(null) }
        val existing = ks.getKey(KEY_ALIAS, null) as? SecretKey
        if (existing != null) return existing

        val generator = KeyGenerator.getInstance(KeyProperties.KEY_ALGORITHM_AES, KEYSTORE_PROVIDER)
        val spec = KeyGenParameterSpec.Builder(
            KEY_ALIAS,
            KeyProperties.PURPOSE_ENCRYPT or KeyProperties.PURPOSE_DECRYPT
        )
            .setBlockModes(KeyProperties.BLOCK_MODE_GCM)
            .setEncryptionPaddings(KeyProperties.ENCRYPTION_PADDING_NONE)
            .setKeySize(256)
            .setRandomizedEncryptionRequired(true)
            .build()
        generator.init(spec)
        return generator.generateKey()
    }

    fun encrypt(plaintext: String): String {
        return try {
            val cipher = Cipher.getInstance(TRANSFORMATION)
            cipher.init(Cipher.ENCRYPT_MODE, getOrCreateKey())
            val iv = cipher.iv
            val ciphertext = cipher.doFinal(plaintext.toByteArray(StandardCharsets.UTF_8))
            val combined = ByteArray(iv.size + ciphertext.size)
            System.arraycopy(iv, 0, combined, 0, iv.size)
            System.arraycopy(ciphertext, 0, combined, iv.size, ciphertext.size)
            PREFIX_GCM + Base64.encodeToString(combined, Base64.NO_WRAP)
        } catch (e: KeyStoreException) {
            if (Build.FINGERPRINT == null) {
                plaintext
            } else {
                throw IllegalStateException("AndroidKeyStore unavailable for session encryption", e)
            }
        }
    }

    fun decrypt(stored: String?): String? {
        if (stored == null) return null
        if (!stored.startsWith(PREFIX_GCM)) {
            // Migrate seamlessly only for legacy plaintext or JVM unit tests; AndroidKeyStore decrypts prefixed values.
            return stored
        }
        return runCatching {
            val raw = Base64.decode(stored.removePrefix(PREFIX_GCM), Base64.NO_WRAP)
            if (raw.size <= GCM_IV_BYTES) return null
            val iv = raw.copyOfRange(0, GCM_IV_BYTES)
            val ciphertext = raw.copyOfRange(GCM_IV_BYTES, raw.size)
            val cipher = Cipher.getInstance(TRANSFORMATION)
            cipher.init(Cipher.DECRYPT_MODE, getOrCreateKey(), GCMParameterSpec(GCM_TAG_BITS, iv))
            String(cipher.doFinal(ciphertext), StandardCharsets.UTF_8)
        }.getOrNull()
    }
}

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

    fun saveFcmToken(token: String) {
        authPrefs.edit()
            .putString(PREF_FCM_TOKEN, SessionCrypto.encrypt(token))
            .commit()
    }

    fun getSavedFcmToken(): String? =
        SessionCrypto.decrypt(authPrefs.getString(PREF_FCM_TOKEN, null))

    override fun saveTokenPair(tokenPair: TokenPairDto) {
        val userJson = json.encodeToString(UserDto.serializer(), tokenPair.user)
        authPrefs.edit()
            .putString(PREF_ACCESS_TOKEN, SessionCrypto.encrypt(tokenPair.accessToken))
            .putString(PREF_REFRESH_TOKEN, SessionCrypto.encrypt(tokenPair.refreshToken))
            .putString(PREF_USER_JSON, SessionCrypto.encrypt(userJson))
            .commit()
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
            .putString(PREF_USER_JSON, SessionCrypto.encrypt(userJson))
            .commit()
        _sessionFlow.value = current.copy(user = updatedUser)
    }

    override fun clearSession() {
        authPrefs.edit().clear().commit()
        _sessionFlow.value = null
    }

    suspend fun clearAllSettingsOnLogout() {
        clearSession()
        context.settingsDataStore.edit { prefs ->
            prefs.remove(KEY_UPLOAD_ON_MOBILE_DATA)
            prefs.remove(KEY_LAST_SYNC_EPOCH_MS)
            prefs.remove(KEY_LAST_SYNC_ERROR)
        }
    }

    suspend fun setUploadOnMobileData(enabled: Boolean) {
        context.settingsDataStore.edit { prefs ->
            prefs[KEY_UPLOAD_ON_MOBILE_DATA] = enabled
        }
    }

    suspend fun setAppLocale(localeTag: String) {
        val normalized = when (localeTag) {
            "ur", "ar" -> localeTag
            else -> "en"
        }
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
        val access = SessionCrypto.decrypt(authPrefs.getString(PREF_ACCESS_TOKEN, null)) ?: return null
        val refresh = SessionCrypto.decrypt(authPrefs.getString(PREF_REFRESH_TOKEN, null)) ?: return null
        val userRaw = SessionCrypto.decrypt(authPrefs.getString(PREF_USER_JSON, null)) ?: return null
        val user = runCatching { json.decodeFromString(UserDto.serializer(), userRaw) }.getOrNull()
            ?: return null
        return AuthSession(accessToken = access, refreshToken = refresh, user = user)
    }

    companion object {
        private const val PREF_ACCESS_TOKEN = "access_token"
        private const val PREF_REFRESH_TOKEN = "refresh_token"
        private const val PREF_USER_JSON = "user_json"
        private const val PREF_FCM_TOKEN = "fcm_token"

        private val KEY_UPLOAD_ON_MOBILE_DATA = booleanPreferencesKey("upload_on_mobile_data")
        private val KEY_APP_LOCALE = stringPreferencesKey("app_locale")
        private val KEY_LAST_SYNC_EPOCH_MS = longPreferencesKey("last_sync_epoch_ms")
        private val KEY_LAST_SYNC_ERROR = stringPreferencesKey("last_sync_error")
    }
}

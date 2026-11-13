package com.sitediary.mobile.data.remote

import com.sitediary.mobile.data.remote.dto.RefreshRequestDto
import com.sitediary.mobile.data.remote.dto.TokenPairDto
import kotlinx.serialization.json.Json
import okhttp3.Authenticator
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.RequestBody.Companion.toRequestBody
import okhttp3.Response
import okhttp3.Route
import java.io.IOException

/**
 * Rotates refresh tokens via `POST /v1/auth/refresh`.
 *
 * CRITICAL CONTRACT RULE:
 * - NEVER clears session / logs the user out on network or IO errors or 5xx responses.
 * - ONLY clears session when `/v1/auth/refresh` returns HTTP 401 (TOKEN_REUSED / TOKEN_EXPIRED).
 * - Synchronized with double-checked token comparison so concurrent 401s do not reuse an
 *   already-rotated refresh token.
 */
class TokenRefreshAuthenticator(
    private val baseUrl: String,
    private val tokenStore: TokenStore,
    private val refreshClient: OkHttpClient,
    private val json: Json = JsonProvider.json
) : Authenticator {

    private val lock = Any()

    override fun authenticate(route: Route?, response: Response): Request? {
        val path = response.request.url.encodedPath
        if (path == "/v1/auth/login" || path == "/v1/auth/refresh" || path == "/v1/auth/logout") {
            return null
        }

        if (responseCount(response) >= 2) {
            return null
        }

        val sentAuthHeader = response.request.header("Authorization")
        val sentToken = sentAuthHeader?.removePrefix("Bearer ")?.trim()

        synchronized(lock) {
            val latestAccessToken = tokenStore.getAccessToken()
            if (!latestAccessToken.isNullOrBlank() && latestAccessToken != sentToken) {
                // Another thread already refreshed the token pair while we waited
                return response.request.newBuilder()
                    .header("Authorization", "Bearer $latestAccessToken")
                    .build()
            }

            val refreshToken = tokenStore.getRefreshToken() ?: return null
            val bodyJson = json.encodeToString(
                RefreshRequestDto.serializer(),
                RefreshRequestDto(refreshToken = refreshToken)
            )
            val refreshUrl = "${baseUrl.trimEnd('/')}/v1/auth/refresh"
            val refreshRequest = Request.Builder()
                .url(refreshUrl)
                .post(bodyJson.toRequestBody("application/json; charset=utf-8".toMediaType()))
                .build()

            val refreshResponse = try {
                refreshClient.newCall(refreshRequest).execute()
            } catch (_: IOException) {
                // Network failure — preserve offline session!
                return null
            }

            refreshResponse.use { res ->
                when (res.code) {
                    200 -> {
                        val rawBody = res.body?.string() ?: return null
                        val tokenPair = runCatching {
                            json.decodeFromString(TokenPairDto.serializer(), rawBody)
                        }.getOrNull() ?: return null

                        tokenStore.saveTokenPair(tokenPair)
                        return response.request.newBuilder()
                            .header("Authorization", "Bearer ${tokenPair.accessToken}")
                            .build()
                    }

                    401 -> {
                        // Refresh token expired or reused (chain revoked) -> log user out
                        tokenStore.clearSession()
                        return null
                    }

                    else -> {
                        // 5xx or unexpected transient error — preserve session!
                        return null
                    }
                }
            }
        }
    }

    private fun responseCount(response: Response): Int {
        var result = 1
        var prior = response.priorResponse
        while (prior != null) {
            result++
            prior = prior.priorResponse
        }
        return result
    }
}

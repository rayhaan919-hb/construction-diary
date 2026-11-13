package com.sitediary.mobile.data.remote

import okhttp3.Interceptor
import okhttp3.Response

class AuthInterceptor(
    private val tokenStore: TokenStore
) : Interceptor {

    override fun intercept(chain: Interceptor.Chain): Response {
        val original = chain.request()
        val path = original.url.encodedPath

        // Public auth endpoints and signed local PUT URLs must not receive Bearer auth
        if (path == "/v1/auth/login" ||
            path == "/v1/auth/refresh" ||
            path.startsWith("/v1/media/local/") ||
            original.header("Authorization") != null
        ) {
            return chain.proceed(original)
        }

        val accessToken = tokenStore.getAccessToken()
        val req = if (!accessToken.isNullOrBlank()) {
            original.newBuilder()
                .header("Authorization", "Bearer $accessToken")
                .build()
        } else {
            original
        }
        return chain.proceed(req)
    }
}

package com.sitediary.mobile.data.remote

import com.sitediary.mobile.data.remote.dto.TokenPairDto

/**
 * Synchronous token session store consumed by OkHttp Interceptors/Authenticator.
 * Decoupled from DataStore implementation details for fast unit testing.
 */
interface TokenStore {
    fun getAccessToken(): String?
    fun getRefreshToken(): String?
    fun saveTokenPair(tokenPair: TokenPairDto)
    fun clearSession()
}

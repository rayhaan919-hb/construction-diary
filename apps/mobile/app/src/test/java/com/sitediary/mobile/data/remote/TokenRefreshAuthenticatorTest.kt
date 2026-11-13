package com.sitediary.mobile.data.remote

import com.sitediary.mobile.data.remote.dto.TokenPairDto
import com.sitediary.mobile.data.remote.dto.UserDto
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.mockwebserver.MockResponse
import okhttp3.mockwebserver.MockWebServer
import org.junit.After
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertNull
import org.junit.Before
import org.junit.Test
import java.util.concurrent.Callable
import java.util.concurrent.Executors
import java.util.concurrent.TimeUnit
import java.util.concurrent.atomic.AtomicInteger

class TokenRefreshAuthenticatorTest {

    private lateinit var server: MockWebServer

    private class InMemoryTokenStore(
        initialAccess: String?,
        initialRefresh: String?
    ) : TokenStore {
        @Volatile var access: String? = initialAccess
        @Volatile var refresh: String? = initialRefresh
        @Volatile var clearCount: Int = 0

        override fun getAccessToken(): String? = access
        override fun getRefreshToken(): String? = refresh
        override fun saveTokenPair(tokenPair: TokenPairDto) {
            access = tokenPair.accessToken
            refresh = tokenPair.refreshToken
        }

        override fun clearSession() {
            clearCount++
            access = null
            refresh = null
        }
    }

    @Before
    fun setUp() {
        server = MockWebServer()
        server.start()
    }

    @After
    fun tearDown() {
        server.shutdown()
    }

    private fun buildClient(tokenStore: TokenStore, refreshBaseUrl: String = server.url("/").toString()): OkHttpClient {
        val refreshClient = OkHttpClient.Builder()
            .connectTimeout(1, TimeUnit.SECONDS)
            .readTimeout(1, TimeUnit.SECONDS)
            .build()
        return OkHttpClient.Builder()
            .addInterceptor(AuthInterceptor(tokenStore))
            .authenticator(
                TokenRefreshAuthenticator(
                    baseUrl = refreshBaseUrl,
                    tokenStore = tokenStore,
                    refreshClient = refreshClient
                )
            )
            .build()
    }

    @Test
    fun `rotates token on 401 and retries request with new access token`() {
        val store = InMemoryTokenStore("expired-access", "rt-1")
        val tokenJson = JsonProvider.json.encodeToString(
            TokenPairDto.serializer(),
            TokenPairDto(
                accessToken = "fresh-access",
                refreshToken = "rt-2",
                accessExpiresIn = 900,
                refreshExpiresAt = "2027-01-01T00:00:00Z",
                user = UserDto("u1", "sup@site.pk", "Ali", "SUPERVISOR", "en", false)
            )
        )
        server.enqueue(MockResponse().setResponseCode(401))
        server.enqueue(MockResponse().setResponseCode(200).setBody(tokenJson))
        server.enqueue(MockResponse().setResponseCode(200).setBody("""{"ok":true}"""))

        val client = buildClient(store)
        val res = client.newCall(Request.Builder().url(server.url("/v1/projects")).build()).execute()

        assertEquals(200, res.code)
        assertEquals("fresh-access", store.access)
        assertEquals("rt-2", store.refresh)
        assertEquals(0, store.clearCount)
    }

    @Test
    fun `NEVER clears session on IOException during refresh`() {
        val store = InMemoryTokenStore("expired-access", "rt-1")
        server.enqueue(MockResponse().setResponseCode(401))

        // Point refresh URL to closed port so IOException occurs
        val unreachableUrl = "http://127.0.0.1:1"
        val client = buildClient(store, refreshBaseUrl = unreachableUrl)
        val res = client.newCall(Request.Builder().url(server.url("/v1/projects")).build()).execute()

        assertEquals(401, res.code)
        assertEquals(0, store.clearCount)
        assertEquals("rt-1", store.refresh)
    }

    @Test
    fun `NEVER clears session on 500 error from auth refresh`() {
        val store = InMemoryTokenStore("expired-access", "rt-1")
        server.enqueue(MockResponse().setResponseCode(401))
        server.enqueue(MockResponse().setResponseCode(503))

        val client = buildClient(store)
        val res = client.newCall(Request.Builder().url(server.url("/v1/projects")).build()).execute()

        assertEquals(401, res.code)
        assertEquals(0, store.clearCount)
        assertNotNull(store.refresh)
    }

    @Test
    fun `clears session ONLY when auth refresh returns HTTP 401`() {
        val store = InMemoryTokenStore("expired-access", "rt-reused")
        server.enqueue(MockResponse().setResponseCode(401))
        server.enqueue(
            MockResponse()
                .setResponseCode(401)
                .setBody("""{"type":"about:blank","title":"Unauthorized","status":401,"code":"TOKEN_REUSED"}""")
        )

        val client = buildClient(store)
        val res = client.newCall(Request.Builder().url(server.url("/v1/projects")).build()).execute()

        assertEquals(401, res.code)
        assertEquals(1, store.clearCount)
        assertNull(store.access)
        assertNull(store.refresh)
    }

    @Test
    fun `concurrent 401 responses refresh only once under lock`() {
        val store = InMemoryTokenStore("expired-access", "rt-1")
        val refreshCalls = AtomicInteger(0)
        val tokenJson = JsonProvider.json.encodeToString(
            TokenPairDto.serializer(),
            TokenPairDto(
                accessToken = "fresh-access",
                refreshToken = "rt-2",
                accessExpiresIn = 900,
                refreshExpiresAt = "2027-01-01T00:00:00Z",
                user = UserDto("u1", "sup@site.pk", "Ali", "SUPERVISOR", "en", false)
            )
        )

        server.dispatcher = object : okhttp3.mockwebserver.Dispatcher() {
            override fun dispatch(request: okhttp3.mockwebserver.RecordedRequest): MockResponse {
                return when (request.path) {
                    "/v1/auth/refresh" -> {
                        refreshCalls.incrementAndGet()
                        MockResponse().setResponseCode(200).setBody(tokenJson)
                    }
                    else -> {
                        if (request.getHeader("Authorization") == "Bearer fresh-access") {
                            MockResponse().setResponseCode(200).setBody("ok")
                        } else {
                            MockResponse().setResponseCode(401)
                        }
                    }
                }
            }
        }

        val client = buildClient(store)
        val pool = Executors.newFixedThreadPool(2)
        val futures = listOf(
            pool.submit(Callable {
                client.newCall(Request.Builder().url(server.url("/v1/projects")).build()).execute().code
            }),
            pool.submit(Callable {
                client.newCall(Request.Builder().url(server.url("/v1/sync/pull?since=0")).build()).execute().code
            })
        )
        val codes = futures.map { it.get() }
        pool.shutdown()

        assertEquals(listOf(200, 200), codes)
        assertEquals(1, refreshCalls.get())
    }
}

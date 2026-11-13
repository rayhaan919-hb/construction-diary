package com.sitediary.mobile.data.remote

import kotlinx.serialization.json.Json

object JsonProvider {
    val json: Json = Json {
        ignoreUnknownKeys = true
        encodeDefaults = true
        explicitNulls = true
        isLenient = true
    }
}

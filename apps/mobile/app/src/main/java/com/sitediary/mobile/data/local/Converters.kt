package com.sitediary.mobile.data.local

import androidx.room.TypeConverter
import com.sitediary.mobile.data.remote.JsonProvider
import com.sitediary.mobile.data.remote.dto.StructuredSummaryDto

class Converters {
    @TypeConverter
    fun fromStructuredSummary(value: StructuredSummaryDto?): String? {
        return value?.let {
            JsonProvider.json.encodeToString(StructuredSummaryDto.serializer(), it)
        }
    }

    @TypeConverter
    fun toStructuredSummary(raw: String?): StructuredSummaryDto? {
        if (raw.isNullOrBlank()) return null
        return runCatching {
            JsonProvider.json.decodeFromString(StructuredSummaryDto.serializer(), raw)
        }.getOrNull()
    }
}

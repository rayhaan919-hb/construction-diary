package com.sitediary.mobile.data.remote.dto

import kotlinx.serialization.KSerializer
import kotlinx.serialization.SerialName
import kotlinx.serialization.Serializable
import kotlinx.serialization.descriptors.SerialDescriptor
import kotlinx.serialization.encoding.Decoder
import kotlinx.serialization.encoding.Encoder
import kotlinx.serialization.json.JsonDecoder
import kotlinx.serialization.json.JsonEncoder
import kotlinx.serialization.json.JsonNull
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.JsonPrimitive
import kotlinx.serialization.json.buildJsonObject
import kotlinx.serialization.json.put

@Serializable
data class StructuredSummaryDto(
    @SerialName("tasks_completed") val tasksCompleted: List<String> = emptyList(),
    @SerialName("labor_count") val laborCount: Int? = null,
    @SerialName("material_deliveries") val materialDeliveries: List<String> = emptyList(),
    val blockers: List<String> = emptyList()
)

@Serializable
data class SiteLogPhotoDto(
    val id: String,
    @SerialName("site_log_id") val siteLogId: String,
    @SerialName("storage_uri") val storageUri: String,
    @SerialName("upload_status") val uploadStatus: String,
    val url: String? = null,
    val width: Int? = null,
    val height: Int? = null,
    @SerialName("byte_size") val byteSize: Int? = null,
    @SerialName("taken_at") val takenAt: String? = null,
    @SerialName("sort_order") val sortOrder: Int = 0,
    @SerialName("deleted_at") val deletedAt: String? = null,
    @SerialName("server_version") val serverVersion: Long
)

@Serializable
data class SiteLogPhotoPushDto(
    val id: String,
    @SerialName("site_log_id") val siteLogId: String,
    @SerialName("storage_uri") val storageUri: String,
    val width: Int? = null,
    val height: Int? = null,
    @SerialName("byte_size") val byteSize: Int? = null,
    @SerialName("taken_at") val takenAt: String? = null,
    @SerialName("sort_order") val sortOrder: Int = 0,
    @SerialName("deleted_at") val deletedAt: String? = null
)

@Serializable
data class SiteLogDto(
    val id: String,
    @SerialName("project_id") val projectId: String,
    @SerialName("author_id") val authorId: String,
    @SerialName("author_name") val authorName: String? = null,
    @SerialName("log_date") val logDate: String,
    @SerialName("recorded_at") val recordedAt: String,
    val notes: String? = null,
    @SerialName("audio_uri") val audioUri: String? = null,
    @SerialName("audio_duration_ms") val audioDurationMs: Int? = null,
    @SerialName("audio_upload_status") val audioUploadStatus: String,
    @SerialName("extraction_status") val extractionStatus: String,
    @SerialName("extraction_attempts") val extractionAttempts: Int = 0,
    @SerialName("extraction_error") val extractionError: String? = null,
    @SerialName("extraction_model") val extractionModel: String? = null,
    @SerialName("extracted_at") val extractedAt: String? = null,
    val transcript: String? = null,
    @SerialName("detected_language") val detectedLanguage: String? = null,
    @SerialName("structured_summary") val structuredSummary: StructuredSummaryDto? = null,
    @SerialName("edited_by_human") val editedByHuman: Boolean = false,
    val photos: List<SiteLogPhotoDto>? = null,
    @SerialName("client_updated_at") val clientUpdatedAt: String,
    @SerialName("created_at") val createdAt: String,
    @SerialName("updated_at") val updatedAt: String,
    @SerialName("deleted_at") val deletedAt: String? = null,
    @SerialName("server_version") val serverVersion: Long
)

/**
 * Custom serializer guarantees `structured_summary` is omitted when `edited_by_human=false`
 * and included only when `edited_by_human=true`, matching `api-contract.yaml`.
 */
@Serializable(with = SiteLogPushSerializer::class)
data class SiteLogPushDto(
    val id: String,
    @SerialName("project_id") val projectId: String,
    @SerialName("log_date") val logDate: String,
    @SerialName("recorded_at") val recordedAt: String,
    val notes: String? = null,
    @SerialName("audio_uri") val audioUri: String? = null,
    @SerialName("audio_duration_ms") val audioDurationMs: Int? = null,
    @SerialName("structured_summary") val structuredSummary: StructuredSummaryDto? = null,
    @SerialName("edited_by_human") val editedByHuman: Boolean = false,
    @SerialName("deleted_at") val deletedAt: String? = null,
    @SerialName("client_updated_at") val clientUpdatedAt: String
)

object SiteLogPushSerializer : KSerializer<SiteLogPushDto> {
    @Serializable
    private data class Surrogate(
        val id: String,
        @SerialName("project_id") val projectId: String,
        @SerialName("log_date") val logDate: String,
        @SerialName("recorded_at") val recordedAt: String,
        val notes: String? = null,
        @SerialName("audio_uri") val audioUri: String? = null,
        @SerialName("audio_duration_ms") val audioDurationMs: Int? = null,
        @SerialName("structured_summary") val structuredSummary: StructuredSummaryDto? = null,
        @SerialName("edited_by_human") val editedByHuman: Boolean = false,
        @SerialName("deleted_at") val deletedAt: String? = null,
        @SerialName("client_updated_at") val clientUpdatedAt: String
    )

    override val descriptor: SerialDescriptor = Surrogate.serializer().descriptor

    override fun serialize(encoder: Encoder, value: SiteLogPushDto) {
        val jsonEncoder = encoder as? JsonEncoder
            ?: throw IllegalStateException("SiteLogPushSerializer requires JsonEncoder")
        val json = jsonEncoder.json
        val obj = buildJsonObject {
            put("id", value.id)
            put("project_id", value.projectId)
            put("log_date", value.logDate)
            put("recorded_at", value.recordedAt)
            put("notes", value.notes?.let { JsonPrimitive(it) } ?: JsonNull)
            put("audio_uri", value.audioUri?.let { JsonPrimitive(it) } ?: JsonNull)
            put("audio_duration_ms", value.audioDurationMs?.let { JsonPrimitive(it) } ?: JsonNull)
            if (value.editedByHuman && value.structuredSummary != null) {
                put(
                    "structured_summary",
                    json.encodeToJsonElement(StructuredSummaryDto.serializer(), value.structuredSummary)
                )
            }
            put("edited_by_human", value.editedByHuman)
            put("deleted_at", value.deletedAt?.let { JsonPrimitive(it) } ?: JsonNull)
            put("client_updated_at", value.clientUpdatedAt)
        }
        jsonEncoder.encodeJsonElement(obj)
    }

    override fun deserialize(decoder: Decoder): SiteLogPushDto {
        val jsonDecoder = decoder as? JsonDecoder
            ?: throw IllegalStateException("SiteLogPushSerializer requires JsonDecoder")
        val elem = jsonDecoder.decodeJsonElement() as JsonObject
        val surrogate = jsonDecoder.json.decodeFromJsonElement(Surrogate.serializer(), elem)
        return SiteLogPushDto(
            id = surrogate.id,
            projectId = surrogate.projectId,
            logDate = surrogate.logDate,
            recordedAt = surrogate.recordedAt,
            notes = surrogate.notes,
            audioUri = surrogate.audioUri,
            audioDurationMs = surrogate.audioDurationMs,
            structuredSummary = if (surrogate.editedByHuman) surrogate.structuredSummary else null,
            editedByHuman = surrogate.editedByHuman,
            deletedAt = surrogate.deletedAt,
            clientUpdatedAt = surrogate.clientUpdatedAt
        )
    }
}

@Serializable
data class ExtractRequestDto(
    @SerialName("log_id") val logId: String
)

@Serializable
data class ExtractResponseDto(
    @SerialName("log_id") val logId: String,
    @SerialName("extraction_status") val extractionStatus: String
)

@Serializable
data class DailyReportDto(
    @SerialName("project_id") val projectId: String,
    @SerialName("project_name") val projectName: String? = null,
    @SerialName("log_date") val logDate: String,
    @SerialName("labor_max") val laborMax: Int? = null,
    @SerialName("log_count") val logCount: Int,
    @SerialName("pending_extraction_count") val pendingExtractionCount: Int,
    @SerialName("tasks_completed") val tasksCompleted: List<String>,
    @SerialName("material_deliveries") val materialDeliveries: List<String>,
    val blockers: List<String>,
    val logs: List<SiteLogDto>,
    val permits: List<PermitDto>? = null
)

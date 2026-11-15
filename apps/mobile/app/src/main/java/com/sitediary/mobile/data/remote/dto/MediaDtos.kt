package com.sitediary.mobile.data.remote.dto

import kotlinx.serialization.SerialName
import kotlinx.serialization.Serializable

@Serializable
enum class MediaKind {
    AUDIO,
    PHOTO,
    PERMIT_DOC
}

@Serializable
data class MediaReservationRequestDto(
    val kind: MediaKind,
    @SerialName("project_id") val projectId: String,
    @SerialName("object_id") val objectId: String,
    @SerialName("ttl_seconds") val ttlSeconds: Int? = null
)

@Serializable
data class MediaReservationResponseDto(
    @SerialName("reservation_id") val reservationId: String,
    val kind: MediaKind,
    @SerialName("project_id") val projectId: String,
    @SerialName("object_id") val objectId: String,
    val status: String,
    @SerialName("expires_at") val expiresAt: String
)

@Serializable
data class UploadUrlRequestDto(
    val kind: MediaKind,
    @SerialName("project_id") val projectId: String,
    @SerialName("object_id") val objectId: String,
    @SerialName("content_type") val contentType: String,
    @SerialName("byte_size") val byteSize: Long
)

@Serializable
data class UploadTicketDto(
    @SerialName("ticket_id") val ticketId: String? = null,
    @SerialName("upload_url") val uploadUrl: String,
    val method: String,
    val headers: Map<String, String>,
    @SerialName("storage_uri") val storageUri: String,
    @SerialName("expires_at") val expiresAt: String
)

@Serializable
data class MediaCompleteRequestDto(
    val kind: MediaKind,
    @SerialName("object_id") val objectId: String,
    @SerialName("ticket_id") val ticketId: String? = null,
    val sha256: String? = null
)

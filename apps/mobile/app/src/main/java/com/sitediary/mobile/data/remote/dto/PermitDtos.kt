package com.sitediary.mobile.data.remote.dto

import kotlinx.serialization.SerialName
import kotlinx.serialization.Serializable

@Serializable
data class PermitDto(
    val id: String,
    @SerialName("project_id") val projectId: String,
    @SerialName("permit_name") val permitName: String,
    val authority: String,
    @SerialName("permit_number") val permitNumber: String? = null,
    @SerialName("issue_date") val issueDate: String? = null,
    @SerialName("expiry_date") val expiryDate: String,
    val status: String,
    @SerialName("days_to_expiry") val daysToExpiry: Int,
    @SerialName("document_photo_uri") val documentPhotoUri: String? = null,
    @SerialName("document_photo_url") val documentPhotoUrl: String? = null,
    @SerialName("created_by") val createdBy: String,
    @SerialName("created_at") val createdAt: String,
    @SerialName("updated_at") val updatedAt: String,
    @SerialName("deleted_at") val deletedAt: String? = null,
    @SerialName("server_version") val serverVersion: Long
)

@Serializable
data class PermitPushDto(
    val id: String,
    @SerialName("project_id") val projectId: String,
    @SerialName("permit_name") val permitName: String,
    val authority: String,
    @SerialName("permit_number") val permitNumber: String? = null,
    @SerialName("issue_date") val issueDate: String? = null,
    @SerialName("expiry_date") val expiryDate: String,
    @SerialName("document_photo_uri") val documentPhotoUri: String? = null,
    @SerialName("deleted_at") val deletedAt: String? = null,
    @SerialName("client_updated_at") val clientUpdatedAt: String
)

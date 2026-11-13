package com.sitediary.mobile.data.remote.dto

import kotlinx.serialization.SerialName
import kotlinx.serialization.Serializable

@Serializable
data class ProjectDto(
    val id: String,
    val name: String,
    @SerialName("site_address") val siteAddress: String,
    @SerialName("owner_phone") val ownerPhone: String? = null,
    val timezone: String,
    @SerialName("allow_photo_gps") val allowPhotoGps: Boolean,
    @SerialName("created_at") val createdAt: String,
    @SerialName("updated_at") val updatedAt: String,
    @SerialName("deleted_at") val deletedAt: String? = null,
    @SerialName("server_version") val serverVersion: Long
)

@Serializable
data class MemberDto(
    @SerialName("project_id") val projectId: String,
    @SerialName("user_id") val userId: String,
    val role: String,
    @SerialName("full_name") val fullName: String,
    val email: String,
    @SerialName("deleted_at") val deletedAt: String? = null,
    @SerialName("server_version") val serverVersion: Long
)

@Serializable
data class TodayStatsDto(
    @SerialName("log_date") val logDate: String,
    @SerialName("labor_max") val laborMax: Int? = null,
    @SerialName("log_count") val logCount: Int,
    @SerialName("last_log_at") val lastLogAt: String? = null
)

@Serializable
data class ProjectSummaryDto(
    val project: ProjectDto,
    val today: TodayStatsDto,
    @SerialName("permit_health") val permitHealth: String,
    @SerialName("next_expiring_permit") val nextExpiringPermit: PermitDto? = null,
    @SerialName("open_blockers_count") val openBlockersCount: Int
)

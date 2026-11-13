package com.sitediary.mobile.data.remote.dto

import kotlinx.serialization.SerialName
import kotlinx.serialization.Serializable

@Serializable
data class SyncPushRequestDto(
    val changes: SyncPushChangesDto
)

@Serializable
data class SyncPushChangesDto(
    val permits: List<PermitPushDto> = emptyList(),
    @SerialName("site_logs") val siteLogs: List<SiteLogPushDto> = emptyList(),
    @SerialName("site_log_photos") val siteLogPhotos: List<SiteLogPhotoPushDto> = emptyList()
)

@Serializable
data class SyncPushResponseDto(
    @SerialName("server_time") val serverTime: String,
    val results: List<SyncPushResultDto>
)

@Serializable
data class SyncPushResultDto(
    val entity: String,
    val id: String,
    val status: String,
    @SerialName("server_version") val serverVersion: Long? = null,
    @SerialName("error_code") val errorCode: String? = null,
    @SerialName("error_detail") val errorDetail: String? = null
)

@Serializable
data class SyncPullResponseDto(
    @SerialName("next_cursor") val nextCursor: Long,
    @SerialName("has_more") val hasMore: Boolean,
    val changes: SyncPullChangesDto
)

@Serializable
data class SyncPullChangesDto(
    val projects: List<ProjectDto> = emptyList(),
    @SerialName("project_members") val projectMembers: List<MemberDto> = emptyList(),
    val permits: List<PermitDto> = emptyList(),
    @SerialName("site_logs") val siteLogs: List<SiteLogDto> = emptyList(),
    @SerialName("site_log_photos") val siteLogPhotos: List<SiteLogPhotoDto> = emptyList()
)

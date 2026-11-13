package com.sitediary.mobile.data.remote

import com.sitediary.mobile.data.remote.dto.ChangePasswordRequestDto
import com.sitediary.mobile.data.remote.dto.DailyReportDto
import com.sitediary.mobile.data.remote.dto.DeviceTokenRequestDto
import com.sitediary.mobile.data.remote.dto.ExtractRequestDto
import com.sitediary.mobile.data.remote.dto.ExtractResponseDto
import com.sitediary.mobile.data.remote.dto.LoginRequestDto
import com.sitediary.mobile.data.remote.dto.LogoutRequestDto
import com.sitediary.mobile.data.remote.dto.MediaCompleteRequestDto
import com.sitediary.mobile.data.remote.dto.ProjectSummaryDto
import com.sitediary.mobile.data.remote.dto.RefreshRequestDto
import com.sitediary.mobile.data.remote.dto.SiteLogDto
import com.sitediary.mobile.data.remote.dto.SyncPullResponseDto
import com.sitediary.mobile.data.remote.dto.SyncPushRequestDto
import com.sitediary.mobile.data.remote.dto.SyncPushResponseDto
import com.sitediary.mobile.data.remote.dto.TokenPairDto
import com.sitediary.mobile.data.remote.dto.UploadTicketDto
import com.sitediary.mobile.data.remote.dto.UploadUrlRequestDto
import com.sitediary.mobile.data.remote.dto.UserDto
import retrofit2.Response
import retrofit2.http.Body
import retrofit2.http.GET
import retrofit2.http.POST
import retrofit2.http.Path
import retrofit2.http.Query

interface SiteDiaryApi {

    @POST("/v1/auth/login")
    suspend fun login(@Body request: LoginRequestDto): Response<TokenPairDto>

    @POST("/v1/auth/refresh")
    suspend fun refresh(@Body request: RefreshRequestDto): Response<TokenPairDto>

    @POST("/v1/auth/logout")
    suspend fun logout(@Body request: LogoutRequestDto): Response<Unit>

    @GET("/v1/me")
    suspend fun getMe(): Response<UserDto>

    @POST("/v1/me/password")
    suspend fun changePassword(@Body request: ChangePasswordRequestDto): Response<Unit>

    @POST("/v1/me/device-tokens")
    suspend fun registerDeviceToken(@Body request: DeviceTokenRequestDto): Response<Unit>

    @GET("/v1/projects")
    suspend fun getProjects(): Response<List<ProjectSummaryDto>>

    @GET("/v1/projects/{project_id}/days/{log_date}")
    suspend fun getDailyReport(
        @Path("project_id") projectId: String,
        @Path("log_date") logDate: String
    ): Response<DailyReportDto>

    @GET("/v1/logs/{log_id}")
    suspend fun getSiteLog(@Path("log_id") logId: String): Response<SiteLogDto>

    @POST("/v1/logs/extract")
    suspend fun queueExtraction(@Body request: ExtractRequestDto): Response<ExtractResponseDto>

    @POST("/v1/media/upload-url")
    suspend fun getUploadUrl(@Body request: UploadUrlRequestDto): Response<UploadTicketDto>

    @POST("/v1/media/complete")
    suspend fun completeMediaUpload(@Body request: MediaCompleteRequestDto): Response<Unit>

    @POST("/v1/sync/push")
    suspend fun syncPush(@Body request: SyncPushRequestDto): Response<SyncPushResponseDto>

    @GET("/v1/sync/pull")
    suspend fun syncPull(
        @Query("since") since: Long,
        @Query("limit") limit: Int = 500,
        @Query("project_id") projectId: String? = null
    ): Response<SyncPullResponseDto>
}

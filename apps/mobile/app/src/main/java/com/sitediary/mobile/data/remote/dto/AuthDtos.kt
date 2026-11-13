package com.sitediary.mobile.data.remote.dto

import kotlinx.serialization.SerialName
import kotlinx.serialization.Serializable

@Serializable
data class LoginRequestDto(
    val email: String,
    val password: String,
    @SerialName("device_label") val deviceLabel: String? = null
)

@Serializable
data class RefreshRequestDto(
    @SerialName("refresh_token") val refreshToken: String
)

@Serializable
data class LogoutRequestDto(
    @SerialName("refresh_token") val refreshToken: String
)

@Serializable
data class ChangePasswordRequestDto(
    @SerialName("current_password") val currentPassword: String,
    @SerialName("new_password") val newPassword: String
)

@Serializable
data class DeviceTokenRequestDto(
    @SerialName("fcm_token") val fcmToken: String
)

@Serializable
data class UserDto(
    val id: String,
    val email: String,
    @SerialName("full_name") val fullName: String,
    val role: String,
    @SerialName("preferred_locale") val preferredLocale: String,
    @SerialName("must_change_password") val mustChangePassword: Boolean
)

@Serializable
data class TokenPairDto(
    @SerialName("access_token") val accessToken: String,
    @SerialName("refresh_token") val refreshToken: String,
    @SerialName("access_expires_in") val accessExpiresIn: Int,
    @SerialName("refresh_expires_at") val refreshExpiresAt: String,
    val user: UserDto
)

@Serializable
data class FieldErrorDto(
    val field: String? = null,
    val message: String? = null
)

@Serializable
data class ProblemDto(
    val type: String = "about:blank",
    val title: String,
    val status: Int,
    val code: String,
    val detail: String? = null,
    val errors: List<FieldErrorDto> = emptyList()
)

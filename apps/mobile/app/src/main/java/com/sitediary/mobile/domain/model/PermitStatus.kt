package com.sitediary.mobile.domain.model

import java.time.LocalDate

enum class PermitStatus {
    ACTIVE,
    EXPIRING_SOON,
    EXPIRED
}

enum class PermitHealth {
    OK,
    WARN,
    EXPIRED,
    NONE
}

data class PermitEvaluation(
    val status: PermitStatus,
    val daysToExpiry: Int
)

data class EvaluatedPermit(
    val id: String,
    val projectId: String,
    val permitName: String,
    val authority: String,
    val permitNumber: String?,
    val issueDate: String?,
    val expiryDate: LocalDate,
    val documentPhotoUri: String?,
    val documentLocalPath: String?,
    val documentUploadStatus: String,
    val status: PermitStatus,
    val daysToExpiry: Int,
    val syncDirty: Boolean
)

data class PermitBannerSummary(
    val expiredCount: Int,
    val expiringSoonCount: Int,
    val highlightPermitName: String,
    val highlightDaysToExpiry: Int
) {
    val hasAlert: Boolean get() = expiredCount > 0 || expiringSoonCount > 0
}

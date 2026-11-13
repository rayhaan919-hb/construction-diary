package com.sitediary.mobile.domain.model

import java.time.Clock
import java.time.LocalDate
import java.time.ZoneId
import java.time.temporal.ChronoUnit
import javax.inject.Inject
import javax.inject.Singleton

/**
 * Mirrors `permits_with_status` PostgreSQL view in `contracts/schema.sql`:
 * - EXPIRED: expiry_date < project-local today
 * - EXPIRING_SOON: 0 <= days_to_expiry <= 14
 * - ACTIVE: days_to_expiry > 14
 */
@Singleton
class PermitStatusCalculator @Inject constructor(
    private val clock: Clock
) {
    fun projectToday(timezone: String): LocalDate {
        val zoneId = runCatching { ZoneId.of(timezone) }
            .getOrElse { ZoneId.of(DEFAULT_TIMEZONE) }
        return clock.instant().atZone(zoneId).toLocalDate()
    }

    fun evaluate(expiryDate: LocalDate, projectTimezone: String): PermitEvaluation {
        val today = projectToday(projectTimezone)
        val daysToExpiry = ChronoUnit.DAYS.between(today, expiryDate).toInt()
        val status = when {
            daysToExpiry < 0 -> PermitStatus.EXPIRED
            daysToExpiry <= EXPIRING_SOON_DAYS -> PermitStatus.EXPIRING_SOON
            else -> PermitStatus.ACTIVE
        }
        return PermitEvaluation(status = status, daysToExpiry = daysToExpiry)
    }

    fun evaluate(expiryDateIso: String, projectTimezone: String): PermitEvaluation {
        val parsed = LocalDate.parse(expiryDateIso)
        return evaluate(parsed, projectTimezone)
    }

    fun computeProjectHealth(evaluations: List<PermitEvaluation>): PermitHealth {
        if (evaluations.isEmpty()) return PermitHealth.NONE
        if (evaluations.any { it.status == PermitStatus.EXPIRED }) return PermitHealth.EXPIRED
        if (evaluations.any { it.status == PermitStatus.EXPIRING_SOON }) return PermitHealth.WARN
        return PermitHealth.OK
    }

    fun computeBannerSummary(permits: List<EvaluatedPermit>): PermitBannerSummary? {
        val expired = permits.filter { it.status == PermitStatus.EXPIRED }
            .sortedBy { it.expiryDate }
        val expiringSoon = permits.filter { it.status == PermitStatus.EXPIRING_SOON }
            .sortedBy { it.expiryDate }

        if (expired.isEmpty() && expiringSoon.isEmpty()) return null

        val highlight = expired.firstOrNull() ?: expiringSoon.first()
        return PermitBannerSummary(
            expiredCount = expired.size,
            expiringSoonCount = expiringSoon.size,
            highlightPermitName = highlight.permitName,
            highlightDaysToExpiry = highlight.daysToExpiry
        )
    }

    companion object {
        const val EXPIRING_SOON_DAYS = 14
        const val DEFAULT_TIMEZONE = "Asia/Karachi"
    }
}

package com.sitediary.mobile.domain.model

import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Test
import java.time.Clock
import java.time.Instant
import java.time.LocalDate
import java.time.ZoneOffset

class PermitStatusCalculatorTest {

    @Test
    fun `active beyond 14 days returns ACTIVE`() {
        val clock = Clock.fixed(Instant.parse("2026-11-14T10:00:00Z"), ZoneOffset.UTC)
        val calculator = PermitStatusCalculator(clock)

        val result = calculator.evaluate(LocalDate.of(2026, 11, 29), "UTC")

        assertEquals(PermitStatus.ACTIVE, result.status)
        assertEquals(15, result.daysToExpiry)
    }

    @Test
    fun `exactly 14 days boundary returns EXPIRING_SOON`() {
        val clock = Clock.fixed(Instant.parse("2026-11-14T10:00:00Z"), ZoneOffset.UTC)
        val calculator = PermitStatusCalculator(clock)

        val result = calculator.evaluate(LocalDate.of(2026, 11, 28), "UTC")

        assertEquals(PermitStatus.EXPIRING_SOON, result.status)
        assertEquals(14, result.daysToExpiry)
    }

    @Test
    fun `same day expiry returns EXPIRING_SOON with zero days`() {
        val clock = Clock.fixed(Instant.parse("2026-11-14T10:00:00Z"), ZoneOffset.UTC)
        val calculator = PermitStatusCalculator(clock)

        val result = calculator.evaluate(LocalDate.of(2026, 11, 14), "UTC")

        assertEquals(PermitStatus.EXPIRING_SOON, result.status)
        assertEquals(0, result.daysToExpiry)
    }

    @Test
    fun `past expiry date returns EXPIRED with negative days`() {
        val clock = Clock.fixed(Instant.parse("2026-11-14T10:00:00Z"), ZoneOffset.UTC)
        val calculator = PermitStatusCalculator(clock)

        val result = calculator.evaluate(LocalDate.of(2026, 11, 13), "UTC")

        assertEquals(PermitStatus.EXPIRED, result.status)
        assertEquals(-1, result.daysToExpiry)
    }

    @Test
    fun `project timezone boundary evaluates midnight rollover accurately`() {
        // 2026-11-14T20:00:00Z is 2026-11-14 in UTC, but 2026-11-15T01:00+05:00 in Asia/Karachi
        val clock = Clock.fixed(Instant.parse("2026-11-14T20:00:00Z"), ZoneOffset.UTC)
        val calculator = PermitStatusCalculator(clock)
        val expiry = LocalDate.of(2026, 11, 14)

        val utcEval = calculator.evaluate(expiry, "UTC")
        val karachiEval = calculator.evaluate(expiry, "Asia/Karachi")

        assertEquals(PermitStatus.EXPIRING_SOON, utcEval.status)
        assertEquals(0, utcEval.daysToExpiry)

        assertEquals(PermitStatus.EXPIRED, karachiEval.status)
        assertEquals(-1, karachiEval.daysToExpiry)
    }

    @Test
    fun `computeProjectHealth returns worst status or NONE`() {
        val calculator = PermitStatusCalculator(Clock.systemUTC())

        assertEquals(PermitHealth.NONE, calculator.computeProjectHealth(emptyList()))
        assertEquals(
            PermitHealth.OK,
            calculator.computeProjectHealth(listOf(PermitEvaluation(PermitStatus.ACTIVE, 20)))
        )
        assertEquals(
            PermitHealth.WARN,
            calculator.computeProjectHealth(
                listOf(
                    PermitEvaluation(PermitStatus.ACTIVE, 30),
                    PermitEvaluation(PermitStatus.EXPIRING_SOON, 5)
                )
            )
        )
        assertEquals(
            PermitHealth.EXPIRED,
            calculator.computeProjectHealth(
                listOf(
                    PermitEvaluation(PermitStatus.EXPIRING_SOON, 5),
                    PermitEvaluation(PermitStatus.EXPIRED, -2)
                )
            )
        )
    }

    @Test
    fun `computeBannerSummary highlights expired first or returns null when all active`() {
        val calculator = PermitStatusCalculator(Clock.systemUTC())

        val activeOnly = listOf(
            EvaluatedPermit(
                id = "p1",
                projectId = "pr1",
                permitName = "Excavation",
                authority = "LDA",
                permitNumber = null,
                issueDate = null,
                expiryDate = LocalDate.of(2027, 1, 1),
                documentPhotoUri = null,
                documentLocalPath = null,
                documentUploadStatus = "NONE",
                status = PermitStatus.ACTIVE,
                daysToExpiry = 48,
                syncDirty = false
            )
        )
        assertNull(calculator.computeBannerSummary(activeOnly))

        val mixed = activeOnly + listOf(
            EvaluatedPermit(
                id = "p2",
                projectId = "pr1",
                permitName = "Crane Safety",
                authority = "OSHA",
                permitNumber = null,
                issueDate = null,
                expiryDate = LocalDate.of(2026, 11, 20),
                documentPhotoUri = null,
                documentLocalPath = null,
                documentUploadStatus = "NONE",
                status = PermitStatus.EXPIRING_SOON,
                daysToExpiry = 6,
                syncDirty = false
            ),
            EvaluatedPermit(
                id = "p3",
                projectId = "pr1",
                permitName = "Fire NOC",
                authority = "Civil Defense",
                permitNumber = null,
                issueDate = null,
                expiryDate = LocalDate.of(2026, 11, 10),
                documentPhotoUri = null,
                documentLocalPath = null,
                documentUploadStatus = "NONE",
                status = PermitStatus.EXPIRED,
                daysToExpiry = -4,
                syncDirty = false
            )
        )
        val banner = calculator.computeBannerSummary(mixed)!!
        assertEquals(1, banner.expiredCount)
        assertEquals(1, banner.expiringSoonCount)
        assertEquals("Fire NOC", banner.highlightPermitName)
        assertEquals(-4, banner.highlightDaysToExpiry)
    }
}

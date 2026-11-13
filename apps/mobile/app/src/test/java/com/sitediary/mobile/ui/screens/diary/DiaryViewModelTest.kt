package com.sitediary.mobile.ui.screens.diary

import androidx.lifecycle.SavedStateHandle
import app.cash.turbine.test
import com.sitediary.mobile.data.local.SiteDiaryDatabase
import com.sitediary.mobile.data.local.entity.PermitEntity
import com.sitediary.mobile.data.local.entity.ProjectEntity
import com.sitediary.mobile.data.local.entity.SiteLogEntity
import com.sitediary.mobile.data.prefs.AppPreferences
import com.sitediary.mobile.data.remote.SiteDiaryApi
import com.sitediary.mobile.data.remote.dto.StructuredSummaryDto
import com.sitediary.mobile.data.repository.SiteDiaryRepository
import com.sitediary.mobile.data.sync.SyncScheduler
import com.sitediary.mobile.domain.model.PermitStatusCalculator
import com.sitediary.mobile.testdoubles.FakePermitDao
import com.sitediary.mobile.testdoubles.FakeProjectDao
import com.sitediary.mobile.testdoubles.FakeSiteLogDao
import com.sitediary.mobile.testdoubles.FakeSiteLogPhotoDao
import io.mockk.every
import io.mockk.mockk
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.ExperimentalCoroutinesApi
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.flowOf
import kotlinx.coroutines.test.StandardTestDispatcher
import kotlinx.coroutines.test.resetMain
import kotlinx.coroutines.test.runTest
import kotlinx.coroutines.test.setMain
import org.junit.After
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNotNull
import org.junit.Before
import org.junit.Test
import java.time.Clock
import java.time.Instant
import java.time.ZoneOffset

@OptIn(ExperimentalCoroutinesApi::class)
class DiaryViewModelTest {

    private val testDispatcher = StandardTestDispatcher()

    private lateinit var projectDao: FakeProjectDao
    private lateinit var permitDao: FakePermitDao
    private lateinit var photoDao: FakeSiteLogPhotoDao
    private lateinit var logDao: FakeSiteLogDao
    private lateinit var appPreferences: AppPreferences
    private val clock = Clock.fixed(Instant.parse("2026-11-14T10:00:00Z"), ZoneOffset.UTC)

    @Before
    fun setUp() {
        Dispatchers.setMain(testDispatcher)
        projectDao = FakeProjectDao()
        permitDao = FakePermitDao()
        photoDao = FakeSiteLogPhotoDao()
        logDao = FakeSiteLogDao(photoDao)

        appPreferences = mockk(relaxed = true) {
            every { isSyncing } returns MutableStateFlow(false)
            every { lastSyncError } returns flowOf(null)
        }
    }

    @After
    fun tearDown() {
        Dispatchers.resetMain()
    }

    @Test
    fun `emits local permit expiry banner and daily labor_max with deduplicated blockers`() = runTest {
        val calculator = PermitStatusCalculator(clock)
        val repository = SiteDiaryRepository(
            database = mockk<SiteDiaryDatabase>(relaxed = true),
            projectDao = projectDao,
            permitDao = permitDao,
            siteLogDao = logDao,
            siteLogPhotoDao = photoDao,
            api = mockk<SiteDiaryApi>(relaxed = true),
            appPreferences = appPreferences,
            syncScheduler = mockk<SyncScheduler>(relaxed = true),
            permitStatusCalculator = calculator,
            clock = clock
        )

        projectDao.upsertAll(
            listOf(
                ProjectEntity(
                    id = "proj-1",
                    name = "Civic Tower",
                    siteAddress = "Main Blvd",
                    timezone = "Asia/Karachi",
                    allowPhotoGps = false,
                    createdAt = "2026-11-01T00:00:00Z",
                    updatedAt = "2026-11-01T00:00:00Z",
                    serverVersion = 1L
                )
            )
        )
        permitDao.upsert(
            PermitEntity(
                id = "perm-1",
                projectId = "proj-1",
                permitName = "Crane Operation NOC",
                authority = "LDA",
                expiryDate = "2026-11-20", // 6 days from 2026-11-14 -> EXPIRING_SOON
                createdBy = "u1",
                clientUpdatedAt = "2026-11-01T00:00:00Z",
                createdAt = "2026-11-01T00:00:00Z",
                updatedAt = "2026-11-01T00:00:00Z"
            )
        )
        logDao.upsertAll(
            listOf(
                SiteLogEntity(
                    id = "log-1",
                    projectId = "proj-1",
                    authorId = "u1",
                    logDate = "2026-11-14",
                    recordedAt = "2026-11-14T08:00:00Z",
                    structuredSummary = StructuredSummaryDto(
                        tasksCompleted = listOf("Footing pour"),
                        laborCount = 14,
                        blockers = listOf("Pump delay ")
                    ),
                    clientUpdatedAt = "2026-11-14T08:00:00Z",
                    createdAt = "2026-11-14T08:00:00Z",
                    updatedAt = "2026-11-14T08:00:00Z"
                ),
                SiteLogEntity(
                    id = "log-2",
                    projectId = "proj-1",
                    authorId = "u1",
                    logDate = "2026-11-14",
                    recordedAt = "2026-11-14T11:00:00Z",
                    structuredSummary = StructuredSummaryDto(
                        tasksCompleted = listOf("Steel tying"),
                        laborCount = 22,
                        blockers = listOf("pump delay", "Rebar shortage")
                    ),
                    clientUpdatedAt = "2026-11-14T11:00:00Z",
                    createdAt = "2026-11-14T11:00:00Z",
                    updatedAt = "2026-11-14T11:00:00Z"
                )
            )
        )

        val viewModel = DiaryViewModel(
            savedStateHandle = SavedStateHandle(mapOf("projectId" to "proj-1")),
            repository = repository,
            appPreferences = appPreferences,
            permitStatusCalculator = calculator
        )

        viewModel.uiState.test {
            // Skip initial empty value if emitted first
            var state = awaitItem()
            if (state.project == null) {
                state = awaitItem()
            }

            assertEquals("Civic Tower", state.project?.name)
            assertEquals("2026-11-14", state.todayDate)
            assertEquals(2, state.todayLogCount)
            assertEquals(22, state.todayLaborMax) // MAX, not sum (36)
            assertEquals(2, state.todayBlockersCount) // Case-insensitive trimmed deduplication

            assertNotNull(state.bannerSummary)
            assertEquals(0, state.bannerSummary!!.expiredCount)
            assertEquals(1, state.bannerSummary!!.expiringSoonCount)
            assertEquals("Crane Operation NOC", state.bannerSummary!!.highlightPermitName)
            assertEquals(6, state.bannerSummary!!.highlightDaysToExpiry)
            cancelAndIgnoreRemainingEvents()
        }
    }
}

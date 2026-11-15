package com.sitediary.mobile.data.repository

import android.content.Context
import android.content.SharedPreferences
import androidx.lifecycle.SavedStateHandle
import com.sitediary.mobile.data.local.SiteDiaryDatabase
import com.sitediary.mobile.data.local.entity.PermitEntity
import com.sitediary.mobile.data.local.entity.ProjectEntity
import com.sitediary.mobile.data.local.entity.SiteLogEntity
import com.sitediary.mobile.data.media.AudioRecorderController
import com.sitediary.mobile.data.media.LocalMediaFileManager
import com.sitediary.mobile.data.media.PhotoProcessor
import com.sitediary.mobile.data.prefs.AppPreferences
import com.sitediary.mobile.data.remote.SiteDiaryApi
import com.sitediary.mobile.data.remote.dto.TokenPairDto
import com.sitediary.mobile.data.remote.dto.UserDto
import com.sitediary.mobile.data.sync.SyncScheduler
import com.sitediary.mobile.domain.model.EvaluatedPermit
import com.sitediary.mobile.domain.model.PermitStatus
import com.sitediary.mobile.domain.model.PermitStatusCalculator
import com.sitediary.mobile.testdoubles.FakePermitDao
import com.sitediary.mobile.testdoubles.FakeProjectDao
import com.sitediary.mobile.testdoubles.FakeSiteLogDao
import com.sitediary.mobile.testdoubles.FakeSiteLogPhotoDao
import com.sitediary.mobile.ui.screens.detail.LogDetailViewModel
import com.sitediary.mobile.ui.screens.permits.PermitsViewModel
import io.mockk.every
import io.mockk.mockk
import io.mockk.verify
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.ExperimentalCoroutinesApi
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.test.UnconfinedTestDispatcher
import kotlinx.coroutines.test.resetMain
import kotlinx.coroutines.test.runTest
import kotlinx.coroutines.test.setMain
import kotlinx.coroutines.withContext
import kotlinx.coroutines.withTimeout
import kotlinx.serialization.json.Json
import org.junit.After
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Before
import org.junit.Test
import java.io.File
import java.nio.file.Files
import java.time.Clock
import java.time.Instant
import java.time.LocalDate
import java.time.ZoneOffset

@OptIn(ExperimentalCoroutinesApi::class)
class SecurityRepositoryAndViewModelTest {

    private val testDispatcher = UnconfinedTestDispatcher()
    private lateinit var tempDir: File
    private lateinit var context: Context
    private lateinit var prefsMap: MutableMap<String, Any?>
    private lateinit var sharedPrefs: SharedPreferences
    private lateinit var appPreferences: AppPreferences
    private lateinit var projectDao: FakeProjectDao
    private lateinit var permitDao: FakePermitDao
    private lateinit var photoDao: FakeSiteLogPhotoDao
    private lateinit var logDao: FakeSiteLogDao
    private lateinit var repository: SiteDiaryRepository
    private val clock = Clock.fixed(Instant.parse("2026-11-15T10:00:00Z"), ZoneOffset.UTC)

    @Before
    fun setUp() {
        Dispatchers.setMain(testDispatcher)
        tempDir = Files.createTempDirectory("sitediary_repo_test_").toFile()
        prefsMap = mutableMapOf()
        sharedPrefs = mockk(relaxed = true)
        every { sharedPrefs.getString(any(), any()) } answers {
            prefsMap[firstArg()] as? String ?: secondArg()
        }
        every { sharedPrefs.edit() } answers {
            val pending = mutableMapOf<String, Any?>()
            val removed = mutableSetOf<String>()
            var clearRequested = false
            mockk<SharedPreferences.Editor>(relaxed = true).also { ed ->
                every { ed.putString(any(), any()) } answers {
                    pending[firstArg()] = secondArg()
                    removed.remove(firstArg())
                    ed
                }
                every { ed.remove(any()) } answers {
                    removed.add(firstArg())
                    pending.remove(firstArg())
                    ed
                }
                every { ed.clear() } answers {
                    clearRequested = true
                    pending.clear()
                    ed
                }
                every { ed.commit() } answers {
                    if (clearRequested) prefsMap.clear()
                    removed.forEach { prefsMap.remove(it) }
                    prefsMap.putAll(pending)
                    true
                }
                every { ed.apply() } answers {
                    if (clearRequested) prefsMap.clear()
                    removed.forEach { prefsMap.remove(it) }
                    prefsMap.putAll(pending)
                }
            }
        }

        context = mockk(relaxed = true)
        every { context.applicationContext } returns context
        every { context.filesDir } returns tempDir
        every { context.cacheDir } returns tempDir
        every { context.getSharedPreferences(any(), any()) } returns sharedPrefs

        appPreferences = AppPreferences(context = context)
        projectDao = FakeProjectDao()
        permitDao = FakePermitDao()
        photoDao = FakeSiteLogPhotoDao()
        logDao = FakeSiteLogDao(photoDao)

        val db = mockk<SiteDiaryDatabase>(relaxed = true)
        val syncScheduler = mockk<SyncScheduler>(relaxed = true)
        val api = mockk<SiteDiaryApi>(relaxed = true)

        repository = SiteDiaryRepository(
            database = db,
            projectDao = projectDao,
            permitDao = permitDao,
            siteLogDao = logDao,
            siteLogPhotoDao = photoDao,
            api = api,
            appPreferences = appPreferences,
            syncScheduler = syncScheduler,
            permitStatusCalculator = PermitStatusCalculator(clock),
            clock = clock
        )
    }

    @After
    fun tearDown() {
        Dispatchers.resetMain()
        tempDir.deleteRecursively()
    }

    @Test
    fun `AppPreferences preserves Arabic locale and wipes session and FCM token on logout`() = runTest {
        appPreferences.setAppLocale("ar")
        assertEquals("ar", appPreferences.appLocale.first())

        appPreferences.setUploadOnMobileData(true)
        appPreferences.saveFcmToken("fcm-token-123")
        appPreferences.saveTokenPair(
            TokenPairDto(
                accessToken = "acc-123",
                refreshToken = "ref-456",
                accessExpiresIn = 900,
                refreshExpiresAt = "2026-12-15T10:00:00Z",
                user = UserDto(
                    id = "u-1",
                    email = "owner@acme.pk",
                    fullName = "Owner",
                    role = "OWNER",
                    preferredLocale = "en",
                    mustChangePassword = false
                )
            )
        )
        assertNotNull(appPreferences.getAccessToken())
        assertEquals("fcm-token-123", appPreferences.getSavedFcmToken())

        appPreferences.clearAllSettingsOnLogout()
        assertNull(appPreferences.getAccessToken())
        assertNull(appPreferences.getSavedFcmToken())
        assertFalse(appPreferences.uploadOnMobileData.first())
    }

    @Test
    fun `SiteDiaryRepository supports offline log edits soft-deletes and permit updates`() = runTest {
        projectDao.upsertAll(
            listOf(
                ProjectEntity(
                    id = "proj-1",
                    name = "Test Tower",
                    siteAddress = "Plot 1",
                    timezone = "Asia/Karachi",
                    allowPhotoGps = false,
                    createdAt = "2026-11-01T00:00:00Z",
                    updatedAt = "2026-11-01T00:00:00Z",
                    serverVersion = 1L
                )
            )
        )
        logDao.upsert(
            SiteLogEntity(
                id = "log-1",
                projectId = "proj-1",
                authorId = "u-1",
                logDate = "2026-11-15",
                recordedAt = "2026-11-15T08:00:00Z",
                notes = "Initial note",
                clientUpdatedAt = "2026-11-15T08:00:00Z",
                createdAt = "2026-11-15T08:00:00Z",
                updatedAt = "2026-11-15T08:00:00Z",
                syncDirty = false,
                localMutationSeq = 1L
            )
        )
        permitDao.upsert(
            PermitEntity(
                id = "perm-1",
                projectId = "proj-1",
                permitName = "Crane Permit",
                authority = "LDA",
                expiryDate = "2026-12-30",
                createdBy = "u-1",
                clientUpdatedAt = "2026-11-15T08:00:00Z",
                createdAt = "2026-11-15T08:00:00Z",
                updatedAt = "2026-11-15T08:00:00Z",
                syncDirty = false,
                localMutationSeq = 1L
            )
        )

        repository.editSiteLogNotesOffline("log-1", "Updated steel pour notes")
        val editedLog = logDao.getById("log-1")!!
        assertEquals("Updated steel pour notes", editedLog.notes)
        assertTrue(editedLog.syncDirty)
        assertTrue(editedLog.editedByHuman)
        assertEquals(2L, editedLog.localMutationSeq)

        repository.softDeleteSiteLogOffline("log-1")
        val deletedLog = logDao.getById("log-1")!!
        assertNotNull(deletedLog.deletedAt)
        assertTrue(deletedLog.syncDirty)

        repository.editPermitOffline(
            permitId = "perm-1",
            permitName = "Tower Crane Permit",
            authority = "LDA Lahore",
            permitNumber = "LDA-99",
            issueDate = "2026-11-01",
            expiryDate = "2027-01-15"
        )
        val editedPermit = permitDao.getById("perm-1")!!
        assertEquals("Tower Crane Permit", editedPermit.permitName)
        assertEquals("LDA-99", editedPermit.permitNumber)
        assertTrue(editedPermit.syncDirty)

        repository.softDeletePermitOffline("perm-1")
        val deletedPermit = permitDao.getById("perm-1")!!
        assertNotNull(deletedPermit.deletedAt)
        assertTrue(deletedPermit.syncDirty)
    }

    @Test
    fun `LogDetailViewModel plays remote audioUrl and supports offline notes and deletion`() = runTest {
        logDao.upsert(
            SiteLogEntity(
                id = "log-remote",
                projectId = "proj-1",
                authorId = "u-1",
                logDate = "2026-11-15",
                recordedAt = "2026-11-15T08:00:00Z",
                notes = "Before edit",
                audioUrl = "https://storage.googleapis.com/bucket/note.m4a?sig=1",
                clientUpdatedAt = "2026-11-15T08:00:00Z",
                createdAt = "2026-11-15T08:00:00Z",
                updatedAt = "2026-11-15T08:00:00Z"
            )
        )
        val audioController = mockk<AudioRecorderController>(relaxed = true)
        every { audioController.isPlaying } returns MutableStateFlow(false)

        val vm = LogDetailViewModel(
            savedStateHandle = SavedStateHandle(mapOf("logId" to "log-remote")),
            repository = repository,
            audioRecorder = audioController
        )
        vm.uiState.first { it.logWithPhotos != null }

        vm.toggleAudioPlayback()
        verify { audioController.togglePlayback("https://storage.googleapis.com/bucket/note.m4a?sig=1") }

        vm.updateNotes("Edited remotely synced log")
        assertEquals("Edited remotely synced log", logDao.getById("log-remote")?.notes)

        var deletedCallbackFired = false
        vm.deleteLog { deletedCallbackFired = true }
        withContext(Dispatchers.Default) {
            withTimeout(2_000) {
                while (!deletedCallbackFired) delay(10)
            }
        }
        assertTrue(deletedCallbackFired)
        assertNotNull(logDao.getById("log-remote")?.deletedAt)
    }

    @Test
    fun `PermitsViewModel edits and deletes permits offline-first`() = runTest {
        permitDao.upsert(
            PermitEntity(
                id = "perm-edit",
                projectId = "proj-1",
                permitName = "Old Permit",
                authority = "CDA",
                expiryDate = "2026-12-20",
                createdBy = "u-1",
                clientUpdatedAt = "2026-11-15T08:00:00Z",
                createdAt = "2026-11-15T08:00:00Z",
                updatedAt = "2026-11-15T08:00:00Z"
            )
        )
        val vm = PermitsViewModel(
            savedStateHandle = SavedStateHandle(mapOf("projectId" to "proj-1")),
            repository = repository,
            appPreferences = appPreferences,
            photoProcessor = mockk(relaxed = true),
            mediaFileManager = LocalMediaFileManager(context)
        )
        vm.openEditDialog(
            EvaluatedPermit(
                id = "perm-edit",
                projectId = "proj-1",
                permitName = "Old Permit",
                authority = "CDA",
                permitNumber = null,
                issueDate = null,
                expiryDate = LocalDate.parse("2026-12-20"),
                documentPhotoUri = null,
                documentLocalPath = null,
                documentUploadStatus = "NONE",
                status = PermitStatus.ACTIVE,
                daysToExpiry = 35,
                syncDirty = false
            )
        )
        vm.onPermitNameChange("Renewed Building Permit")
        vm.onExpiryDateChange("2027-06-30")
        vm.savePermit()

        val updated = permitDao.getById("perm-edit")!!
        assertEquals("Renewed Building Permit", updated.permitName)
        assertEquals("2027-06-30", updated.expiryDate)

        vm.deletePermit("perm-edit")
        assertNotNull(permitDao.getById("perm-edit")?.deletedAt)
    }
}

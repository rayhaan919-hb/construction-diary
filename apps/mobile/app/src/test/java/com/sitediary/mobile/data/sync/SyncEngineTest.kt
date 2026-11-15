package com.sitediary.mobile.data.sync

import android.content.Context
import com.sitediary.mobile.data.local.entity.PermitEntity
import com.sitediary.mobile.data.local.entity.ProjectEntity
import com.sitediary.mobile.data.local.entity.ProjectMemberEntity
import com.sitediary.mobile.data.local.entity.SiteLogEntity
import com.sitediary.mobile.data.local.entity.SiteLogPhotoEntity
import com.sitediary.mobile.data.local.entity.SyncCursorEntity
import com.sitediary.mobile.data.media.LocalMediaFileManager
import com.sitediary.mobile.data.remote.SiteDiaryApi
import com.sitediary.mobile.data.remote.dto.MediaCompleteRequestDto
import com.sitediary.mobile.data.remote.dto.MediaKind
import com.sitediary.mobile.data.remote.dto.MemberDto
import com.sitediary.mobile.data.remote.dto.PermitDto
import com.sitediary.mobile.data.remote.dto.ProjectDto
import com.sitediary.mobile.data.remote.dto.SiteLogDto
import com.sitediary.mobile.data.remote.dto.SiteLogPhotoDto
import com.sitediary.mobile.data.remote.dto.SyncPullChangesDto
import com.sitediary.mobile.data.remote.dto.SyncPullResponseDto
import com.sitediary.mobile.data.remote.dto.SyncPushRequestDto
import com.sitediary.mobile.data.remote.dto.SyncPushResponseDto
import com.sitediary.mobile.data.remote.dto.SyncPushResultDto
import com.sitediary.mobile.data.remote.dto.UploadTicketDto
import com.sitediary.mobile.testdoubles.FakePermitDao
import com.sitediary.mobile.testdoubles.FakeProjectDao
import com.sitediary.mobile.testdoubles.FakeProjectMemberDao
import com.sitediary.mobile.testdoubles.FakeSiteLogDao
import com.sitediary.mobile.testdoubles.FakeSiteLogPhotoDao
import com.sitediary.mobile.testdoubles.FakeSyncCursorDao
import io.mockk.coEvery
import io.mockk.coVerify
import io.mockk.every
import io.mockk.mockk
import kotlinx.coroutines.test.runTest
import okhttp3.OkHttpClient
import okhttp3.mockwebserver.MockResponse
import okhttp3.mockwebserver.MockWebServer
import org.junit.After
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Before
import org.junit.Rule
import org.junit.Test
import org.junit.rules.TemporaryFolder
import retrofit2.Response
import java.io.File
import java.time.Clock
import java.time.Instant
import java.time.ZoneOffset

class SyncEngineTest {

    @Rule
    @JvmField
    val tempFolder = TemporaryFolder()

    private lateinit var projectDao: FakeProjectDao
    private lateinit var memberDao: FakeProjectMemberDao
    private lateinit var permitDao: FakePermitDao
    private lateinit var photoDao: FakeSiteLogPhotoDao
    private lateinit var logDao: FakeSiteLogDao
    private lateinit var cursorDao: FakeSyncCursorDao
    private lateinit var mediaFileManager: LocalMediaFileManager
    private lateinit var api: SiteDiaryApi
    private lateinit var syncEngine: SyncEngine
    private val clock = Clock.fixed(Instant.parse("2026-11-14T12:00:00Z"), ZoneOffset.UTC)
    private val currentUserId = "user-sup-1"

    @Before
    fun setUp() {
        projectDao = FakeProjectDao()
        memberDao = FakeProjectMemberDao()
        permitDao = FakePermitDao()
        photoDao = FakeSiteLogPhotoDao()
        logDao = FakeSiteLogDao(photoDao)
        cursorDao = FakeSyncCursorDao()

        val filesDir = tempFolder.newFolder("files")
        val cacheDir = tempFolder.newFolder("cache")
        val mockContext = mockk<Context> {
            every { this@mockk.filesDir } returns filesDir
            every { this@mockk.cacheDir } returns cacheDir
        }
        mediaFileManager = LocalMediaFileManager(mockContext)
        api = mockk(relaxed = true)

        syncEngine = SyncEngine(
            api = api,
            projectDao = projectDao,
            projectMemberDao = memberDao,
            permitDao = permitDao,
            siteLogDao = logDao,
            siteLogPhotoDao = photoDao,
            syncCursorDao = cursorDao,
            mediaFileManager = mediaFileManager,
            currentUserIdProvider = { currentUserId },
            clock = clock,
            runInTransaction = { block -> block() }
        )
    }

    @Test
    fun `push batches dirty records in chunks of at most 200 and preserves mid-flight edits`() = runTest {
        val logs = (1..205).map { idx ->
            SiteLogEntity(
                id = "log-$idx",
                projectId = "proj-1",
                authorId = currentUserId,
                logDate = "2026-11-14",
                recordedAt = "2026-11-14T08:00:00Z",
                notes = "Note $idx",
                clientUpdatedAt = "2026-11-14T08:00:00Z",
                createdAt = "2026-11-14T08:00:00Z",
                updatedAt = "2026-11-14T08:00:00Z",
                syncDirty = true,
                localMutationSeq = 1L
            )
        }
        logDao.upsertAll(logs)

        var pushCallCount = 0
        val batchSizes = mutableListOf<Int>()
        coEvery { api.syncPush(any()) } coAnswers {
            val req = firstArg<SyncPushRequestDto>()
            pushCallCount++
            batchSizes += req.changes.siteLogs.size

            // Simulate a mid-flight edit to log-1 during the very first push batch!
            if (pushCallCount == 1) {
                val edited = logDao.getById("log-1")!!
                logDao.upsert(
                    edited.copy(
                        notes = "Edited while push in flight",
                        localMutationSeq = 2L,
                        syncDirty = true
                    )
                )
            }

            Response.success(
                SyncPushResponseDto(
                    serverTime = "2026-11-14T12:00:00Z",
                    results = req.changes.siteLogs.mapIndexed { i, item ->
                        SyncPushResultDto(
                            entity = "site_logs",
                            id = item.id,
                            status = "APPLIED",
                            serverVersion = 100L + i
                        )
                    }
                )
            )
        }
        coEvery { api.syncPull(since = any(), limit = any(), projectId = null) } returns Response.success(
            SyncPullResponseDto(nextCursor = 10L, hasMore = false, changes = SyncPullChangesDto())
        )

        val outcome = syncEngine.syncAll()
        assertEquals(SyncOutcome.Success, outcome)
        // Batch 1 = 200 items, Batch 2 = 5 remaining + log-1 re-queued = 6 items!
        assertEquals(listOf(200, 6), batchSizes)
        assertFalse(logDao.getById("log-1")!!.syncDirty)
        assertEquals("Edited while push in flight", logDao.getById("log-1")!!.notes)
    }

    @Test
    fun `scoped backfill triggers when newly added membership is discovered after global cursor`() = runTest {
        cursorDao.upsert(SyncCursorEntity(SyncEngine.GLOBAL_CURSOR_KEY, 50L, 1000L))

        val newMember = MemberDto(
            projectId = "proj-2",
            userId = currentUserId,
            role = "SUPERVISOR",
            fullName = "Ali Khan",
            email = "ali@site.pk",
            serverVersion = 55L
        )
        val project2 = ProjectDto(
            id = "proj-2",
            name = "Bahria Plaza",
            siteAddress = "Sector C",
            timezone = "Asia/Karachi",
            allowPhotoGps = false,
            createdAt = "2026-10-01T00:00:00Z",
            updatedAt = "2026-11-14T00:00:00Z",
            serverVersion = 10L
        )
        val oldPermit = PermitDto(
            id = "perm-old",
            projectId = "proj-2",
            permitName = "Excavation NOC",
            authority = "CDA",
            expiryDate = "2026-12-01",
            status = "ACTIVE",
            daysToExpiry = 17,
            createdBy = "owner-1",
            createdAt = "2026-10-02T00:00:00Z",
            updatedAt = "2026-10-02T00:00:00Z",
            serverVersion = 12L
        )

        // Global pull since 50 returns new membership only
        coEvery { api.syncPull(since = 50L, limit = any(), projectId = null) } returns Response.success(
            SyncPullResponseDto(
                nextCursor = 55L,
                hasMore = false,
                changes = SyncPullChangesDto(projectMembers = listOf(newMember))
            )
        )
        // Scoped backfill for proj-2 starts at since=0 and paginates across 2 pages
        coEvery { api.syncPull(since = 0L, limit = any(), projectId = "proj-2") } returns Response.success(
            SyncPullResponseDto(
                nextCursor = 10L,
                hasMore = true,
                changes = SyncPullChangesDto(projects = listOf(project2))
            )
        )
        coEvery { api.syncPull(since = 10L, limit = any(), projectId = "proj-2") } returns Response.success(
            SyncPullResponseDto(
                nextCursor = 55L,
                hasMore = false,
                changes = SyncPullChangesDto(permits = listOf(oldPermit))
            )
        )

        val outcome = syncEngine.syncAll()
        assertEquals(SyncOutcome.Success, outcome)

        assertNotNull(projectDao.getById("proj-2"))
        assertNotNull(permitDao.getById("perm-old"))
        assertEquals(55L, cursorDao.getCursor(SyncEngine.GLOBAL_CURSOR_KEY))
        assertEquals(55L, cursorDao.getCursor(SyncEngine.projectCursorKey("proj-2")))
    }

    @Test
    fun `membership tombstone purges all local Room rows and media files for that project`() = runTest {
        val project1 = ProjectEntity(
            id = "proj-1",
            name = "Removed Site",
            siteAddress = "Plot 9",
            timezone = "Asia/Karachi",
            allowPhotoGps = false,
            createdAt = "2026-11-01T00:00:00Z",
            updatedAt = "2026-11-01T00:00:00Z",
            serverVersion = 1L
        )
        projectDao.upsertAll(listOf(project1))
        memberDao.upsertAll(
            listOf(
                ProjectMemberEntity(
                    projectId = "proj-1",
                    userId = currentUserId,
                    role = "SUPERVISOR",
                    fullName = "Ali",
                    email = "ali@site.pk",
                    serverVersion = 2L
                )
            )
        )
        val audioFile = mediaFileManager.createAudioFile("proj-1", "log-1").apply {
            writeText("fake-m4a-bytes")
        }
        val photoFile = mediaFileManager.createPhotoFile("proj-1", "photo-1").apply {
            writeText("fake-jpg-bytes")
        }
        val permitFile = mediaFileManager.createPermitDocumentFile("proj-1", "perm-1").apply {
            writeText("fake-doc-bytes")
        }

        logDao.upsert(
            SiteLogEntity(
                id = "log-1",
                projectId = "proj-1",
                authorId = currentUserId,
                logDate = "2026-11-14",
                recordedAt = "2026-11-14T08:00:00Z",
                clientUpdatedAt = "2026-11-14T08:00:00Z",
                createdAt = "2026-11-14T08:00:00Z",
                updatedAt = "2026-11-14T08:00:00Z",
                audioLocalPath = audioFile.absolutePath
            )
        )
        photoDao.upsertAll(
            listOf(
                SiteLogPhotoEntity(
                    id = "photo-1",
                    siteLogId = "log-1",
                    projectId = "proj-1",
                    createdAt = "2026-11-14T08:00:00Z",
                    updatedAt = "2026-11-14T08:00:00Z",
                    localPath = photoFile.absolutePath
                )
            )
        )
        permitDao.upsert(
            PermitEntity(
                id = "perm-1",
                projectId = "proj-1",
                permitName = "Safety",
                authority = "OSHA",
                expiryDate = "2026-12-30",
                createdBy = currentUserId,
                clientUpdatedAt = "2026-11-14T08:00:00Z",
                createdAt = "2026-11-14T08:00:00Z",
                updatedAt = "2026-11-14T08:00:00Z",
                documentLocalPath = permitFile.absolutePath
            )
        )
        cursorDao.upsert(SyncCursorEntity(SyncEngine.projectCursorKey("proj-1"), 10L, 1000L))

        val tombstoneMember = MemberDto(
            projectId = "proj-1",
            userId = currentUserId,
            role = "SUPERVISOR",
            fullName = "Ali",
            email = "ali@site.pk",
            deletedAt = "2026-11-14T11:55:00Z",
            serverVersion = 60L
        )
        coEvery { api.syncPull(since = 0L, limit = any(), projectId = null) } returns Response.success(
            SyncPullResponseDto(
                nextCursor = 60L,
                hasMore = false,
                changes = SyncPullChangesDto(projectMembers = listOf(tombstoneMember))
            )
        )

        val outcome = syncEngine.syncAll()
        assertEquals(SyncOutcome.Success, outcome)

        assertNull(projectDao.getById("proj-1"))
        assertNull(memberDao.getMembership("proj-1", currentUserId))
        assertNull(logDao.getById("log-1"))
        assertNull(photoDao.getById("photo-1"))
        assertNull(permitDao.getById("perm-1"))
        assertNull(cursorDao.getCursor(SyncEngine.projectCursorKey("proj-1")))

        assertFalse(audioFile.exists())
        assertFalse(photoFile.exists())
        assertFalse(permitFile.exists())
    }

    @Test
    fun `MediaUploader updates storage_uri and pushes row BEFORE PUT and media complete`() = runTest {
        val server = MockWebServer()
        server.start()
        try {
            server.enqueue(MockResponse().setResponseCode(200))
            val uploadUrl = server.url("/v1/media/local/projects%2Fproj-1%2Faudio%2Flog-1.m4a?sig=1&exp=999").toString()

            val audioFile = mediaFileManager.createAudioFile("proj-1", "log-1").apply {
                writeBytes(ByteArray(128) { 7 })
            }
            logDao.upsert(
                SiteLogEntity(
                    id = "log-1",
                    projectId = "proj-1",
                    authorId = currentUserId,
                    logDate = "2026-11-14",
                    recordedAt = "2026-11-14T08:00:00Z",
                    audioDurationMs = 5000,
                    audioUploadStatus = "PENDING",
                    extractionStatus = "PENDING",
                    clientUpdatedAt = "2026-11-14T08:00:00Z",
                    createdAt = "2026-11-14T08:00:00Z",
                    updatedAt = "2026-11-14T08:00:00Z",
                    audioLocalPath = audioFile.absolutePath,
                    syncDirty = true,
                    localMutationSeq = 1L
                )
            )

            val events = mutableListOf<String>()
            coEvery { api.getUploadUrl(any()) } coAnswers {
                events += "upload-url"
                Response.success(
                    UploadTicketDto(
                        uploadUrl = uploadUrl,
                        method = "PUT",
                        headers = mapOf("Content-Type" to "audio/mp4", "x-test-header" to "abc"),
                        storageUri = "local://projects/proj-1/audio/log-1.m4a",
                        expiresAt = "2026-11-14T12:15:00Z"
                    )
                )
            }
            coEvery { api.syncPush(any()) } coAnswers {
                val req = firstArg<SyncPushRequestDto>()
                events += "sync-push:${req.changes.siteLogs.first().audioUri}"
                Response.success(
                    SyncPushResponseDto(
                        serverTime = "2026-11-14T12:00:00Z",
                        results = req.changes.siteLogs.map {
                            SyncPushResultDto("site_logs", it.id, "APPLIED", 70L)
                        }
                    )
                )
            }
            coEvery { api.completeMediaUpload(any()) } coAnswers {
                val req = firstArg<MediaCompleteRequestDto>()
                events += "complete:${req.kind}:${req.objectId}"
                Response.success(Unit)
            }

            val uploader = MediaUploader(
                api = api,
                rawUploadClient = OkHttpClient(),
                syncEngine = syncEngine,
                siteLogDao = logDao,
                siteLogPhotoDao = photoDao,
                permitDao = permitDao,
                clock = clock
            )

            val outcome = uploader.uploadAllPending()
            assertEquals(SyncOutcome.Success, outcome)

            val putRequest = server.takeRequest()
            assertEquals("PUT", putRequest.method)
            assertEquals("abc", putRequest.getHeader("x-test-header"))
            assertNull(putRequest.getHeader("Authorization"))

            assertEquals(
                listOf(
                    "upload-url",
                    "sync-push:local://projects/proj-1/audio/log-1.m4a",
                    "complete:AUDIO:log-1"
                ),
                events
            )
            val saved = logDao.getById("log-1")!!
            assertEquals("UPLOADED", saved.audioUploadStatus)
            assertEquals(clock.millis(), saved.audioUploadedAtEpochMs)
        } finally {
            server.shutdown()
        }
    }

    @Test
    fun `push CONFLICT leaves local dirty edit intact with CONFLICT_PENDING error`() = runTest {
        logDao.upsert(
            SiteLogEntity(
                id = "log-conflict",
                projectId = "proj-1",
                authorId = currentUserId,
                logDate = "2026-11-14",
                recordedAt = "2026-11-14T08:00:00Z",
                notes = "Supervisor local note",
                clientUpdatedAt = "2026-11-14T09:00:00Z",
                createdAt = "2026-11-14T08:00:00Z",
                updatedAt = "2026-11-14T09:00:00Z",
                syncDirty = true,
                localMutationSeq = 1L
            )
        )

        coEvery { api.syncPush(any()) } returns Response.success(
            SyncPushResponseDto(
                serverTime = "2026-11-14T12:00:00Z",
                results = listOf(
                    SyncPushResultDto(
                        entity = "site_logs",
                        id = "log-conflict",
                        status = "CONFLICT",
                        errorDetail = "Server version is newer"
                    )
                )
            )
        )
        coEvery { api.syncPull(since = any(), limit = any(), projectId = null) } returns Response.success(
            SyncPullResponseDto(
                nextCursor = 15L,
                hasMore = false,
                changes = SyncPullChangesDto(
                    siteLogs = listOf(
                        SiteLogDto(
                            id = "log-conflict",
                            projectId = "proj-1",
                            authorId = currentUserId,
                            logDate = "2026-11-14",
                            recordedAt = "2026-11-14T08:00:00Z",
                            notes = "Owner server edit",
                            audioUploadStatus = "NONE",
                            extractionStatus = "DONE",
                            clientUpdatedAt = "2026-11-14T10:00:00Z",
                            createdAt = "2026-11-14T08:00:00Z",
                            updatedAt = "2026-11-14T10:00:00Z",
                            serverVersion = 15L
                        )
                    )
                )
            )
        )

        val outcome = syncEngine.syncAll()
        assertEquals(SyncOutcome.Success, outcome)

        val retained = logDao.getById("log-conflict")!!
        assertEquals("Supervisor local note", retained.notes)
        assertEquals(true, retained.syncDirty)
        assertTrue(retained.syncError?.contains("CONFLICT_PENDING") == true)
    }

    @Test
    fun `pull tombstone removes local photo file from device`() = runTest {
        val photoFile = mediaFileManager.createPhotoFile("proj-1", "photo-del").apply {
            writeText("jpg-bytes")
        }
        photoDao.upsertAll(
            listOf(
                SiteLogPhotoEntity(
                    id = "photo-del",
                    siteLogId = "log-1",
                    projectId = "proj-1",
                    createdAt = "2026-11-14T08:00:00Z",
                    updatedAt = "2026-11-14T08:00:00Z",
                    localPath = photoFile.absolutePath,
                    uploadStatus = "UPLOADED"
                )
            )
        )

        coEvery { api.syncPull(since = 0L, limit = any(), projectId = null) } returns Response.success(
            SyncPullResponseDto(
                nextCursor = 25L,
                hasMore = false,
                changes = SyncPullChangesDto(
                    siteLogPhotos = listOf(
                        SiteLogPhotoDto(
                            id = "photo-del",
                            siteLogId = "log-1",
                            storageUri = "local://projects/proj-1/photos/photo-del.jpg",
                            uploadStatus = "UPLOADED",
                            deletedAt = "2026-11-14T11:00:00Z",
                            serverVersion = 25L
                        )
                    )
                )
            )
        )

        val outcome = syncEngine.syncAll()
        assertEquals(SyncOutcome.Success, outcome)
        assertNull(photoDao.getById("photo-del"))
        assertFalse(photoFile.exists())
    }

    @Test
    fun `MediaUploader forwards ticket_id and sha256 checksum on completion`() = runTest {
        val server = MockWebServer()
        server.start()
        try {
            server.enqueue(MockResponse().setResponseCode(200))
            val uploadUrl = server.url("/v1/media/local/doc-1.jpg").toString()
            val docFile = mediaFileManager.createPermitDocumentFile("proj-1", "perm-doc-1").apply {
                writeBytes(byteArrayOf(1, 2, 3, 4, 5))
            }
            permitDao.upsert(
                PermitEntity(
                    id = "perm-doc-1",
                    projectId = "proj-1",
                    permitName = "Fire NOC",
                    authority = "Rescue 1122",
                    expiryDate = "2026-12-31",
                    createdBy = currentUserId,
                    clientUpdatedAt = "2026-11-14T08:00:00Z",
                    createdAt = "2026-11-14T08:00:00Z",
                    updatedAt = "2026-11-14T08:00:00Z",
                    documentLocalPath = docFile.absolutePath,
                    documentUploadStatus = "PENDING"
                )
            )

            var capturedComplete: MediaCompleteRequestDto? = null
            coEvery { api.getUploadUrl(any()) } returns Response.success(
                UploadTicketDto(
                    ticketId = "ticket-123",
                    uploadUrl = uploadUrl,
                    method = "PUT",
                    headers = mapOf("Content-Type" to "image/jpeg"),
                    storageUri = "local://projects/proj-1/permits/perm-doc-1.jpg",
                    expiresAt = "2026-11-14T12:15:00Z"
                )
            )
            coEvery { api.syncPush(any()) } returns Response.success(
                SyncPushResponseDto(
                    serverTime = "2026-11-14T12:00:00Z",
                    results = listOf(SyncPushResultDto("permits", "perm-doc-1", "APPLIED", 90L))
                )
            )
            coEvery { api.completeMediaUpload(any()) } coAnswers {
                capturedComplete = firstArg()
                Response.success(Unit)
            }

            val uploader = MediaUploader(
                api = api,
                rawUploadClient = OkHttpClient(),
                syncEngine = syncEngine,
                siteLogDao = logDao,
                siteLogPhotoDao = photoDao,
                permitDao = permitDao,
                clock = clock
            )

            val outcome = uploader.uploadAllPending()
            assertEquals(SyncOutcome.Success, outcome)
            assertEquals("ticket-123", capturedComplete?.ticketId)
            assertEquals(MediaKind.PERMIT_DOC, capturedComplete?.kind)
            assertEquals(64, capturedComplete?.sha256?.length)
            assertEquals("UPLOADED", permitDao.getById("perm-doc-1")?.documentUploadStatus)
        } finally {
            server.shutdown()
        }
    }
}

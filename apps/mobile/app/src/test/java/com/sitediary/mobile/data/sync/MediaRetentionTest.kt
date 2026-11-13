package com.sitediary.mobile.data.sync

import android.content.Context
import com.sitediary.mobile.data.local.entity.PermitEntity
import com.sitediary.mobile.data.local.entity.SiteLogEntity
import com.sitediary.mobile.data.local.entity.SiteLogPhotoEntity
import com.sitediary.mobile.data.media.LocalMediaFileManager
import com.sitediary.mobile.testdoubles.FakePermitDao
import com.sitediary.mobile.testdoubles.FakeSiteLogDao
import com.sitediary.mobile.testdoubles.FakeSiteLogPhotoDao
import io.mockk.every
import io.mockk.mockk
import kotlinx.coroutines.test.runTest
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Before
import org.junit.Rule
import org.junit.Test
import org.junit.rules.TemporaryFolder
import java.time.Clock
import java.time.Instant
import java.time.ZoneOffset

class MediaRetentionTest {

    @Rule
    @JvmField
    val tempFolder = TemporaryFolder()

    private lateinit var permitDao: FakePermitDao
    private lateinit var photoDao: FakeSiteLogPhotoDao
    private lateinit var logDao: FakeSiteLogDao
    private lateinit var fileManager: LocalMediaFileManager

    private val now = Instant.parse("2026-11-14T12:00:00Z")
    private val clock = Clock.fixed(now, ZoneOffset.UTC)

    @Before
    fun setUp() {
        permitDao = FakePermitDao()
        photoDao = FakeSiteLogPhotoDao()
        logDao = FakeSiteLogDao(photoDao)

        val filesDir = tempFolder.newFolder("files")
        val cacheDir = tempFolder.newFolder("cache")
        val mockContext = mockk<Context> {
            every { this@mockk.filesDir } returns filesDir
            every { this@mockk.cacheDir } returns cacheDir
        }
        fileManager = LocalMediaFileManager(mockContext)
    }

    @Test
    fun `purges local media ONLY when UPLOADED and strictly older than 7 days`() = runTest {
        val sevenDaysMs = 7L * 24L * 60L * 60L * 1000L

        // 1. Uploaded 7 days + 1 minute ago -> ELIGIBLE for purge
        val oldAudio = fileManager.createAudioFile("pr1", "log-old").apply { writeText("old-audio") }
        val oldPhoto = fileManager.createPhotoFile("pr1", "ph-old").apply { writeText("old-photo") }
        val oldPermitDoc = fileManager.createPermitDocumentFile("pr1", "pm-old").apply { writeText("old-doc") }

        // 2. Uploaded exactly 7 days ago -> MUST NOT purge (boundary: > 7 days)
        val boundaryAudio = fileManager.createAudioFile("pr1", "log-boundary").apply { writeText("boundary") }

        // 3. Uploaded 6 days ago -> MUST NOT purge
        val recentPhoto = fileManager.createPhotoFile("pr1", "ph-recent").apply { writeText("recent") }

        // 4. Older than 10 days but STILL PENDING -> NEVER purge!
        val pendingAudio = fileManager.createAudioFile("pr1", "log-pending").apply { writeText("pending") }

        logDao.upsertAll(
            listOf(
                SiteLogEntity(
                    id = "log-old",
                    projectId = "pr1",
                    authorId = "u1",
                    logDate = "2026-11-01",
                    recordedAt = "2026-11-01T10:00:00Z",
                    audioUploadStatus = "UPLOADED",
                    audioLocalPath = oldAudio.absolutePath,
                    audioUploadedAtEpochMs = now.toEpochMilli() - sevenDaysMs - 60_000L,
                    clientUpdatedAt = "2026-11-01T10:00:00Z",
                    createdAt = "2026-11-01T10:00:00Z",
                    updatedAt = "2026-11-01T10:00:00Z"
                ),
                SiteLogEntity(
                    id = "log-boundary",
                    projectId = "pr1",
                    authorId = "u1",
                    logDate = "2026-11-07",
                    recordedAt = "2026-11-07T12:00:00Z",
                    audioUploadStatus = "UPLOADED",
                    audioLocalPath = boundaryAudio.absolutePath,
                    audioUploadedAtEpochMs = now.toEpochMilli() - sevenDaysMs,
                    clientUpdatedAt = "2026-11-07T12:00:00Z",
                    createdAt = "2026-11-07T12:00:00Z",
                    updatedAt = "2026-11-07T12:00:00Z"
                ),
                SiteLogEntity(
                    id = "log-pending",
                    projectId = "pr1",
                    authorId = "u1",
                    logDate = "2026-11-01",
                    recordedAt = "2026-11-01T10:00:00Z",
                    audioUploadStatus = "PENDING",
                    audioLocalPath = pendingAudio.absolutePath,
                    audioUploadedAtEpochMs = null,
                    clientUpdatedAt = "2026-11-01T10:00:00Z",
                    createdAt = "2026-11-01T10:00:00Z",
                    updatedAt = "2026-11-01T10:00:00Z"
                )
            )
        )

        photoDao.upsertAll(
            listOf(
                SiteLogPhotoEntity(
                    id = "ph-old",
                    siteLogId = "log-old",
                    projectId = "pr1",
                    uploadStatus = "UPLOADED",
                    localPath = oldPhoto.absolutePath,
                    uploadedAtEpochMs = now.toEpochMilli() - sevenDaysMs - 1_000L,
                    createdAt = "2026-11-01T10:00:00Z",
                    updatedAt = "2026-11-01T10:00:00Z"
                ),
                SiteLogPhotoEntity(
                    id = "ph-recent",
                    siteLogId = "log-boundary",
                    projectId = "pr1",
                    uploadStatus = "UPLOADED",
                    localPath = recentPhoto.absolutePath,
                    uploadedAtEpochMs = now.toEpochMilli() - (6L * 24L * 60L * 60L * 1000L),
                    createdAt = "2026-11-08T10:00:00Z",
                    updatedAt = "2026-11-08T10:00:00Z"
                )
            )
        )

        permitDao.upsert(
            PermitEntity(
                id = "pm-old",
                projectId = "pr1",
                permitName = "NOC",
                authority = "LDA",
                expiryDate = "2027-01-01",
                createdBy = "u1",
                clientUpdatedAt = "2026-11-01T10:00:00Z",
                createdAt = "2026-11-01T10:00:00Z",
                updatedAt = "2026-11-01T10:00:00Z",
                documentLocalPath = oldPermitDoc.absolutePath,
                documentUploadStatus = "UPLOADED",
                documentUploadedAtEpochMs = now.toEpochMilli() - sevenDaysMs - 5_000L
            )
        )

        val sweeper = MediaRetentionSweeper(
            siteLogDao = logDao,
            siteLogPhotoDao = photoDao,
            permitDao = permitDao,
            mediaFileManager = fileManager,
            clock = clock
        )

        val deletedCount = sweeper.purgeExpiredLocalMedia()
        assertEquals(3, deletedCount)

        // Old uploaded files deleted & paths cleared
        assertFalse(oldAudio.exists())
        assertNull(logDao.getById("log-old")!!.audioLocalPath)

        assertFalse(oldPhoto.exists())
        assertNull(photoDao.getById("ph-old")!!.localPath)

        assertFalse(oldPermitDoc.exists())
        assertNull(permitDao.getById("pm-old")!!.documentLocalPath)

        // Protected files remain intact
        assertTrue(boundaryAudio.exists())
        assertNotNull(logDao.getById("log-boundary")!!.audioLocalPath)

        assertTrue(recentPhoto.exists())
        assertNotNull(photoDao.getById("ph-recent")!!.localPath)

        assertTrue(pendingAudio.exists())
        assertNotNull(logDao.getById("log-pending")!!.audioLocalPath)
    }
}

package com.sitediary.mobile.data.sync

import com.sitediary.mobile.data.local.dao.PermitDao
import com.sitediary.mobile.data.local.dao.SiteLogDao
import com.sitediary.mobile.data.local.dao.SiteLogPhotoDao
import com.sitediary.mobile.data.media.LocalMediaFileManager
import java.time.Clock
import javax.inject.Inject
import javax.inject.Singleton

/**
 * Purges local media files ONLY when:
 * 1) upload status is confirmed `UPLOADED`
 * 2) `uploadedAtEpochMs` is strictly older than 7 days (`now - uploadedAt > 7 days`).
 */
@Singleton
class MediaRetentionSweeper @Inject constructor(
    private val siteLogDao: SiteLogDao,
    private val siteLogPhotoDao: SiteLogPhotoDao,
    private val permitDao: PermitDao,
    private val mediaFileManager: LocalMediaFileManager,
    private val clock: Clock
) {

    suspend fun purgeExpiredLocalMedia(): Int {
        val now = clock.millis()
        val cutoff = now - LocalMediaFileManager.RETENTION_MILLIS
        var deletedCount = 0

        val logs = siteLogDao.getAudioEligibleForPurge(cutoff)
        for (log in logs) {
            val uploadedAt = log.audioUploadedAtEpochMs ?: continue
            if (log.audioUploadStatus == "UPLOADED" &&
                LocalMediaFileManager.isOlderThanRetentionWindow(uploadedAt, now)
            ) {
                mediaFileManager.deleteFileIfExists(log.audioLocalPath)
                siteLogDao.clearAudioLocalPath(log.id)
                deletedCount++
            }
        }

        val photos = siteLogPhotoDao.getEligibleForPurge(cutoff)
        for (photo in photos) {
            val uploadedAt = photo.uploadedAtEpochMs ?: continue
            if (photo.uploadStatus == "UPLOADED" &&
                LocalMediaFileManager.isOlderThanRetentionWindow(uploadedAt, now)
            ) {
                mediaFileManager.deleteFileIfExists(photo.localPath)
                siteLogPhotoDao.clearLocalPath(photo.id)
                deletedCount++
            }
        }

        val permits = permitDao.getDocumentsEligibleForPurge(cutoff)
        for (permit in permits) {
            val uploadedAt = permit.documentUploadedAtEpochMs ?: continue
            if (permit.documentUploadStatus == "UPLOADED" &&
                LocalMediaFileManager.isOlderThanRetentionWindow(uploadedAt, now)
            ) {
                mediaFileManager.deleteFileIfExists(permit.documentLocalPath)
                permitDao.clearDocumentLocalPath(permit.id)
                deletedCount++
            }
        }

        return deletedCount
    }
}

package com.sitediary.mobile.data.local.dao

import androidx.room.Dao
import androidx.room.Insert
import androidx.room.OnConflictStrategy
import androidx.room.Query
import com.sitediary.mobile.data.local.entity.SiteLogPhotoEntity
import kotlinx.coroutines.flow.Flow

@Dao
interface SiteLogPhotoDao {
    @Query("SELECT * FROM site_log_photos WHERE id = :id")
    suspend fun getById(id: String): SiteLogPhotoEntity?

    /**
     * Only push photos that have received their canonical `storage_uri` from `/v1/media/upload-url`.
     */
    @Query("SELECT * FROM site_log_photos WHERE sync_dirty = 1 AND storage_uri != '' LIMIT :limit")
    suspend fun getDirtyPushableBatch(limit: Int): List<SiteLogPhotoEntity>

    @Query("SELECT COUNT(*) FROM site_log_photos WHERE sync_dirty = 1 OR (upload_status = 'PENDING' AND deleted_at IS NULL)")
    fun observePendingCount(): Flow<Int>

    @Query(
        """
        SELECT * FROM site_log_photos
        WHERE deleted_at IS NULL
          AND local_path IS NOT NULL
          AND upload_status = 'PENDING'
        """
    )
    suspend fun getPendingUploads(): List<SiteLogPhotoEntity>

    @Query(
        """
        SELECT * FROM site_log_photos
        WHERE local_path IS NOT NULL
          AND upload_status = 'UPLOADED'
          AND uploaded_at_epoch_ms IS NOT NULL
          AND uploaded_at_epoch_ms < :cutoffEpochMs
        """
    )
    suspend fun getEligibleForPurge(cutoffEpochMs: Long): List<SiteLogPhotoEntity>

    @Query("SELECT local_path FROM site_log_photos WHERE project_id = :projectId AND local_path IS NOT NULL")
    suspend fun getLocalPathsForProject(projectId: String): List<String>

    @Insert(onConflict = OnConflictStrategy.REPLACE)
    suspend fun upsertAll(photos: List<SiteLogPhotoEntity>)

    @Query(
        """
        UPDATE site_log_photos
        SET sync_dirty = CASE WHEN local_mutation_seq = :expectedSeq THEN 0 ELSE 1 END,
            server_version = CASE WHEN local_mutation_seq = :expectedSeq THEN :serverVersion ELSE server_version END,
            sync_error = CASE WHEN local_mutation_seq = :expectedSeq THEN NULL ELSE sync_error END
        WHERE id = :id
        """
    )
    suspend fun markSyncedIfSeqMatches(id: String, expectedSeq: Long, serverVersion: Long)

    @Query(
        """
        UPDATE site_log_photos
        SET sync_dirty = CASE WHEN local_mutation_seq = :expectedSeq THEN 0 ELSE 1 END,
            sync_error = CASE WHEN local_mutation_seq = :expectedSeq THEN :error ELSE sync_error END
        WHERE id = :id
        """
    )
    suspend fun markSyncRejectedIfSeqMatches(id: String, expectedSeq: Long, error: String)

    @Query(
        """
        UPDATE site_log_photos
        SET sync_dirty = 1,
            sync_error = CASE WHEN local_mutation_seq = :expectedSeq THEN :error ELSE sync_error END
        WHERE id = :id
        """
    )
    suspend fun markSyncConflictIfSeqMatches(id: String, expectedSeq: Long, error: String)

    @Query(
        """
        UPDATE site_log_photos
        SET storage_uri = :storageUri,
            sync_dirty = 1,
            local_mutation_seq = local_mutation_seq + 1
        WHERE id = :id
        """
    )
    suspend fun setStorageUriAndMarkDirty(id: String, storageUri: String)

    @Query(
        """
        UPDATE site_log_photos
        SET upload_status = 'UPLOADED',
            uploaded_at_epoch_ms = :uploadedAtEpochMs
        WHERE id = :id
        """
    )
    suspend fun markUploaded(id: String, uploadedAtEpochMs: Long)

    @Query("UPDATE site_log_photos SET local_path = NULL WHERE id = :id")
    suspend fun clearLocalPath(id: String)

    @Query("DELETE FROM site_log_photos WHERE id = :id")
    suspend fun deleteById(id: String)

    @Query("DELETE FROM site_log_photos WHERE project_id = :projectId")
    suspend fun deleteByProjectId(projectId: String)

    @Query("DELETE FROM site_log_photos")
    suspend fun deleteAll()
}

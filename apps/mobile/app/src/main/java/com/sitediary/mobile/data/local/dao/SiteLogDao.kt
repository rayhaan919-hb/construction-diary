package com.sitediary.mobile.data.local.dao

import androidx.room.Dao
import androidx.room.Embedded
import androidx.room.Insert
import androidx.room.OnConflictStrategy
import androidx.room.Query
import androidx.room.Relation
import androidx.room.Transaction
import com.sitediary.mobile.data.local.entity.SiteLogEntity
import com.sitediary.mobile.data.local.entity.SiteLogPhotoEntity
import kotlinx.coroutines.flow.Flow

data class SiteLogWithPhotos(
    @Embedded val log: SiteLogEntity,
    @Relation(
        parentColumn = "id",
        entityColumn = "site_log_id"
    )
    val photos: List<SiteLogPhotoEntity>
)

@Dao
interface SiteLogDao {
    @Transaction
    @Query(
        """
        SELECT * FROM site_logs
        WHERE project_id = :projectId AND deleted_at IS NULL
        ORDER BY log_date DESC, recorded_at DESC
        """
    )
    fun observeLogsWithPhotosByProject(projectId: String): Flow<List<SiteLogWithPhotos>>

    @Transaction
    @Query("SELECT * FROM site_logs WHERE id = :logId AND deleted_at IS NULL")
    fun observeLogWithPhotos(logId: String): Flow<SiteLogWithPhotos?>

    @Query("SELECT * FROM site_logs WHERE deleted_at IS NULL")
    fun observeAllActive(): Flow<List<SiteLogEntity>>

    @Query("SELECT * FROM site_logs WHERE id = :id")
    suspend fun getById(id: String): SiteLogEntity?

    @Query("SELECT * FROM site_logs WHERE sync_dirty = 1 LIMIT :limit")
    suspend fun getDirtyBatch(limit: Int): List<SiteLogEntity>

    @Query("SELECT COUNT(*) FROM site_logs WHERE sync_dirty = 1")
    fun observeDirtyCount(): Flow<Int>

    @Query(
        """
        SELECT * FROM site_logs
        WHERE deleted_at IS NULL
          AND audio_local_path IS NOT NULL
          AND audio_upload_status = 'PENDING'
        """
    )
    suspend fun getPendingAudioUploads(): List<SiteLogEntity>

    @Query(
        """
        SELECT * FROM site_logs
        WHERE audio_local_path IS NOT NULL
          AND audio_upload_status = 'UPLOADED'
          AND audio_uploaded_at_epoch_ms IS NOT NULL
          AND audio_uploaded_at_epoch_ms < :cutoffEpochMs
        """
    )
    suspend fun getAudioEligibleForPurge(cutoffEpochMs: Long): List<SiteLogEntity>

    @Query("SELECT audio_local_path FROM site_logs WHERE project_id = :projectId AND audio_local_path IS NOT NULL")
    suspend fun getLocalAudioPathsForProject(projectId: String): List<String>

    @Insert(onConflict = OnConflictStrategy.REPLACE)
    suspend fun upsert(log: SiteLogEntity)

    @Insert(onConflict = OnConflictStrategy.REPLACE)
    suspend fun upsertAll(logs: List<SiteLogEntity>)

    @Query(
        """
        UPDATE site_logs
        SET sync_dirty = CASE WHEN local_mutation_seq = :expectedSeq THEN 0 ELSE 1 END,
            server_version = CASE WHEN local_mutation_seq = :expectedSeq THEN :serverVersion ELSE server_version END,
            sync_error = CASE WHEN local_mutation_seq = :expectedSeq THEN NULL ELSE sync_error END
        WHERE id = :id
        """
    )
    suspend fun markSyncedIfSeqMatches(id: String, expectedSeq: Long, serverVersion: Long)

    @Query(
        """
        UPDATE site_logs
        SET sync_dirty = CASE WHEN local_mutation_seq = :expectedSeq THEN 0 ELSE 1 END,
            sync_error = CASE WHEN local_mutation_seq = :expectedSeq THEN :error ELSE sync_error END
        WHERE id = :id
        """
    )
    suspend fun markSyncRejectedIfSeqMatches(id: String, expectedSeq: Long, error: String)

    @Query(
        """
        UPDATE site_logs
        SET audio_uri = :storageUri,
            sync_dirty = 1,
            local_mutation_seq = local_mutation_seq + 1
        WHERE id = :id
        """
    )
    suspend fun setAudioStorageUriAndMarkDirty(id: String, storageUri: String)

    @Query(
        """
        UPDATE site_logs
        SET audio_upload_status = 'UPLOADED',
            audio_uploaded_at_epoch_ms = :uploadedAtEpochMs,
            extraction_status = CASE WHEN extraction_status = 'DONE' THEN 'DONE' ELSE 'PENDING' END
        WHERE id = :id
        """
    )
    suspend fun markAudioUploaded(id: String, uploadedAtEpochMs: Long)

    @Query("UPDATE site_logs SET extraction_status = :status WHERE id = :id")
    suspend fun updateExtractionStatus(id: String, status: String)

    @Query("UPDATE site_logs SET audio_local_path = NULL WHERE id = :id")
    suspend fun clearAudioLocalPath(id: String)

    @Query("DELETE FROM site_logs WHERE project_id = :projectId")
    suspend fun deleteByProjectId(projectId: String)

    @Query("DELETE FROM site_logs")
    suspend fun deleteAll()
}

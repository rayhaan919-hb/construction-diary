package com.sitediary.mobile.data.local.dao

import androidx.room.Dao
import androidx.room.Insert
import androidx.room.OnConflictStrategy
import androidx.room.Query
import com.sitediary.mobile.data.local.entity.PermitEntity
import kotlinx.coroutines.flow.Flow

@Dao
interface PermitDao {
    @Query("SELECT * FROM permits WHERE project_id = :projectId AND deleted_at IS NULL ORDER BY expiry_date ASC")
    fun observeByProject(projectId: String): Flow<List<PermitEntity>>

    @Query("SELECT * FROM permits WHERE deleted_at IS NULL")
    fun observeAllActive(): Flow<List<PermitEntity>>

    @Query("SELECT * FROM permits WHERE id = :id")
    suspend fun getById(id: String): PermitEntity?

    @Query("SELECT * FROM permits WHERE sync_dirty = 1 LIMIT :limit")
    suspend fun getDirtyBatch(limit: Int): List<PermitEntity>

    @Query("SELECT COUNT(*) FROM permits WHERE sync_dirty = 1")
    fun observeDirtyCount(): Flow<Int>

    @Query(
        """
        SELECT * FROM permits
        WHERE deleted_at IS NULL
          AND document_local_path IS NOT NULL
          AND document_upload_status = 'PENDING'
        """
    )
    suspend fun getPendingDocumentUploads(): List<PermitEntity>

    @Query(
        """
        SELECT * FROM permits
        WHERE document_local_path IS NOT NULL
          AND document_upload_status = 'UPLOADED'
          AND document_uploaded_at_epoch_ms IS NOT NULL
          AND document_uploaded_at_epoch_ms < :cutoffEpochMs
        """
    )
    suspend fun getDocumentsEligibleForPurge(cutoffEpochMs: Long): List<PermitEntity>

    @Query("SELECT document_local_path FROM permits WHERE project_id = :projectId AND document_local_path IS NOT NULL")
    suspend fun getLocalPathsForProject(projectId: String): List<String>

    @Insert(onConflict = OnConflictStrategy.REPLACE)
    suspend fun upsert(permit: PermitEntity)

    @Insert(onConflict = OnConflictStrategy.REPLACE)
    suspend fun upsertAll(permits: List<PermitEntity>)

    @Query(
        """
        UPDATE permits
        SET sync_dirty = CASE WHEN local_mutation_seq = :expectedSeq THEN 0 ELSE 1 END,
            server_version = CASE WHEN local_mutation_seq = :expectedSeq THEN :serverVersion ELSE server_version END,
            sync_error = CASE WHEN local_mutation_seq = :expectedSeq THEN NULL ELSE sync_error END
        WHERE id = :id
        """
    )
    suspend fun markSyncedIfSeqMatches(id: String, expectedSeq: Long, serverVersion: Long)

    @Query(
        """
        UPDATE permits
        SET sync_dirty = CASE WHEN local_mutation_seq = :expectedSeq THEN 0 ELSE 1 END,
            sync_error = CASE WHEN local_mutation_seq = :expectedSeq THEN :error ELSE sync_error END
        WHERE id = :id
        """
    )
    suspend fun markSyncRejectedIfSeqMatches(id: String, expectedSeq: Long, error: String)

    @Query(
        """
        UPDATE permits
        SET document_photo_uri = :storageUri,
            sync_dirty = 1,
            local_mutation_seq = local_mutation_seq + 1
        WHERE id = :id
        """
    )
    suspend fun setDocumentStorageUriAndMarkDirty(id: String, storageUri: String)

    @Query(
        """
        UPDATE permits
        SET document_upload_status = 'UPLOADED',
            document_uploaded_at_epoch_ms = :uploadedAtEpochMs
        WHERE id = :id
        """
    )
    suspend fun markDocumentUploaded(id: String, uploadedAtEpochMs: Long)

    @Query("UPDATE permits SET document_local_path = NULL WHERE id = :id")
    suspend fun clearDocumentLocalPath(id: String)

    @Query("DELETE FROM permits WHERE project_id = :projectId")
    suspend fun deleteByProjectId(projectId: String)

    @Query("DELETE FROM permits")
    suspend fun deleteAll()
}

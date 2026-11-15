package com.sitediary.mobile.data.local.entity

import androidx.room.ColumnInfo
import androidx.room.Entity
import androidx.room.Index
import androidx.room.PrimaryKey
import com.sitediary.mobile.data.remote.dto.StructuredSummaryDto

@Entity(
    tableName = "site_logs",
    indices = [
        Index(value = ["project_id", "log_date"]),
        Index(value = ["sync_dirty"])
    ]
)
data class SiteLogEntity(
    @PrimaryKey
    val id: String,
    @ColumnInfo(name = "project_id")
    val projectId: String,
    @ColumnInfo(name = "author_id")
    val authorId: String,
    @ColumnInfo(name = "author_name")
    val authorName: String? = null,
    @ColumnInfo(name = "log_date")
    val logDate: String,
    @ColumnInfo(name = "recorded_at")
    val recordedAt: String,
    val notes: String? = null,
    @ColumnInfo(name = "audio_uri")
    val audioUri: String? = null,
    @ColumnInfo(name = "audio_url")
    val audioUrl: String? = null,
    @ColumnInfo(name = "audio_duration_ms")
    val audioDurationMs: Int? = null,
    @ColumnInfo(name = "audio_upload_status")
    val audioUploadStatus: String = "NONE",
    @ColumnInfo(name = "extraction_status")
    val extractionStatus: String = "NOT_STARTED",
    @ColumnInfo(name = "extraction_attempts")
    val extractionAttempts: Int = 0,
    @ColumnInfo(name = "extraction_error")
    val extractionError: String? = null,
    @ColumnInfo(name = "extraction_model")
    val extractionModel: String? = null,
    @ColumnInfo(name = "extracted_at")
    val extractedAt: String? = null,
    val transcript: String? = null,
    @ColumnInfo(name = "detected_language")
    val detectedLanguage: String? = null,
    @ColumnInfo(name = "structured_summary")
    val structuredSummary: StructuredSummaryDto? = null,
    @ColumnInfo(name = "edited_by_human")
    val editedByHuman: Boolean = false,
    @ColumnInfo(name = "client_updated_at")
    val clientUpdatedAt: String,
    @ColumnInfo(name = "created_at")
    val createdAt: String,
    @ColumnInfo(name = "updated_at")
    val updatedAt: String,
    @ColumnInfo(name = "deleted_at")
    val deletedAt: String? = null,
    @ColumnInfo(name = "server_version")
    val serverVersion: Long = 0L,
    // Local-only media & sync tracking
    @ColumnInfo(name = "audio_local_path")
    val audioLocalPath: String? = null,
    @ColumnInfo(name = "audio_uploaded_at_epoch_ms")
    val audioUploadedAtEpochMs: Long? = null,
    @ColumnInfo(name = "sync_dirty")
    val syncDirty: Boolean = false,
    @ColumnInfo(name = "local_mutation_seq")
    val localMutationSeq: Long = 0L,
    @ColumnInfo(name = "sync_error")
    val syncError: String? = null
)

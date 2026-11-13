package com.sitediary.mobile.data.local.entity

import androidx.room.ColumnInfo
import androidx.room.Entity
import androidx.room.Index
import androidx.room.PrimaryKey

@Entity(
    tableName = "permits",
    indices = [
        Index(value = ["project_id"]),
        Index(value = ["expiry_date"])
    ]
)
data class PermitEntity(
    @PrimaryKey
    val id: String,
    @ColumnInfo(name = "project_id")
    val projectId: String,
    @ColumnInfo(name = "permit_name")
    val permitName: String,
    val authority: String,
    @ColumnInfo(name = "permit_number")
    val permitNumber: String? = null,
    @ColumnInfo(name = "issue_date")
    val issueDate: String? = null,
    @ColumnInfo(name = "expiry_date")
    val expiryDate: String,
    @ColumnInfo(name = "document_photo_uri")
    val documentPhotoUri: String? = null,
    @ColumnInfo(name = "document_photo_url")
    val documentPhotoUrl: String? = null,
    @ColumnInfo(name = "created_by")
    val createdBy: String,
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
    @ColumnInfo(name = "document_local_path")
    val documentLocalPath: String? = null,
    @ColumnInfo(name = "document_upload_status")
    val documentUploadStatus: String = "NONE",
    @ColumnInfo(name = "document_uploaded_at_epoch_ms")
    val documentUploadedAtEpochMs: Long? = null,
    @ColumnInfo(name = "sync_dirty")
    val syncDirty: Boolean = false,
    @ColumnInfo(name = "local_mutation_seq")
    val localMutationSeq: Long = 0L,
    @ColumnInfo(name = "sync_error")
    val syncError: String? = null
)

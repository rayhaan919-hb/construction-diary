package com.sitediary.mobile.data.local.entity

import androidx.room.ColumnInfo
import androidx.room.Entity
import androidx.room.Index
import androidx.room.PrimaryKey

@Entity(
    tableName = "site_log_photos",
    indices = [
        Index(value = ["site_log_id"]),
        Index(value = ["project_id"])
    ]
)
data class SiteLogPhotoEntity(
    @PrimaryKey
    val id: String,
    @ColumnInfo(name = "site_log_id")
    val siteLogId: String,
    @ColumnInfo(name = "project_id")
    val projectId: String,
    @ColumnInfo(name = "storage_uri")
    val storageUri: String = "",
    @ColumnInfo(name = "upload_status")
    val uploadStatus: String = "PENDING",
    @ColumnInfo(name = "remote_url")
    val remoteUrl: String? = null,
    val width: Int? = null,
    val height: Int? = null,
    @ColumnInfo(name = "byte_size")
    val byteSize: Int? = null,
    @ColumnInfo(name = "taken_at")
    val takenAt: String? = null,
    @ColumnInfo(name = "sort_order")
    val sortOrder: Int = 0,
    @ColumnInfo(name = "created_at")
    val createdAt: String,
    @ColumnInfo(name = "updated_at")
    val updatedAt: String,
    @ColumnInfo(name = "deleted_at")
    val deletedAt: String? = null,
    @ColumnInfo(name = "server_version")
    val serverVersion: Long = 0L,
    // Local-only media & sync tracking
    @ColumnInfo(name = "local_path")
    val localPath: String? = null,
    @ColumnInfo(name = "uploaded_at_epoch_ms")
    val uploadedAtEpochMs: Long? = null,
    @ColumnInfo(name = "sync_dirty")
    val syncDirty: Boolean = false,
    @ColumnInfo(name = "local_mutation_seq")
    val localMutationSeq: Long = 0L,
    @ColumnInfo(name = "sync_error")
    val syncError: String? = null
)

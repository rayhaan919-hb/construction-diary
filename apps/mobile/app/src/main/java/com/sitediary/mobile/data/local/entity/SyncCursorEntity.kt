package com.sitediary.mobile.data.local.entity

import androidx.room.ColumnInfo
import androidx.room.Entity
import androidx.room.PrimaryKey

@Entity(tableName = "sync_cursors")
data class SyncCursorEntity(
    @PrimaryKey
    @ColumnInfo(name = "scope_key")
    val scopeKey: String,
    val cursor: Long,
    @ColumnInfo(name = "updated_at_epoch_ms")
    val updatedAtEpochMs: Long
)

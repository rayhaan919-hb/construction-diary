package com.sitediary.mobile.data.local.entity

import androidx.room.ColumnInfo
import androidx.room.Entity
import androidx.room.Index

@Entity(
    tableName = "project_members",
    primaryKeys = ["project_id", "user_id"],
    indices = [Index(value = ["user_id"])]
)
data class ProjectMemberEntity(
    @ColumnInfo(name = "project_id")
    val projectId: String,
    @ColumnInfo(name = "user_id")
    val userId: String,
    val role: String,
    @ColumnInfo(name = "full_name")
    val fullName: String,
    val email: String,
    @ColumnInfo(name = "deleted_at")
    val deletedAt: String? = null,
    @ColumnInfo(name = "server_version")
    val serverVersion: Long
)

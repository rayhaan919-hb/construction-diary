package com.sitediary.mobile.data.local.entity

import androidx.room.ColumnInfo
import androidx.room.Entity
import androidx.room.PrimaryKey

@Entity(tableName = "projects")
data class ProjectEntity(
    @PrimaryKey
    val id: String,
    val name: String,
    @ColumnInfo(name = "site_address")
    val siteAddress: String,
    @ColumnInfo(name = "owner_phone")
    val ownerPhone: String? = null,
    val timezone: String,
    @ColumnInfo(name = "allow_photo_gps")
    val allowPhotoGps: Boolean,
    @ColumnInfo(name = "created_at")
    val createdAt: String,
    @ColumnInfo(name = "updated_at")
    val updatedAt: String,
    @ColumnInfo(name = "deleted_at")
    val deletedAt: String? = null,
    @ColumnInfo(name = "server_version")
    val serverVersion: Long
)

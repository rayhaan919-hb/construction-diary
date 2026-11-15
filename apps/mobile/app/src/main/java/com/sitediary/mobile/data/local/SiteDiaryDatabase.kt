package com.sitediary.mobile.data.local

import androidx.room.Database
import androidx.room.RoomDatabase
import androidx.room.TypeConverters
import androidx.room.migration.Migration
import androidx.sqlite.db.SupportSQLiteDatabase
import com.sitediary.mobile.data.local.dao.PermitDao
import com.sitediary.mobile.data.local.dao.ProjectDao
import com.sitediary.mobile.data.local.dao.ProjectMemberDao
import com.sitediary.mobile.data.local.dao.SiteLogDao
import com.sitediary.mobile.data.local.dao.SiteLogPhotoDao
import com.sitediary.mobile.data.local.dao.SyncCursorDao
import com.sitediary.mobile.data.local.entity.PermitEntity
import com.sitediary.mobile.data.local.entity.ProjectEntity
import com.sitediary.mobile.data.local.entity.ProjectMemberEntity
import com.sitediary.mobile.data.local.entity.SiteLogEntity
import com.sitediary.mobile.data.local.entity.SiteLogPhotoEntity
import com.sitediary.mobile.data.local.entity.SyncCursorEntity

@Database(
    entities = [
        ProjectEntity::class,
        ProjectMemberEntity::class,
        PermitEntity::class,
        SiteLogEntity::class,
        SiteLogPhotoEntity::class,
        SyncCursorEntity::class
    ],
    version = 2,
    exportSchema = true
)
@TypeConverters(Converters::class)
abstract class SiteDiaryDatabase : RoomDatabase() {
    abstract fun projectDao(): ProjectDao
    abstract fun projectMemberDao(): ProjectMemberDao
    abstract fun permitDao(): PermitDao
    abstract fun siteLogDao(): SiteLogDao
    abstract fun siteLogPhotoDao(): SiteLogPhotoDao
    abstract fun syncCursorDao(): SyncCursorDao

    companion object {
        val MIGRATION_1_2: Migration = object : Migration(1, 2) {
            override fun migrate(db: SupportSQLiteDatabase) {
                db.execSQL("ALTER TABLE site_logs ADD COLUMN audio_url TEXT")
            }
        }
    }
}

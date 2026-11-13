package com.sitediary.mobile.di

import android.content.Context
import androidx.room.Room
import com.sitediary.mobile.data.local.SiteDiaryDatabase
import com.sitediary.mobile.data.local.dao.PermitDao
import com.sitediary.mobile.data.local.dao.ProjectDao
import com.sitediary.mobile.data.local.dao.ProjectMemberDao
import com.sitediary.mobile.data.local.dao.SiteLogDao
import com.sitediary.mobile.data.local.dao.SiteLogPhotoDao
import com.sitediary.mobile.data.local.dao.SyncCursorDao
import dagger.Module
import dagger.Provides
import dagger.hilt.InstallIn
import dagger.hilt.android.qualifiers.ApplicationContext
import dagger.hilt.components.SingletonComponent
import javax.inject.Singleton

@Module
@InstallIn(SingletonComponent::class)
object DatabaseModule {

    @Provides
    @Singleton
    fun provideDatabase(@ApplicationContext context: Context): SiteDiaryDatabase {
        return Room.databaseBuilder(
            context,
            SiteDiaryDatabase::class.java,
            "site_diary.db"
        ).fallbackToDestructiveMigration(dropAllTables = true).build()
    }

    @Provides
    fun provideProjectDao(db: SiteDiaryDatabase): ProjectDao = db.projectDao()

    @Provides
    fun provideProjectMemberDao(db: SiteDiaryDatabase): ProjectMemberDao = db.projectMemberDao()

    @Provides
    fun providePermitDao(db: SiteDiaryDatabase): PermitDao = db.permitDao()

    @Provides
    fun provideSiteLogDao(db: SiteDiaryDatabase): SiteLogDao = db.siteLogDao()

    @Provides
    fun provideSiteLogPhotoDao(db: SiteDiaryDatabase): SiteLogPhotoDao = db.siteLogPhotoDao()

    @Provides
    fun provideSyncCursorDao(db: SiteDiaryDatabase): SyncCursorDao = db.syncCursorDao()
}

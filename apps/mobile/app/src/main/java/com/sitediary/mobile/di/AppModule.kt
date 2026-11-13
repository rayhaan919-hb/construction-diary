package com.sitediary.mobile.di

import androidx.room.withTransaction
import com.sitediary.mobile.data.local.SiteDiaryDatabase
import com.sitediary.mobile.data.local.dao.PermitDao
import com.sitediary.mobile.data.local.dao.ProjectDao
import com.sitediary.mobile.data.local.dao.ProjectMemberDao
import com.sitediary.mobile.data.local.dao.SiteLogDao
import com.sitediary.mobile.data.local.dao.SiteLogPhotoDao
import com.sitediary.mobile.data.local.dao.SyncCursorDao
import com.sitediary.mobile.data.media.LocalMediaFileManager
import com.sitediary.mobile.data.prefs.AppPreferences
import com.sitediary.mobile.data.remote.SiteDiaryApi
import com.sitediary.mobile.data.sync.SyncEngine
import dagger.Module
import dagger.Provides
import dagger.hilt.InstallIn
import dagger.hilt.components.SingletonComponent
import java.time.Clock
import javax.inject.Singleton

@Module
@InstallIn(SingletonComponent::class)
object AppModule {

    @Provides
    @Singleton
    fun provideClock(): Clock = Clock.systemUTC()

    @Provides
    @Singleton
    fun provideSyncEngine(
        api: SiteDiaryApi,
        database: SiteDiaryDatabase,
        projectDao: ProjectDao,
        projectMemberDao: ProjectMemberDao,
        permitDao: PermitDao,
        siteLogDao: SiteLogDao,
        siteLogPhotoDao: SiteLogPhotoDao,
        syncCursorDao: SyncCursorDao,
        mediaFileManager: LocalMediaFileManager,
        appPreferences: AppPreferences,
        clock: Clock
    ): SyncEngine {
        return SyncEngine(
            api = api,
            projectDao = projectDao,
            projectMemberDao = projectMemberDao,
            permitDao = permitDao,
            siteLogDao = siteLogDao,
            siteLogPhotoDao = siteLogPhotoDao,
            syncCursorDao = syncCursorDao,
            mediaFileManager = mediaFileManager,
            currentUserIdProvider = { appPreferences.getCurrentUser()?.id },
            clock = clock,
            runInTransaction = { block -> database.withTransaction { block() } }
        )
    }
}

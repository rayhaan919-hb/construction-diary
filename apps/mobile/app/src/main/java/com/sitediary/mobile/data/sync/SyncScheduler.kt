package com.sitediary.mobile.data.sync

import android.content.Context
import androidx.work.BackoffPolicy
import androidx.work.Constraints
import androidx.work.ExistingPeriodicWorkPolicy
import androidx.work.ExistingWorkPolicy
import androidx.work.NetworkType
import androidx.work.OneTimeWorkRequestBuilder
import androidx.work.PeriodicWorkRequestBuilder
import androidx.work.WorkManager
import dagger.hilt.android.qualifiers.ApplicationContext
import java.util.concurrent.TimeUnit
import javax.inject.Inject
import javax.inject.Singleton

@Singleton
class SyncScheduler @Inject constructor(
    @ApplicationContext private val context: Context
) {
    private val workManager: WorkManager by lazy { WorkManager.getInstance(context) }

    fun scheduleImmediateSync(uploadOnMobileData: Boolean) {
        val syncConstraints = Constraints.Builder()
            .setRequiredNetworkType(NetworkType.CONNECTED)
            .build()

        val syncRequest = OneTimeWorkRequestBuilder<SyncWorker>()
            .setConstraints(syncConstraints)
            .setBackoffCriteria(BackoffPolicy.EXPONENTIAL, 15, TimeUnit.SECONDS)
            .build()

        val mediaNetworkType = if (uploadOnMobileData) {
            NetworkType.CONNECTED
        } else {
            NetworkType.UNMETERED
        }
        val mediaConstraints = Constraints.Builder()
            .setRequiredNetworkType(mediaNetworkType)
            .build()

        val mediaRequest = OneTimeWorkRequestBuilder<MediaUploadWorker>()
            .setConstraints(mediaConstraints)
            .setBackoffCriteria(BackoffPolicy.EXPONENTIAL, 30, TimeUnit.SECONDS)
            .build()

        workManager
            .beginUniqueWork(UNIQUE_SYNC_CHAIN, ExistingWorkPolicy.REPLACE, syncRequest)
            .then(mediaRequest)
            .enqueue()
    }

    fun rescheduleMediaUpload(uploadOnMobileData: Boolean) {
        val mediaNetworkType = if (uploadOnMobileData) {
            NetworkType.CONNECTED
        } else {
            NetworkType.UNMETERED
        }
        val mediaConstraints = Constraints.Builder()
            .setRequiredNetworkType(mediaNetworkType)
            .build()

        val mediaRequest = OneTimeWorkRequestBuilder<MediaUploadWorker>()
            .setConstraints(mediaConstraints)
            .setBackoffCriteria(BackoffPolicy.EXPONENTIAL, 30, TimeUnit.SECONDS)
            .build()

        workManager.enqueueUniqueWork(
            UNIQUE_MEDIA_UPLOAD,
            ExistingWorkPolicy.REPLACE,
            mediaRequest
        )
    }

    fun ensurePeriodicWorkersScheduled() {
        val syncConstraints = Constraints.Builder()
            .setRequiredNetworkType(NetworkType.CONNECTED)
            .build()

        val periodicSync = PeriodicWorkRequestBuilder<SyncWorker>(15, TimeUnit.MINUTES)
            .setConstraints(syncConstraints)
            .build()

        workManager.enqueueUniquePeriodicWork(
            UNIQUE_PERIODIC_SYNC,
            ExistingPeriodicWorkPolicy.KEEP,
            periodicSync
        )

        val periodicRetention = PeriodicWorkRequestBuilder<MediaRetentionWorker>(1, TimeUnit.DAYS)
            .build()

        workManager.enqueueUniquePeriodicWork(
            UNIQUE_PERIODIC_RETENTION,
            ExistingPeriodicWorkPolicy.KEEP,
            periodicRetention
        )
    }

    fun cancelAllSyncWork() {
        workManager.cancelUniqueWork(UNIQUE_SYNC_CHAIN)
        workManager.cancelUniqueWork(UNIQUE_MEDIA_UPLOAD)
    }

    companion object {
        private const val UNIQUE_SYNC_CHAIN = "site_diary_sync_chain"
        private const val UNIQUE_MEDIA_UPLOAD = "site_diary_media_upload"
        private const val UNIQUE_PERIODIC_SYNC = "site_diary_periodic_sync"
        private const val UNIQUE_PERIODIC_RETENTION = "site_diary_periodic_retention"
    }
}

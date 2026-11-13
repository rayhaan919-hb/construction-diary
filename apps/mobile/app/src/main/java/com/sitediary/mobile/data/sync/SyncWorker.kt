package com.sitediary.mobile.data.sync

import android.content.Context
import androidx.hilt.work.HiltWorker
import androidx.work.CoroutineWorker
import androidx.work.WorkerParameters
import com.sitediary.mobile.data.prefs.AppPreferences
import dagger.assisted.Assisted
import dagger.assisted.AssistedInject
import java.time.Clock

@HiltWorker
class SyncWorker @AssistedInject constructor(
    @Assisted appContext: Context,
    @Assisted params: WorkerParameters,
    private val syncEngine: SyncEngine,
    private val appPreferences: AppPreferences,
    private val clock: Clock
) : CoroutineWorker(appContext, params) {

    override suspend fun doWork(): Result {
        appPreferences.setSyncing(true)
        return try {
            when (val outcome = syncEngine.syncAll()) {
                is SyncOutcome.Success -> {
                    appPreferences.recordSyncOutcome(clock.millis(), null)
                    Result.success()
                }

                is SyncOutcome.NotAuthenticated -> {
                    Result.success()
                }

                is SyncOutcome.RetryableError -> {
                    appPreferences.recordSyncOutcome(clock.millis(), outcome.message)
                    Result.retry()
                }
            }
        } finally {
            appPreferences.setSyncing(false)
        }
    }
}

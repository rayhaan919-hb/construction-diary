package com.sitediary.mobile.data.sync

import android.content.Context
import androidx.hilt.work.HiltWorker
import androidx.work.CoroutineWorker
import androidx.work.WorkerParameters
import dagger.assisted.Assisted
import dagger.assisted.AssistedInject

@HiltWorker
class MediaRetentionWorker @AssistedInject constructor(
    @Assisted appContext: Context,
    @Assisted params: WorkerParameters,
    private val retentionSweeper: MediaRetentionSweeper
) : CoroutineWorker(appContext, params) {

    override suspend fun doWork(): Result {
        retentionSweeper.purgeExpiredLocalMedia()
        return Result.success()
    }
}

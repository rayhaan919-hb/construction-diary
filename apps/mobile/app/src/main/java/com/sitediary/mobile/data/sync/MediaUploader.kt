package com.sitediary.mobile.data.sync

import com.sitediary.mobile.data.local.dao.PermitDao
import com.sitediary.mobile.data.local.dao.SiteLogDao
import com.sitediary.mobile.data.local.dao.SiteLogPhotoDao
import com.sitediary.mobile.data.remote.SiteDiaryApi
import com.sitediary.mobile.data.remote.dto.MediaCompleteRequestDto
import com.sitediary.mobile.data.remote.dto.MediaKind
import com.sitediary.mobile.data.remote.dto.UploadUrlRequestDto
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.RequestBody.Companion.asRequestBody
import java.io.File
import java.io.IOException
import java.time.Clock
import javax.inject.Inject
import javax.inject.Named
import javax.inject.Singleton

@Singleton
class MediaUploader @Inject constructor(
    private val api: SiteDiaryApi,
    @Named("mediaPut") private val rawUploadClient: OkHttpClient,
    private val syncEngine: SyncEngine,
    private val siteLogDao: SiteLogDao,
    private val siteLogPhotoDao: SiteLogPhotoDao,
    private val permitDao: PermitDao,
    private val clock: Clock
) {

    suspend fun uploadAllPending(): SyncOutcome {
        val audioOutcome = uploadPendingAudio()
        if (audioOutcome !is SyncOutcome.Success) return audioOutcome

        val photoOutcome = uploadPendingPhotos()
        if (photoOutcome !is SyncOutcome.Success) return photoOutcome

        return uploadPendingPermitDocuments()
    }

    private suspend fun uploadPendingAudio(): SyncOutcome {
        val pendingLogs = siteLogDao.getPendingAudioUploads()
        for (log in pendingLogs) {
            val path = log.audioLocalPath ?: continue
            val file = File(path)
            if (!file.exists() || file.length() <= 0L) continue

            val outcome = uploadSingleMedia(
                kind = MediaKind.AUDIO,
                projectId = log.projectId,
                objectId = log.id,
                contentType = "audio/mp4",
                file = file,
                onStorageUriReceived = { storageUri ->
                    siteLogDao.setAudioStorageUriAndMarkDirty(log.id, storageUri)
                },
                callComplete = true,
                onUploadCompleted = { uploadedAt ->
                    siteLogDao.markAudioUploaded(log.id, uploadedAt)
                }
            )
            if (outcome !is SyncOutcome.Success) return outcome
        }
        return SyncOutcome.Success
    }

    private suspend fun uploadPendingPhotos(): SyncOutcome {
        val pendingPhotos = siteLogPhotoDao.getPendingUploads()
        for (photo in pendingPhotos) {
            val path = photo.localPath ?: continue
            val file = File(path)
            if (!file.exists() || file.length() <= 0L) continue

            val outcome = uploadSingleMedia(
                kind = MediaKind.PHOTO,
                projectId = photo.projectId,
                objectId = photo.id,
                contentType = "image/jpeg",
                file = file,
                onStorageUriReceived = { storageUri ->
                    siteLogPhotoDao.setStorageUriAndMarkDirty(photo.id, storageUri)
                },
                callComplete = true,
                onUploadCompleted = { uploadedAt ->
                    siteLogPhotoDao.markUploaded(photo.id, uploadedAt)
                }
            )
            if (outcome !is SyncOutcome.Success) return outcome
        }
        return SyncOutcome.Success
    }

    private suspend fun uploadPendingPermitDocuments(): SyncOutcome {
        val pendingPermits = permitDao.getPendingDocumentUploads()
        for (permit in pendingPermits) {
            val path = permit.documentLocalPath ?: continue
            val file = File(path)
            if (!file.exists() || file.length() <= 0L) continue

            val outcome = uploadSingleMedia(
                kind = MediaKind.PERMIT_DOC,
                projectId = permit.projectId,
                objectId = permit.id,
                contentType = "image/jpeg",
                file = file,
                onStorageUriReceived = { storageUri ->
                    permitDao.setDocumentStorageUriAndMarkDirty(permit.id, storageUri)
                },
                callComplete = false,
                onUploadCompleted = { uploadedAt ->
                    permitDao.markDocumentUploaded(permit.id, uploadedAt)
                }
            )
            if (outcome !is SyncOutcome.Success) return outcome
        }
        return SyncOutcome.Success
    }

    private suspend fun uploadSingleMedia(
        kind: MediaKind,
        projectId: String,
        objectId: String,
        contentType: String,
        file: File,
        onStorageUriReceived: suspend (String) -> Unit,
        callComplete: Boolean,
        onUploadCompleted: suspend (Long) -> Unit
    ): SyncOutcome {
        // 1. Request signed upload ticket
        val ticketResponse = try {
            api.getUploadUrl(
                UploadUrlRequestDto(
                    kind = kind,
                    projectId = projectId,
                    objectId = objectId,
                    contentType = contentType,
                    byteSize = file.length()
                )
            )
        } catch (e: IOException) {
            return SyncOutcome.RetryableError(e.message ?: "Network error requesting upload URL")
        }

        if (!ticketResponse.isSuccessful) {
            return SyncOutcome.RetryableError("HTTP ${ticketResponse.code()} requesting upload URL")
        }
        val ticket = ticketResponse.body()
            ?: return SyncOutcome.RetryableError("Empty upload ticket body")

        // 2. Store canonical storage_uri in Room and push via /v1/sync/push FIRST
        //    so /v1/media/complete never hits ROW_NOT_SYNCED.
        onStorageUriReceived(ticket.storageUri)
        val pushOutcome = syncEngine.pushPendingChanges()
        if (pushOutcome !is SyncOutcome.Success) return pushOutcome

        // 3. Direct PUT of file bytes to upload_url with exact headers
        val putBuilder = Request.Builder()
            .url(ticket.uploadUrl)
            .put(file.asRequestBody(contentType.toMediaType()))

        ticket.headers.forEach { (key, value) ->
            putBuilder.header(key, value)
        }

        val putResponse = try {
            rawUploadClient.newCall(putBuilder.build()).execute()
        } catch (e: IOException) {
            return SyncOutcome.RetryableError(e.message ?: "Network error uploading bytes")
        }

        putResponse.use { res ->
            if (!res.isSuccessful) {
                return SyncOutcome.RetryableError("HTTP ${res.code} uploading media bytes")
            }
        }

        // 4. Confirm upload for AUDIO and PHOTO via /v1/media/complete and record timestamp
        if (callComplete) {
            val completeResult = completeWithSinglePushRetry(kind, objectId)
            if (completeResult !is SyncOutcome.Success) return completeResult
        }

        onUploadCompleted(clock.millis())
        return SyncOutcome.Success
    }

    private suspend fun completeWithSinglePushRetry(kind: MediaKind, objectId: String): SyncOutcome {
        val req = MediaCompleteRequestDto(kind = kind, objectId = objectId)
        val firstRes = try {
            api.completeMediaUpload(req)
        } catch (e: IOException) {
            return SyncOutcome.RetryableError(e.message ?: "Network error completing media upload")
        }

        if (firstRes.isSuccessful) return SyncOutcome.Success

        if (firstRes.code() == 409) {
            val retryPush = syncEngine.pushPendingChanges()
            if (retryPush !is SyncOutcome.Success) return retryPush

            val secondRes = try {
                api.completeMediaUpload(req)
            } catch (e: IOException) {
                return SyncOutcome.RetryableError(e.message ?: "Network error retrying media complete")
            }
            if (secondRes.isSuccessful) return SyncOutcome.Success
            return SyncOutcome.RetryableError("HTTP ${secondRes.code()} completing media upload")
        }

        return SyncOutcome.RetryableError("HTTP ${firstRes.code()} completing media upload")
    }
}

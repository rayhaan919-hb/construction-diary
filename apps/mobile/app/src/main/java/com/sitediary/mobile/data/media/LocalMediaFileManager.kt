package com.sitediary.mobile.data.media

import android.content.Context
import dagger.hilt.android.qualifiers.ApplicationContext
import java.io.File
import javax.inject.Inject
import javax.inject.Singleton

@Singleton
class LocalMediaFileManager @Inject constructor(
    @ApplicationContext private val context: Context
) {
    private val mediaRootDir: File
        get() = File(context.filesDir, "media").apply { mkdirs() }

    fun createAudioFile(projectId: String, logId: String): File {
        val dir = File(mediaRootDir, "projects/$projectId/audio").apply { mkdirs() }
        return File(dir, "$logId.m4a")
    }

    fun createPhotoFile(projectId: String, photoId: String): File {
        val dir = File(mediaRootDir, "projects/$projectId/photos").apply { mkdirs() }
        return File(dir, "$photoId.jpg")
    }

    fun createPermitDocumentFile(projectId: String, permitId: String): File {
        val dir = File(mediaRootDir, "projects/$projectId/permits").apply { mkdirs() }
        return File(dir, "$permitId.jpg")
    }

    fun createTempCaptureFile(prefix: String): File {
        val dir = File(context.cacheDir, "captures").apply { mkdirs() }
        return File.createTempFile(prefix, ".jpg", dir)
    }

    fun deleteFileIfExists(path: String?) {
        if (path.isNullOrBlank()) return
        runCatching {
            val file = File(path)
            if (file.exists()) {
                file.delete()
            }
        }
    }

    fun deleteProjectMedia(projectId: String, explicitPaths: List<String> = emptyList()) {
        explicitPaths.forEach { deleteFileIfExists(it) }
        val projectDir = File(mediaRootDir, "projects/$projectId")
        if (projectDir.exists()) {
            projectDir.deleteRecursively()
        }
    }

    fun clearAllMedia() {
        if (mediaRootDir.exists()) {
            mediaRootDir.deleteRecursively()
        }
        val capturesCacheDir = File(context.cacheDir, "captures")
        if (capturesCacheDir.exists()) {
            capturesCacheDir.deleteRecursively()
        }
    }

    companion object {
        const val RETENTION_MILLIS: Long = 7L * 24L * 60L * 60L * 1000L

        fun isOlderThanRetentionWindow(uploadedAtEpochMs: Long, nowEpochMs: Long): Boolean {
            return (nowEpochMs - uploadedAtEpochMs) > RETENTION_MILLIS
        }
    }
}

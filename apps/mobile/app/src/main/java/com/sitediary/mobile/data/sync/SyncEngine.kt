package com.sitediary.mobile.data.sync

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
import com.sitediary.mobile.data.media.LocalMediaFileManager
import com.sitediary.mobile.data.remote.SiteDiaryApi
import com.sitediary.mobile.data.remote.dto.PermitDto
import com.sitediary.mobile.data.remote.dto.PermitPushDto
import com.sitediary.mobile.data.remote.dto.SiteLogDto
import com.sitediary.mobile.data.remote.dto.SiteLogPhotoDto
import com.sitediary.mobile.data.remote.dto.SiteLogPhotoPushDto
import com.sitediary.mobile.data.remote.dto.SiteLogPushDto
import com.sitediary.mobile.data.remote.dto.SyncPullChangesDto
import com.sitediary.mobile.data.remote.dto.SyncPushChangesDto
import com.sitediary.mobile.data.remote.dto.SyncPushRequestDto
import java.io.IOException
import java.time.Clock
import javax.inject.Inject
import javax.inject.Singleton

sealed interface SyncOutcome {
    data object Success : SyncOutcome
    data object NotAuthenticated : SyncOutcome
    data class RetryableError(val message: String) : SyncOutcome
}

@Singleton
class SyncEngine @Inject constructor(
    private val api: SiteDiaryApi,
    private val projectDao: ProjectDao,
    private val projectMemberDao: ProjectMemberDao,
    private val permitDao: PermitDao,
    private val siteLogDao: SiteLogDao,
    private val siteLogPhotoDao: SiteLogPhotoDao,
    private val syncCursorDao: SyncCursorDao,
    private val mediaFileManager: LocalMediaFileManager,
    private val currentUserIdProvider: () -> String?,
    private val clock: Clock,
    private val runInTransaction: suspend (suspend () -> Unit) -> Unit
) {

    suspend fun syncAll(): SyncOutcome {
        val currentUserId = currentUserIdProvider() ?: return SyncOutcome.NotAuthenticated

        val pushResult = pushPendingChanges()
        if (pushResult !is SyncOutcome.Success) {
            return pushResult
        }

        return pullAndBackfill(currentUserId)
    }

    suspend fun pushPendingChanges(): SyncOutcome {
        if (currentUserIdProvider() == null) return SyncOutcome.NotAuthenticated

        while (true) {
            val permits = permitDao.getDirtyBatch(MAX_PUSH_BATCH)
            val remainingAfterPermits = MAX_PUSH_BATCH - permits.size
            val siteLogs = if (remainingAfterPermits > 0) {
                siteLogDao.getDirtyBatch(remainingAfterPermits)
            } else {
                emptyList()
            }
            val remainingAfterLogs = remainingAfterPermits - siteLogs.size
            val photos = if (remainingAfterLogs > 0) {
                siteLogPhotoDao.getDirtyPushableBatch(remainingAfterLogs)
            } else {
                emptyList()
            }

            if (permits.isEmpty() && siteLogs.isEmpty() && photos.isEmpty()) {
                return SyncOutcome.Success
            }

            val permitSeqs = permits.associate { it.id to it.localMutationSeq }
            val logSeqs = siteLogs.associate { it.id to it.localMutationSeq }
            val photoSeqs = photos.associate { it.id to it.localMutationSeq }

            val request = SyncPushRequestDto(
                changes = SyncPushChangesDto(
                    permits = permits.map { it.toPushDto() },
                    siteLogs = siteLogs.map { it.toPushDto() },
                    siteLogPhotos = photos.map { it.toPushDto() }
                )
            )

            val response = try {
                api.syncPush(request)
            } catch (e: IOException) {
                return SyncOutcome.RetryableError(e.message ?: "Network error during sync push")
            }

            if (!response.isSuccessful) {
                return SyncOutcome.RetryableError("HTTP ${response.code()} during sync push")
            }

            val body = response.body()
                ?: return SyncOutcome.RetryableError("Empty response body from sync push")

            val pathsToDelete = mutableListOf<Pair<String, List<String>>>()
            var handledCount = 0

            runInTransaction {
                for (result in body.results) {
                    handledCount++
                    when (result.entity) {
                        "permits" -> {
                            val expectedSeq = permitSeqs[result.id] ?: continue
                            if (result.status == "APPLIED") {
                                permitDao.markSyncedIfSeqMatches(
                                    id = result.id,
                                    expectedSeq = expectedSeq,
                                    serverVersion = result.serverVersion ?: 0L
                                )
                            } else if (result.errorCode == "PROJECT_DELETED") {
                                val permit = permitDao.getById(result.id)
                                if (permit != null) {
                                    pathsToDelete += permit.projectId to collectProjectFilePaths(permit.projectId)
                                    purgeProjectDbRows(permit.projectId)
                                }
                            } else {
                                permitDao.markSyncRejectedIfSeqMatches(
                                    id = result.id,
                                    expectedSeq = expectedSeq,
                                    error = formatRejectionError(result.errorCode, result.errorDetail)
                                )
                            }
                        }

                        "site_logs" -> {
                            val expectedSeq = logSeqs[result.id] ?: continue
                            if (result.status == "APPLIED") {
                                siteLogDao.markSyncedIfSeqMatches(
                                    id = result.id,
                                    expectedSeq = expectedSeq,
                                    serverVersion = result.serverVersion ?: 0L
                                )
                            } else if (result.errorCode == "PROJECT_DELETED") {
                                val log = siteLogDao.getById(result.id)
                                if (log != null) {
                                    pathsToDelete += log.projectId to collectProjectFilePaths(log.projectId)
                                    purgeProjectDbRows(log.projectId)
                                }
                            } else {
                                siteLogDao.markSyncRejectedIfSeqMatches(
                                    id = result.id,
                                    expectedSeq = expectedSeq,
                                    error = formatRejectionError(result.errorCode, result.errorDetail)
                                )
                            }
                        }

                        "site_log_photos" -> {
                            val expectedSeq = photoSeqs[result.id] ?: continue
                            if (result.status == "APPLIED") {
                                siteLogPhotoDao.markSyncedIfSeqMatches(
                                    id = result.id,
                                    expectedSeq = expectedSeq,
                                    serverVersion = result.serverVersion ?: 0L
                                )
                            } else {
                                siteLogPhotoDao.markSyncRejectedIfSeqMatches(
                                    id = result.id,
                                    expectedSeq = expectedSeq,
                                    error = formatRejectionError(result.errorCode, result.errorDetail)
                                )
                            }
                        }
                    }
                }
            }

            pathsToDelete.forEach { (projectId, paths) ->
                mediaFileManager.deleteProjectMedia(projectId, paths)
            }

            if (handledCount == 0) {
                return SyncOutcome.Success
            }
        }
    }

    private suspend fun pullAndBackfill(currentUserId: String): SyncOutcome {
        var globalCursor = syncCursorDao.getCursor(GLOBAL_CURSOR_KEY) ?: 0L
        val projectsToBackfill = linkedSetOf<String>()
        val purgedProjects = linkedSetOf<String>()

        while (true) {
            val response = try {
                api.syncPull(since = globalCursor, limit = PULL_LIMIT, projectId = null)
            } catch (e: IOException) {
                return SyncOutcome.RetryableError(e.message ?: "Network error during sync pull")
            }

            if (!response.isSuccessful) {
                return SyncOutcome.RetryableError("HTTP ${response.code()} during sync pull")
            }

            val page = response.body()
                ?: return SyncOutcome.RetryableError("Empty response body from sync pull")

            val filesToDelete = mutableListOf<Pair<String, List<String>>>()

            runInTransaction {
                val previouslyKnownActiveProjects = projectMemberDao
                    .getActiveProjectIdsForUser(currentUserId)
                    .toSet()

                for (member in page.changes.projectMembers) {
                    if (member.userId == currentUserId) {
                        if (member.deletedAt != null) {
                            purgedProjects += member.projectId
                            projectsToBackfill.remove(member.projectId)
                        } else if (
                            member.projectId !in previouslyKnownActiveProjects &&
                            member.projectId !in purgedProjects
                        ) {
                            projectsToBackfill += member.projectId
                        }
                    }
                }

                for (project in page.changes.projects) {
                    if (project.deletedAt != null) {
                        purgedProjects += project.id
                        projectsToBackfill.remove(project.id)
                    }
                }

                applyChangesToRoom(page.changes, purgedProjects)

                for (projectId in purgedProjects) {
                    val paths = collectProjectFilePaths(projectId)
                    if (paths.isNotEmpty()) {
                        filesToDelete += projectId to paths
                    }
                    purgeProjectDbRows(projectId)
                }

                syncCursorDao.upsert(
                    SyncCursorEntity(
                        scopeKey = GLOBAL_CURSOR_KEY,
                        cursor = page.nextCursor,
                        updatedAtEpochMs = clock.millis()
                    )
                )
            }

            filesToDelete.forEach { (projectId, paths) ->
                mediaFileManager.deleteProjectMedia(projectId, paths)
            }
            purgedProjects.forEach { projectId ->
                mediaFileManager.deleteProjectMedia(projectId)
            }

            globalCursor = page.nextCursor
            if (!page.hasMore) break
        }

        for (projectId in projectsToBackfill) {
            if (projectId in purgedProjects) continue
            val backfillResult = backfillProject(projectId, currentUserId)
            if (backfillResult !is SyncOutcome.Success) {
                return backfillResult
            }
        }

        return SyncOutcome.Success
    }

    private suspend fun backfillProject(projectId: String, currentUserId: String): SyncOutcome {
        val cursorKey = projectCursorKey(projectId)
        var projectCursor = syncCursorDao.getCursor(cursorKey) ?: 0L

        while (true) {
            val response = try {
                api.syncPull(since = projectCursor, limit = PULL_LIMIT, projectId = projectId)
            } catch (e: IOException) {
                return SyncOutcome.RetryableError(e.message ?: "Network error during project backfill")
            }

            if (!response.isSuccessful) {
                return SyncOutcome.RetryableError("HTTP ${response.code()} during project backfill")
            }

            val page = response.body()
                ?: return SyncOutcome.RetryableError("Empty response body from project backfill")

            var projectTombstoned = false
            val filesToDelete = mutableListOf<String>()

            runInTransaction {
                val hasSelfTombstone = page.changes.projectMembers.any {
                    it.projectId == projectId && it.userId == currentUserId && it.deletedAt != null
                }
                val hasDeletedProject = page.changes.projects.any {
                    it.id == projectId && it.deletedAt != null
                }
                if (hasSelfTombstone || hasDeletedProject) {
                    projectTombstoned = true
                    filesToDelete += collectProjectFilePaths(projectId)
                    purgeProjectDbRows(projectId)
                } else {
                    applyChangesToRoom(page.changes, emptySet())
                    syncCursorDao.upsert(
                        SyncCursorEntity(
                            scopeKey = cursorKey,
                            cursor = page.nextCursor,
                            updatedAtEpochMs = clock.millis()
                        )
                    )
                }
            }

            if (projectTombstoned) {
                mediaFileManager.deleteProjectMedia(projectId, filesToDelete)
                return SyncOutcome.Success
            }

            projectCursor = page.nextCursor
            if (!page.hasMore) break
        }

        return SyncOutcome.Success
    }

    private suspend fun applyChangesToRoom(
        changes: SyncPullChangesDto,
        purgedProjects: Set<String>
    ) {
        val projects = changes.projects
            .filter { it.id !in purgedProjects }
            .map { it.toEntity() }
        if (projects.isNotEmpty()) {
            projectDao.upsertAll(projects)
        }

        val members = changes.projectMembers
            .filter { it.projectId !in purgedProjects }
            .map {
                ProjectMemberEntity(
                    projectId = it.projectId,
                    userId = it.userId,
                    role = it.role,
                    fullName = it.fullName,
                    email = it.email,
                    deletedAt = it.deletedAt,
                    serverVersion = it.serverVersion
                )
            }
        if (members.isNotEmpty()) {
            projectMemberDao.upsertAll(members)
        }

        val permitsToUpsert = mutableListOf<PermitEntity>()
        for (dto in changes.permits) {
            if (dto.projectId in purgedProjects) continue
            val existing = permitDao.getById(dto.id)
            if (existing != null && existing.syncDirty) {
                // Never clobber dirty local edits
                permitsToUpsert += existing.copy(
                    serverVersion = maxOf(existing.serverVersion, dto.serverVersion),
                    documentPhotoUrl = dto.documentPhotoUrl ?: existing.documentPhotoUrl
                )
            } else {
                permitsToUpsert += dto.toEntity(existing)
            }
        }
        if (permitsToUpsert.isNotEmpty()) {
            permitDao.upsertAll(permitsToUpsert)
        }

        val logsToUpsert = mutableListOf<SiteLogEntity>()
        for (dto in changes.siteLogs) {
            if (dto.projectId in purgedProjects) continue
            val existing = siteLogDao.getById(dto.id)
            if (existing != null && existing.syncDirty) {
                // Preserve client-owned fields while updating server-owned extraction metadata
                logsToUpsert += existing.copy(
                    extractionStatus = dto.extractionStatus,
                    extractionAttempts = dto.extractionAttempts,
                    extractionError = dto.extractionError,
                    extractionModel = dto.extractionModel,
                    extractedAt = dto.extractedAt,
                    transcript = dto.transcript,
                    detectedLanguage = dto.detectedLanguage,
                    structuredSummary = if (existing.editedByHuman) {
                        existing.structuredSummary
                    } else {
                        dto.structuredSummary
                    },
                    serverVersion = maxOf(existing.serverVersion, dto.serverVersion)
                )
            } else {
                logsToUpsert += dto.toEntity(existing)
            }
        }
        if (logsToUpsert.isNotEmpty()) {
            siteLogDao.upsertAll(logsToUpsert)
        }

        val photosToUpsert = mutableListOf<SiteLogPhotoEntity>()
        for (dto in changes.siteLogPhotos) {
            val existing = siteLogPhotoDao.getById(dto.id)
            val resolvedProjectId = existing?.projectId
                ?: siteLogDao.getById(dto.siteLogId)?.projectId
                ?: continue
            if (resolvedProjectId in purgedProjects) continue

            if (existing != null && existing.syncDirty) {
                photosToUpsert += existing.copy(
                    remoteUrl = dto.url ?: existing.remoteUrl,
                    uploadStatus = dto.uploadStatus,
                    serverVersion = maxOf(existing.serverVersion, dto.serverVersion)
                )
            } else {
                photosToUpsert += dto.toEntity(resolvedProjectId, existing)
            }
        }
        if (photosToUpsert.isNotEmpty()) {
            siteLogPhotoDao.upsertAll(photosToUpsert)
        }
    }

    private suspend fun collectProjectFilePaths(projectId: String): List<String> {
        return buildList {
            addAll(siteLogDao.getLocalAudioPathsForProject(projectId))
            addAll(siteLogPhotoDao.getLocalPathsForProject(projectId))
            addAll(permitDao.getLocalPathsForProject(projectId))
        }
    }

    private suspend fun purgeProjectDbRows(projectId: String) {
        siteLogPhotoDao.deleteByProjectId(projectId)
        siteLogDao.deleteByProjectId(projectId)
        permitDao.deleteByProjectId(projectId)
        projectMemberDao.deleteByProjectId(projectId)
        projectDao.deleteById(projectId)
        syncCursorDao.deleteByScope(projectCursorKey(projectId))
    }

    private fun formatRejectionError(code: String?, detail: String?): String {
        return listOfNotNull(code, detail).joinToString(": ").ifBlank { "SYNC_REJECTED" }
    }

    companion object {
        const val MAX_PUSH_BATCH = 200
        const val PULL_LIMIT = 500
        const val GLOBAL_CURSOR_KEY = "global"

        fun projectCursorKey(projectId: String): String = "project:$projectId"
    }
}

private fun PermitEntity.toPushDto(): PermitPushDto = PermitPushDto(
    id = id,
    projectId = projectId,
    permitName = permitName,
    authority = authority,
    permitNumber = permitNumber,
    issueDate = issueDate,
    expiryDate = expiryDate,
    documentPhotoUri = documentPhotoUri,
    deletedAt = deletedAt,
    clientUpdatedAt = clientUpdatedAt
)

private fun SiteLogEntity.toPushDto(): SiteLogPushDto = SiteLogPushDto(
    id = id,
    projectId = projectId,
    logDate = logDate,
    recordedAt = recordedAt,
    notes = notes,
    audioUri = audioUri,
    audioDurationMs = audioDurationMs,
    structuredSummary = if (editedByHuman) structuredSummary else null,
    editedByHuman = editedByHuman,
    deletedAt = deletedAt,
    clientUpdatedAt = clientUpdatedAt
)

private fun SiteLogPhotoEntity.toPushDto(): SiteLogPhotoPushDto = SiteLogPhotoPushDto(
    id = id,
    siteLogId = siteLogId,
    storageUri = storageUri,
    width = width,
    height = height,
    byteSize = byteSize,
    takenAt = takenAt,
    sortOrder = sortOrder,
    deletedAt = deletedAt
)

private fun com.sitediary.mobile.data.remote.dto.ProjectDto.toEntity(): ProjectEntity =
    ProjectEntity(
        id = id,
        name = name,
        siteAddress = siteAddress,
        ownerPhone = ownerPhone,
        timezone = timezone,
        allowPhotoGps = allowPhotoGps,
        createdAt = createdAt,
        updatedAt = updatedAt,
        deletedAt = deletedAt,
        serverVersion = serverVersion
    )

private fun PermitDto.toEntity(existing: PermitEntity?): PermitEntity {
    val sameDocUri = existing?.documentPhotoUri != null && existing.documentPhotoUri == documentPhotoUri
    val uploadStatus = when {
        sameDocUri -> existing.documentUploadStatus
        documentPhotoUri != null -> "UPLOADED"
        else -> existing?.documentUploadStatus ?: "NONE"
    }
    return PermitEntity(
        id = id,
        projectId = projectId,
        permitName = permitName,
        authority = authority,
        permitNumber = permitNumber,
        issueDate = issueDate,
        expiryDate = expiryDate,
        documentPhotoUri = documentPhotoUri,
        documentPhotoUrl = documentPhotoUrl ?: existing?.documentPhotoUrl,
        createdBy = createdBy,
        clientUpdatedAt = updatedAt,
        createdAt = createdAt,
        updatedAt = updatedAt,
        deletedAt = deletedAt,
        serverVersion = serverVersion,
        documentLocalPath = existing?.documentLocalPath,
        documentUploadStatus = uploadStatus,
        documentUploadedAtEpochMs = existing?.documentUploadedAtEpochMs,
        syncDirty = false,
        localMutationSeq = existing?.localMutationSeq ?: 0L,
        syncError = null
    )
}

private fun SiteLogDto.toEntity(existing: SiteLogEntity?): SiteLogEntity {
    val resolvedSummary = if (existing?.editedByHuman == true && !editedByHuman) {
        existing.structuredSummary
    } else {
        structuredSummary
    }
    return SiteLogEntity(
        id = id,
        projectId = projectId,
        authorId = authorId,
        authorName = authorName ?: existing?.authorName,
        logDate = logDate,
        recordedAt = recordedAt,
        notes = notes,
        audioUri = audioUri,
        audioDurationMs = audioDurationMs,
        audioUploadStatus = audioUploadStatus,
        extractionStatus = extractionStatus,
        extractionAttempts = extractionAttempts,
        extractionError = extractionError,
        extractionModel = extractionModel,
        extractedAt = extractedAt,
        transcript = transcript,
        detectedLanguage = detectedLanguage,
        structuredSummary = resolvedSummary,
        editedByHuman = editedByHuman,
        clientUpdatedAt = clientUpdatedAt,
        createdAt = createdAt,
        updatedAt = updatedAt,
        deletedAt = deletedAt,
        serverVersion = serverVersion,
        audioLocalPath = existing?.audioLocalPath,
        audioUploadedAtEpochMs = existing?.audioUploadedAtEpochMs,
        syncDirty = false,
        localMutationSeq = existing?.localMutationSeq ?: 0L,
        syncError = null
    )
}

private fun SiteLogPhotoDto.toEntity(
    projectId: String,
    existing: SiteLogPhotoEntity?
): SiteLogPhotoEntity {
    return SiteLogPhotoEntity(
        id = id,
        siteLogId = siteLogId,
        projectId = projectId,
        storageUri = storageUri,
        uploadStatus = uploadStatus,
        remoteUrl = url ?: existing?.remoteUrl,
        width = width,
        height = height,
        byteSize = byteSize,
        takenAt = takenAt,
        sortOrder = sortOrder,
        createdAt = existing?.createdAt ?: "",
        updatedAt = existing?.updatedAt ?: "",
        deletedAt = deletedAt,
        serverVersion = serverVersion,
        localPath = existing?.localPath,
        uploadedAtEpochMs = existing?.uploadedAtEpochMs,
        syncDirty = false,
        localMutationSeq = existing?.localMutationSeq ?: 0L,
        syncError = null
    )
}

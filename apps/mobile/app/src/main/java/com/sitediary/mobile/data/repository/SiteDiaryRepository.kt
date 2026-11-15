package com.sitediary.mobile.data.repository

import androidx.room.withTransaction
import com.sitediary.mobile.data.local.SiteDiaryDatabase
import com.sitediary.mobile.data.local.dao.PermitDao
import com.sitediary.mobile.data.local.dao.ProjectDao
import com.sitediary.mobile.data.local.dao.SiteLogDao
import com.sitediary.mobile.data.local.dao.SiteLogPhotoDao
import com.sitediary.mobile.data.local.dao.SiteLogWithPhotos
import com.sitediary.mobile.data.local.entity.PermitEntity
import com.sitediary.mobile.data.local.entity.ProjectEntity
import com.sitediary.mobile.data.local.entity.SiteLogEntity
import com.sitediary.mobile.data.local.entity.SiteLogPhotoEntity
import com.sitediary.mobile.data.media.ProcessedPhotoResult
import com.sitediary.mobile.data.prefs.AppPreferences
import com.sitediary.mobile.data.remote.SiteDiaryApi
import com.sitediary.mobile.data.remote.dto.ExtractRequestDto
import com.sitediary.mobile.data.remote.dto.StructuredSummaryDto
import com.sitediary.mobile.data.sync.SyncScheduler
import com.sitediary.mobile.domain.model.EvaluatedPermit
import com.sitediary.mobile.domain.model.PermitHealth
import com.sitediary.mobile.domain.model.PermitStatusCalculator
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.combine
import kotlinx.coroutines.flow.first
import java.io.File
import java.io.IOException
import java.time.Clock
import java.time.LocalDate
import java.util.UUID
import javax.inject.Inject
import javax.inject.Singleton

data class ProjectCardModel(
    val project: ProjectEntity,
    val permitHealth: PermitHealth,
    val todayLogCount: Int,
    val todayLaborMax: Int?,
    val openBlockersCount: Int,
    val pendingSyncCount: Int
)

data class CapturedPhotoDraft(
    val id: String,
    val processed: ProcessedPhotoResult,
    val takenAtIso: String
)

@Singleton
class SiteDiaryRepository @Inject constructor(
    private val database: SiteDiaryDatabase,
    private val projectDao: ProjectDao,
    private val permitDao: PermitDao,
    private val siteLogDao: SiteLogDao,
    private val siteLogPhotoDao: SiteLogPhotoDao,
    private val api: SiteDiaryApi,
    private val appPreferences: AppPreferences,
    private val syncScheduler: SyncScheduler,
    private val permitStatusCalculator: PermitStatusCalculator,
    private val clock: Clock
) {

    fun observeProjectCards(userId: String): Flow<List<ProjectCardModel>> {
        return combine(
            projectDao.observeActiveProjectsForUser(userId),
            permitDao.observeAllActive(),
            siteLogDao.observeAllActive()
        ) { projects, permits, logs ->
            val permitsByProject = permits.groupBy { it.projectId }
            val logsByProject = logs.groupBy { it.projectId }

            projects.map { project ->
                val projectToday = permitStatusCalculator.projectToday(project.timezone).toString()
                val projectPermits = permitsByProject[project.id].orEmpty()
                val evaluations = projectPermits.map {
                    permitStatusCalculator.evaluate(it.expiryDate, project.timezone)
                }
                val health = permitStatusCalculator.computeProjectHealth(evaluations)

                val projectLogs = logsByProject[project.id].orEmpty()
                val todayLogs = projectLogs.filter { it.logDate == projectToday }
                val laborMax = todayLogs.mapNotNull { it.structuredSummary?.laborCount }.maxOrNull()
                val blockersCount = todayLogs
                    .flatMap { it.structuredSummary?.blockers.orEmpty() }
                    .map { it.trim().lowercase() }
                    .filter { it.isNotEmpty() }
                    .distinct()
                    .size

                val pendingCount = projectPermits.count { it.syncDirty } +
                    projectLogs.count { it.syncDirty || it.audioUploadStatus == "PENDING" }

                ProjectCardModel(
                    project = project,
                    permitHealth = health,
                    todayLogCount = todayLogs.size,
                    todayLaborMax = laborMax,
                    openBlockersCount = blockersCount,
                    pendingSyncCount = pendingCount
                )
            }
        }
    }

    fun observeProject(projectId: String): Flow<ProjectEntity?> =
        projectDao.observeProject(projectId)

    fun observeProjectPermits(projectId: String): Flow<List<EvaluatedPermit>> {
        return combine(
            permitDao.observeByProject(projectId),
            projectDao.observeProject(projectId)
        ) { permits, project ->
            val tz = project?.timezone ?: PermitStatusCalculator.DEFAULT_TIMEZONE
            permits.map { entity ->
                val evaluation = permitStatusCalculator.evaluate(entity.expiryDate, tz)
                EvaluatedPermit(
                    id = entity.id,
                    projectId = entity.projectId,
                    permitName = entity.permitName,
                    authority = entity.authority,
                    permitNumber = entity.permitNumber,
                    issueDate = entity.issueDate,
                    expiryDate = LocalDate.parse(entity.expiryDate),
                    documentPhotoUri = entity.documentPhotoUri,
                    documentLocalPath = entity.documentLocalPath,
                    documentUploadStatus = entity.documentUploadStatus,
                    status = evaluation.status,
                    daysToExpiry = evaluation.daysToExpiry,
                    syncDirty = entity.syncDirty
                )
            }.sortedBy { it.expiryDate }
        }
    }

    fun observeProjectLogs(projectId: String): Flow<List<SiteLogWithPhotos>> {
        return siteLogDao.observeLogsWithPhotosByProject(projectId).combine(
            siteLogPhotoDao.observePendingCount()
        ) { list, _ ->
            list.map { item ->
                item.copy(
                    photos = item.photos
                        .filter { it.deletedAt == null }
                        .sortedBy { it.sortOrder }
                )
            }
        }
    }

    fun observeLogDetail(logId: String): Flow<SiteLogWithPhotos?> {
        return siteLogDao.observeLogWithPhotos(logId).combine(
            siteLogPhotoDao.observePendingCount()
        ) { item, _ ->
            item?.copy(
                photos = item.photos
                    .filter { it.deletedAt == null }
                    .sortedBy { it.sortOrder }
            )
        }
    }

    fun observeTotalPendingSyncCount(): Flow<Int> {
        return combine(
            permitDao.observeDirtyCount(),
            siteLogDao.observeDirtyCount(),
            siteLogPhotoDao.observePendingCount()
        ) { permits, logs, photos ->
            permits + logs + photos
        }
    }

    suspend fun createSiteLogOffline(
        logId: String,
        projectId: String,
        notes: String?,
        audioFile: File?,
        audioDurationMs: Int?,
        photos: List<CapturedPhotoDraft>
    ) {
        val currentUser = appPreferences.getCurrentUser()
            ?: throw IllegalStateException("Cannot create log while signed out")
        val project = projectDao.getById(projectId)
        val timezone = project?.timezone ?: PermitStatusCalculator.DEFAULT_TIMEZONE
        val localDate = permitStatusCalculator.projectToday(timezone).toString()
        val nowIso = clock.instant().toString()

        val logEntity = SiteLogEntity(
            id = logId,
            projectId = projectId,
            authorId = currentUser.id,
            authorName = currentUser.fullName,
            logDate = localDate,
            recordedAt = nowIso,
            notes = notes?.trim()?.takeIf { it.isNotEmpty() },
            audioUri = null,
            audioDurationMs = audioDurationMs,
            audioUploadStatus = if (audioFile != null) "PENDING" else "NONE",
            extractionStatus = if (audioFile != null) "PENDING" else "NOT_STARTED",
            extractionAttempts = 0,
            editedByHuman = false,
            clientUpdatedAt = nowIso,
            createdAt = nowIso,
            updatedAt = nowIso,
            audioLocalPath = audioFile?.absolutePath,
            syncDirty = true,
            localMutationSeq = 1L
        )

        val photoEntities = photos.mapIndexed { index, draft ->
            SiteLogPhotoEntity(
                id = draft.id,
                siteLogId = logId,
                projectId = projectId,
                storageUri = "",
                uploadStatus = "PENDING",
                width = draft.processed.width,
                height = draft.processed.height,
                byteSize = draft.processed.byteSize,
                takenAt = draft.takenAtIso,
                sortOrder = index,
                createdAt = nowIso,
                updatedAt = nowIso,
                localPath = draft.processed.file.absolutePath,
                syncDirty = true,
                localMutationSeq = 1L
            )
        }

        database.withTransaction {
            siteLogDao.upsert(logEntity)
            if (photoEntities.isNotEmpty()) {
                siteLogPhotoDao.upsertAll(photoEntities)
            }
        }

        triggerSync()
    }

    suspend fun saveHumanSummaryCorrection(
        logId: String,
        tasksCompleted: List<String>,
        laborCount: Int?,
        materialDeliveries: List<String>,
        blockers: List<String>
    ) {
        val existing = siteLogDao.getById(logId) ?: return
        val nowIso = clock.instant().toString()
        val updated = existing.copy(
            structuredSummary = StructuredSummaryDto(
                tasksCompleted = tasksCompleted,
                laborCount = laborCount,
                materialDeliveries = materialDeliveries,
                blockers = blockers
            ),
            editedByHuman = true,
            clientUpdatedAt = nowIso,
            updatedAt = nowIso,
            syncDirty = true,
            localMutationSeq = existing.localMutationSeq + 1L,
            syncError = null
        )
        siteLogDao.upsert(updated)
        triggerSync()
    }

    suspend fun retryExtraction(logId: String): Result<String> {
        val response = try {
            api.queueExtraction(ExtractRequestDto(logId = logId))
        } catch (e: IOException) {
            return Result.failure(e)
        }
        return if (response.isSuccessful) {
            val status = response.body()?.extractionStatus ?: "PENDING"
            siteLogDao.updateExtractionStatus(logId, status)
            triggerSync()
            Result.success(status)
        } else {
            Result.failure(IllegalStateException("Extraction request failed (${response.code()})"))
        }
    }

    suspend fun createPermitOffline(
        permitId: String = UUID.randomUUID().toString(),
        projectId: String,
        permitName: String,
        authority: String,
        permitNumber: String?,
        issueDate: String?,
        expiryDate: String,
        documentFile: File?
    ) {
        val currentUser = appPreferences.getCurrentUser()
            ?: throw IllegalStateException("Cannot create permit while signed out")
        val nowIso = clock.instant().toString()

        val permit = PermitEntity(
            id = permitId,
            projectId = projectId,
            permitName = permitName.trim(),
            authority = authority.trim(),
            permitNumber = permitNumber?.trim()?.takeIf { it.isNotEmpty() },
            issueDate = issueDate?.trim()?.takeIf { it.isNotEmpty() },
            expiryDate = expiryDate.trim(),
            documentPhotoUri = null,
            createdBy = currentUser.id,
            clientUpdatedAt = nowIso,
            createdAt = nowIso,
            updatedAt = nowIso,
            documentLocalPath = documentFile?.absolutePath,
            documentUploadStatus = if (documentFile != null) "PENDING" else "NONE",
            syncDirty = true,
            localMutationSeq = 1L
        )
        permitDao.upsert(permit)
        triggerSync()
    }

    suspend fun editSiteLogNotesOffline(logId: String, notes: String) {
        val existing = siteLogDao.getById(logId) ?: return
        val nowIso = clock.instant().toString()
        val updated = existing.copy(
            notes = notes.trim().takeIf { it.isNotEmpty() },
            editedByHuman = true,
            clientUpdatedAt = nowIso,
            updatedAt = nowIso,
            syncDirty = true,
            localMutationSeq = existing.localMutationSeq + 1L,
            syncError = null
        )
        siteLogDao.upsert(updated)
        triggerSync()
    }

    suspend fun softDeleteSiteLogOffline(logId: String) {
        val existing = siteLogDao.getById(logId) ?: return
        val nowIso = clock.instant().toString()
        val deleted = existing.copy(
            deletedAt = nowIso,
            clientUpdatedAt = nowIso,
            updatedAt = nowIso,
            syncDirty = true,
            localMutationSeq = existing.localMutationSeq + 1L,
            syncError = null
        )
        siteLogDao.upsert(deleted)
        triggerSync()
    }

    suspend fun editPermitOffline(
        permitId: String,
        permitName: String,
        authority: String,
        permitNumber: String?,
        issueDate: String?,
        expiryDate: String
    ) {
        val existing = permitDao.getById(permitId) ?: return
        val nowIso = clock.instant().toString()
        val updated = existing.copy(
            permitName = permitName.trim(),
            authority = authority.trim(),
            permitNumber = permitNumber?.trim()?.takeIf { it.isNotEmpty() },
            issueDate = issueDate?.trim()?.takeIf { it.isNotEmpty() },
            expiryDate = expiryDate.trim(),
            clientUpdatedAt = nowIso,
            updatedAt = nowIso,
            syncDirty = true,
            localMutationSeq = existing.localMutationSeq + 1L,
            syncError = null
        )
        permitDao.upsert(updated)
        triggerSync()
    }

    suspend fun softDeletePermitOffline(permitId: String) {
        val existing = permitDao.getById(permitId) ?: return
        val nowIso = clock.instant().toString()
        val deleted = existing.copy(
            deletedAt = nowIso,
            clientUpdatedAt = nowIso,
            updatedAt = nowIso,
            syncDirty = true,
            localMutationSeq = existing.localMutationSeq + 1L,
            syncError = null
        )
        permitDao.upsert(deleted)
        triggerSync()
    }

    suspend fun triggerSync() {
        val mobileData = appPreferences.uploadOnMobileData.first()
        syncScheduler.scheduleImmediateSync(mobileData)
    }

    suspend fun setUploadOnMobileData(enabled: Boolean) {
        appPreferences.setUploadOnMobileData(enabled)
        syncScheduler.rescheduleMediaUpload(enabled)
    }
}

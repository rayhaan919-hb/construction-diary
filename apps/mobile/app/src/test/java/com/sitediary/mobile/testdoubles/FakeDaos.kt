package com.sitediary.mobile.testdoubles

import com.sitediary.mobile.data.local.dao.PermitDao
import com.sitediary.mobile.data.local.dao.ProjectDao
import com.sitediary.mobile.data.local.dao.ProjectMemberDao
import com.sitediary.mobile.data.local.dao.SiteLogDao
import com.sitediary.mobile.data.local.dao.SiteLogPhotoDao
import com.sitediary.mobile.data.local.dao.SiteLogWithPhotos
import com.sitediary.mobile.data.local.dao.SyncCursorDao
import com.sitediary.mobile.data.local.entity.PermitEntity
import com.sitediary.mobile.data.local.entity.ProjectEntity
import com.sitediary.mobile.data.local.entity.ProjectMemberEntity
import com.sitediary.mobile.data.local.entity.SiteLogEntity
import com.sitediary.mobile.data.local.entity.SiteLogPhotoEntity
import com.sitediary.mobile.data.local.entity.SyncCursorEntity
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.combine
import kotlinx.coroutines.flow.map

class FakeProjectDao : ProjectDao {
    private val store = MutableStateFlow<Map<String, ProjectEntity>>(emptyMap())

    override fun observeActiveProjectsForUser(userId: String): Flow<List<ProjectEntity>> =
        store.map { map -> map.values.filter { it.deletedAt == null }.sortedBy { it.name } }

    override fun observeProject(projectId: String): Flow<ProjectEntity?> =
        store.map { map -> map[projectId]?.takeIf { it.deletedAt == null } }

    override suspend fun getById(projectId: String): ProjectEntity? = store.value[projectId]

    override suspend fun getAllActiveProjectIds(): List<String> =
        store.value.values.filter { it.deletedAt == null }.map { it.id }

    override suspend fun upsertAll(projects: List<ProjectEntity>) {
        store.value = store.value.toMutableMap().apply {
            projects.forEach { put(it.id, it) }
        }
    }

    override suspend fun deleteById(projectId: String) {
        store.value = store.value.toMutableMap().apply { remove(projectId) }
    }

    override suspend fun deleteAll() {
        store.value = emptyMap()
    }
}

class FakeProjectMemberDao : ProjectMemberDao {
    private val store = MutableStateFlow<Map<Pair<String, String>, ProjectMemberEntity>>(emptyMap())

    override suspend fun getMembership(projectId: String, userId: String): ProjectMemberEntity? =
        store.value[projectId to userId]

    override suspend fun getActiveProjectIdsForUser(userId: String): List<String> =
        store.value.values
            .filter { it.userId == userId && it.deletedAt == null }
            .map { it.projectId }

    override suspend fun upsertAll(members: List<ProjectMemberEntity>) {
        store.value = store.value.toMutableMap().apply {
            members.forEach { put(it.projectId to it.userId, it) }
        }
    }

    override suspend fun deleteByProjectId(projectId: String) {
        store.value = store.value.filterKeys { it.first != projectId }
    }

    override suspend fun deleteAll() {
        store.value = emptyMap()
    }
}

class FakePermitDao : PermitDao {
    private val store = MutableStateFlow<Map<String, PermitEntity>>(emptyMap())

    override fun observeByProject(projectId: String): Flow<List<PermitEntity>> =
        store.map { map ->
            map.values
                .filter { it.projectId == projectId && it.deletedAt == null }
                .sortedBy { it.expiryDate }
        }

    override fun observeAllActive(): Flow<List<PermitEntity>> =
        store.map { map -> map.values.filter { it.deletedAt == null } }

    override suspend fun getById(id: String): PermitEntity? = store.value[id]

    override suspend fun getDirtyBatch(limit: Int): List<PermitEntity> =
        store.value.values.filter { it.syncDirty }.take(limit)

    override fun observeDirtyCount(): Flow<Int> =
        store.map { map -> map.values.count { it.syncDirty } }

    override suspend fun getPendingDocumentUploads(): List<PermitEntity> =
        store.value.values.filter {
            it.deletedAt == null && it.documentLocalPath != null && it.documentUploadStatus == "PENDING"
        }

    override suspend fun getDocumentsEligibleForPurge(cutoffEpochMs: Long): List<PermitEntity> =
        store.value.values.filter {
            it.documentLocalPath != null &&
                it.documentUploadStatus == "UPLOADED" &&
                it.documentUploadedAtEpochMs != null &&
                it.documentUploadedAtEpochMs < cutoffEpochMs
        }

    override suspend fun getLocalPathsForProject(projectId: String): List<String> =
        store.value.values
            .filter { it.projectId == projectId }
            .mapNotNull { it.documentLocalPath }

    override suspend fun upsert(permit: PermitEntity) {
        store.value = store.value.toMutableMap().apply { put(permit.id, permit) }
    }

    override suspend fun upsertAll(permits: List<PermitEntity>) {
        store.value = store.value.toMutableMap().apply {
            permits.forEach { put(it.id, it) }
        }
    }

    override suspend fun markSyncedIfSeqMatches(id: String, expectedSeq: Long, serverVersion: Long) {
        val current = store.value[id] ?: return
        if (current.localMutationSeq == expectedSeq) {
            upsert(current.copy(syncDirty = false, serverVersion = serverVersion, syncError = null))
        }
    }

    override suspend fun markSyncRejectedIfSeqMatches(id: String, expectedSeq: Long, error: String) {
        val current = store.value[id] ?: return
        if (current.localMutationSeq == expectedSeq) {
            upsert(current.copy(syncDirty = false, syncError = error))
        }
    }

    override suspend fun setDocumentStorageUriAndMarkDirty(id: String, storageUri: String) {
        val current = store.value[id] ?: return
        upsert(
            current.copy(
                documentPhotoUri = storageUri,
                syncDirty = true,
                localMutationSeq = current.localMutationSeq + 1L
            )
        )
    }

    override suspend fun markDocumentUploaded(id: String, uploadedAtEpochMs: Long) {
        val current = store.value[id] ?: return
        upsert(
            current.copy(
                documentUploadStatus = "UPLOADED",
                documentUploadedAtEpochMs = uploadedAtEpochMs
            )
        )
    }

    override suspend fun clearDocumentLocalPath(id: String) {
        val current = store.value[id] ?: return
        upsert(current.copy(documentLocalPath = null))
    }

    override suspend fun deleteByProjectId(projectId: String) {
        store.value = store.value.filterValues { it.projectId != projectId }
    }

    override suspend fun deleteAll() {
        store.value = emptyMap()
    }
}

class FakeSiteLogDao(
    private val photoDao: FakeSiteLogPhotoDao
) : SiteLogDao {
    private val store = MutableStateFlow<Map<String, SiteLogEntity>>(emptyMap())

    override fun observeLogsWithPhotosByProject(projectId: String): Flow<List<SiteLogWithPhotos>> =
        combine(store, photoDao.store) { logs, photos ->
            logs.values
                .filter { it.projectId == projectId && it.deletedAt == null }
                .sortedWith(compareByDescending<SiteLogEntity> { it.logDate }.thenByDescending { it.recordedAt })
                .map { log ->
                    SiteLogWithPhotos(
                        log = log,
                        photos = photos.values.filter { it.siteLogId == log.id }
                    )
                }
        }

    override fun observeLogWithPhotos(logId: String): Flow<SiteLogWithPhotos?> =
        combine(store, photoDao.store) { logs, photos ->
            val log = logs[logId]?.takeIf { it.deletedAt == null } ?: return@combine null
            SiteLogWithPhotos(
                log = log,
                photos = photos.values.filter { it.siteLogId == log.id }
            )
        }

    override fun observeAllActive(): Flow<List<SiteLogEntity>> =
        store.map { map -> map.values.filter { it.deletedAt == null } }

    override suspend fun getById(id: String): SiteLogEntity? = store.value[id]

    override suspend fun getDirtyBatch(limit: Int): List<SiteLogEntity> =
        store.value.values.filter { it.syncDirty }.take(limit)

    override fun observeDirtyCount(): Flow<Int> =
        store.map { map -> map.values.count { it.syncDirty } }

    override suspend fun getPendingAudioUploads(): List<SiteLogEntity> =
        store.value.values.filter {
            it.deletedAt == null && it.audioLocalPath != null && it.audioUploadStatus == "PENDING"
        }

    override suspend fun getAudioEligibleForPurge(cutoffEpochMs: Long): List<SiteLogEntity> =
        store.value.values.filter {
            it.audioLocalPath != null &&
                it.audioUploadStatus == "UPLOADED" &&
                it.audioUploadedAtEpochMs != null &&
                it.audioUploadedAtEpochMs < cutoffEpochMs
        }

    override suspend fun getLocalAudioPathsForProject(projectId: String): List<String> =
        store.value.values.filter { it.projectId == projectId }.mapNotNull { it.audioLocalPath }

    override suspend fun upsert(log: SiteLogEntity) {
        store.value = store.value.toMutableMap().apply { put(log.id, log) }
    }

    override suspend fun upsertAll(logs: List<SiteLogEntity>) {
        store.value = store.value.toMutableMap().apply {
            logs.forEach { put(it.id, it) }
        }
    }

    override suspend fun markSyncedIfSeqMatches(id: String, expectedSeq: Long, serverVersion: Long) {
        val current = store.value[id] ?: return
        if (current.localMutationSeq == expectedSeq) {
            upsert(current.copy(syncDirty = false, serverVersion = serverVersion, syncError = null))
        }
    }

    override suspend fun markSyncRejectedIfSeqMatches(id: String, expectedSeq: Long, error: String) {
        val current = store.value[id] ?: return
        if (current.localMutationSeq == expectedSeq) {
            upsert(current.copy(syncDirty = false, syncError = error))
        }
    }

    override suspend fun setAudioStorageUriAndMarkDirty(id: String, storageUri: String) {
        val current = store.value[id] ?: return
        upsert(
            current.copy(
                audioUri = storageUri,
                syncDirty = true,
                localMutationSeq = current.localMutationSeq + 1L
            )
        )
    }

    override suspend fun markAudioUploaded(id: String, uploadedAtEpochMs: Long) {
        val current = store.value[id] ?: return
        upsert(
            current.copy(
                audioUploadStatus = "UPLOADED",
                audioUploadedAtEpochMs = uploadedAtEpochMs,
                extractionStatus = if (current.extractionStatus == "DONE") "DONE" else "PENDING"
            )
        )
    }

    override suspend fun updateExtractionStatus(id: String, status: String) {
        val current = store.value[id] ?: return
        upsert(current.copy(extractionStatus = status))
    }

    override suspend fun clearAudioLocalPath(id: String) {
        val current = store.value[id] ?: return
        upsert(current.copy(audioLocalPath = null))
    }

    override suspend fun deleteByProjectId(projectId: String) {
        store.value = store.value.filterValues { it.projectId != projectId }
    }

    override suspend fun deleteAll() {
        store.value = emptyMap()
    }
}

class FakeSiteLogPhotoDao : SiteLogPhotoDao {
    val store = MutableStateFlow<Map<String, SiteLogPhotoEntity>>(emptyMap())

    override suspend fun getById(id: String): SiteLogPhotoEntity? = store.value[id]

    override suspend fun getDirtyPushableBatch(limit: Int): List<SiteLogPhotoEntity> =
        store.value.values.filter { it.syncDirty && it.storageUri.isNotEmpty() }.take(limit)

    override fun observePendingCount(): Flow<Int> =
        store.map { map ->
            map.values.count { it.syncDirty || (it.uploadStatus == "PENDING" && it.deletedAt == null) }
        }

    override suspend fun getPendingUploads(): List<SiteLogPhotoEntity> =
        store.value.values.filter {
            it.deletedAt == null && it.localPath != null && it.uploadStatus == "PENDING"
        }

    override suspend fun getEligibleForPurge(cutoffEpochMs: Long): List<SiteLogPhotoEntity> =
        store.value.values.filter {
            it.localPath != null &&
                it.uploadStatus == "UPLOADED" &&
                it.uploadedAtEpochMs != null &&
                it.uploadedAtEpochMs < cutoffEpochMs
        }

    override suspend fun getLocalPathsForProject(projectId: String): List<String> =
        store.value.values.filter { it.projectId == projectId }.mapNotNull { it.localPath }

    override suspend fun upsertAll(photos: List<SiteLogPhotoEntity>) {
        store.value = store.value.toMutableMap().apply {
            photos.forEach { put(it.id, it) }
        }
    }

    override suspend fun markSyncedIfSeqMatches(id: String, expectedSeq: Long, serverVersion: Long) {
        val current = store.value[id] ?: return
        if (current.localMutationSeq == expectedSeq) {
            upsertAll(listOf(current.copy(syncDirty = false, serverVersion = serverVersion, syncError = null)))
        }
    }

    override suspend fun markSyncRejectedIfSeqMatches(id: String, expectedSeq: Long, error: String) {
        val current = store.value[id] ?: return
        if (current.localMutationSeq == expectedSeq) {
            upsertAll(listOf(current.copy(syncDirty = false, syncError = error)))
        }
    }

    override suspend fun setStorageUriAndMarkDirty(id: String, storageUri: String) {
        val current = store.value[id] ?: return
        upsertAll(
            listOf(
                current.copy(
                    storageUri = storageUri,
                    syncDirty = true,
                    localMutationSeq = current.localMutationSeq + 1L
                )
            )
        )
    }

    override suspend fun markUploaded(id: String, uploadedAtEpochMs: Long) {
        val current = store.value[id] ?: return
        upsertAll(listOf(current.copy(uploadStatus = "UPLOADED", uploadedAtEpochMs = uploadedAtEpochMs)))
    }

    override suspend fun clearLocalPath(id: String) {
        val current = store.value[id] ?: return
        upsertAll(listOf(current.copy(localPath = null)))
    }

    override suspend fun deleteByProjectId(projectId: String) {
        store.value = store.value.filterValues { it.projectId != projectId }
    }

    override suspend fun deleteAll() {
        store.value = emptyMap()
    }
}

class FakeSyncCursorDao : SyncCursorDao {
    private val store = mutableMapOf<String, SyncCursorEntity>()

    override suspend fun getCursor(scopeKey: String): Long? = store[scopeKey]?.cursor

    override suspend fun upsert(entity: SyncCursorEntity) {
        store[entity.scopeKey] = entity
    }

    override suspend fun deleteByScope(scopeKey: String) {
        store.remove(scopeKey)
    }

    override suspend fun deleteAll() {
        store.clear()
    }
}

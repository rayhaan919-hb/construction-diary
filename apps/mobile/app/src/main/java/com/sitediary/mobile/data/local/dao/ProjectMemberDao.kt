package com.sitediary.mobile.data.local.dao

import androidx.room.Dao
import androidx.room.Insert
import androidx.room.OnConflictStrategy
import androidx.room.Query
import com.sitediary.mobile.data.local.entity.ProjectMemberEntity

@Dao
interface ProjectMemberDao {
    @Query("SELECT * FROM project_members WHERE project_id = :projectId AND user_id = :userId")
    suspend fun getMembership(projectId: String, userId: String): ProjectMemberEntity?

    @Query("SELECT project_id FROM project_members WHERE user_id = :userId AND deleted_at IS NULL")
    suspend fun getActiveProjectIdsForUser(userId: String): List<String>

    @Insert(onConflict = OnConflictStrategy.REPLACE)
    suspend fun upsertAll(members: List<ProjectMemberEntity>)

    @Query("DELETE FROM project_members WHERE project_id = :projectId")
    suspend fun deleteByProjectId(projectId: String)

    @Query("DELETE FROM project_members")
    suspend fun deleteAll()
}

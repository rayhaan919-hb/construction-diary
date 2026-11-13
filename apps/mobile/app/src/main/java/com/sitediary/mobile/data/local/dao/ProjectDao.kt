package com.sitediary.mobile.data.local.dao

import androidx.room.Dao
import androidx.room.Insert
import androidx.room.OnConflictStrategy
import androidx.room.Query
import com.sitediary.mobile.data.local.entity.ProjectEntity
import kotlinx.coroutines.flow.Flow

@Dao
interface ProjectDao {
    @Query(
        """
        SELECT p.* FROM projects p
        INNER JOIN project_members pm ON pm.project_id = p.id
        WHERE p.deleted_at IS NULL
          AND pm.user_id = :userId
          AND pm.deleted_at IS NULL
        ORDER BY p.name ASC
        """
    )
    fun observeActiveProjectsForUser(userId: String): Flow<List<ProjectEntity>>

    @Query("SELECT * FROM projects WHERE id = :projectId AND deleted_at IS NULL")
    fun observeProject(projectId: String): Flow<ProjectEntity?>

    @Query("SELECT * FROM projects WHERE id = :projectId")
    suspend fun getById(projectId: String): ProjectEntity?

    @Query("SELECT id FROM projects WHERE deleted_at IS NULL")
    suspend fun getAllActiveProjectIds(): List<String>

    @Insert(onConflict = OnConflictStrategy.REPLACE)
    suspend fun upsertAll(projects: List<ProjectEntity>)

    @Query("DELETE FROM projects WHERE id = :projectId")
    suspend fun deleteById(projectId: String)

    @Query("DELETE FROM projects")
    suspend fun deleteAll()
}

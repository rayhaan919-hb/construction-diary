package com.sitediary.mobile.data.local.dao

import androidx.room.Dao
import androidx.room.Insert
import androidx.room.OnConflictStrategy
import androidx.room.Query
import com.sitediary.mobile.data.local.entity.SyncCursorEntity

@Dao
interface SyncCursorDao {
    @Query("SELECT cursor FROM sync_cursors WHERE scope_key = :scopeKey")
    suspend fun getCursor(scopeKey: String): Long?

    @Insert(onConflict = OnConflictStrategy.REPLACE)
    suspend fun upsert(entity: SyncCursorEntity)

    @Query("DELETE FROM sync_cursors WHERE scope_key = :scopeKey")
    suspend fun deleteByScope(scopeKey: String)

    @Query("DELETE FROM sync_cursors")
    suspend fun deleteAll()
}

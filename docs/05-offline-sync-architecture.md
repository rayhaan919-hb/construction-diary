# 05 — Offline-First Synchronization Engine (Android + FastAPI)

Offline-first sync guarantees that no construction log, photo, audio memo, or permit update created in low/zero connectivity is ever lost or duplicated.

---

## Database Sync Primitives (`services/api/app/db/models.py`)

- Monotonic big-integer `sync_events.seq` records every project change (`projects`, `project_members`, `permits`, `site_logs`, `site_log_photos`).
- Server entities maintain `server_version`, `client_updated_at`, and soft-delete tombstones (`deleted_at`).
- Alembic migration `0002_commercial_saas_hardening.py` adds indexes for fast cursor scans and tenant-scoped delta retrieval.

---

## Android Local Queue & Mutation Tracking (`apps/mobile`)

- Entities (`SiteLogEntity`, `SiteLogPhotoEntity`, `PermitEntity`) store `syncDirty`, `localMutationSeq`, `syncError`, `serverVersion`, and `deletedAt`.
- Offline writes increment `localMutationSeq` atomically before scheduling `SyncScheduler.scheduleImmediateSync()`.
- Push acknowledgements call `markSyncedIfSeqMatches(id, expectedSeq, serverVersion)` so a mid-flight offline edit made *after* a batch started never gets mistakenly marked clean (`SyncEngineTest` verifies this concurrency guard).

---

## Conflict Detection & Resolution

1. Client pushes batches of up to `MAX_PUSH_BATCH = 200` dirty records (`permits`, `siteLogs`, `siteLogPhotos` with canonical `storageUri`).
2. When the backend returns `status = "CONFLICT"` (server version advanced concurrently):
   - `SyncEngine` calls `markSyncConflictIfSeqMatches(...)`, preserving `syncDirty = true` and recording a `CONFLICT_PENDING: ...` error badge rather than discarding the field worker's changes.
   - Conflicted entity IDs are tracked for the remainder of the current `pushPendingChanges()` loop to prevent tight retry spin.
3. During `pullAndBackfill()`, when an incoming server DTO matches a locally `syncDirty` log:
   - Server extraction metadata (`transcript`, `extractionStatus`, `audioUrl`, `serverVersion`) merges forward cleanly.
   - Local `notes`, `deletedAt`, and `structuredSummary` (when `editedByHuman = true`) remain preserved for user review/re-push.

---

## Scoped Project Backfill & Tombstone Purging

- Discovering a new `ProjectMemberEntity` triggers persisted `backfill:<projectId>` cursor markers in `sync_cursors`.
- Interruption or app restart resumes unfinished project backfills seamlessly.
- Removing a user's project membership or soft-deleting a project sets a tombstone that cascades across Room (`purgeProjectDbRows`) and deletes all cached local media files (`LocalMediaFileManager.deleteProjectMedia`).
- Remote photo tombstones (`deletedAt != null`) delete both the local photo file on disk and the `site_log_photos` Room row.

---

## Background Workers & Network Constraints

- `ConnectivityObserver` monitors live connectivity and drives `OfflineStatusBanner` in Compose UI plus immediate foreground sync recovery on network restoration.
- `MediaUploadWorker` respects the user's `uploadOnMobileData` DataStore toggle (`NetworkType.UNMETERED` vs `NetworkType.CONNECTED`) with exponential WorkManager backoff.
- `MediaRetentionWorker` purges uploaded local files older than 7 days while retaining DB summaries.

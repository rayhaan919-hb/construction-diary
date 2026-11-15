# 07 — AI Extraction & Durable Asynchronous Worker Pipeline

Construction Diary extracts structured daily progress summaries (`tasks_completed`, `labor_count`, `material_deliveries`, `blockers`, bilingual transcripts, and `detected_language`) from field audio notes using Google Vertex AI / Gemini (`services/api/app/services/ai_extractor.py`) and durable background queues (`services/api/app/services/extraction_worker.py`).

---

## Durable Queue (`extraction_jobs` Table)

Rather than firing fragile in-process tasks that vanish on container restart:
1. Uploading `AUDIO` via `/v1/media/complete` or hitting `POST /v1/logs/{id}/extract` calls `enqueue_extraction_job()`.
2. A unique pending/processing constraint prevents duplicate queued jobs for the same `site_log_id`.
3. Each `ExtractionJob` stores `status` (`QUEUED`, `RUNNING`, `SUCCEEDED`, `FAILED`), `attempts`, `max_attempts`, `lease_expires_at`, `available_at`, and `last_error`.
4. When `CLOUD_TASKS_QUEUE_PATH` and `CLOUD_TASKS_HANDLER_URL` are configured (Cloud Run production), `enqueue_extraction_job()` dispatches an OIDC-authenticated Cloud Task to `POST /internal/tasks/extract` protected by both `X-CloudTasks-Secret` and Cloud Tasks identity headers.
5. In local/test runs without Cloud Tasks, an idempotent lease-locked execution executes safely via database state transitions.

---

## Stale Lease Recovery & Retry Logic

- Workers claim a job using PostgreSQL `SELECT ... FOR UPDATE SKIP LOCKED` and set `lease_expires_at = now + EXTRACTION_STALE_LEASE_SECONDS`.
- If a Cloud Run worker crashes mid-flight, another worker reclaims the expired lease cleanly (`reclaim_stale_jobs`).
- Transient failures schedule exponential backoff until `attempts >= EXTRACTION_MAX_ATTEMPTS`, transitioning `site_logs.extraction_status` to `FAILED` while preserving raw audio so owners/supervisors can manually retry extraction or correct the summary.

---

## Validation & Human Edit Preservation

- AI JSON responses are strictly validated against `StructuredSummary` Pydantic models before DB writes; malformed JSON or schema violations fail cleanly with truncated diagnostic messages.
- Setting `edited_by_human = true` locks the structured summary against subsequent AI overwrites during future retries or Android delta sync pulls.

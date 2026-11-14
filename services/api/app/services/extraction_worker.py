from __future__ import annotations

import base64
import logging
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID

import google.auth
import httpx
from google.auth.transport.requests import Request as GoogleAuthRequest
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import Settings, get_settings
from app.core.logging_config import safe_public_error_summary
from app.db.models import (
    ExtractionJob,
    Organization,
    Permit,
    SiteLog,
    SiteLogPhoto,
)
from app.db.session import create_session_factory
from app.services.ai_extractor import (
    ExtractionError,
    extract_from_audio_with_model,
    extract_from_permit_document,
    extract_from_photo,
    extract_from_text_notes,
)
from app.services.storage import MediaStorageService

logger = logging.getLogger(__name__)

_CLOUD_TASKS_SCOPE = "https://www.googleapis.com/auth/cloud-platform"


def _dispatch_to_cloud_tasks(job: ExtractionJob, settings: Settings) -> str | None:
    """Enqueue an ExtractionJob to Google Cloud Tasks when configured; return task name."""
    if not settings.CLOUD_TASKS_QUEUE_PATH or not settings.CLOUD_TASKS_HANDLER_URL:
        return None
    target_url = f"{settings.CLOUD_TASKS_HANDLER_URL.rstrip('/')}/v1/internal/tasks/extraction"
    payload = {"job_id": str(job.id)}
    body_bytes = httpx.Request("POST", target_url, json=payload).content

    http_request: dict[str, Any] = {
        "httpMethod": "POST",
        "url": target_url,
        "headers": {"Content-Type": "application/json"},
        "body": base64.b64encode(body_bytes).decode("ascii"),
    }
    if settings.CLOUD_TASKS_SHARED_SECRET:
        http_request["headers"]["X-Task-Secret"] = settings.CLOUD_TASKS_SHARED_SECRET
    if settings.CLOUD_TASKS_INVOKER_SA_EMAIL:
        http_request["oidcToken"] = {
            "serviceAccountEmail": settings.CLOUD_TASKS_INVOKER_SA_EMAIL,
            "audience": settings.CLOUD_TASKS_HANDLER_URL.rstrip("/"),
        }

    creds, _ = google.auth.default(scopes=[_CLOUD_TASKS_SCOPE])
    creds.refresh(GoogleAuthRequest())  # type: ignore[no-untyped-call]
    token = getattr(creds, "token", None)
    if not token:
        raise RuntimeError("Could not obtain ADC access token for Cloud Tasks")

    api_url = f"https://cloudtasks.googleapis.com/v2/{settings.CLOUD_TASKS_QUEUE_PATH}/tasks"
    with httpx.Client(timeout=10.0) as client:
        resp = client.post(
            api_url,
            headers={"Authorization": f"Bearer {token}"},
            json={"task": {"httpRequest": http_request}},
        )
    if resp.status_code not in (200, 201):
        raise RuntimeError(f"Cloud Tasks enqueue failed HTTP {resp.status_code}")
    return str(resp.json().get("name") or "")


def enqueue_extraction_job(
    db: Session,
    *,
    organization_id: UUID | None,
    project_id: UUID,
    target_type: str,
    target_id: UUID,
    idempotency_key: str,
    settings: Settings,
    force_reset: bool = False,
) -> tuple[ExtractionJob, bool]:
    """Create or reuse a durable ExtractionJob row idempotently.

    Returns ``(job, should_dispatch_local)``.
    """
    now = datetime.now(UTC)
    existing = db.scalar(
        select(ExtractionJob).where(ExtractionJob.idempotency_key == idempotency_key)
    )
    if existing is not None:
        if force_reset and existing.status in ("FAILED", "COMPLETED", "CANCELED"):
            existing.status = "PENDING"
            existing.attempts = 0
            existing.next_run_at = now
            existing.locked_until = None
            existing.last_error = None
            existing.updated_at = now
            db.flush()
        elif existing.status in ("PENDING", "PROCESSING", "COMPLETED"):
            return existing, False
    else:
        stmt = (
            pg_insert(ExtractionJob)
            .values(
                organization_id=organization_id,
                project_id=project_id,
                target_type=target_type,
                target_id=target_id,
                idempotency_key=idempotency_key,
                status="PENDING",
                attempts=0,
                max_attempts=max(settings.EXTRACTION_MAX_ATTEMPTS, 1),
                next_run_at=now,
            )
            .on_conflict_do_nothing(index_elements=["idempotency_key"])
            .returning(ExtractionJob.id)
        )
        new_id = db.scalar(stmt)
        if new_id is not None:
            existing = db.get(ExtractionJob, new_id)
        else:
            existing = db.scalar(
                select(ExtractionJob).where(ExtractionJob.idempotency_key == idempotency_key)
            )

    assert existing is not None
    cloud_task_used = False
    if settings.CLOUD_TASKS_QUEUE_PATH and settings.CLOUD_TASKS_HANDLER_URL:
        try:
            task_name = _dispatch_to_cloud_tasks(existing, settings)
            existing.cloud_task_name = task_name
            cloud_task_used = True
        except Exception as exc:
            # Keep job durable in DB so local/recovery sweep picks it up; never discard!
            logger.warning(
                "Cloud Tasks enqueue failed for job %s; falling back to local execution (%s)",
                existing.id,
                type(exc).__name__,
            )
    return existing, (not cloud_task_used)


def _increment_org_ai_usage(db: Session, org_id: UUID | None) -> None:
    if org_id is None:
        return
    org = db.scalar(select(Organization).where(Organization.id == org_id).with_for_update())
    if org is None:
        return
    current_month = datetime.now(UTC).strftime("%Y-%m")
    if org.billing_month != current_month:
        org.billing_month = current_month
        org.ai_extractions_this_month = 1
    else:
        org.ai_extractions_this_month = int(org.ai_extractions_this_month or 0) + 1


def _guess_mime_from_uri(uri: str | None, default: str) -> str:
    if not uri:
        return default
    lowered = uri.lower()
    if lowered.endswith(".png"):
        return "image/png"
    if lowered.endswith(".webp"):
        return "image/webp"
    if lowered.endswith(".pdf"):
        return "application/pdf"
    if lowered.endswith(".jpg") or lowered.endswith(".jpeg"):
        return "image/jpeg"
    if lowered.endswith(".m4a"):
        return "audio/mp4"
    return default


def execute_extraction_job(
    job_id: UUID,
    session_factory: sessionmaker[Session],
    settings: Settings | None = None,
    *,
    worker_id: str | None = None,
) -> None:
    """Claim and run a single ExtractionJob durably with row locking and sanitized errors."""
    cfg = settings or get_settings()
    storage = MediaStorageService(cfg)
    active_worker = worker_id or f"worker-{uuid.uuid4().hex[:8]}"
    now = datetime.now(UTC)

    with session_factory() as db:
        job = db.scalar(
            select(ExtractionJob)
            .where(ExtractionJob.id == job_id)
            .with_for_update(skip_locked=True)
        )
        if job is None:
            return
        if job.status in ("COMPLETED", "CANCELED"):
            return
        if job.status == "FAILED" and job.attempts >= job.max_attempts:
            return
        if (
            job.status == "PROCESSING"
            and job.locked_until is not None
            and job.locked_until > now
        ):
            return

        job.status = "PROCESSING"
        job.attempts = int(job.attempts or 0) + 1
        job.worker_id = active_worker
        job.locked_until = now + timedelta(seconds=cfg.EXTRACTION_STALE_LEASE_SECONDS)
        job.updated_at = now
        target_type = job.target_type
        target_id = job.target_id
        org_id = job.organization_id

        # Snapshot inputs cleanly inside transaction before external AI call
        audio_uri: str | None = None
        notes_text: str | None = None
        photo_uri: str | None = None
        permit_uri: str | None = None
        if target_type == "SITE_LOG":
            log = db.get(SiteLog, target_id)
            if log is None or log.deleted_at is not None:
                job.status = "CANCELED"
                job.locked_until = None
                db.commit()
                return
            audio_uri = log.audio_uri if log.audio_upload_status == "UPLOADED" else None
            notes_text = log.notes
            log.extraction_status = "PROCESSING"
            log.extraction_attempts = job.attempts
            log.extraction_error = None
        elif target_type == "SITE_LOG_PHOTO":
            photo = db.get(SiteLogPhoto, target_id)
            if photo is None or photo.deleted_at is not None or photo.upload_status != "UPLOADED":
                job.status = "CANCELED"
                job.locked_until = None
                db.commit()
                return
            photo_uri = photo.storage_uri
        elif target_type == "PERMIT":
            permit = db.get(Permit, target_id)
            if permit is None or permit.deleted_at is not None or not permit.document_photo_uri:
                job.status = "CANCELED"
                job.locked_until = None
                db.commit()
                return
            permit_uri = permit.document_photo_uri

        db.commit()

    # Run Gemini / mock extraction outside DB transaction so locks aren't held over network I/O
    result_dict: dict[str, Any] = {}
    model_used = "unknown"
    try:
        if target_type == "SITE_LOG":
            if audio_uri:
                ext_res, model_used = extract_from_audio_with_model(
                    audio_uri,
                    storage_service=storage,
                    settings=cfg,
                    notes_hint=notes_text,
                )
            elif notes_text and notes_text.strip():
                ext_res, model_used = extract_from_text_notes(
                    notes_text,
                    settings=cfg,
                )
            else:
                raise ExtractionError("No audio or notes available to extract", retryable=False)
            result_dict = {
                "transcript": ext_res.transcript,
                "detected_language": ext_res.detected_language,
                "structured_summary": ext_res.structured_summary.model_dump(),
            }
        elif target_type == "SITE_LOG_PHOTO":
            assert photo_uri is not None
            mime = _guess_mime_from_uri(photo_uri, "image/jpeg")
            photo_res, model_used = extract_from_photo(
                photo_uri,
                mime_type=mime,  # type: ignore[arg-type]
                storage_service=storage,
                settings=cfg,
            )
            result_dict = photo_res.model_dump(mode="json")
        elif target_type == "PERMIT":
            assert permit_uri is not None
            mime = _guess_mime_from_uri(permit_uri, "image/jpeg")
            permit_res, model_used = extract_from_permit_document(
                permit_uri,
                mime_type=mime,
                storage_service=storage,
                settings=cfg,
            )
            result_dict = permit_res.model_dump(mode="json")
    except ExtractionError as exc:
        _handle_job_failure(
            job_id=job_id,
            session_factory=session_factory,
            err_msg=safe_public_error_summary(exc, fallback="Extraction failed"),
            retryable=exc.retryable,
            cfg=cfg,
        )
        return
    except Exception as exc:
        logger.exception("Unexpected error in extraction job %s", job_id)
        _handle_job_failure(
            job_id=job_id,
            session_factory=session_factory,
            err_msg=safe_public_error_summary(exc, fallback="Extraction processing error"),
            retryable=True,
            cfg=cfg,
        )
        return

    # Persist successful results atomically under row lock
    done_at = datetime.now(UTC)
    with session_factory() as db:
        job = db.scalar(
            select(ExtractionJob).where(ExtractionJob.id == job_id).with_for_update()
        )
        if job is None:
            return
        job.status = "COMPLETED"
        job.locked_until = None
        job.last_error = None
        job.model_name = model_used
        job.result_payload = result_dict
        job.completed_at = done_at
        job.updated_at = done_at

        if target_type == "SITE_LOG":
            log = db.scalar(
                select(SiteLog).where(SiteLog.id == target_id).with_for_update()
            )
            if log is not None:
                # Preserve human edits monotonically; AI cannot clobber human corrections
                if not log.edited_by_human:
                    log.transcript = result_dict["transcript"]
                    log.detected_language = result_dict["detected_language"]
                    log.structured_summary = result_dict["structured_summary"]
                log.extraction_status = "DONE"
                log.extraction_model = model_used
                log.extracted_at = done_at
                log.extraction_error = None
        elif target_type == "SITE_LOG_PHOTO":
            photo = db.scalar(
                select(SiteLogPhoto).where(SiteLogPhoto.id == target_id).with_for_update()
            )
            if photo is not None:
                photo.ai_caption = result_dict.get("caption")
                photo.ai_labels = {
                    "work_items": result_dict.get("work_items", []),
                    "safety_hazards": result_dict.get("safety_hazards", []),
                    "materials_visible": result_dict.get("materials_visible", []),
                    "model": model_used,
                }
        elif target_type == "PERMIT":
            permit = db.scalar(
                select(Permit).where(Permit.id == target_id).with_for_update()
            )
            if permit is not None:
                permit.ai_extracted_data = {**result_dict, "model": model_used}

        _increment_org_ai_usage(db, org_id)
        db.commit()


def _handle_job_failure(
    *,
    job_id: UUID,
    session_factory: sessionmaker[Session],
    err_msg: str,
    retryable: bool,
    cfg: Settings,
) -> None:
    now = datetime.now(UTC)
    re_enqueue_cloud = False
    with session_factory() as db:
        job = db.scalar(
            select(ExtractionJob).where(ExtractionJob.id == job_id).with_for_update()
        )
        if job is None:
            return
        can_retry = retryable and job.attempts < job.max_attempts
        job.locked_until = None
        job.last_error = err_msg[:1000]
        job.updated_at = now
        if can_retry:
            backoff_secs = min(2 ** max(job.attempts - 1, 0), 300)
            job.status = "PENDING"
            job.next_run_at = now + timedelta(seconds=backoff_secs)
            re_enqueue_cloud = bool(
                cfg.CLOUD_TASKS_QUEUE_PATH and cfg.CLOUD_TASKS_HANDLER_URL
            )
        else:
            job.status = "FAILED"

        if job.target_type == "SITE_LOG":
            log = db.scalar(
                select(SiteLog).where(SiteLog.id == job.target_id).with_for_update()
            )
            if log is not None:
                log.extraction_attempts = job.attempts
                log.extraction_error = err_msg[:1000]
                log.extraction_status = "PENDING" if can_retry else "FAILED"
        db.commit()

    if re_enqueue_cloud:
        try:
            with session_factory() as db:
                j = db.get(ExtractionJob, job_id)
                if j is not None:
                    _dispatch_to_cloud_tasks(j, cfg)
        except Exception as exc:
            logger.warning(
                "Retry Cloud Task dispatch failed for %s: %s", job_id, type(exc).__name__
            )


def run_extraction_for_log(
    log_id: UUID,
    session_factory: sessionmaker[Session],
    settings: Settings | None = None,
) -> None:
    """Execute extraction for a site log, routing through a durable ExtractionJob."""
    cfg = settings or get_settings()
    with session_factory() as db:
        log = db.scalar(select(SiteLog).where(SiteLog.id == log_id))
        if log is None or log.deleted_at is not None:
            return
        from app.db.models import Project

        proj = db.get(Project, log.project_id)
        org_id = proj.organization_id if proj is not None else None
        # Check for an existing uncompleted job for this log first
        job = db.scalar(
            select(ExtractionJob)
            .where(
                ExtractionJob.target_type == "SITE_LOG",
                ExtractionJob.target_id == log_id,
                ExtractionJob.status.in_(("PENDING", "PROCESSING")),
            )
            .order_by(ExtractionJob.created_at.desc())
        )
        if job is None:
            key = f"SITE_LOG:{log_id}:{log.audio_uri or 'notes'}:{log.server_version}"
            job = db.scalar(select(ExtractionJob).where(ExtractionJob.idempotency_key == key))
            if job is None:
                job = ExtractionJob(
                    organization_id=org_id,
                    project_id=log.project_id,
                    target_type="SITE_LOG",
                    target_id=log_id,
                    idempotency_key=key,
                    status="PENDING",
                    attempts=0,
                    max_attempts=max(cfg.EXTRACTION_MAX_ATTEMPTS, 1),
                    next_run_at=datetime.now(UTC),
                )
                db.add(job)
            else:
                job.status = "PENDING"
                job.attempts = 0
                job.locked_until = None
                job.next_run_at = datetime.now(UTC)
            db.commit()
        job_id = job.id

    # Run synchronously up to max_attempts cleanly if transient without thread stalls in tests
    for _ in range(max(cfg.EXTRACTION_MAX_ATTEMPTS, 1)):
        execute_extraction_job(job_id, session_factory, cfg)
        with session_factory() as db:
            j = db.get(ExtractionJob, job_id)
            if j is None or j.status in ("COMPLETED", "FAILED", "CANCELED"):
                break
            # Force next_run_at due immediately inside direct worker execution loop
            if j.status == "PENDING" and not cfg.CLOUD_TASKS_QUEUE_PATH:
                j.next_run_at = datetime.now(UTC)
                db.commit()


def recover_stuck_extractions(
    session_factory: sessionmaker[Session] | None = None,
    settings: Settings | None = None,
) -> list[UUID]:
    """Reset stale PROCESSING extractions/jobs (including expired leases) and return log UUIDs."""
    cfg = settings or get_settings()
    factory = session_factory or create_session_factory()
    now = datetime.now(UTC)
    recovered_log_ids: list[UUID] = []

    with factory() as db:
        # 1. Release stale PROCESSING jobs whose lease expired
        stale_jobs = list(
            db.scalars(
                select(ExtractionJob)
                .where(
                    ExtractionJob.status == "PROCESSING",
                    (
                        ExtractionJob.locked_until.is_(None)
                        | (ExtractionJob.locked_until <= now)
                    ),
                )
                .with_for_update(skip_locked=True)
            )
        )
        for job in stale_jobs:
            job.status = "PENDING"
            job.locked_until = None
            job.next_run_at = now
            if job.target_type == "SITE_LOG" and job.target_id not in recovered_log_ids:
                recovered_log_ids.append(job.target_id)

        # 2. Recover SiteLogs stuck in PROCESSING/PENDING (backward compat + startup crashes)
        pending_logs = list(
            db.scalars(
                select(SiteLog)
                .where(
                    SiteLog.deleted_at.is_(None),
                    SiteLog.audio_upload_status == "UPLOADED",
                    SiteLog.extraction_status.in_(("PENDING", "PROCESSING")),
                    SiteLog.extraction_attempts < cfg.EXTRACTION_MAX_ATTEMPTS,
                )
                .with_for_update(skip_locked=True)
            )
        )
        for row in pending_logs:
            if row.extraction_status == "PROCESSING":
                row.extraction_status = "PENDING"
            if row.id not in recovered_log_ids:
                recovered_log_ids.append(row.id)

        db.commit()

    return recovered_log_ids

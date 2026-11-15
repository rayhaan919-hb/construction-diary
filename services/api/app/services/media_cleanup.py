from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.core.logging_config import safe_public_error_summary
from app.db.models import (
    ExtractionJob,
    MediaCleanupRun,
    MediaReservation,
    Permit,
    SiteLog,
    SiteLogPhoto,
    UploadTicket,
)
from app.services.audit import record_audit_event
from app.services.storage import MediaStorageService

logger = logging.getLogger(__name__)


def _collect_referenced_storage_uris(db: Session) -> set[str]:
    """Collect every storage URI referenced by database records (including soft-deleted)."""
    uris: set[str] = set()
    for val in db.scalars(select(SiteLog.audio_uri).where(SiteLog.audio_uri.is_not(None))):
        if val:
            uris.add(val)
    for val in db.scalars(
        select(SiteLogPhoto.storage_uri).where(SiteLogPhoto.storage_uri.is_not(None))
    ):
        if val:
            uris.add(val)
    for val in db.scalars(
        select(Permit.document_photo_uri).where(Permit.document_photo_uri.is_not(None))
    ):
        if val:
            uris.add(val)
    return uris


def _uri_to_object_key(storage: MediaStorageService, storage_uri: str) -> str | None:
    try:
        _, _, key = storage.parse_storage_uri(storage_uri)
        return key
    except ValueError:
        return None


def run_media_cleanup(
    db: Session,
    *,
    storage: MediaStorageService | None = None,
    settings: Settings | None = None,
    now: datetime | None = None,
    orphan_grace_seconds: int | None = None,
    failed_job_retention_days: int | None = None,
    dry_run: bool = False,
) -> MediaCleanupRun:
    """Clean expired tickets/reservations, incomplete/unattached objects, and old failed jobs.

    Guarantees that any object referenced by a SiteLog, SiteLogPhoto, Permit, or active
    in-flight upload ticket is never deleted, and records an auditable run history.
    """
    cfg = settings or get_settings()
    store = storage or MediaStorageService(cfg)
    current = now or datetime.now(UTC)
    grace_s = (
        int(cfg.MEDIA_ORPHAN_GRACE_SECONDS)
        if orphan_grace_seconds is None
        else max(0, int(orphan_grace_seconds))
    )
    retention_d = (
        int(cfg.MEDIA_FAILED_JOB_RETENTION_DAYS)
        if failed_job_retention_days is None
        else max(0, int(failed_job_retention_days))
    )

    orphan_cutoff = current - timedelta(seconds=grace_s)
    failed_cutoff = current - timedelta(days=retention_d)

    run = MediaCleanupRun(
        started_at=current,
        status="RUNNING",
        dry_run=dry_run,
    )
    db.add(run)
    db.flush()

    deleted_keys: list[str] = []
    expired_tickets = 0
    expired_reservations = 0
    incomplete_uploads = 0
    unattached_deleted = 0
    failed_pruned = 0
    bytes_reclaimed = 0

    try:
        # 1. Mark expired ACTIVE reservations as EXPIRED
        stale_reservations = list(
            db.scalars(
                select(MediaReservation)
                .where(
                    MediaReservation.status == "ACTIVE",
                    MediaReservation.expires_at <= current,
                )
                .with_for_update()
            )
        )
        expired_reservations = len(stale_reservations)
        if not dry_run:
            for res in stale_reservations:
                res.status = "EXPIRED"

        # 2. Collect ALL customer-referenced storage URIs/keys BEFORE any object deletion
        referenced_uris = _collect_referenced_storage_uris(db)
        protected_keys: set[str] = set()
        for uri in referenced_uris:
            parsed_key = _uri_to_object_key(store, uri)
            if parsed_key is not None:
                protected_keys.add(parsed_key)

        # 3. Expire overdue ISSUED tickets cleanly (never mark an attached UPLOADED row lost)
        overdue_tickets = list(
            db.scalars(
                select(UploadTicket)
                .where(
                    UploadTicket.status.in_(("ISSUED", "UPLOADED")),
                    UploadTicket.expires_at <= current,
                )
                .with_for_update()
            )
        )
        for ticket in overdue_tickets:
            is_attached = ticket.storage_uri in referenced_uris
            if ticket.status == "ISSUED":
                expired_tickets += 1
                if not dry_run:
                    ticket.status = "EXPIRED"
            elif not is_attached and ticket.expires_at <= orphan_cutoff:
                # Uploaded unattached ticket well past grace period -> safe to expire & clean
                expired_tickets += 1
                if not dry_run:
                    ticket.status = "EXPIRED"

        if not dry_run:
            db.flush()

        # Protect all non-expired active upload tickets still within their window or attached
        active_ticket_keys = set(
            db.scalars(
                select(UploadTicket.object_key).where(
                    UploadTicket.status.in_(("ISSUED", "UPLOADED")),
                    UploadTicket.expires_at > current,
                )
            )
        )
        protected_keys.update(active_ticket_keys)

        # 4. Remove incomplete upload objects tied to EXPIRED/REVOKED tickets past grace window
        incomplete_candidates = list(
            db.scalars(
                select(UploadTicket).where(
                    UploadTicket.status.in_(("EXPIRED", "REVOKED")),
                    UploadTicket.created_at <= orphan_cutoff,
                )
            )
        )
        cleaned_keys: set[str] = set()
        for ticket in incomplete_candidates:
            if (
                ticket.storage_uri in referenced_uris
                or ticket.object_key in protected_keys
                or ticket.object_key in cleaned_keys
            ):
                continue
            info = store.inspect_object(ticket.storage_uri)
            if info.exists:
                obj_size = int(info.byte_size or 0)
                if dry_run or store.delete_object(ticket.storage_uri):
                    incomplete_uploads += 1
                    bytes_reclaimed += obj_size
                    cleaned_keys.add(ticket.object_key)
                    if len(deleted_keys) < 100:
                        deleted_keys.append(ticket.object_key)

        # 5. Sweep storage prefix for any unattached orphan files past grace window
        for object_key, modified_at, obj_size in store.list_object_keys("projects/"):
            # Skip temp upload staging files unless stale past grace window
            if object_key in protected_keys or object_key in cleaned_keys:
                continue
            if modified_at > orphan_cutoff:
                continue
            if dry_run or store.delete_object(object_key):
                unattached_deleted += 1
                bytes_reclaimed += obj_size
                cleaned_keys.add(object_key)
                if len(deleted_keys) < 100:
                    deleted_keys.append(object_key)

        # 6. Prune aged dead-letter FAILED extraction jobs beyond retention
        failed_job_ids = list(
            db.scalars(
                select(ExtractionJob.id).where(
                    ExtractionJob.status == "FAILED",
                    ExtractionJob.updated_at <= failed_cutoff,
                )
            )
        )
        failed_pruned = len(failed_job_ids)
        if failed_pruned and not dry_run:
            db.execute(
                delete(ExtractionJob).where(ExtractionJob.id.in_(failed_job_ids))
            )

        run.completed_at = datetime.now(UTC)
        run.status = "COMPLETED"
        run.expired_tickets_cleaned = expired_tickets
        run.expired_reservations_cleaned = expired_reservations
        run.incomplete_uploads_cleaned = incomplete_uploads
        run.unattached_objects_deleted = unattached_deleted
        run.failed_jobs_pruned = failed_pruned
        run.bytes_reclaimed = bytes_reclaimed
        details_payload: dict[str, Any] = {
            "dry_run": dry_run,
            "orphan_grace_seconds": grace_s,
            "failed_job_retention_days": retention_d,
            "sample_deleted_keys": deleted_keys,
        }
        run.details = details_payload

        record_audit_event(
            db,
            action="media.cleanup.run",
            resource_type="media_cleanup_run",
            resource_id=run.id,
            details={
                "dry_run": dry_run,
                "expired_tickets_cleaned": expired_tickets,
                "expired_reservations_cleaned": expired_reservations,
                "incomplete_uploads_cleaned": incomplete_uploads,
                "unattached_objects_deleted": unattached_deleted,
                "failed_jobs_pruned": failed_pruned,
                "bytes_reclaimed": bytes_reclaimed,
            },
        )
        db.commit()
        db.refresh(run)
        return run
    except Exception as exc:
        logger.exception("Media orphan cleanup failed")
        run.completed_at = datetime.now(UTC)
        run.status = "FAILED"
        run.error_summary = safe_public_error_summary(exc, fallback="Cleanup job failed")
        db.commit()
        raise

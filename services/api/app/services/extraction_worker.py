from __future__ import annotations

import logging
import time
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import Settings, get_settings
from app.db.models import SiteLog
from app.db.session import create_session_factory
from app.services.ai_extractor import extract_from_audio
from app.services.storage import MediaStorageService

logger = logging.getLogger(__name__)


def run_extraction_for_log(
    log_id: UUID,
    session_factory: sessionmaker[Session] | None = None,
    settings: Settings | None = None,
) -> None:
    """Process Gemini voice extraction for a single site_log with retries."""
    cfg = settings or get_settings()
    factory = session_factory or create_session_factory()
    storage = MediaStorageService(cfg)

    with factory() as db:
        log = db.scalar(
            select(SiteLog)
            .where(SiteLog.id == log_id, SiteLog.deleted_at.is_(None))
            .with_for_update()
        )
        if log is None:
            return
        if not log.audio_uri or log.audio_upload_status != "UPLOADED":
            return
        if log.extraction_status not in ("PENDING", "FAILED"):
            return

        log.extraction_status = "PROCESSING"
        log.extraction_error = None
        audio_uri = log.audio_uri
        db.commit()

    max_attempts = max(1, cfg.EXTRACTION_MAX_ATTEMPTS)
    last_error: str | None = None

    for attempt in range(1, max_attempts + 1):
        with factory() as db:
            row = db.get(SiteLog, log_id)
            if row is None or row.deleted_at is not None:
                return
            row.extraction_attempts = attempt
            db.commit()

        try:
            result = extract_from_audio(audio_uri=audio_uri, storage=storage, settings=cfg)
        except Exception as exc:
            last_error = f"{type(exc).__name__}: {exc}"
            logger.warning(
                "Extraction attempt %s/%s failed for log %s: %s",
                attempt,
                max_attempts,
                log_id,
                last_error,
            )
            if attempt < max_attempts and not cfg.USE_MOCK_GEMINI:
                time.sleep(min(2 ** (attempt - 1), 8))
            continue

        with factory() as db:
            row = db.get(SiteLog, log_id)
            if row is None or row.deleted_at is not None:
                return
            row.extraction_status = "DONE"
            row.extraction_model = (
                "mock-gemini" if cfg.USE_MOCK_GEMINI else cfg.GEMINI_MODEL
            )
            row.extracted_at = datetime.now(UTC)
            row.extraction_error = None
            row.transcript = result.transcript
            row.detected_language = result.detected_language
            # Never overwrite human-edited structured_summary.
            if not row.edited_by_human:
                row.structured_summary = result.structured_summary.model_dump()
            db.commit()
        return

    with factory() as db:
        row = db.get(SiteLog, log_id)
        if row is None or row.deleted_at is not None:
            return
        row.extraction_status = "FAILED"
        row.extraction_error = (last_error or "Extraction failed")[:1000]
        db.commit()


def recover_stuck_extractions(
    session_factory: sessionmaker[Session] | None = None,
) -> list[UUID]:
    """Reset interrupted PROCESSING rows to PENDING and return log IDs ready for extraction."""
    factory = session_factory or create_session_factory()
    with factory() as db:
        rows = list(
            db.scalars(
                select(SiteLog).where(
                    SiteLog.deleted_at.is_(None),
                    SiteLog.audio_upload_status == "UPLOADED",
                    SiteLog.audio_uri.is_not(None),
                    SiteLog.extraction_status.in_(("PENDING", "PROCESSING")),
                )
            )
        )
        log_ids: list[UUID] = []
        for row in rows:
            if row.extraction_status == "PROCESSING":
                row.extraction_status = "PENDING"
            log_ids.append(row.id)
        if rows:
            db.commit()
        return log_ids

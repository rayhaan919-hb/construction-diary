from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable
from datetime import date
from typing import Literal, cast
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import PermitWithStatus, Project, SiteLog, SiteLogPhoto, User
from app.schemas.logs import (
    AudioUploadStatus,
    DailyReportResponse,
    DetectedLanguage,
    ExtractionStatus,
    PhotoUploadStatus,
    SiteLogPhotoResponse,
    SiteLogPullResponse,
    SiteLogResponse,
    StructuredSummary,
)
from app.schemas.permits import PermitResponse, PermitStatus
from app.services.storage import MediaStorageService


def dedupe_strings_ci(items: Iterable[str]) -> list[str]:
    """Trim blanks and deduplicate strings case-insensitively while preserving order."""
    seen: set[str] = set()
    result: list[str] = []
    for raw in items:
        cleaned = str(raw).strip()
        if not cleaned:
            continue
        key = cleaned.lower()
        if key not in seen:
            seen.add(key)
            result.append(cleaned)
    return result


def serialize_permit(
    row: PermitWithStatus,
    storage: MediaStorageService,
    include_signed_url: bool = True,
) -> PermitResponse:
    signed_url: str | None = None
    if include_signed_url and row.document_photo_uri:
        try:
            signed_url = storage.sign_get_url(row.document_photo_uri, ttl_seconds=3600)
        except ValueError:
            signed_url = None
    return PermitResponse(
        id=row.id,
        project_id=row.project_id,
        permit_name=row.permit_name,
        authority=row.authority,
        permit_number=row.permit_number,
        issue_date=row.issue_date,
        expiry_date=row.expiry_date,
        status=cast(PermitStatus, row.status),
        days_to_expiry=row.days_to_expiry,
        document_photo_uri=row.document_photo_uri,
        document_photo_url=signed_url,
        document_upload_status=getattr(row, "document_upload_status", "NONE"),
        ai_extracted_data=getattr(row, "ai_extracted_data", None),
        created_by=row.created_by,
        created_at=row.created_at,
        updated_at=row.updated_at,
        deleted_at=row.deleted_at,
        server_version=row.server_version,
    )


def serialize_photo(
    photo: SiteLogPhoto,
    storage: MediaStorageService,
    include_signed_url: bool = True,
) -> SiteLogPhotoResponse:
    url: str | None = None
    if include_signed_url and photo.upload_status == "UPLOADED":
        try:
            url = storage.sign_get_url(photo.storage_uri, ttl_seconds=3600)
        except ValueError:
            url = None
    return SiteLogPhotoResponse(
        id=photo.id,
        site_log_id=photo.site_log_id,
        storage_uri=photo.storage_uri,
        upload_status=cast(PhotoUploadStatus, photo.upload_status),
        url=url,
        width=photo.width,
        height=photo.height,
        byte_size=photo.byte_size,
        taken_at=photo.taken_at,
        sort_order=photo.sort_order,
        ai_caption=photo.ai_caption,
        ai_labels=photo.ai_labels,
        deleted_at=photo.deleted_at,
        server_version=photo.server_version,
    )


def _parse_summary(raw: dict[str, object] | None) -> StructuredSummary | None:
    if raw is None:
        return None
    return StructuredSummary.model_validate(raw)


def _sign_audio_url(
    log: SiteLog,
    storage: MediaStorageService | None,
    include_signed_url: bool,
) -> str | None:
    if (
        not include_signed_url
        or storage is None
        or not log.audio_uri
        or log.audio_upload_status != "UPLOADED"
    ):
        return None
    try:
        return storage.sign_get_url(log.audio_uri, ttl_seconds=3600)
    except ValueError:
        return None


def serialize_site_log(
    log: SiteLog,
    author_name: str | None,
    photos: list[SiteLogPhotoResponse],
    storage: MediaStorageService | None = None,
    *,
    include_signed_url: bool = True,
) -> SiteLogResponse:
    return SiteLogResponse(
        id=log.id,
        project_id=log.project_id,
        author_id=log.author_id,
        author_name=author_name,
        log_date=log.log_date,
        recorded_at=log.recorded_at,
        notes=log.notes,
        audio_uri=log.audio_uri,
        audio_url=_sign_audio_url(log, storage, include_signed_url),
        audio_duration_ms=log.audio_duration_ms,
        audio_upload_status=cast(AudioUploadStatus, log.audio_upload_status),
        extraction_status=cast(ExtractionStatus, log.extraction_status),
        extraction_attempts=log.extraction_attempts,
        extraction_error=log.extraction_error,
        extraction_model=log.extraction_model,
        extracted_at=log.extracted_at,
        transcript=log.transcript,
        detected_language=cast(DetectedLanguage | None, log.detected_language),
        structured_summary=_parse_summary(log.structured_summary),
        edited_by_human=log.edited_by_human,
        photos=photos,
        client_updated_at=log.client_updated_at,
        created_at=log.created_at,
        updated_at=log.updated_at,
        deleted_at=log.deleted_at,
        server_version=log.server_version,
    )


def serialize_site_log_pull(
    log: SiteLog,
    author_name: str | None,
    storage: MediaStorageService | None = None,
) -> SiteLogPullResponse:
    return SiteLogPullResponse(
        id=log.id,
        project_id=log.project_id,
        author_id=log.author_id,
        author_name=author_name,
        log_date=log.log_date,
        recorded_at=log.recorded_at,
        notes=log.notes,
        audio_uri=log.audio_uri,
        audio_url=_sign_audio_url(log, storage, True) if storage is not None else None,
        audio_duration_ms=log.audio_duration_ms,
        audio_upload_status=cast(AudioUploadStatus, log.audio_upload_status),
        extraction_status=cast(ExtractionStatus, log.extraction_status),
        extraction_attempts=log.extraction_attempts,
        extraction_error=log.extraction_error,
        extraction_model=log.extraction_model,
        extracted_at=log.extracted_at,
        transcript=log.transcript,
        detected_language=cast(DetectedLanguage | None, log.detected_language),
        structured_summary=_parse_summary(log.structured_summary),
        edited_by_human=log.edited_by_human,
        client_updated_at=log.client_updated_at,
        created_at=log.created_at,
        updated_at=log.updated_at,
        deleted_at=log.deleted_at,
        server_version=log.server_version,
    )


def compute_permit_health(
    permits: list[PermitWithStatus],
) -> Literal["OK", "WARN", "EXPIRED", "NONE"]:
    if not permits:
        return "NONE"
    statuses = {p.status for p in permits}
    if "EXPIRED" in statuses:
        return "EXPIRED"
    if "EXPIRING_SOON" in statuses:
        return "WARN"
    return "OK"


def build_daily_reports_for_dates(
    db: Session,
    project: Project,
    dates: list[date],
    storage: MediaStorageService,
) -> list[DailyReportResponse]:
    if not dates:
        return []

    permit_rows = list(
        db.scalars(
            select(PermitWithStatus)
            .where(
                PermitWithStatus.project_id == project.id,
                PermitWithStatus.deleted_at.is_(None),
            )
            .order_by(PermitWithStatus.expiry_date.asc(), PermitWithStatus.created_at.asc())
        )
    )
    serialized_permits = [serialize_permit(p, storage) for p in permit_rows]

    log_rows = db.execute(
        select(SiteLog, User.full_name)
        .join(User, User.id == SiteLog.author_id)
        .where(
            SiteLog.project_id == project.id,
            SiteLog.deleted_at.is_(None),
            SiteLog.log_date.in_(dates),
        )
        .order_by(SiteLog.recorded_at.asc(), SiteLog.created_at.asc())
    ).all()

    log_ids = [row[0].id for row in log_rows]
    photos_by_log: dict[UUID, list[SiteLogPhotoResponse]] = defaultdict(list)
    if log_ids:
        photo_rows = list(
            db.scalars(
                select(SiteLogPhoto)
                .where(
                    SiteLogPhoto.site_log_id.in_(log_ids),
                    SiteLogPhoto.deleted_at.is_(None),
                )
                .order_by(SiteLogPhoto.sort_order.asc(), SiteLogPhoto.created_at.asc())
            )
        )
        for photo in photo_rows:
            photos_by_log[photo.site_log_id].append(serialize_photo(photo, storage))

    logs_by_date: dict[date, list[SiteLogResponse]] = defaultdict(list)
    for log, author_name in log_rows:
        logs_by_date[log.log_date].append(
            serialize_site_log(log, author_name, photos_by_log[log.id], storage)
        )

    reports: list[DailyReportResponse] = []
    for target_date in dates:
        day_logs = logs_by_date[target_date]
        labor_counts: list[int] = []
        raw_tasks: list[str] = []
        raw_materials: list[str] = []
        raw_blockers: list[str] = []
        pending_count = 0

        for item in day_logs:
            if item.extraction_status != "DONE":
                pending_count += 1
            if item.structured_summary is not None:
                if item.structured_summary.labor_count is not None:
                    labor_counts.append(item.structured_summary.labor_count)
                raw_tasks.extend(item.structured_summary.tasks_completed)
                raw_materials.extend(item.structured_summary.material_deliveries)
                raw_blockers.extend(item.structured_summary.blockers)

        reports.append(
            DailyReportResponse(
                project_id=project.id,
                project_name=project.name,
                log_date=target_date,
                labor_max=max(labor_counts) if labor_counts else None,
                log_count=len(day_logs),
                pending_extraction_count=pending_count,
                tasks_completed=dedupe_strings_ci(raw_tasks),
                material_deliveries=dedupe_strings_ci(raw_materials),
                blockers=dedupe_strings_ci(raw_blockers),
                logs=day_logs,
                permits=serialized_permits,
            )
        )
    return reports

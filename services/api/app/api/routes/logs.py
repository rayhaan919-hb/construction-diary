from __future__ import annotations

import hmac
from datetime import UTC, date, datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, Header, Query, Request, Response
from pydantic import BaseModel
from sqlalchemy import select, update
from sqlalchemy.orm import Session, sessionmaker

from app.api.deps import (
    extract_client_meta,
    get_storage,
    get_verified_user,
    require_active_project_member,
)
from app.core.config import Settings, get_settings
from app.core.errors import ProblemException
from app.core.permissions import (
    EXTRACTION_TRIGGER_ROLES,
    LOG_WRITE_ROLES,
    PROJECT_ELEVATED_RECORD_ROLES,
)
from app.db.models import (
    ExtractionJob,
    Organization,
    Permit,
    Project,
    ProjectMember,
    SiteLog,
    SiteLogPhoto,
    User,
)
from app.db.session import get_db
from app.schemas.logs import (
    DailyReportResponse,
    ExtractionJobResponse,
    ExtractQueuedResponse,
    ExtractRequest,
    SiteLogPatchRequest,
    SiteLogResponse,
    TimelineResponse,
)
from app.services.audit import record_audit_event
from app.services.extraction_worker import (
    enqueue_extraction_job,
    execute_extraction_job,
)
from app.services.reports import (
    build_daily_reports_for_dates,
    serialize_photo,
    serialize_site_log,
)
from app.services.saas import enforce_ai_quota, ensure_org_active
from app.services.storage import MediaStorageService

router = APIRouter(prefix="/v1", tags=["logs"])


class CloudTaskExtractionPayload(BaseModel):
    job_id: UUID


def _load_log_and_member(
    db: Session, log_id: UUID, user: User
) -> tuple[SiteLog, str, Project, ProjectMember]:
    row = db.execute(
        select(SiteLog, User.full_name, Project, ProjectMember)
        .join(User, User.id == SiteLog.author_id)
        .join(Project, Project.id == SiteLog.project_id)
        .join(ProjectMember, ProjectMember.project_id == Project.id)
        .where(
            SiteLog.id == log_id,
            SiteLog.deleted_at.is_(None),
            Project.deleted_at.is_(None),
            ProjectMember.user_id == user.id,
            ProjectMember.deleted_at.is_(None),
        )
    ).first()
    if row is None:
        raise ProblemException(
            status_code=404,
            code="NOT_FOUND",
            title="Not Found",
            detail="Site log not found",
        )
    log, author_name, project, member = row[0], row[1], row[2], row[3]
    if (
        user.organization_id is not None
        and project.organization_id is not None
        and project.organization_id != user.organization_id
    ):
        raise ProblemException(
            status_code=404,
            code="NOT_FOUND",
            title="Not Found",
            detail="Site log not found",
        )
    if project.organization_id is not None:
        org = db.get(Organization, project.organization_id)
        ensure_org_active(org)
    return log, author_name, project, member


@router.get("/projects/{project_id}/timeline", response_model=TimelineResponse)
def get_project_timeline(
    project_id: UUID,
    current_user: Annotated[User, Depends(get_verified_user)],
    db: Annotated[Session, Depends(get_db)],
    storage: Annotated[MediaStorageService, Depends(get_storage)],
    before: Annotated[date | None, Query()] = None,
    days: Annotated[int, Query(ge=1, le=31)] = 7,
) -> TimelineResponse:
    project, _ = require_active_project_member(db, project_id, current_user)

    date_stmt = (
        select(SiteLog.log_date)
        .distinct()
        .where(
            SiteLog.project_id == project_id,
            SiteLog.deleted_at.is_(None),
        )
    )
    if before is not None:
        date_stmt = date_stmt.where(SiteLog.log_date < before)

    date_stmt = date_stmt.order_by(SiteLog.log_date.desc()).limit(days + 1)
    distinct_dates = list(db.scalars(date_stmt))

    has_more = len(distinct_dates) > days
    selected_dates = distinct_dates[:days]
    next_before = selected_dates[-1] if has_more and selected_dates else None

    reports = build_daily_reports_for_dates(db, project, selected_dates, storage)
    return TimelineResponse(days=reports, next_before=next_before)


@router.get(
    "/projects/{project_id}/days/{log_date}",
    response_model=DailyReportResponse,
)
def get_daily_report(
    project_id: UUID,
    log_date: date,
    current_user: Annotated[User, Depends(get_verified_user)],
    db: Annotated[Session, Depends(get_db)],
    storage: Annotated[MediaStorageService, Depends(get_storage)],
) -> DailyReportResponse:
    project, _ = require_active_project_member(db, project_id, current_user)
    reports = build_daily_reports_for_dates(db, project, [log_date], storage)
    return reports[0]


@router.get("/logs/{log_id}", response_model=SiteLogResponse)
def get_site_log(
    log_id: UUID,
    current_user: Annotated[User, Depends(get_verified_user)],
    db: Annotated[Session, Depends(get_db)],
    storage: Annotated[MediaStorageService, Depends(get_storage)],
) -> SiteLogResponse:
    log, author_name, _, _ = _load_log_and_member(db, log_id, current_user)
    photo_rows = list(
        db.scalars(
            select(SiteLogPhoto)
            .where(
                SiteLogPhoto.site_log_id == log.id,
                SiteLogPhoto.deleted_at.is_(None),
            )
            .order_by(SiteLogPhoto.sort_order.asc(), SiteLogPhoto.created_at.asc())
        )
    )
    photos = [serialize_photo(photo, storage) for photo in photo_rows]
    return serialize_site_log(log, author_name, photos, storage)


@router.patch("/logs/{log_id}", response_model=SiteLogResponse)
def update_site_log(
    log_id: UUID,
    payload: SiteLogPatchRequest,
    request: Request,
    current_user: Annotated[User, Depends(get_verified_user)],
    db: Annotated[Session, Depends(get_db)],
    storage: Annotated[MediaStorageService, Depends(get_storage)],
) -> SiteLogResponse:
    log, author_name, project, member = _load_log_and_member(db, log_id, current_user)
    if member.role not in LOG_WRITE_ROLES or (
        member.role not in PROJECT_ELEVATED_RECORD_ROLES
        and log.author_id != current_user.id
    ):
        raise ProblemException(
            status_code=403,
            code="FORBIDDEN",
            title="Forbidden",
            detail="Insufficient permissions to edit this site log",
        )

    fields_set = payload.model_fields_set
    if "notes" in fields_set:
        log.notes = payload.notes
        log.edited_by_human = True
    if "transcript" in fields_set:
        log.transcript = payload.transcript
        log.edited_by_human = True
    if "structured_summary" in fields_set:
        log.structured_summary = (
            payload.structured_summary.model_dump()
            if payload.structured_summary is not None
            else None
        )
        log.edited_by_human = True
    if "edited_by_human" in fields_set and payload.edited_by_human is not None:
        log.edited_by_human = payload.edited_by_human
    log.client_updated_at = datetime.now(UTC)

    ip_addr, user_agent = extract_client_meta(request)
    record_audit_event(
        db,
        action="site_log.update",
        resource_type="site_log",
        resource_id=log.id,
        actor_user=current_user,
        organization_id=project.organization_id,
        ip_address=ip_addr,
        user_agent=user_agent,
        details={"fields": sorted(fields_set)},
    )
    db.commit()
    db.refresh(log)

    photo_rows = list(
        db.scalars(
            select(SiteLogPhoto)
            .where(
                SiteLogPhoto.site_log_id == log.id,
                SiteLogPhoto.deleted_at.is_(None),
            )
            .order_by(SiteLogPhoto.sort_order.asc(), SiteLogPhoto.created_at.asc())
        )
    )
    photos = [serialize_photo(photo, storage) for photo in photo_rows]
    return serialize_site_log(log, author_name, photos, storage)


@router.delete("/logs/{log_id}", status_code=204)
def delete_site_log(
    log_id: UUID,
    request: Request,
    current_user: Annotated[User, Depends(get_verified_user)],
    db: Annotated[Session, Depends(get_db)],
) -> Response:
    log, _, project, member = _load_log_and_member(db, log_id, current_user)
    if member.role not in LOG_WRITE_ROLES or (
        member.role not in PROJECT_ELEVATED_RECORD_ROLES
        and log.author_id != current_user.id
    ):
        raise ProblemException(
            status_code=403,
            code="FORBIDDEN",
            title="Forbidden",
            detail="Insufficient permissions to delete this site log",
        )
    now = datetime.now(UTC)
    log.deleted_at = now
    db.execute(
        update(SiteLogPhoto)
        .where(
            SiteLogPhoto.site_log_id == log.id,
            SiteLogPhoto.deleted_at.is_(None),
        )
        .values(deleted_at=now)
    )

    ip_addr, user_agent = extract_client_meta(request)
    record_audit_event(
        db,
        action="site_log.delete",
        resource_type="site_log",
        resource_id=log.id,
        actor_user=current_user,
        organization_id=project.organization_id,
        ip_address=ip_addr,
        user_agent=user_agent,
    )
    db.commit()
    return Response(status_code=204)


@router.post("/logs/extract", response_model=ExtractQueuedResponse, status_code=202)
def queue_log_extraction(
    payload: ExtractRequest,
    request: Request,
    background_tasks: BackgroundTasks,
    current_user: Annotated[User, Depends(get_verified_user)],
    db: Annotated[Session, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> ExtractQueuedResponse:
    target_type = payload.target_type
    target_id = payload.target_id or payload.log_id
    if target_id is None:
        raise ProblemException(
            status_code=422,
            code="VALIDATION",
            title="Validation Error",
            detail="target_id or log_id is required",
        )

    project: Project | None = None
    idempotency_key = ""

    if target_type == "SITE_LOG":
        log, _, project, member = _load_log_and_member(db, target_id, current_user)
        if member.role not in EXTRACTION_TRIGGER_ROLES:
            raise ProblemException(
                status_code=403,
                code="FORBIDDEN",
                title="Forbidden",
                detail="Insufficient permissions to queue extraction",
            )
        has_audio = bool(log.audio_uri and log.audio_upload_status == "UPLOADED")
        audio_expected_but_missing = bool(
            log.audio_uri or log.audio_upload_status == "PENDING"
        ) and log.audio_upload_status != "UPLOADED"
        has_notes = bool(log.notes and log.notes.strip())
        if audio_expected_but_missing or (not has_audio and not has_notes):
            raise ProblemException(
                status_code=409,
                code="AUDIO_NOT_UPLOADED",
                title="Conflict",
                detail="Audio has not been uploaded yet and no extractable notes are present",
            )
        if log.extraction_status == "PROCESSING":
            raise ProblemException(
                status_code=409,
                code="EXTRACTION_IN_PROGRESS",
                title="Conflict",
                detail="Extraction is already in progress for this log",
            )
        log.extraction_attempts = 0
        log.extraction_status = "PENDING"
        log.extraction_error = None
        idempotency_key = f"SITE_LOG:{log.id}:{log.audio_uri or 'notes'}:{log.server_version}"
    elif target_type == "SITE_LOG_PHOTO":
        row = db.execute(
            select(SiteLogPhoto, SiteLog, Project, ProjectMember)
            .join(SiteLog, SiteLog.id == SiteLogPhoto.site_log_id)
            .join(Project, Project.id == SiteLog.project_id)
            .join(ProjectMember, ProjectMember.project_id == Project.id)
            .where(
                SiteLogPhoto.id == target_id,
                SiteLogPhoto.deleted_at.is_(None),
                SiteLog.deleted_at.is_(None),
                Project.deleted_at.is_(None),
                ProjectMember.user_id == current_user.id,
                ProjectMember.deleted_at.is_(None),
            )
        ).first()
        if row is None:
            raise ProblemException(
                status_code=404,
                code="NOT_FOUND",
                title="Not Found",
                detail="Photo not found",
            )
        photo, _, project, member = row[0], row[1], row[2], row[3]
        if (
            current_user.organization_id is not None
            and project.organization_id is not None
            and project.organization_id != current_user.organization_id
        ):
            raise ProblemException(
                status_code=404, code="NOT_FOUND", title="Not Found", detail="Photo not found"
            )
        if member.role not in EXTRACTION_TRIGGER_ROLES:
            raise ProblemException(
                status_code=403,
                code="FORBIDDEN",
                title="Forbidden",
                detail="Insufficient permissions to queue extraction",
            )
        if photo.upload_status != "UPLOADED":
            raise ProblemException(
                status_code=409,
                code="PHOTO_NOT_UPLOADED",
                title="Conflict",
                detail="Photo has not finished uploading yet",
            )
        idempotency_key = f"SITE_LOG_PHOTO:{photo.id}:{photo.storage_uri}:{photo.server_version}"
    else:  # PERMIT
        row_p = db.execute(
            select(Permit, Project, ProjectMember)
            .join(Project, Project.id == Permit.project_id)
            .join(ProjectMember, ProjectMember.project_id == Project.id)
            .where(
                Permit.id == target_id,
                Permit.deleted_at.is_(None),
                Project.deleted_at.is_(None),
                ProjectMember.user_id == current_user.id,
                ProjectMember.deleted_at.is_(None),
            )
        ).first()
        if row_p is None:
            raise ProblemException(
                status_code=404,
                code="NOT_FOUND",
                title="Not Found",
                detail="Permit not found",
            )
        permit, project, member = row_p[0], row_p[1], row_p[2]
        if (
            current_user.organization_id is not None
            and project.organization_id is not None
            and project.organization_id != current_user.organization_id
        ):
            raise ProblemException(
                status_code=404,
                code="NOT_FOUND",
                title="Not Found",
                detail="Permit not found",
            )
        if member.role not in EXTRACTION_TRIGGER_ROLES:
            raise ProblemException(
                status_code=403,
                code="FORBIDDEN",
                title="Forbidden",
                detail="Insufficient permissions to queue extraction",
            )
        if not permit.document_photo_uri:
            raise ProblemException(
                status_code=409,
                code="DOCUMENT_NOT_UPLOADED",
                title="Conflict",
                detail="Permit has no uploaded document to extract",
            )
        idempotency_key = f"PERMIT:{permit.id}:{permit.document_photo_uri}:{permit.server_version}"

    if project.organization_id is not None:
        org = db.get(Organization, project.organization_id)
        ensure_org_active(org)
        if org is not None:
            enforce_ai_quota(org)

    job, should_dispatch_local = enqueue_extraction_job(
        db,
        organization_id=project.organization_id,
        project_id=project.id,
        target_type=target_type,
        target_id=target_id,
        idempotency_key=idempotency_key,
        settings=settings,
        force_reset=True,
    )

    ip_addr, user_agent = extract_client_meta(request)
    record_audit_event(
        db,
        action="extraction.queue",
        resource_type=target_type.lower(),
        resource_id=target_id,
        actor_user=current_user,
        organization_id=project.organization_id,
        ip_address=ip_addr,
        user_agent=user_agent,
        details={"job_id": str(job.id)},
    )
    db.commit()

    if should_dispatch_local:
        session_factory = sessionmaker(
            bind=db.get_bind(),
            autocommit=False,
            autoflush=False,
            expire_on_commit=False,
        )
        background_tasks.add_task(
            execute_extraction_job,
            job.id,
            session_factory,
            settings,
        )
    return ExtractQueuedResponse(
        log_id=target_id,
        extraction_status="PENDING",
        job_id=job.id,
    )


@router.get("/projects/{project_id}/extraction-jobs", response_model=list[ExtractionJobResponse])
def list_extraction_jobs(
    project_id: UUID,
    current_user: Annotated[User, Depends(get_verified_user)],
    db: Annotated[Session, Depends(get_db)],
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> list[ExtractionJobResponse]:
    require_active_project_member(db, project_id, current_user)
    jobs = list(
        db.scalars(
            select(ExtractionJob)
            .where(ExtractionJob.project_id == project_id)
            .order_by(ExtractionJob.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
    )
    return [ExtractionJobResponse.model_validate(job) for job in jobs]


@router.post("/internal/tasks/extraction")
def handle_cloud_task_extraction(
    payload: CloudTaskExtractionPayload,
    db: Annotated[Session, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
    x_task_secret: Annotated[str | None, Header(alias="X-Task-Secret")] = None,
) -> dict[str, str]:
    """Authenticated Cloud Tasks HTTP target handler for durable AI extraction."""
    expected = settings.CLOUD_TASKS_SHARED_SECRET.strip()
    if not expected:
        raise ProblemException(
            status_code=503,
            code="SERVICE_MISCONFIGURED",
            title="Service Misconfigured",
            detail="CLOUD_TASKS_SHARED_SECRET is required for internal task webhooks",
        )
    if not (x_task_secret and hmac.compare_digest(x_task_secret, expected)):
        raise ProblemException(
            status_code=403,
            code="FORBIDDEN",
            title="Forbidden",
            detail="Invalid internal task credential",
        )

    session_factory = sessionmaker(
        bind=db.get_bind(),
        autocommit=False,
        autoflush=False,
        expire_on_commit=False,
    )
    execute_extraction_job(payload.job_id, session_factory, settings)
    return {"status": "ok"}

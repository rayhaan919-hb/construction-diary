from __future__ import annotations

from datetime import date
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from app.api.deps import (
    get_current_user,
    get_storage,
    require_active_project_member,
)
from app.core.config import Settings, get_settings
from app.core.errors import ProblemException
from app.db.models import Project, ProjectMember, SiteLog, SiteLogPhoto, User
from app.db.session import get_db
from app.schemas.logs import (
    DailyReportResponse,
    ExtractQueuedResponse,
    ExtractRequest,
    SiteLogResponse,
    TimelineResponse,
)
from app.services.extraction_worker import run_extraction_for_log
from app.services.reports import (
    build_daily_reports_for_dates,
    serialize_photo,
    serialize_site_log,
)
from app.services.storage import MediaStorageService

router = APIRouter(prefix="/v1", tags=["logs"])


@router.get("/projects/{project_id}/timeline", response_model=TimelineResponse)
def get_project_timeline(
    project_id: UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
    storage: Annotated[MediaStorageService, Depends(get_storage)],
    before: Annotated[date | None, Query()] = None,
    days: Annotated[int, Query(ge=1, le=31)] = 7,
) -> TimelineResponse:
    project, _ = require_active_project_member(db, project_id, current_user.id)

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
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
    storage: Annotated[MediaStorageService, Depends(get_storage)],
) -> DailyReportResponse:
    project, _ = require_active_project_member(db, project_id, current_user.id)
    reports = build_daily_reports_for_dates(db, project, [log_date], storage)
    return reports[0]


@router.get("/logs/{log_id}", response_model=SiteLogResponse)
def get_site_log(
    log_id: UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
    storage: Annotated[MediaStorageService, Depends(get_storage)],
) -> SiteLogResponse:
    row = db.execute(
        select(SiteLog, User.full_name)
        .join(User, User.id == SiteLog.author_id)
        .join(Project, Project.id == SiteLog.project_id)
        .join(ProjectMember, ProjectMember.project_id == Project.id)
        .where(
            SiteLog.id == log_id,
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
            detail="Site log not found",
        )

    log, author_name = row[0], row[1]
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
    return serialize_site_log(log, author_name, photos)


@router.post("/logs/extract", response_model=ExtractQueuedResponse, status_code=202)
def queue_log_extraction(
    payload: ExtractRequest,
    background_tasks: BackgroundTasks,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> ExtractQueuedResponse:
    log = db.scalar(
        select(SiteLog)
        .join(Project, Project.id == SiteLog.project_id)
        .join(ProjectMember, ProjectMember.project_id == Project.id)
        .where(
            SiteLog.id == payload.log_id,
            SiteLog.deleted_at.is_(None),
            Project.deleted_at.is_(None),
            ProjectMember.user_id == current_user.id,
            ProjectMember.deleted_at.is_(None),
        )
    )
    if log is None:
        raise ProblemException(
            status_code=404,
            code="NOT_FOUND",
            title="Not Found",
            detail="Site log not found",
        )

    if not log.audio_uri or log.audio_upload_status != "UPLOADED":
        raise ProblemException(
            status_code=409,
            code="AUDIO_NOT_UPLOADED",
            title="Conflict",
            detail="Audio has not been uploaded yet for this log",
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
    db.commit()

    session_factory = sessionmaker(
        bind=db.get_bind(),
        autocommit=False,
        autoflush=False,
        expire_on_commit=False,
    )
    background_tasks.add_task(
        run_extraction_for_log,
        log.id,
        session_factory,
        settings,
    )
    return ExtractQueuedResponse(log_id=log.id, extraction_status="PENDING")

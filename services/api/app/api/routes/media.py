from __future__ import annotations

import mimetypes
from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Depends, Query, Request, Response
from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from app.api.deps import get_current_user, get_storage
from app.core.config import Settings, get_settings
from app.core.errors import ProblemException
from app.db.models import Permit, Project, ProjectMember, SiteLog, SiteLogPhoto, User
from app.db.session import get_db
from app.schemas.media import (
    MediaCompleteRequest,
    UploadTicketResponse,
    UploadUrlRequest,
)
from app.services.extraction_worker import run_extraction_for_log
from app.services.storage import (
    MediaStorageService,
    normalize_and_validate_key,
    verify_local_signature,
)

router = APIRouter(prefix="/v1/media", tags=["media"])

MAX_UPLOAD_BYTES = 20_971_520


@router.post("/upload-url", response_model=UploadTicketResponse)
def create_upload_url(
    payload: UploadUrlRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
    storage: Annotated[MediaStorageService, Depends(get_storage)],
) -> UploadTicketResponse:
    membership = db.execute(
        select(ProjectMember)
        .join(Project, Project.id == ProjectMember.project_id)
        .where(
            Project.id == payload.project_id,
            Project.deleted_at.is_(None),
            ProjectMember.user_id == current_user.id,
            ProjectMember.deleted_at.is_(None),
        )
    ).first()
    if membership is None:
        raise ProblemException(
            status_code=403,
            code="FORBIDDEN",
            title="Forbidden",
            detail="Active project membership required for media upload",
        )

    return storage.create_upload_ticket(
        kind=payload.kind,
        project_id=payload.project_id,
        object_id=payload.object_id,
        content_type=payload.content_type,
    )


@router.post("/complete", status_code=204)
def complete_media_upload(
    payload: MediaCompleteRequest,
    background_tasks: BackgroundTasks,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
    storage: Annotated[MediaStorageService, Depends(get_storage)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> Response:
    if payload.kind == "AUDIO":
        log = db.scalar(
            select(SiteLog).where(
                SiteLog.id == payload.object_id,
                SiteLog.deleted_at.is_(None),
            )
        )
        if log is None:
            raise ProblemException(
                status_code=409,
                code="ROW_NOT_SYNCED",
                title="Conflict",
                detail="Site log row has not been synced yet",
            )

        member = db.scalar(
            select(ProjectMember)
            .join(Project, Project.id == ProjectMember.project_id)
            .where(
                Project.id == log.project_id,
                Project.deleted_at.is_(None),
                ProjectMember.user_id == current_user.id,
                ProjectMember.deleted_at.is_(None),
            )
        )
        if member is None or (member.role != "OWNER" and log.author_id != current_user.id):
            raise ProblemException(
                status_code=403,
                code="FORBIDDEN",
                title="Forbidden",
                detail="Not authorized to confirm upload for this site log",
            )

        if not log.audio_uri or not storage.exists(log.audio_uri):
            raise ProblemException(
                status_code=404,
                code="OBJECT_MISSING",
                title="Not Found",
                detail="Uploaded audio object not found in storage",
            )

        should_queue = log.extraction_status in ("NOT_STARTED", "FAILED")
        changed = False
        if log.audio_upload_status != "UPLOADED":
            log.audio_upload_status = "UPLOADED"
            changed = True
        if should_queue:
            log.extraction_status = "PENDING"
            log.extraction_attempts = 0
            log.extraction_error = None
            changed = True
        if changed:
            db.commit()

        if should_queue:
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
        return Response(status_code=204)

    if payload.kind == "PHOTO":
        row = db.execute(
            select(SiteLogPhoto, SiteLog)
            .join(SiteLog, SiteLog.id == SiteLogPhoto.site_log_id)
            .where(
                SiteLogPhoto.id == payload.object_id,
                SiteLogPhoto.deleted_at.is_(None),
                SiteLog.deleted_at.is_(None),
            )
        ).first()
        if row is None:
            raise ProblemException(
                status_code=409,
                code="ROW_NOT_SYNCED",
                title="Conflict",
                detail="Site log photo row has not been synced yet",
            )
        photo, log = row[0], row[1]

        member = db.scalar(
            select(ProjectMember)
            .join(Project, Project.id == ProjectMember.project_id)
            .where(
                Project.id == log.project_id,
                Project.deleted_at.is_(None),
                ProjectMember.user_id == current_user.id,
                ProjectMember.deleted_at.is_(None),
            )
        )
        if member is None or (member.role != "OWNER" and log.author_id != current_user.id):
            raise ProblemException(
                status_code=403,
                code="FORBIDDEN",
                title="Forbidden",
                detail="Not authorized to confirm upload for this photo",
            )

        if not storage.exists(photo.storage_uri):
            raise ProblemException(
                status_code=404,
                code="OBJECT_MISSING",
                title="Not Found",
                detail="Uploaded photo object not found in storage",
            )

        if photo.upload_status != "UPLOADED":
            photo.upload_status = "UPLOADED"
            db.commit()
        return Response(status_code=204)

    # PERMIT_DOC
    permit = db.scalar(
        select(Permit).where(
            Permit.id == payload.object_id,
            Permit.deleted_at.is_(None),
        )
    )
    if permit is None:
        raise ProblemException(
            status_code=409,
            code="ROW_NOT_SYNCED",
            title="Conflict",
            detail="Permit row has not been synced yet",
        )

    member = db.scalar(
        select(ProjectMember)
        .join(Project, Project.id == ProjectMember.project_id)
        .where(
            Project.id == permit.project_id,
            Project.deleted_at.is_(None),
            ProjectMember.user_id == current_user.id,
            ProjectMember.deleted_at.is_(None),
        )
    )
    if member is None or (member.role != "OWNER" and permit.created_by != current_user.id):
        raise ProblemException(
            status_code=403,
            code="FORBIDDEN",
            title="Forbidden",
            detail="Not authorized to confirm upload for this permit document",
        )

    if not permit.document_photo_uri or not storage.exists(permit.document_photo_uri):
        raise ProblemException(
            status_code=404,
            code="OBJECT_MISSING",
            title="Not Found",
            detail="Uploaded permit document object not found in storage",
        )

    return Response(status_code=204)


def _require_local_backend_and_signature(
    method: str,
    raw_key: str,
    sig: str,
    exp: int,
    settings: Settings,
) -> str:
    if settings.STORAGE_BACKEND != "local":
        raise ProblemException(
            status_code=404,
            code="NOT_FOUND",
            title="Not Found",
            detail="Local media endpoint is disabled",
        )
    clean_key = normalize_and_validate_key(raw_key)
    if not verify_local_signature(method, clean_key, sig, exp, settings):
        raise ProblemException(
            status_code=403,
            code="FORBIDDEN",
            title="Forbidden",
            detail="Invalid or expired signed URL",
        )
    return clean_key


@router.put("/local/{key:path}")
async def put_local_media(
    key: str,
    request: Request,
    sig: Annotated[str, Query()],
    exp: Annotated[int, Query()],
    settings: Annotated[Settings, Depends(get_settings)],
    storage: Annotated[MediaStorageService, Depends(get_storage)],
) -> dict[str, str]:
    clean_key = _require_local_backend_and_signature("PUT", key, sig, exp, settings)
    body = await request.body()
    if not body:
        raise ProblemException(
            status_code=422,
            code="VALIDATION",
            title="Validation Error",
            detail="Upload body cannot be empty",
        )
    if len(body) > MAX_UPLOAD_BYTES:
        raise ProblemException(
            status_code=413,
            code="PAYLOAD_TOO_LARGE",
            title="Payload Too Large",
            detail="Upload exceeds 20 MiB limit",
        )
    storage.write_local_bytes(clean_key, body)
    return {"status": "stored"}


@router.get("/local/{key:path}")
def get_local_media(
    key: str,
    sig: Annotated[str, Query()],
    exp: Annotated[int, Query()],
    settings: Annotated[Settings, Depends(get_settings)],
    storage: Annotated[MediaStorageService, Depends(get_storage)],
) -> Response:
    clean_key = _require_local_backend_and_signature("GET", key, sig, exp, settings)
    data = storage.read_local_bytes(clean_key)
    if data is None:
        raise ProblemException(
            status_code=404,
            code="NOT_FOUND",
            title="Not Found",
            detail="Object not found",
        )
    if clean_key.endswith(".m4a"):
        media_type = "audio/mp4"
    elif clean_key.endswith((".jpg", ".jpeg")):
        media_type = "image/jpeg"
    else:
        media_type = mimetypes.guess_type(clean_key)[0] or "application/octet-stream"
    return Response(content=data, media_type=media_type)

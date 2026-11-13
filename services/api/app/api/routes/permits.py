from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import (
    get_current_user,
    get_storage,
    require_active_project_member,
)
from app.core.errors import ProblemException
from app.db.models import Permit, PermitWithStatus, Project, ProjectMember, User
from app.db.session import get_db
from app.schemas.permits import PermitInput, PermitPatch, PermitResponse
from app.services.reports import serialize_permit
from app.services.storage import MediaStorageService

router = APIRouter(prefix="/v1", tags=["permits"])


def _load_permit_and_member(
    db: Session,
    permit_id: UUID,
    user_id: UUID,
) -> tuple[Permit, ProjectMember]:
    row = db.execute(
        select(Permit, ProjectMember)
        .join(Project, Project.id == Permit.project_id)
        .join(ProjectMember, ProjectMember.project_id == Project.id)
        .where(
            Permit.id == permit_id,
            Permit.deleted_at.is_(None),
            Project.deleted_at.is_(None),
            ProjectMember.user_id == user_id,
            ProjectMember.deleted_at.is_(None),
        )
    ).first()
    if row is None:
        raise ProblemException(
            status_code=404,
            code="NOT_FOUND",
            title="Not Found",
            detail="Permit not found",
        )
    return row[0], row[1]


@router.get("/projects/{project_id}/permits", response_model=list[PermitResponse])
def list_permits(
    project_id: UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
    storage: Annotated[MediaStorageService, Depends(get_storage)],
) -> list[PermitResponse]:
    require_active_project_member(db, project_id, current_user.id)
    rows = list(
        db.scalars(
            select(PermitWithStatus)
            .where(
                PermitWithStatus.project_id == project_id,
                PermitWithStatus.deleted_at.is_(None),
            )
            .order_by(PermitWithStatus.expiry_date.asc(), PermitWithStatus.created_at.asc())
        )
    )
    return [serialize_permit(row, storage) for row in rows]


@router.post(
    "/projects/{project_id}/permits",
    response_model=PermitResponse,
    status_code=201,
)
def create_permit(
    project_id: UUID,
    payload: PermitInput,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
    storage: Annotated[MediaStorageService, Depends(get_storage)],
) -> PermitResponse:
    require_active_project_member(db, project_id, current_user.id)
    permit = Permit(
        project_id=project_id,
        permit_name=payload.permit_name,
        authority=payload.authority,
        permit_number=payload.permit_number,
        issue_date=payload.issue_date,
        expiry_date=payload.expiry_date,
        document_photo_uri=payload.document_photo_uri,
        created_by=current_user.id,
    )
    db.add(permit)
    db.commit()

    view_row = db.get(PermitWithStatus, permit.id)
    if view_row is None:
        raise RuntimeError("Created permit missing from permits_with_status view")
    return serialize_permit(view_row, storage)


@router.patch("/permits/{permit_id}", response_model=PermitResponse)
def update_permit(
    permit_id: UUID,
    payload: PermitPatch,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
    storage: Annotated[MediaStorageService, Depends(get_storage)],
) -> PermitResponse:
    permit, member = _load_permit_and_member(db, permit_id, current_user.id)
    if member.role != "OWNER" and permit.created_by != current_user.id:
        raise ProblemException(
            status_code=403,
            code="FORBIDDEN",
            title="Forbidden",
            detail="Supervisors may only update permits they created",
        )

    fields_set = payload.model_fields_set
    if "permit_name" in fields_set and payload.permit_name is not None:
        permit.permit_name = payload.permit_name
    if "authority" in fields_set and payload.authority is not None:
        permit.authority = payload.authority
    if "permit_number" in fields_set:
        permit.permit_number = payload.permit_number
    if "issue_date" in fields_set:
        permit.issue_date = payload.issue_date
    if "expiry_date" in fields_set and payload.expiry_date is not None:
        permit.expiry_date = payload.expiry_date
    if "document_photo_uri" in fields_set:
        permit.document_photo_uri = payload.document_photo_uri

    db.commit()
    view_row = db.get(PermitWithStatus, permit.id)
    if view_row is None:
        raise RuntimeError("Updated permit missing from permits_with_status view")
    return serialize_permit(view_row, storage)


@router.delete("/permits/{permit_id}", status_code=204)
def delete_permit(
    permit_id: UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> Response:
    permit, member = _load_permit_and_member(db, permit_id, current_user.id)
    if member.role != "OWNER" and permit.created_by != current_user.id:
        raise ProblemException(
            status_code=403,
            code="FORBIDDEN",
            title="Forbidden",
            detail="Supervisors may only delete permits they created",
        )
    permit.deleted_at = datetime.now(UTC)
    db.commit()
    return Response(status_code=204)

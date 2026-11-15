from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request, Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import (
    extract_client_meta,
    get_storage,
    get_verified_user,
    require_active_project_member,
)
from app.core.config import Settings, get_settings
from app.core.errors import ProblemException
from app.core.permissions import PERMIT_WRITE_ROLES, PROJECT_ELEVATED_RECORD_ROLES
from app.db.models import (
    Organization,
    Permit,
    PermitWithStatus,
    Project,
    ProjectMember,
    UploadTicket,
    User,
)
from app.db.session import get_db
from app.schemas.permits import PermitInput, PermitPatch, PermitResponse
from app.services.audit import record_audit_event
from app.services.media_security import validate_project_storage_uri
from app.services.reports import serialize_permit
from app.services.saas import ensure_org_active
from app.services.storage import MediaStorageService

router = APIRouter(prefix="/v1", tags=["permits"])


def _load_permit_and_member(
    db: Session,
    permit_id: UUID,
    user: User,
) -> tuple[Permit, Project, ProjectMember]:
    row = db.execute(
        select(Permit, Project, ProjectMember)
        .join(Project, Project.id == Permit.project_id)
        .join(ProjectMember, ProjectMember.project_id == Project.id)
        .where(
            Permit.id == permit_id,
            Permit.deleted_at.is_(None),
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
            detail="Permit not found",
        )
    permit, project, member = row[0], row[1], row[2]
    if (
        user.organization_id is not None
        and project.organization_id is not None
        and project.organization_id != user.organization_id
    ):
        raise ProblemException(
            status_code=404,
            code="NOT_FOUND",
            title="Not Found",
            detail="Permit not found",
        )
    if project.organization_id is not None:
        org = db.get(Organization, project.organization_id)
        ensure_org_active(org)
    return permit, project, member


def _resolve_document_upload_status(
    db: Session,
    *,
    project_id: UUID,
    uri: str | None,
    settings: Settings,
    actor_user_id: UUID,
    member_role: str,
) -> str:
    if not uri:
        return "NONE"
    ok, err = validate_project_storage_uri(
        uri,
        project_id=project_id,
        storage_backend=settings.STORAGE_BACKEND,
        gcs_bucket=settings.GCS_BUCKET,
        expected_subdir="permits",
    )
    if not ok:
        raise ProblemException(
            status_code=422,
            code="VALIDATION",
            title="Validation Error",
            detail=err or "Invalid permit document storage URI",
        )
    matching_ticket = db.scalar(
        select(UploadTicket).where(UploadTicket.storage_uri == uri)
    )
    if matching_ticket is not None and (
        matching_ticket.project_id != project_id
        or (
            matching_ticket.user_id != actor_user_id
            and member_role not in PROJECT_ELEVATED_RECORD_ROLES
        )
    ):
        raise ProblemException(
            status_code=403,
            code="FORBIDDEN",
            title="Forbidden",
            detail="Cannot attach an upload ticket belonging to another user or project",
        )
    completed_ticket = db.scalar(
        select(UploadTicket).where(
            UploadTicket.project_id == project_id,
            UploadTicket.storage_uri == uri,
            UploadTicket.status.in_(("UPLOADED", "COMPLETED")),
        )
    )
    return "UPLOADED" if completed_ticket is not None else "PENDING"


@router.get("/projects/{project_id}/permits", response_model=list[PermitResponse])
def list_permits(
    project_id: UUID,
    current_user: Annotated[User, Depends(get_verified_user)],
    db: Annotated[Session, Depends(get_db)],
    storage: Annotated[MediaStorageService, Depends(get_storage)],
    limit: Annotated[int, Query(ge=1, le=200)] = 100,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> list[PermitResponse]:
    require_active_project_member(db, project_id, current_user)
    rows = list(
        db.scalars(
            select(PermitWithStatus)
            .where(
                PermitWithStatus.project_id == project_id,
                PermitWithStatus.deleted_at.is_(None),
            )
            .order_by(PermitWithStatus.expiry_date.asc(), PermitWithStatus.created_at.asc())
            .limit(limit)
            .offset(offset)
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
    request: Request,
    current_user: Annotated[User, Depends(get_verified_user)],
    db: Annotated[Session, Depends(get_db)],
    storage: Annotated[MediaStorageService, Depends(get_storage)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> PermitResponse:
    project, member = require_active_project_member(
        db, project_id, current_user, allowed_roles=PERMIT_WRITE_ROLES
    )
    doc_status = _resolve_document_upload_status(
        db,
        project_id=project_id,
        uri=payload.document_photo_uri,
        settings=settings,
        actor_user_id=current_user.id,
        member_role=member.role,
    )
    permit = Permit(
        project_id=project_id,
        permit_name=payload.permit_name,
        authority=payload.authority,
        permit_number=payload.permit_number,
        issue_date=payload.issue_date,
        expiry_date=payload.expiry_date,
        document_photo_uri=payload.document_photo_uri,
        document_upload_status=doc_status,
        created_by=current_user.id,
    )
    db.add(permit)
    db.flush()

    ip_addr, user_agent = extract_client_meta(request)
    record_audit_event(
        db,
        action="permit.create",
        resource_type="permit",
        resource_id=permit.id,
        actor_user=current_user,
        organization_id=project.organization_id,
        ip_address=ip_addr,
        user_agent=user_agent,
        details={"project_id": str(project_id), "permit_name": permit.permit_name},
    )
    db.commit()

    view_row = db.get(PermitWithStatus, permit.id)
    if view_row is None:
        raise RuntimeError("Created permit missing from permits_with_status view")
    return serialize_permit(view_row, storage)


@router.patch("/permits/{permit_id}", response_model=PermitResponse)
def update_permit(
    permit_id: UUID,
    payload: PermitPatch,
    request: Request,
    current_user: Annotated[User, Depends(get_verified_user)],
    db: Annotated[Session, Depends(get_db)],
    storage: Annotated[MediaStorageService, Depends(get_storage)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> PermitResponse:
    permit, project, member = _load_permit_and_member(db, permit_id, current_user)
    if member.role not in PERMIT_WRITE_ROLES or (
        member.role not in PROJECT_ELEVATED_RECORD_ROLES
        and permit.created_by != current_user.id
    ):
        raise ProblemException(
            status_code=403,
            code="FORBIDDEN",
            title="Forbidden",
            detail="Insufficient permissions to modify this permit",
        )

    fields_set = payload.model_fields_set
    effective_issue = (
        payload.issue_date if "issue_date" in fields_set else permit.issue_date
    )
    effective_expiry = (
        payload.expiry_date
        if "expiry_date" in fields_set and payload.expiry_date is not None
        else permit.expiry_date
    )
    if effective_issue is not None and effective_issue > effective_expiry:
        raise ProblemException(
            status_code=422,
            code="VALIDATION",
            title="Validation Error",
            detail="issue_date must not be later than expiry_date",
        )

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
        permit.document_upload_status = _resolve_document_upload_status(
            db,
            project_id=permit.project_id,
            uri=payload.document_photo_uri,
            settings=settings,
            actor_user_id=current_user.id,
            member_role=member.role,
        )

    ip_addr, user_agent = extract_client_meta(request)
    record_audit_event(
        db,
        action="permit.update",
        resource_type="permit",
        resource_id=permit.id,
        actor_user=current_user,
        organization_id=project.organization_id,
        ip_address=ip_addr,
        user_agent=user_agent,
        details={"fields": sorted(fields_set)},
    )
    db.commit()
    view_row = db.get(PermitWithStatus, permit.id)
    if view_row is None:
        raise RuntimeError("Updated permit missing from permits_with_status view")
    return serialize_permit(view_row, storage)


@router.delete("/permits/{permit_id}", status_code=204)
def delete_permit(
    permit_id: UUID,
    request: Request,
    current_user: Annotated[User, Depends(get_verified_user)],
    db: Annotated[Session, Depends(get_db)],
) -> Response:
    permit, project, member = _load_permit_and_member(db, permit_id, current_user)
    if member.role not in PERMIT_WRITE_ROLES or (
        member.role not in PROJECT_ELEVATED_RECORD_ROLES
        and permit.created_by != current_user.id
    ):
        raise ProblemException(
            status_code=403,
            code="FORBIDDEN",
            title="Forbidden",
            detail="Insufficient permissions to delete this permit",
        )
    permit.deleted_at = datetime.now(UTC)
    ip_addr, user_agent = extract_client_meta(request)
    record_audit_event(
        db,
        action="permit.delete",
        resource_type="permit",
        resource_id=permit.id,
        actor_user=current_user,
        organization_id=project.organization_id,
        ip_address=ip_addr,
        user_agent=user_agent,
    )
    db.commit()
    return Response(status_code=204)

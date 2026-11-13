from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.core.errors import ProblemException
from app.db.models import Project, ProjectMember, User
from app.db.session import get_db
from app.services.auth import decode_access_token
from app.services.storage import MediaStorageService

bearer_scheme = HTTPBearer(auto_error=False)


def get_storage(
    settings: Annotated[Settings, Depends(get_settings)],
) -> MediaStorageService:
    return MediaStorageService(settings)


def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)],
    db: Annotated[Session, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> User:
    if (
        credentials is None
        or credentials.scheme.lower() != "bearer"
        or not credentials.credentials
    ):
        raise ProblemException(
            status_code=401,
            code="INVALID_CREDENTIALS",
            title="Unauthorized",
            detail="Missing or invalid bearer token",
        )
    user_id = decode_access_token(credentials.credentials, settings)
    user = db.get(User, user_id)
    if user is None:
        raise ProblemException(
            status_code=401,
            code="INVALID_CREDENTIALS",
            title="Unauthorized",
            detail="User not found",
        )
    return user


def require_active_project_member(
    db: Session,
    project_id: UUID,
    user_id: UUID,
) -> tuple[Project, ProjectMember]:
    row = db.execute(
        select(Project, ProjectMember)
        .join(ProjectMember, ProjectMember.project_id == Project.id)
        .where(
            Project.id == project_id,
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
            detail="Project not found",
        )
    return row[0], row[1]


def require_project_owner(
    db: Session,
    project_id: UUID,
    user_id: UUID,
) -> tuple[Project, ProjectMember]:
    project, member = require_active_project_member(db, project_id, user_id)
    if member.role != "OWNER":
        raise ProblemException(
            status_code=403,
            code="FORBIDDEN",
            title="Forbidden",
            detail="Project owner role required",
        )
    return project, member

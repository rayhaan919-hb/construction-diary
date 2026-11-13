from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Response
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.config import Settings, get_settings
from app.core.errors import ProblemException
from app.db.models import DeviceToken, User
from app.db.session import get_db
from app.schemas.auth import (
    ChangePasswordRequest,
    DeviceTokenRequest,
    LoginRequest,
    LogoutRequest,
    RefreshRequest,
    TokenPairResponse,
    UserResponse,
)
from app.services.auth import (
    authenticate_user,
    hash_password,
    issue_token_pair,
    revoke_single_refresh_token,
    rotate_refresh_token,
    verify_password,
)

router = APIRouter(prefix="/v1", tags=["auth"])


@router.post("/auth/login", response_model=TokenPairResponse)
def login(
    payload: LoginRequest,
    db: Annotated[Session, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> TokenPairResponse:
    user = authenticate_user(db, payload.email, payload.password)
    return issue_token_pair(
        db=db,
        user=user,
        device_label=payload.device_label,
        settings=settings,
    )


@router.post("/auth/refresh", response_model=TokenPairResponse)
def refresh_tokens(
    payload: RefreshRequest,
    db: Annotated[Session, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> TokenPairResponse:
    return rotate_refresh_token(db=db, raw_refresh_token=payload.refresh_token, settings=settings)


@router.post("/auth/logout", status_code=204)
def logout(
    payload: LogoutRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> Response:
    revoke_single_refresh_token(db, current_user.id, payload.refresh_token)
    return Response(status_code=204)


@router.get("/me", response_model=UserResponse)
def get_me(current_user: Annotated[User, Depends(get_current_user)]) -> UserResponse:
    return UserResponse.model_validate(current_user)


@router.post("/me/password", status_code=204)
def change_password(
    payload: ChangePasswordRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> Response:
    if not verify_password(payload.current_password, current_user.password_hash):
        raise ProblemException(
            status_code=401,
            code="INVALID_CREDENTIALS",
            title="Unauthorized",
            detail="Current password is incorrect",
        )
    current_user.password_hash = hash_password(payload.new_password)
    current_user.must_change_password = False
    db.commit()
    return Response(status_code=204)


@router.post("/me/device-tokens", status_code=204)
def register_device_token(
    payload: DeviceTokenRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> Response:
    stmt = pg_insert(DeviceToken).values(
        user_id=current_user.id,
        fcm_token=payload.fcm_token,
        platform="ANDROID",
    )
    stmt = stmt.on_conflict_do_update(
        index_elements=[DeviceToken.fcm_token],
        set_={
            "user_id": current_user.id,
            "platform": "ANDROID",
            "updated_at": datetime.now(UTC),
        },
    )
    db.execute(stmt)
    db.commit()
    return Response(status_code=204)

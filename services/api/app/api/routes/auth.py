from __future__ import annotations

import smtplib
from datetime import UTC, datetime
from email.message import EmailMessage
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, Request, Response
from sqlalchemy import delete, func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from app.api.deps import extract_client_meta, get_current_user
from app.core.config import Settings, get_settings
from app.core.errors import ProblemException
from app.core.rate_limit import rate_limiter
from app.db.models import DeviceToken, RefreshToken, User
from app.db.session import get_db
from app.schemas.auth import (
    ChangePasswordRequest,
    DeviceTokenRequest,
    LoginRequest,
    LogoutRequest,
    PasswordResetConfirmRequest,
    PasswordResetRequest,
    PasswordResetRequestResponse,
    ProfilePatchRequest,
    RefreshRequest,
    SessionResponse,
    TokenPairResponse,
    UserResponse,
)
from app.services.audit import record_audit_event
from app.services.auth import (
    TokenError,
    clear_login_failures,
    consume_password_reset_token,
    create_password_reset_token,
    hash_password,
    is_account_locked,
    issue_token_pair,
    needs_password_rehash,
    record_failed_login,
    revoke_all_user_sessions,
    revoke_single_refresh_token,
    rotate_refresh_token,
    verify_dummy_password,
    verify_password,
)

router = APIRouter(tags=["auth"])


def _send_password_reset_email(
    recipient_email: str,
    reset_token: str,
    settings: Settings,
) -> None:
    if not settings.SMTP_HOST:
        return
    msg = EmailMessage()
    msg["Subject"] = "Site Diary Password Reset"
    msg["From"] = settings.SMTP_FROM
    msg["To"] = recipient_email
    base = settings.cors_origin_list[0] if settings.cors_origin_list else ""
    reset_hint = f"{base.rstrip('/')}/reset-password?token={reset_token}" if base else reset_token
    msg.set_content(
        "A password reset was requested for your Site Diary account.\n\n"
        f"Reset link or token (expires in {settings.PASSWORD_RESET_TTL_MINUTES} minutes):\n"
        f"{reset_hint}\n\n"
        "If you did not request this, you can safely ignore this message.\n"
    )
    with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT, timeout=15) as smtp:
        smtp.ehlo()
        if smtp.has_extn("starttls"):
            smtp.starttls()
            smtp.ehlo()
        if settings.SMTP_USER and settings.SMTP_PASSWORD:
            smtp.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
        smtp.send_message(msg)


@router.post("/v1/auth/login", response_model=TokenPairResponse)
def login(
    payload: LoginRequest,
    request: Request,
    db: Annotated[Session, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> TokenPairResponse:
    ip_addr, user_agent = extract_client_meta(request)
    email = payload.email.strip().lower()

    ip_decision = rate_limiter.check(
        f"login:ip:{ip_addr or 'unknown'}",
        settings.RATE_LIMIT_AUTH_PER_MINUTE,
        60,
    )
    if not ip_decision.allowed:
        raise ProblemException(
            status_code=429,
            code="RATE_LIMITED",
            title="Too Many Requests",
            detail="Too many authentication attempts. Please wait before trying again.",
            headers={"Retry-After": str(ip_decision.retry_after_seconds)},
        )

    user = db.scalar(select(User).where(func.lower(User.email) == email))
    if user is None:
        verify_dummy_password(payload.password)
        record_audit_event(
            db,
            action="auth.login.failed",
            resource_type="user",
            actor_email=email,
            ip_address=ip_addr,
            user_agent=user_agent,
            details={"reason": "unknown_email"},
        )
        db.commit()
        raise ProblemException(
            status_code=401,
            code="INVALID_CREDENTIALS",
            title="Unauthorized",
            detail="Invalid email or password",
        )

    if user.status != "ACTIVE":
        record_audit_event(
            db,
            action="auth.login.blocked_inactive",
            resource_type="user",
            resource_id=user.id,
            actor_user=user,
            ip_address=ip_addr,
            user_agent=user_agent,
        )
        db.commit()
        raise ProblemException(
            status_code=403,
            code="ACCOUNT_INACTIVE",
            title="Account Inactive",
            detail="Your account is inactive or suspended. Contact your administrator.",
        )

    if is_account_locked(user):
        retry_secs = max(
            1,
            int((user.locked_until - datetime.now(UTC)).total_seconds())
            if user.locked_until
            else 60,
        )
        record_audit_event(
            db,
            action="auth.login.locked_out",
            resource_type="user",
            resource_id=user.id,
            actor_user=user,
            ip_address=ip_addr,
            user_agent=user_agent,
        )
        db.commit()
        raise ProblemException(
            status_code=429,
            code="ACCOUNT_LOCKED",
            title="Account Temporarily Locked",
            detail="Too many failed login attempts. Try again later or reset your password.",
            headers={"Retry-After": str(retry_secs)},
        )

    if not verify_password(user.password_hash, payload.password):
        locked_now = record_failed_login(db, user, settings)
        record_audit_event(
            db,
            action="auth.lockout" if locked_now else "auth.login.failed",
            resource_type="user",
            resource_id=user.id,
            actor_user=user,
            ip_address=ip_addr,
            user_agent=user_agent,
            details={"failed_attempts": user.failed_login_attempts, "locked": locked_now},
        )
        db.commit()
        if locked_now:
            raise ProblemException(
                status_code=429,
                code="ACCOUNT_LOCKED",
                title="Account Temporarily Locked",
                detail="Too many failed login attempts. Try again later or reset your password.",
                headers={"Retry-After": str(settings.LOGIN_LOCKOUT_MINUTES * 60)},
            )
        raise ProblemException(
            status_code=401,
            code="INVALID_CREDENTIALS",
            title="Unauthorized",
            detail="Invalid email or password",
        )

    clear_login_failures(db, user)
    if needs_password_rehash(user.password_hash):
        user.password_hash = hash_password(payload.password)

    pair = issue_token_pair(
        db,
        user,
        device_label=payload.device_label,
        settings=settings,
    )
    record_audit_event(
        db,
        action="auth.login.success",
        resource_type="user",
        resource_id=user.id,
        actor_user=user,
        ip_address=ip_addr,
        user_agent=user_agent,
        details={"device_label": payload.device_label},
    )
    db.commit()
    db.refresh(user)
    return TokenPairResponse(
        access_token=pair.access_token,
        refresh_token=pair.refresh_token,
        access_expires_in=pair.access_expires_in,
        refresh_expires_at=pair.refresh_expires_at,
        user=UserResponse.model_validate(user),
    )


@router.post("/v1/auth/refresh", response_model=TokenPairResponse)
def refresh(
    payload: RefreshRequest,
    request: Request,
    db: Annotated[Session, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> TokenPairResponse:
    ip_addr, user_agent = extract_client_meta(request)
    try:
        user, pair = rotate_refresh_token(db, payload.refresh_token, settings=settings)
    except TokenError as exc:
        if exc.code == "TOKEN_REUSED":
            record_audit_event(
                db,
                action="auth.security.token_reused",
                resource_type="refresh_token",
                ip_address=ip_addr,
                user_agent=user_agent,
                details={"severity": "high"},
            )
            db.commit()
        raise ProblemException(
            status_code=401,
            code=exc.code,
            title=exc.title,
            detail=exc.detail,
        ) from exc

    db.commit()
    db.refresh(user)
    return TokenPairResponse(
        access_token=pair.access_token,
        refresh_token=pair.refresh_token,
        access_expires_in=pair.access_expires_in,
        refresh_expires_at=pair.refresh_expires_at,
        user=UserResponse.model_validate(user),
    )


@router.post("/v1/auth/logout", status_code=204)
def logout(
    payload: LogoutRequest,
    request: Request,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> Response:
    ip_addr, user_agent = extract_client_meta(request)
    revoke_single_refresh_token(
        db, payload.refresh_token, expected_user_id=current_user.id
    )
    if payload.fcm_token:
        db.execute(
            delete(DeviceToken).where(
                DeviceToken.user_id == current_user.id,
                DeviceToken.fcm_token == payload.fcm_token.strip(),
            )
        )
    record_audit_event(
        db,
        action="auth.logout",
        resource_type="user",
        resource_id=current_user.id,
        actor_user=current_user,
        ip_address=ip_addr,
        user_agent=user_agent,
    )
    db.commit()
    return Response(status_code=204)


@router.post("/v1/auth/logout-all", status_code=204)
def logout_all_sessions(
    request: Request,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> Response:
    ip_addr, user_agent = extract_client_meta(request)
    revoke_all_user_sessions(
        db,
        current_user,
        bump_token_version=True,
        clear_device_tokens=True,
    )
    record_audit_event(
        db,
        action="auth.logout_all",
        resource_type="user",
        resource_id=current_user.id,
        actor_user=current_user,
        ip_address=ip_addr,
        user_agent=user_agent,
    )
    db.commit()
    return Response(status_code=204)


@router.post(
    "/v1/auth/password-reset/request",
    response_model=PasswordResetRequestResponse,
    status_code=202,
)
def request_password_reset(
    payload: PasswordResetRequest,
    request: Request,
    background_tasks: BackgroundTasks,
    db: Annotated[Session, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> PasswordResetRequestResponse:
    ip_addr, user_agent = extract_client_meta(request)
    email = payload.email.strip().lower()
    decision = rate_limiter.check(f"pwreset:{ip_addr or 'unknown'}:{email}", 5, 300)
    if not decision.allowed:
        raise ProblemException(
            status_code=429,
            code="RATE_LIMITED",
            title="Too Many Requests",
            detail="Please wait before requesting another password reset.",
            headers={"Retry-After": str(decision.retry_after_seconds)},
        )

    user = db.scalar(select(User).where(func.lower(User.email) == email))
    dev_token: str | None = None
    if user is not None and user.status == "ACTIVE":
        raw_token, _ = create_password_reset_token(db, user, settings=settings)
        record_audit_event(
            db,
            action="auth.password_reset.requested",
            resource_type="user",
            resource_id=user.id,
            actor_user=user,
            ip_address=ip_addr,
            user_agent=user_agent,
        )
        db.commit()
        if settings.SMTP_HOST:
            background_tasks.add_task(
                _send_password_reset_email, user.email, raw_token, settings
            )
        elif not settings.is_deployed_env:
            dev_token = raw_token

    return PasswordResetRequestResponse(
        accepted=True,
        message=(
            "If an active account matches that email, "
            "password reset instructions have been sent."
        ),
        dev_reset_token=dev_token,
    )


@router.post("/v1/auth/password-reset/confirm", status_code=204)
def confirm_password_reset(
    payload: PasswordResetConfirmRequest,
    request: Request,
    db: Annotated[Session, Depends(get_db)],
) -> Response:
    ip_addr, user_agent = extract_client_meta(request)
    try:
        user = consume_password_reset_token(db, payload.token, payload.new_password)
    except TokenError as exc:
        raise ProblemException(
            status_code=400,
            code=exc.code,
            title=exc.title,
            detail=exc.detail,
        ) from exc

    record_audit_event(
        db,
        action="auth.password_reset.completed",
        resource_type="user",
        resource_id=user.id,
        actor_user=user,
        ip_address=ip_addr,
        user_agent=user_agent,
    )
    db.commit()
    return Response(status_code=204)


@router.get("/v1/me", response_model=UserResponse)
def get_me(current_user: Annotated[User, Depends(get_current_user)]) -> UserResponse:
    return UserResponse.model_validate(current_user)


@router.patch("/v1/me", response_model=UserResponse)
def update_me(
    payload: ProfilePatchRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> UserResponse:
    if payload.full_name is not None:
        current_user.full_name = payload.full_name.strip()
    if payload.preferred_locale is not None:
        current_user.preferred_locale = payload.preferred_locale
    db.commit()
    db.refresh(current_user)
    return UserResponse.model_validate(current_user)


@router.post("/v1/me/password", status_code=204)
def change_password(
    payload: ChangePasswordRequest,
    request: Request,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> Response:
    ip_addr, user_agent = extract_client_meta(request)
    if not verify_password(current_user.password_hash, payload.current_password):
        raise ProblemException(
            status_code=401,
            code="INVALID_CREDENTIALS",
            title="Unauthorized",
            detail="Current password is incorrect",
        )
    now = datetime.now(UTC)
    current_user.password_hash = hash_password(payload.new_password)
    current_user.must_change_password = False
    current_user.password_changed_at = now
    # Revoke all long-lived refresh tokens when credentials change
    revoke_all_user_sessions(
        db,
        current_user,
        bump_token_version=False,
        clear_device_tokens=False,
    )
    record_audit_event(
        db,
        action="auth.password.changed",
        resource_type="user",
        resource_id=current_user.id,
        actor_user=current_user,
        ip_address=ip_addr,
        user_agent=user_agent,
    )
    db.commit()
    return Response(status_code=204)


@router.get("/v1/me/sessions", response_model=list[SessionResponse])
def list_sessions(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> list[SessionResponse]:
    now = datetime.now(UTC)
    rows = list(
        db.scalars(
            select(RefreshToken)
            .where(
                RefreshToken.user_id == current_user.id,
                RefreshToken.revoked_at.is_(None),
                RefreshToken.expires_at > now,
            )
            .order_by(RefreshToken.created_at.desc())
            .limit(50)
        )
    )
    return [
        SessionResponse(
            id=row.id,
            device_label=row.device_label,
            created_at=row.created_at,
            expires_at=row.expires_at,
            revoked_at=row.revoked_at,
        )
        for row in rows
    ]


@router.delete("/v1/me/sessions/{session_id}", status_code=204)
def revoke_session(
    session_id: UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> Response:
    row = db.scalar(
        select(RefreshToken).where(
            RefreshToken.id == session_id,
            RefreshToken.user_id == current_user.id,
        )
    )
    if row is None:
        raise ProblemException(
            status_code=404,
            code="NOT_FOUND",
            title="Not Found",
            detail="Session not found",
        )
    if row.revoked_at is None:
        row.revoked_at = datetime.now(UTC)
        db.commit()
    return Response(status_code=204)


@router.post("/v1/me/device-tokens", status_code=204)
def register_device_token(
    payload: DeviceTokenRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> Response:
    now = datetime.now(UTC)
    fcm_tok = payload.fcm_token.strip()
    existing = db.scalar(select(DeviceToken).where(DeviceToken.fcm_token == fcm_tok))
    if existing is not None and existing.user_id != current_user.id:
        # Reject hijacking another active user's registered push token cleanly
        raise ProblemException(
            status_code=409,
            code="CONFLICT",
            title="Conflict",
            detail="Device token is currently bound to another account",
        )
    stmt = (
        pg_insert(DeviceToken)
        .values(
            user_id=current_user.id,
            fcm_token=fcm_tok,
            platform=payload.platform,
            updated_at=now,
        )
        .on_conflict_do_update(
            index_elements=[DeviceToken.fcm_token],
            set_={
                "user_id": current_user.id,
                "platform": payload.platform,
                "updated_at": now,
            },
        )
    )
    db.execute(stmt)
    db.commit()
    return Response(status_code=204)


@router.delete("/v1/me/device-tokens", status_code=204)
def unregister_device_tokens(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
    fcm_token: str | None = None,
) -> Response:
    stmt = delete(DeviceToken).where(DeviceToken.user_id == current_user.id)
    if fcm_token:
        stmt = stmt.where(DeviceToken.fcm_token == fcm_token.strip())
    db.execute(stmt)
    db.commit()
    return Response(status_code=204)

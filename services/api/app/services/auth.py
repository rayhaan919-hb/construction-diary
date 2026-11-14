from __future__ import annotations

import contextlib
import hashlib
import secrets
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID, uuid4

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerifyMismatchError
from sqlalchemy import delete, select, text, update
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.core.permissions import Role
from app.db.models import DeviceToken, PasswordResetToken, RefreshToken, User

_PASSWORD_HASHER = PasswordHasher(time_cost=3, memory_cost=65536, parallelism=4)
# Precomputed valid Argon2id hash so timing attacks on unknown emails do real Argon2 work.
_DUMMY_ARGON2_HASH = _PASSWORD_HASHER.hash("timing-dummy-password-never-used")
MAX_PASSWORD_LENGTH = 512


class TokenError(Exception):
    def __init__(self, code: str, title: str, detail: str) -> None:
        super().__init__(detail)
        self.code = code
        self.title = title
        self.detail = detail


@dataclass(frozen=True)
class IssuedTokenPair:
    access_token: str
    refresh_token: str
    access_expires_in: int
    refresh_expires_at: datetime


def hash_password(password: str) -> str:
    if len(password.encode("utf-8")) > MAX_PASSWORD_LENGTH:
        raise ValueError("Password exceeds maximum allowed length")
    return _PASSWORD_HASHER.hash(password)


def verify_password(password_hash: str, password: str) -> bool:
    if not password or len(password.encode("utf-8")) > MAX_PASSWORD_LENGTH:
        # Still perform constant-time failure feel safely without DoS memory allocation
        return False
    try:
        return bool(_PASSWORD_HASHER.verify(password_hash, password))
    except (VerifyMismatchError, InvalidHashError):
        return False


def needs_password_rehash(password_hash: str) -> bool:
    try:
        return bool(_PASSWORD_HASHER.check_needs_rehash(password_hash))
    except InvalidHashError:
        return True


def verify_dummy_password(password: str) -> None:
    if not password or len(password.encode("utf-8")) > MAX_PASSWORD_LENGTH:
        return
    with contextlib.suppress(VerifyMismatchError):
        _PASSWORD_HASHER.verify(_DUMMY_ARGON2_HASH, password)


def hash_refresh_token(raw_token: str) -> str:
    return hashlib.sha256(raw_token.encode("utf-8")).hexdigest()


def hash_one_time_token(raw_token: str) -> str:
    return hashlib.sha256(raw_token.encode("utf-8")).hexdigest()


def generate_temporary_password(length: int = 12) -> str:
    alphabet = "abcdefghjkmnpqrstuvwxyzABCDEFGHJKMNPQRSTUVWXYZ23456789"
    return "".join(secrets.choice(alphabet) for _ in range(length))


def create_access_token(
    *,
    user_id: UUID,
    role: Role | str,
    organization_id: UUID | None = None,
    token_version: int = 0,
    settings: Settings | None = None,
) -> tuple[str, int]:
    cfg = settings or get_settings()
    now = datetime.now(UTC)
    expires_in = cfg.ACCESS_TOKEN_TTL_SECONDS
    exp = now + timedelta(seconds=expires_in)
    payload: dict[str, Any] = {
        "sub": str(user_id),
        "role": role,
        "tv": token_version,
        "type": "access",
        "iss": cfg.JWT_ISSUER,
        "aud": cfg.JWT_AUDIENCE,
        "jti": str(uuid4()),
        "iat": int(now.timestamp()),
        "exp": int(exp.timestamp()),
    }
    if organization_id is not None:
        payload["org_id"] = str(organization_id)
    token = jwt.encode(payload, cfg.effective_jwt_secret, algorithm="HS256")
    return token, expires_in


def decode_access_token(token: str, settings: Settings | None = None) -> dict[str, Any]:
    cfg = settings or get_settings()
    try:
        payload: dict[str, Any] = jwt.decode(
            token,
            cfg.effective_jwt_secret,
            algorithms=["HS256"],
            issuer=cfg.JWT_ISSUER,
            audience=cfg.JWT_AUDIENCE,
            options={
                "require": ["sub", "exp", "iat", "iss", "aud", "type"],
            },
        )
    except jwt.ExpiredSignatureError as exc:
        raise TokenError("TOKEN_EXPIRED", "Token expired", "Access token has expired") from exc
    except jwt.PyJWTError as exc:
        raise TokenError(
            "INVALID_CREDENTIALS", "Unauthorized", "Invalid access token"
        ) from exc

    if payload.get("type") != "access" or not payload.get("sub"):
        raise TokenError("INVALID_CREDENTIALS", "Unauthorized", "Invalid token payload")
    return payload


def is_account_locked(user: User, now: datetime | None = None) -> bool:
    current = now or datetime.now(UTC)
    return user.locked_until is not None and user.locked_until > current


def record_failed_login(
    db: Session,
    user: User,
    settings: Settings | None = None,
) -> bool:
    """Increment failure counter and apply lockout threshold cleanly.

    Returns True if newly locked.
    """
    cfg = settings or get_settings()
    user.failed_login_attempts = int(user.failed_login_attempts or 0) + 1
    locked_now = False
    if user.failed_login_attempts >= cfg.LOGIN_RATE_LIMIT_MAX_ATTEMPTS:
        user.locked_until = datetime.now(UTC) + timedelta(
            minutes=cfg.LOGIN_LOCKOUT_MINUTES
        )
        locked_now = True
    db.flush()
    return locked_now


def clear_login_failures(db: Session, user: User) -> None:
    user.failed_login_attempts = 0
    user.locked_until = None
    user.last_login_at = datetime.now(UTC)
    db.flush()


def issue_token_pair(
    db: Session,
    user: User,
    *,
    device_label: str | None = None,
    settings: Settings | None = None,
) -> IssuedTokenPair:
    cfg = settings or get_settings()
    access_token, access_expires_in = create_access_token(
        user_id=user.id,
        role=user.role,
        organization_id=user.organization_id,
        token_version=user.token_version,
        settings=cfg,
    )
    raw_refresh = secrets.token_urlsafe(48)
    refresh_expires_at = datetime.now(UTC) + timedelta(days=cfg.REFRESH_TOKEN_TTL_DAYS)
    db_refresh = RefreshToken(
        user_id=user.id,
        token_hash=hash_refresh_token(raw_refresh),
        device_label=device_label,
        expires_at=refresh_expires_at,
    )
    db.add(db_refresh)
    db.flush()
    return IssuedTokenPair(
        access_token=access_token,
        refresh_token=raw_refresh,
        access_expires_in=access_expires_in,
        refresh_expires_at=refresh_expires_at,
    )


def revoke_refresh_chain(db: Session, root_token_id: UUID, revoked_at: datetime) -> None:
    """Revoke every ancestor and descendant refresh token connected to a compromised token."""
    db.execute(
        text(
            """
            WITH RECURSIVE chain AS (
                SELECT id, replaced_by FROM refresh_tokens WHERE id = :root_id
                UNION
                SELECT rt.id, rt.replaced_by
                FROM refresh_tokens rt
                JOIN chain c ON rt.id = c.replaced_by OR rt.replaced_by = c.id
            )
            UPDATE refresh_tokens
            SET revoked_at = COALESCE(revoked_at, :revoked_at)
            WHERE id IN (SELECT id FROM chain)
            """
        ),
        {"root_id": root_token_id, "revoked_at": revoked_at},
    )


def revoke_all_user_sessions(
    db: Session,
    user: User,
    *,
    bump_token_version: bool = True,
    clear_device_tokens: bool = False,
) -> None:
    """Revoke every active refresh session (and optionally invalidate all JWT access tokens)."""
    now = datetime.now(UTC)
    db.execute(
        update(RefreshToken)
        .where(
            RefreshToken.user_id == user.id,
            RefreshToken.revoked_at.is_(None),
        )
        .values(revoked_at=now)
    )
    if bump_token_version:
        user.token_version = int(user.token_version or 0) + 1
    if clear_device_tokens:
        db.execute(delete(DeviceToken).where(DeviceToken.user_id == user.id))
    db.flush()


def rotate_refresh_token(
    db: Session,
    raw_refresh_token: str,
    *,
    settings: Settings | None = None,
) -> tuple[User, IssuedTokenPair]:
    cfg = settings or get_settings()
    now = datetime.now(UTC)
    token_hash = hash_refresh_token(raw_refresh_token)

    stmt = (
        select(RefreshToken)
        .where(RefreshToken.token_hash == token_hash)
        .with_for_update()
    )
    token_row = db.scalar(stmt)
    if token_row is None:
        raise TokenError("INVALID_CREDENTIALS", "Unauthorized", "Unknown refresh token")

    if token_row.replaced_by is not None:
        # Replay of a previously rotated refresh token -> revoke entire chain + bump token version
        revoke_refresh_chain(db, token_row.id, now)
        user_obj = db.get(User, token_row.user_id)
        if user_obj is not None:
            user_obj.token_version = int(user_obj.token_version or 0) + 1
        db.commit()
        raise TokenError(
            "TOKEN_REUSED",
            "Refresh token reused",
            "Refresh token reuse detected; session family revoked",
        )

    if token_row.revoked_at is not None:
        raise TokenError("INVALID_CREDENTIALS", "Unauthorized", "Refresh token revoked")

    if token_row.expires_at <= now:
        raise TokenError("TOKEN_EXPIRED", "Refresh token expired", "Refresh token expired")

    user = db.get(User, token_row.user_id)
    if user is None or user.status != "ACTIVE":
        raise TokenError("INVALID_CREDENTIALS", "Unauthorized", "Account unavailable")

    new_raw = secrets.token_urlsafe(48)
    new_expires_at = now + timedelta(days=cfg.REFRESH_TOKEN_TTL_DAYS)
    new_row = RefreshToken(
        user_id=user.id,
        token_hash=hash_refresh_token(new_raw),
        device_label=token_row.device_label,
        expires_at=new_expires_at,
    )
    db.add(new_row)
    db.flush()

    token_row.replaced_by = new_row.id
    token_row.revoked_at = now
    db.flush()

    access_token, access_expires_in = create_access_token(
        user_id=user.id,
        role=user.role,
        organization_id=user.organization_id,
        token_version=user.token_version,
        settings=cfg,
    )
    return user, IssuedTokenPair(
        access_token=access_token,
        refresh_token=new_raw,
        access_expires_in=access_expires_in,
        refresh_expires_at=new_expires_at,
    )


def revoke_single_refresh_token(
    db: Session,
    raw_refresh_token: str,
    *,
    expected_user_id: UUID | None = None,
) -> bool:
    token_hash = hash_refresh_token(raw_refresh_token)
    stmt = select(RefreshToken).where(RefreshToken.token_hash == token_hash)
    row = db.scalar(stmt)
    if row is None:
        return False
    if expected_user_id is not None and row.user_id != expected_user_id:
        return False
    if row.revoked_at is None:
        row.revoked_at = datetime.now(UTC)
        db.flush()
    return True


def create_password_reset_token(
    db: Session,
    user: User,
    *,
    settings: Settings | None = None,
) -> tuple[str, datetime]:
    """Invalidate older unused reset tokens for the user and issue a fresh hashed reset token."""
    cfg = settings or get_settings()
    now = datetime.now(UTC)
    db.execute(
        update(PasswordResetToken)
        .where(
            PasswordResetToken.user_id == user.id,
            PasswordResetToken.used_at.is_(None),
        )
        .values(used_at=now)
    )
    raw_token = secrets.token_urlsafe(32)
    expires_at = now + timedelta(minutes=cfg.PASSWORD_RESET_TTL_MINUTES)
    db.add(
        PasswordResetToken(
            user_id=user.id,
            token_hash=hash_one_time_token(raw_token),
            expires_at=expires_at,
        )
    )
    db.flush()
    return raw_token, expires_at


def consume_password_reset_token(
    db: Session,
    raw_token: str,
    new_password: str,
) -> User:
    now = datetime.now(UTC)
    token_hash = hash_one_time_token(raw_token)
    row = db.scalar(
        select(PasswordResetToken)
        .where(PasswordResetToken.token_hash == token_hash)
        .with_for_update()
    )
    if row is None or row.used_at is not None or row.expires_at <= now:
        raise TokenError(
            "INVALID_RESET_TOKEN",
            "Invalid or expired token",
            "Password reset token is invalid or expired",
        )
    user = db.get(User, row.user_id)
    if user is None or user.status != "ACTIVE":
        raise TokenError(
            "INVALID_RESET_TOKEN",
            "Invalid or expired token",
            "User account is unavailable",
        )
    user.password_hash = hash_password(new_password)
    user.must_change_password = False
    user.password_changed_at = now
    clear_login_failures(db, user)
    row.used_at = now
    revoke_all_user_sessions(db, user, bump_token_version=True)
    return user

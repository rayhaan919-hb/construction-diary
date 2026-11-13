from __future__ import annotations

import hashlib
import secrets
from datetime import UTC, datetime, timedelta
from uuid import UUID

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.core.errors import ProblemException
from app.db.models import RefreshToken, User
from app.schemas.auth import TokenPairResponse, UserResponse

_PASSWORD_HASHER = PasswordHasher()
# Precomputed dummy hash to keep timing consistent when email is not found.
_DUMMY_HASH = _PASSWORD_HASHER.hash("dummy-password-for-timing-protection")


def hash_password(password: str) -> str:
    return _PASSWORD_HASHER.hash(password)


def verify_password(plain_password: str, password_hash: str) -> bool:
    try:
        return bool(_PASSWORD_HASHER.verify(password_hash, plain_password))
    except (VerifyMismatchError, InvalidHashError, VerificationError):
        return False


def hash_refresh_token(raw_token: str) -> str:
    return hashlib.sha256(raw_token.encode("utf-8")).hexdigest()


def generate_temporary_password(length: int = 12) -> str:
    alphabet = "ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz23456789"
    return "".join(secrets.choice(alphabet) for _ in range(max(length, 10)))


def create_access_token(user: User, settings: Settings | None = None) -> str:
    cfg = settings or get_settings()
    now = datetime.now(UTC)
    payload = {
        "sub": str(user.id),
        "role": user.role,
        "type": "access",
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(seconds=cfg.ACCESS_TOKEN_TTL_SECONDS)).timestamp()),
    }
    return str(jwt.encode(payload, cfg.JWT_SECRET, algorithm="HS256"))


def decode_access_token(token: str, settings: Settings | None = None) -> UUID:
    cfg = settings or get_settings()
    try:
        payload = jwt.decode(token, cfg.JWT_SECRET, algorithms=["HS256"])
    except jwt.ExpiredSignatureError as exc:
        raise ProblemException(
            status_code=401,
            code="TOKEN_EXPIRED",
            title="Unauthorized",
            detail="Access token has expired",
        ) from exc
    except jwt.InvalidTokenError as exc:
        raise ProblemException(
            status_code=401,
            code="INVALID_CREDENTIALS",
            title="Unauthorized",
            detail="Invalid access token",
        ) from exc

    if payload.get("type") != "access" or "sub" not in payload:
        raise ProblemException(
            status_code=401,
            code="INVALID_CREDENTIALS",
            title="Unauthorized",
            detail="Invalid access token payload",
        )

    try:
        return UUID(str(payload["sub"]))
    except ValueError as exc:
        raise ProblemException(
            status_code=401,
            code="INVALID_CREDENTIALS",
            title="Unauthorized",
            detail="Invalid subject in access token",
        ) from exc


def authenticate_user(db: Session, email: str, password: str) -> User:
    normalized = email.strip().lower()
    user = db.scalar(select(User).where(text("LOWER(email) = :email")).params(email=normalized))
    if user is None:
        verify_password(password, _DUMMY_HASH)
        raise ProblemException(
            status_code=401,
            code="INVALID_CREDENTIALS",
            title="Unauthorized",
            detail="Invalid email or password",
        )
    if not verify_password(password, user.password_hash):
        raise ProblemException(
            status_code=401,
            code="INVALID_CREDENTIALS",
            title="Unauthorized",
            detail="Invalid email or password",
        )
    return user


def issue_token_pair(
    db: Session,
    user: User,
    device_label: str | None = None,
    settings: Settings | None = None,
) -> TokenPairResponse:
    cfg = settings or get_settings()
    now = datetime.now(UTC)
    raw_refresh = secrets.token_urlsafe(48)
    refresh_expires_at = now + timedelta(days=cfg.REFRESH_TOKEN_TTL_DAYS)
    refresh_row = RefreshToken(
        user_id=user.id,
        token_hash=hash_refresh_token(raw_refresh),
        device_label=device_label,
        expires_at=refresh_expires_at,
    )
    db.add(refresh_row)
    db.commit()

    return TokenPairResponse(
        access_token=create_access_token(user, cfg),
        refresh_token=raw_refresh,
        access_expires_in=cfg.ACCESS_TOKEN_TTL_SECONDS,
        refresh_expires_at=refresh_expires_at,
        user=UserResponse.model_validate(user),
    )


def revoke_refresh_chain(db: Session, token_id: UUID) -> None:
    db.execute(
        text(
            """
            WITH RECURSIVE
            ancestors AS (
                SELECT id, replaced_by FROM refresh_tokens WHERE id = :tid
                UNION
                SELECT rt.id, rt.replaced_by
                FROM refresh_tokens rt
                JOIN ancestors a ON rt.replaced_by = a.id
            ),
            descendants AS (
                SELECT id, replaced_by FROM refresh_tokens WHERE id = :tid
                UNION
                SELECT rt.id, rt.replaced_by
                FROM refresh_tokens rt
                JOIN descendants d ON rt.id = d.replaced_by
            )
            UPDATE refresh_tokens
            SET revoked_at = COALESCE(revoked_at, NOW())
            WHERE id IN (
                SELECT id FROM ancestors
                UNION
                SELECT id FROM descendants
            )
            """
        ),
        {"tid": token_id},
    )


def rotate_refresh_token(
    db: Session,
    raw_refresh_token: str,
    settings: Settings | None = None,
) -> TokenPairResponse:
    cfg = settings or get_settings()
    token_hash = hash_refresh_token(raw_refresh_token)
    token_row = db.scalar(
        select(RefreshToken)
        .where(RefreshToken.token_hash == token_hash)
        .with_for_update()
    )
    if token_row is None:
        raise ProblemException(
            status_code=401,
            code="INVALID_CREDENTIALS",
            title="Unauthorized",
            detail="Invalid refresh token",
        )

    if token_row.replaced_by is not None:
        revoke_refresh_chain(db, token_row.id)
        db.commit()
        raise ProblemException(
            status_code=401,
            code="TOKEN_REUSED",
            title="Unauthorized",
            detail="Refresh token reuse detected; token chain revoked",
        )

    if token_row.revoked_at is not None:
        raise ProblemException(
            status_code=401,
            code="INVALID_CREDENTIALS",
            title="Unauthorized",
            detail="Refresh token has been revoked",
        )

    now = datetime.now(UTC)
    if token_row.expires_at <= now:
        raise ProblemException(
            status_code=401,
            code="TOKEN_EXPIRED",
            title="Unauthorized",
            detail="Refresh token has expired",
        )

    user = db.get(User, token_row.user_id)
    if user is None:
        raise ProblemException(
            status_code=401,
            code="INVALID_CREDENTIALS",
            title="Unauthorized",
            detail="User no longer exists",
        )

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
    token_row.last_used_at = now
    db.commit()

    return TokenPairResponse(
        access_token=create_access_token(user, cfg),
        refresh_token=new_raw,
        access_expires_in=cfg.ACCESS_TOKEN_TTL_SECONDS,
        refresh_expires_at=new_expires_at,
        user=UserResponse.model_validate(user),
    )


def revoke_single_refresh_token(db: Session, user_id: UUID, raw_refresh_token: str) -> None:
    token_hash = hash_refresh_token(raw_refresh_token)
    token_row = db.scalar(
        select(RefreshToken).where(
            RefreshToken.token_hash == token_hash,
            RefreshToken.user_id == user_id,
        )
    )
    if token_row is not None and token_row.revoked_at is None:
        token_row.revoked_at = datetime.now(UTC)
        db.commit()

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import jwt
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.models import DeviceToken, RefreshToken, User


def test_login_and_me_and_problem_errors(
    client: TestClient,
    owner_user: User,
) -> None:
    # Wrong password -> 401 RFC 7807 application/problem+json
    bad_login = client.post(
        "/v1/auth/login",
        json={"email": owner_user.email, "password": "wrong-password"},
    )
    assert bad_login.status_code == 401
    assert bad_login.headers["content-type"].startswith("application/problem+json")
    body = bad_login.json()
    assert body["code"] == "INVALID_CREDENTIALS"
    assert body["status"] == 401

    # Validation error -> 422 RFC 7807
    bad_shape = client.post(
        "/v1/auth/login",
        json={"email": "not-an-email", "password": "short"},
    )
    assert bad_shape.status_code == 422
    assert bad_shape.headers["content-type"].startswith("application/problem+json")
    assert bad_shape.json()["code"] == "VALIDATION"
    assert len(bad_shape.json()["errors"]) >= 1

    # Missing bearer token -> 401
    unauth = client.get("/v1/me")
    assert unauth.status_code == 401
    assert unauth.headers["content-type"].startswith("application/problem+json")
    assert unauth.json()["code"] == "INVALID_CREDENTIALS"

    # Expired JWT -> 401 TOKEN_EXPIRED
    cfg = get_settings()
    expired_token = jwt.encode(
        {
            "sub": str(owner_user.id),
            "role": owner_user.role,
            "type": "access",
            "iat": int((datetime.now(UTC) - timedelta(hours=1)).timestamp()),
            "exp": int((datetime.now(UTC) - timedelta(minutes=5)).timestamp()),
        },
        cfg.JWT_SECRET,
        algorithm="HS256",
    )
    expired_resp = client.get(
        "/v1/me",
        headers={"Authorization": f"Bearer {expired_token}"},
    )
    assert expired_resp.status_code == 401
    assert expired_resp.json()["code"] == "TOKEN_EXPIRED"

    # Valid login + /v1/me
    ok_login = client.post(
        "/v1/auth/login",
        json={
            "email": owner_user.email,
            "password": "owner12345",
            "device_label": "pytest-web",
        },
    )
    assert ok_login.status_code == 200
    pair = ok_login.json()
    assert pair["access_expires_in"] == 900
    assert pair["user"]["email"] == owner_user.email

    me_resp = client.get(
        "/v1/me",
        headers={"Authorization": f"Bearer {pair['access_token']}"},
    )
    assert me_resp.status_code == 200
    assert me_resp.json()["id"] == str(owner_user.id)


def test_refresh_rotation_and_theft_detection(
    client: TestClient,
    db_session: Session,
    owner_user: User,
) -> None:
    login_resp = client.post(
        "/v1/auth/login",
        json={"email": owner_user.email, "password": "owner12345"},
    )
    assert login_resp.status_code == 200
    t1 = login_resp.json()["refresh_token"]

    # Rotate T1 -> T2
    r1 = client.post("/v1/auth/refresh", json={"refresh_token": t1})
    assert r1.status_code == 200
    t2 = r1.json()["refresh_token"]
    assert t2 != t1

    # Rotate T2 -> T3
    r2 = client.post("/v1/auth/refresh", json={"refresh_token": t2})
    assert r2.status_code == 200
    t3 = r2.json()["refresh_token"]
    assert t3 != t2

    # Replay T1 (already rotated) -> 401 TOKEN_REUSED & revokes entire chain!
    replay = client.post("/v1/auth/refresh", json={"refresh_token": t1})
    assert replay.status_code == 401
    assert replay.headers["content-type"].startswith("application/problem+json")
    assert replay.json()["code"] == "TOKEN_REUSED"

    # T3 (the active token in the compromised chain) must now be revoked too!
    use_t3 = client.post("/v1/auth/refresh", json={"refresh_token": t3})
    assert use_t3.status_code == 401

    db_session.expire_all()
    chain_rows = list(
        db_session.scalars(
            select(RefreshToken).where(RefreshToken.user_id == owner_user.id)
        )
    )
    assert len(chain_rows) == 3
    assert all(row.revoked_at is not None for row in chain_rows)


def test_logout_password_change_and_device_tokens(
    client: TestClient,
    db_session: Session,
    supervisor_user: User,
) -> None:
    # Force must_change_password=True to verify clearing
    supervisor_user.must_change_password = True
    db_session.commit()

    login_resp = client.post(
        "/v1/auth/login",
        json={"email": supervisor_user.email, "password": "super12345"},
    )
    assert login_resp.status_code == 200
    tokens = login_resp.json()
    headers = {"Authorization": f"Bearer {tokens['access_token']}"}
    assert tokens["user"]["must_change_password"] is True

    # Register FCM token idempotently
    for _ in range(2):
        dt_resp = client.post(
            "/v1/me/device-tokens",
            headers=headers,
            json={"fcm_token": "fcm-device-token-123"},
        )
        assert dt_resp.status_code == 204
    assert len(db_session.scalars(select(DeviceToken)).all()) == 1

    # Wrong current password -> 401
    bad_pw = client.post(
        "/v1/me/password",
        headers=headers,
        json={"current_password": "wrongpassword", "new_password": "newsuper12345"},
    )
    assert bad_pw.status_code == 401
    assert bad_pw.json()["code"] == "INVALID_CREDENTIALS"

    # Valid password change -> 204 & must_change_password cleared
    ok_pw = client.post(
        "/v1/me/password",
        headers=headers,
        json={"current_password": "super12345", "new_password": "newsuper12345"},
    )
    assert ok_pw.status_code == 204

    me_resp = client.get("/v1/me", headers=headers)
    assert me_resp.status_code == 200
    assert me_resp.json()["must_change_password"] is False

    # Logout revokes refresh token
    logout_resp = client.post(
        "/v1/auth/logout",
        headers=headers,
        json={"refresh_token": tokens["refresh_token"]},
    )
    assert logout_resp.status_code == 204

    post_logout_refresh = client.post(
        "/v1/auth/refresh",
        json={"refresh_token": tokens["refresh_token"]},
    )
    assert post_logout_refresh.status_code == 401

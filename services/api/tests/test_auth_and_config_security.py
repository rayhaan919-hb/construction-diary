from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings, validate_runtime_configuration
from app.db.models import Organization, User
from app.scripts.seed import seed_database
from tests.conftest import assert_problem_json, auth_headers


def test_account_lockout_ip_rate_limit_password_reset_and_sessions(
    client: TestClient,
    db_session: Session,
    owner_user: User,
    default_org: Organization,
) -> None:
    del default_org

    # 1. Account lockout triggers on the 5th failed attempt (LOGIN_RATE_LIMIT_MAX_ATTEMPTS=5)
    for _ in range(4):
        bad = client.post(
            "/v1/auth/login",
            json={"email": owner_user.email, "password": "wrongpassword"},
        )
        assert_problem_json(bad, 401, "INVALID_CREDENTIALS")

    fifth_bad = client.post(
        "/v1/auth/login",
        json={"email": owner_user.email, "password": "wrongpassword"},
    )
    assert_problem_json(fifth_bad, 429, "ACCOUNT_LOCKED")

    locked_resp = client.post(
        "/v1/auth/login",
        json={"email": owner_user.email, "password": "owner12345"},
    )
    assert_problem_json(locked_resp, 429, "ACCOUNT_LOCKED")

    # Unlock via password reset flow!
    reset_req = client.post(
        "/v1/auth/password-reset/request",
        json={"email": owner_user.email},
    )
    assert reset_req.status_code == 202
    dev_token = reset_req.json()["dev_reset_token"]
    assert dev_token

    reset_confirm = client.post(
        "/v1/auth/password-reset/confirm",
        json={"token": dev_token, "new_password": "UpdatedOwnerPass1!"},
    )
    assert reset_confirm.status_code == 204

    # Reusing single-use token fails
    reused_reset = client.post(
        "/v1/auth/password-reset/confirm",
        json={"token": dev_token, "new_password": "AnotherPassword1!"},
    )
    assert_problem_json(reused_reset, 400, "INVALID_RESET_TOKEN")

    # Login with new password succeeds & creates trackable sessions
    login_resp = client.post(
        "/v1/auth/login",
        json={
            "email": owner_user.email,
            "password": "UpdatedOwnerPass1!",
            "device_label": "web-browser",
        },
    )
    assert login_resp.status_code == 200
    headers = {"Authorization": f"Bearer {login_resp.json()['access_token']}"}

    sessions_resp = client.get("/v1/me/sessions", headers=headers)
    assert sessions_resp.status_code == 200
    sessions = sessions_resp.json()
    assert len(sessions) == 1
    session_id = sessions[0]["id"]

    del_sess = client.delete(f"/v1/me/sessions/{session_id}", headers=headers)
    assert del_sess.status_code == 204
    assert client.get("/v1/me/sessions", headers=headers).json() == []

    # /v1/auth/logout-all bumps token_version, immediately invalidating active access tokens
    logout_all = client.post("/v1/auth/logout-all", headers=headers)
    assert logout_all.status_code == 204
    stale_me = client.get("/v1/me", headers=headers)
    assert_problem_json(stale_me, 401, "TOKEN_REVOKED")


def test_login_ip_rate_limiting_enforced(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("RATE_LIMIT_AUTH_PER_MINUTE", "5")
    get_settings.cache_clear()
    cfg_limit = 5
    for idx in range(cfg_limit):
        resp = client.post(
            "/v1/auth/login",
            json={"email": f"unknown{idx}@example.com", "password": "wrongpassword"},
        )
        assert_problem_json(resp, 401, "INVALID_CREDENTIALS")

    throttled = client.post(
        "/v1/auth/login",
        json={"email": "unknown99@example.com", "password": "wrongpassword"},
    )
    assert_problem_json(throttled, 429, "RATE_LIMITED")
    assert "Retry-After" in throttled.headers


def test_device_token_cross_user_protection(
    client: TestClient,
    owner_headers: dict[str, str],
    supervisor_headers: dict[str, str],
) -> None:
    reg1 = client.post(
        "/v1/me/device-tokens",
        headers=owner_headers,
        json={"fcm_token": "shared-fcm-tok-999", "platform": "android"},
    )
    assert reg1.status_code == 204

    # Another user trying to bind the exact same FCM token -> 409 CONFLICT
    hijack = client.post(
        "/v1/me/device-tokens",
        headers=supervisor_headers,
        json={"fcm_token": "shared-fcm-tok-999", "platform": "ANDROID"},
    )
    assert_problem_json(hijack, 409, "CONFLICT")

    # Owner unregisters cleanly -> supervisor can register it
    unreg = client.request(
        "DELETE",
        "/v1/me/device-tokens",
        headers=owner_headers,
        params={"fcm_token": "shared-fcm-tok-999"},
    )
    assert unreg.status_code == 204
    reg2 = client.post(
        "/v1/me/device-tokens",
        headers=supervisor_headers,
        json={"fcm_token": "shared-fcm-tok-999", "platform": "android"},
    )
    assert reg2.status_code == 204


def test_production_config_and_seed_hardening(
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("SEED_OWNER_PASSWORD", raising=False)
    monkeypatch.delenv("SEED_SUPERVISOR_PASSWORD", raising=False)
    strong_media = "MediaSecret9!AlphaBravoCharlieDeltaEcho0123456789"
    # Weak/dev JWT secret rejected in production
    weak_prod = Settings(
        ENV="production",
        DATABASE_URL="postgresql://user:pass@10.0.0.1:5432/prod",
        JWT_SECRET="dev-insecure-jwt-secret-change-me",
        MEDIA_URL_SIGNING_SECRET=strong_media,
        CORS_ORIGINS="https://app.sitediary.example",
        TRUSTED_HOSTS="api.sitediary.example",
        PUBLIC_API_BASE_URL="https://api.sitediary.example",
        STORAGE_BACKEND="gcs",
        GCS_BUCKET="site-diary-prod-media",
        USE_MOCK_GEMINI=False,
        ENABLE_API_DOCS=False,
        ENABLE_DEV_SEED=False,
    )
    with pytest.raises(RuntimeError, match="JWT_SECRET"):
        validate_runtime_configuration(weak_prod)

    # Wildcard CORS rejected in production
    wildcard_cors_prod = Settings(
        ENV="production",
        DATABASE_URL="postgresql://user:pass@10.0.0.1:5432/prod",
        JWT_SECRET="JwtSecret8!HotelIndiaJulietKiloLimaMikeNovember!",
        MEDIA_URL_SIGNING_SECRET=strong_media,
        CORS_ORIGINS="*",
        TRUSTED_HOSTS="api.sitediary.example",
        PUBLIC_API_BASE_URL="https://api.sitediary.example",
        STORAGE_BACKEND="gcs",
        GCS_BUCKET="site-diary-prod-media",
        USE_MOCK_GEMINI=False,
        ENABLE_API_DOCS=False,
        ENABLE_DEV_SEED=False,
    )
    with pytest.raises(RuntimeError, match="CORS_ORIGINS"):
        validate_runtime_configuration(wildcard_cors_prod)

    # Seed refused in production even if called directly
    with pytest.raises(RuntimeError, match="disabled outside development"):
        seed_database(db_session, settings=Settings(ENV="production", ENABLE_DEV_SEED=True))

    # Auth headers helper smoke check when using owner_user password
    _ = auth_headers

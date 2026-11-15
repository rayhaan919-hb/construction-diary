from __future__ import annotations

import hashlib
import os
import threading
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import jwt
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.core.rate_limit import rate_limiter
from app.db.models import (
    AuditLog,
    ExtractionJob,
    MediaCleanupRun,
    MediaReservation,
    Organization,
    OrganizationMember,
    Project,
    ProjectMember,
    UploadTicket,
    User,
)
from app.main import app
from app.services.auth import hash_password
from app.services.media_cleanup import run_media_cleanup
from app.services.storage import MediaStorageService
from tests.conftest import assert_problem_json, auth_headers

VALID_M4A = b"\x00\x00\x00\x18ftypmp42\x00\x00\x00\x00media-payload"
VALID_JPEG = (
    b"\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x00\x00\x01\x00\x01\x00\x00"
    b"photo-bytes\xff\xd9"
)


def _create_verified_user(
    db_session: Session,
    *,
    org_id: uuid.UUID,
    email: str,
    role: str,
) -> User:
    user = User(
        organization_id=org_id,
        email=email,
        password_hash=hash_password("SecurePass1!"),
        full_name=email.split("@")[0],
        role=role,
        preferred_locale="en",
        must_change_password=False,
    )
    db_session.add(user)
    db_session.flush()
    db_session.add(OrganizationMember(organization_id=org_id, user_id=user.id, role=role))
    db_session.commit()
    db_session.refresh(user)
    return user


def test_media_security_boundaries_and_replay_protection(
    client: TestClient,
    db_session: Session,
    default_org: Organization,
    sample_project: Project,
    owner_headers: dict[str, str],
    supervisor_headers: dict[str, str],
) -> None:
    pid = str(sample_project.id)
    now = datetime.now(UTC)

    # 1. Unauthorized user (unauthenticated & VIEWER) cannot issue upload URLs
    unauth = client.post(
        "/v1/media/upload-url",
        json={
            "kind": "AUDIO",
            "project_id": pid,
            "object_id": str(uuid.uuid4()),
            "content_type": "audio/mp4",
            "byte_size": len(VALID_M4A),
        },
    )
    assert_problem_json(unauth, 401, "INVALID_CREDENTIALS")

    viewer = _create_verified_user(
        db_session, org_id=default_org.id, email="viewer-media@example.com", role="VIEWER"
    )
    db_session.add(ProjectMember(project_id=sample_project.id, user_id=viewer.id, role="VIEWER"))
    db_session.commit()
    viewer_headers = auth_headers(client, viewer.email, "SecurePass1!")

    viewer_upload = client.post(
        "/v1/media/upload-url",
        headers=viewer_headers,
        json={
            "kind": "AUDIO",
            "project_id": pid,
            "object_id": str(uuid.uuid4()),
            "content_type": "audio/mp4",
            "byte_size": len(VALID_M4A),
        },
    )
    assert_problem_json(viewer_upload, 403, "FORBIDDEN")

    # 2. Cross-project isolation (other org/project user gets 404)
    other_org = Organization(
        name="Rival Builders", slug="rival-builders", plan_tier="PRO", subscription_status="ACTIVE"
    )
    db_session.add(other_org)
    db_session.flush()
    rival_owner = _create_verified_user(
        db_session, org_id=other_org.id, email="rival@example.com", role="OWNER"
    )
    rival_headers = auth_headers(client, rival_owner.email, "SecurePass1!")

    cross_proj = client.post(
        "/v1/media/upload-url",
        headers=rival_headers,
        json={
            "kind": "AUDIO",
            "project_id": pid,
            "object_id": str(uuid.uuid4()),
            "content_type": "audio/mp4",
            "byte_size": len(VALID_M4A),
        },
    )
    assert_problem_json(cross_proj, 404, "NOT_FOUND")

    # 3. Cross-user upload / completion on another supervisor's site log is forbidden
    sup2 = _create_verified_user(
        db_session, org_id=default_org.id, email="sup2@example.com", role="SUPERVISOR"
    )
    db_session.add(ProjectMember(project_id=sample_project.id, user_id=sup2.id, role="SUPERVISOR"))
    db_session.commit()
    sup2_headers = auth_headers(client, sup2.email, "SecurePass1!")

    log_id = uuid.uuid4()
    sup1_res = client.post(
        "/v1/media/reservations",
        headers=supervisor_headers,
        json={"kind": "AUDIO", "project_id": pid, "object_id": str(log_id)},
    )
    assert sup1_res.status_code == 201
    sup1_ticket = client.post(
        "/v1/media/upload-url",
        headers=supervisor_headers,
        json={
            "kind": "AUDIO",
            "project_id": pid,
            "object_id": str(log_id),
            "content_type": "audio/mp4",
            "byte_size": len(VALID_M4A),
        },
    )
    assert sup1_ticket.status_code == 200
    t1_json = sup1_ticket.json()

    push_resp = client.post(
        "/v1/sync/push",
        headers=supervisor_headers,
        json={
            "changes": {
                "site_logs": [
                    {
                        "id": str(log_id),
                        "project_id": pid,
                        "log_date": "2026-11-12",
                        "recorded_at": now.isoformat(),
                        "notes": "Sup1 audio",
                        "audio_uri": t1_json["storage_uri"],
                        "client_updated_at": now.isoformat(),
                    }
                ]
            }
        },
    )
    assert push_resp.status_code == 200

    cross_user_ticket = client.post(
        "/v1/media/upload-url",
        headers=sup2_headers,
        json={
            "kind": "AUDIO",
            "project_id": pid,
            "object_id": str(log_id),
            "content_type": "audio/mp4",
            "byte_size": len(VALID_M4A),
        },
    )
    assert_problem_json(cross_user_ticket, 403, "FORBIDDEN")

    # 4. Path traversal, dangerous content types, and oversized uploads rejected
    traversal = client.put(
        "/v1/media/local/..%2F..%2Fetc%2Fpasswd?exp=9999999999&sig=deadbeef&ticket=x",
        content=b"bad",
        headers={"Content-Type": "image/jpeg"},
    )
    assert traversal.status_code in (400, 403, 404)

    oversized = client.post(
        "/v1/media/upload-url",
        headers=supervisor_headers,
        json={
            "kind": "PHOTO",
            "project_id": pid,
            "object_id": str(uuid.uuid4()),
            "content_type": "image/jpeg",
            "byte_size": 100 * 1024 * 1024,
        },
    )
    assert_problem_json(oversized, 422, "VALIDATION")

    spoof_photo_id = uuid.uuid4()
    assert (
        client.post(
            "/v1/media/reservations",
            headers=supervisor_headers,
            json={"kind": "PHOTO", "project_id": pid, "object_id": str(spoof_photo_id)},
        ).status_code
        == 201
    )
    spoof_ticket = client.post(
        "/v1/media/upload-url",
        headers=supervisor_headers,
        json={
            "kind": "PHOTO",
            "project_id": pid,
            "object_id": str(spoof_photo_id),
            "content_type": "image/jpeg",
            "byte_size": 10,
        },
    ).json()
    spoof_put = client.put(
        spoof_ticket["upload_url"].replace("http://testserver", ""),
        content=b"MZ\x90\x00\x03\x00\x00\x00\x04\x00",
        headers={"Content-Type": "image/jpeg"},
    )
    assert_problem_json(spoof_put, 422, "VALIDATION")

    # 5. Valid PUT -> duplicate PUT overwrite blocked (409) -> complete -> replay blocked
    digest = hashlib.sha256(VALID_M4A).hexdigest()
    put_url = t1_json["upload_url"].replace("http://testserver", "")
    assert (
        client.put(put_url, content=VALID_M4A, headers={"Content-Type": "audio/mp4"}).status_code
        == 200
    )
    overwrite_put = client.put(
        put_url, content=VALID_M4A, headers={"Content-Type": "audio/mp4"}
    )
    assert_problem_json(overwrite_put, 409, "OBJECT_EXISTS")

    # Sup2 cannot complete Sup1's upload
    cross_user_complete = client.post(
        "/v1/media/complete",
        headers=sup2_headers,
        json={"kind": "AUDIO", "object_id": str(log_id), "ticket_id": t1_json["ticket_id"]},
    )
    assert_problem_json(cross_user_complete, 403, "FORBIDDEN")

    # SHA-256 mismatch rejected
    bad_hash_complete = client.post(
        "/v1/media/complete",
        headers=supervisor_headers,
        json={
            "kind": "AUDIO",
            "object_id": str(log_id),
            "ticket_id": t1_json["ticket_id"],
            "sha256": "0" * 64,
        },
    )
    assert_problem_json(bad_hash_complete, 422, "VALIDATION")

    ok_complete = client.post(
        "/v1/media/complete",
        headers=supervisor_headers,
        json={
            "kind": "AUDIO",
            "object_id": str(log_id),
            "ticket_id": t1_json["ticket_id"],
            "sha256": digest,
        },
    )
    assert ok_complete.status_code == 204

    # Replay / already-completed ticket blocked
    replay_complete = client.post(
        "/v1/media/complete",
        headers=supervisor_headers,
        json={
            "kind": "AUDIO",
            "object_id": str(log_id),
            "ticket_id": t1_json["ticket_id"],
        },
    )
    assert_problem_json(replay_complete, 409, "TICKET_ALREADY_COMPLETED")

    # 6. Expired upload ticket rejected on /complete
    exp_photo_id = uuid.uuid4()
    assert (
        client.post(
            "/v1/media/reservations",
            headers=owner_headers,
            json={"kind": "PHOTO", "project_id": pid, "object_id": str(exp_photo_id)},
        ).status_code
        == 201
    )
    exp_ticket_json = client.post(
        "/v1/media/upload-url",
        headers=owner_headers,
        json={
            "kind": "PHOTO",
            "project_id": pid,
            "object_id": str(exp_photo_id),
            "content_type": "image/jpeg",
            "byte_size": len(VALID_JPEG),
        },
    ).json()
    client.put(
        exp_ticket_json["upload_url"].replace("http://testserver", ""),
        content=VALID_JPEG,
        headers={"Content-Type": "image/jpeg"},
    )
    client.post(
        "/v1/sync/push",
        headers=owner_headers,
        json={
            "changes": {
                "site_log_photos": [
                    {
                        "id": str(exp_photo_id),
                        "site_log_id": str(log_id),
                        "storage_uri": exp_ticket_json["storage_uri"],
                        "sort_order": 0,
                    }
                ]
            }
        },
    )
    ticket_row = db_session.get(UploadTicket, uuid.UUID(exp_ticket_json["ticket_id"]))
    assert ticket_row is not None
    ticket_row.expires_at = datetime.now(UTC) - timedelta(minutes=5)
    db_session.commit()

    expired_complete = client.post(
        "/v1/media/complete",
        headers=owner_headers,
        json={
            "kind": "PHOTO",
            "object_id": str(exp_photo_id),
            "ticket_id": exp_ticket_json["ticket_id"],
        },
    )
    assert_problem_json(expired_complete, 403, "TICKET_EXPIRED")


def test_gcs_impersonated_credentials_signing_fallback() -> None:
    gcs_cfg = Settings(
        STORAGE_BACKEND="gcs",
        GCS_BUCKET="site-diary-test-bucket",
        SIGNED_URL_TTL_SECONDS=600,
    )
    service = MediaStorageService(gcs_cfg)
    fake_blob = MagicMock()
    fake_blob.generate_signed_url.return_value = "https://storage.googleapis.com/impersonated-v4"
    fake_bucket = MagicMock()
    fake_bucket.blob.return_value = fake_blob
    fake_client = MagicMock()
    fake_client.bucket.return_value = fake_bucket

    creds_no_sign = SimpleNamespace(
        service_account_email="sa@proj.iam.gserviceaccount.com",
        refresh=MagicMock(),
    )
    with (
        patch("google.cloud.storage.Client", return_value=fake_client),
        patch("google.auth.default", return_value=(creds_no_sign, "proj")),
        patch("google.auth.impersonated_credentials.Credentials", return_value="imp-creds") as imp,
    ):
        ticket = service.create_upload_ticket(
            project_id=uuid.uuid4(),
            kind="PHOTO",
            object_id=uuid.uuid4(),
            content_type="image/jpeg",
            ticket_id=uuid.uuid4(),
            expected_byte_size=4096,
        )
        assert ticket.upload_url == "https://storage.googleapis.com/impersonated-v4"
        assert ticket.headers["x-goog-if-generation-match"] == "0"
        assert ticket.headers["x-goog-content-length-range"] == "1,4096"
        creds_no_sign.refresh.assert_called_once()
        imp.assert_called_once()


def test_pending_reservation_isolation_concurrency_quota_and_sync(
    client: TestClient,
    db_session: Session,
    default_org: Organization,
    sample_project: Project,
    owner_headers: dict[str, str],
    supervisor_headers: dict[str, str],
) -> None:
    """Covers Issue 5 requirements: missing target rejection, cross-user/project/org
    reservations, expired reservations, storage quotas, rate limiting, concurrency,
    and offline-to-online sync attachment finalization.
    """
    pid = str(sample_project.id)
    now = datetime.now(UTC)

    # Create a second project in the same org to verify cross-project isolation
    proj2_resp = client.post(
        "/v1/projects",
        headers=owner_headers,
        json={"name": "Second Site", "site_address": "Plot 99", "timezone": "Asia/Karachi"},
    )
    assert proj2_resp.status_code == 201
    proj2_id = proj2_resp.json()["id"]

    # 1. Arbitrary unclaimed object_id without record or reservation is rejected immediately
    unclaimed_id = uuid.uuid4()
    missing_ticket = client.post(
        "/v1/media/upload-url",
        headers=supervisor_headers,
        json={
            "kind": "AUDIO",
            "project_id": pid,
            "object_id": str(unclaimed_id),
            "content_type": "audio/mp4",
            "byte_size": len(VALID_M4A),
        },
    )
    assert_problem_json(missing_ticket, 409, "RESERVATION_REQUIRED")

    # 2. Unauthorized user (VIEWER) and cross-organization user cannot reserve
    viewer = _create_verified_user(
        db_session, org_id=default_org.id, email="viewer-res@example.com", role="VIEWER"
    )
    db_session.add(ProjectMember(project_id=sample_project.id, user_id=viewer.id, role="VIEWER"))
    other_org = Organization(
        name="Other Builders",
        slug=f"other-builders-{uuid.uuid4().hex[:6]}",
        plan_tier="PRO",
        subscription_status="ACTIVE",
    )
    db_session.add(other_org)
    db_session.flush()
    other_owner = _create_verified_user(
        db_session,
        org_id=other_org.id,
        email="other-res@example.com",
        role="OWNER",
    )
    db_session.commit()
    viewer_headers = auth_headers(client, viewer.email, "SecurePass1!")
    other_headers = auth_headers(client, other_owner.email, "SecurePass1!")

    assert_problem_json(
        client.post(
            "/v1/media/reservations",
            headers=viewer_headers,
            json={"kind": "PHOTO", "project_id": pid, "object_id": str(uuid.uuid4())},
        ),
        403,
        "FORBIDDEN",
    )
    assert_problem_json(
        client.post(
            "/v1/media/reservations",
            headers=other_headers,
            json={"kind": "PHOTO", "project_id": pid, "object_id": str(uuid.uuid4())},
        ),
        404,
        "NOT_FOUND",
    )

    # 3. Valid pending reservation is bound to user + project + object_id
    reserved_log_id = uuid.uuid4()
    res_resp = client.post(
        "/v1/media/reservations",
        headers=supervisor_headers,
        json={"kind": "AUDIO", "project_id": pid, "object_id": str(reserved_log_id)},
    )
    assert res_resp.status_code == 201
    res_json = res_resp.json()
    assert res_json["status"] == "ACTIVE"

    # Cross-project ticket attempt using reservation bound to project 1 fails 403
    assert_problem_json(
        client.post(
            "/v1/media/upload-url",
            headers=owner_headers,
            json={
                "kind": "AUDIO",
                "project_id": proj2_id,
                "object_id": str(reserved_log_id),
                "content_type": "audio/mp4",
                "byte_size": len(VALID_M4A),
            },
        ),
        403,
        "FORBIDDEN",
    )
    # Different user in same project cannot hijack another user's reservation or reserve it
    assert_problem_json(
        client.post(
            "/v1/media/reservations",
            headers=owner_headers,
            json={"kind": "AUDIO", "project_id": pid, "object_id": str(reserved_log_id)},
        ),
        403,
        "FORBIDDEN",
    )
    assert_problem_json(
        client.post(
            "/v1/media/upload-url",
            headers=owner_headers,
            json={
                "kind": "AUDIO",
                "project_id": pid,
                "object_id": str(reserved_log_id),
                "content_type": "audio/mp4",
                "byte_size": len(VALID_M4A),
            },
        ),
        403,
        "FORBIDDEN",
    )
    # Owner also cannot claim supervisor's reserved log_id via /v1/sync/push
    hijack_push = client.post(
        "/v1/sync/push",
        headers=owner_headers,
        json={
            "changes": {
                "site_logs": [
                    {
                        "id": str(reserved_log_id),
                        "project_id": pid,
                        "log_date": "2026-11-15",
                        "recorded_at": now.isoformat(),
                        "notes": "Hijack attempt",
                        "client_updated_at": now.isoformat(),
                    }
                ]
            }
        },
    ).json()
    assert hijack_push["results"][0]["status"] == "REJECTED"
    assert hijack_push["results"][0]["error_code"] == "FORBIDDEN"

    # 4. Expired reservation is rejected on /upload-url
    expired_obj_id = uuid.uuid4()
    exp_res = client.post(
        "/v1/media/reservations",
        headers=supervisor_headers,
        json={"kind": "PHOTO", "project_id": pid, "object_id": str(expired_obj_id)},
    ).json()
    res_row = db_session.get(MediaReservation, uuid.UUID(exp_res["reservation_id"]))
    assert res_row is not None
    res_row.expires_at = datetime.now(UTC) - timedelta(seconds=10)
    db_session.commit()
    assert_problem_json(
        client.post(
            "/v1/media/upload-url",
            headers=supervisor_headers,
            json={
                "kind": "PHOTO",
                "project_id": pid,
                "object_id": str(expired_obj_id),
                "content_type": "image/jpeg",
                "byte_size": len(VALID_JPEG),
            },
        ),
        403,
        "RESERVATION_EXPIRED",
    )

    # 5. Offline-to-online full lifecycle: reserve -> ticket -> PUT -> sync/push -> complete
    t_resp = client.post(
        "/v1/media/upload-url",
        headers=supervisor_headers,
        json={
            "kind": "AUDIO",
            "project_id": pid,
            "object_id": str(reserved_log_id),
            "content_type": "audio/mp4",
            "byte_size": len(VALID_M4A),
        },
    )
    assert t_resp.status_code == 200
    t_json = t_resp.json()
    assert (
        client.put(
            t_json["upload_url"].replace("http://testserver", ""),
            content=VALID_M4A,
            headers={"Content-Type": "audio/mp4"},
        ).status_code
        == 200
    )

    # Another user in the same project cannot link supervisor's ticket URI onto their own log
    cross_attach = client.post(
        "/v1/sync/push",
        headers=owner_headers,
        json={
            "changes": {
                "site_logs": [
                    {
                        "id": str(uuid.uuid4()),
                        "project_id": pid,
                        "log_date": "2026-11-15",
                        "recorded_at": now.isoformat(),
                        "notes": "Cross-record ticket attach",
                        "audio_uri": t_json["storage_uri"],
                        "client_updated_at": now.isoformat(),
                    }
                ]
            }
        },
    ).json()
    assert cross_attach["results"][0]["status"] == "REJECTED"
    assert cross_attach["results"][0]["error_code"] == "FORBIDDEN"

    # Legit user syncs the reserved site_log -> consumes reservation
    legit_push = client.post(
        "/v1/sync/push",
        headers=supervisor_headers,
        json={
            "changes": {
                "site_logs": [
                    {
                        "id": str(reserved_log_id),
                        "project_id": pid,
                        "log_date": "2026-11-15",
                        "recorded_at": now.isoformat(),
                        "notes": "Legitimate offline voice diary",
                        "audio_uri": t_json["storage_uri"],
                        "client_updated_at": now.isoformat(),
                    }
                ]
            }
        },
    ).json()
    assert legit_push["results"][0]["status"] == "APPLIED"
    consumed_res = db_session.get(MediaReservation, uuid.UUID(res_json["reservation_id"]))
    assert consumed_res is not None
    db_session.refresh(consumed_res)
    assert consumed_res.status == "CONSUMED"

    # 6. Concurrent /complete attempts on the same ticket serialize cleanly via FOR UPDATE:
    # exactly one 204 success and one 409 conflict, storage_bytes_used incremented once!
    db_session.refresh(default_org)
    used_before = int(default_org.storage_bytes_used or 0)
    barrier = threading.Barrier(2)

    def _call_complete() -> int:
        with TestClient(app) as c_client:
            barrier.wait(timeout=5)
            r = c_client.post(
                "/v1/media/complete",
                headers=supervisor_headers,
                json={
                    "kind": "AUDIO",
                    "object_id": str(reserved_log_id),
                    "ticket_id": t_json["ticket_id"],
                },
            )
            return int(r.status_code)

    with ThreadPoolExecutor(max_workers=2) as pool:
        statuses = list(pool.map(lambda _: _call_complete(), range(2)))
    assert sorted(statuses) == [204, 409]

    db_session.expire_all()
    db_session.refresh(default_org)
    assert int(default_org.storage_bytes_used or 0) == used_before + len(VALID_M4A)

    # Re-issuing upload-url for already UPLOADED audio fails 409 ALREADY_UPLOADED
    re_issue = client.post(
        "/v1/media/upload-url",
        headers=supervisor_headers,
        json={
            "kind": "AUDIO",
            "project_id": pid,
            "object_id": str(reserved_log_id),
            "content_type": "audio/mp4",
            "byte_size": len(VALID_M4A),
        },
    )
    assert_problem_json(re_issue, 409, "ALREADY_UPLOADED")

    # 7. Storage quota accounts for in-flight tickets
    orig_max = default_org.max_storage_bytes
    try:
        default_org.max_storage_bytes = int(default_org.storage_bytes_used or 0) + len(VALID_JPEG)
        db_session.commit()
        q1_id = uuid.uuid4()
        q2_id = uuid.uuid4()
        client.post(
            "/v1/media/reservations",
            headers=supervisor_headers,
            json={"kind": "PHOTO", "project_id": pid, "object_id": str(q1_id)},
        )
        client.post(
            "/v1/media/reservations",
            headers=supervisor_headers,
            json={"kind": "PHOTO", "project_id": pid, "object_id": str(q2_id)},
        )
        first_q = client.post(
            "/v1/media/upload-url",
            headers=supervisor_headers,
            json={
                "kind": "PHOTO",
                "project_id": pid,
                "object_id": str(q1_id),
                "content_type": "image/jpeg",
                "byte_size": len(VALID_JPEG),
            },
        )
        assert first_q.status_code == 200
        second_q = client.post(
            "/v1/media/upload-url",
            headers=supervisor_headers,
            json={
                "kind": "PHOTO",
                "project_id": pid,
                "object_id": str(q2_id),
                "content_type": "image/jpeg",
                "byte_size": len(VALID_JPEG),
            },
        )
        assert_problem_json(second_q, 402, "QUOTA_EXCEEDED_STORAGE")
    finally:
        default_org.max_storage_bytes = orig_max
        db_session.commit()

    # 8. Rate limiting on upload-url requests is enforced (then cleared for remaining tests)
    rate_limiter.clear()
    try:
        cfg = get_settings()
        limit = cfg.RATE_LIMIT_MEDIA_UPLOADS_PER_MINUTE
        rl_obj_id = uuid.uuid4()
        client.post(
            "/v1/media/reservations",
            headers=owner_headers,
            json={"kind": "PERMIT_DOC", "project_id": pid, "object_id": str(rl_obj_id)},
        )
        hit_429 = False
        for _ in range(limit + 2):
            resp = client.post(
                "/v1/media/upload-url",
                headers=owner_headers,
                json={
                    "kind": "PERMIT_DOC",
                    "project_id": pid,
                    "object_id": str(rl_obj_id),
                    "content_type": "image/jpeg",
                    "byte_size": len(VALID_JPEG),
                },
            )
            if resp.status_code == 429:
                hit_429 = True
                break
        assert hit_429 is True
    finally:
        rate_limiter.clear()


def test_orphan_media_cleanup_safety_and_audit_history(
    client: TestClient,
    db_session: Session,
    sample_project: Project,
    owner_user: User,
    owner_headers: dict[str, str],
) -> None:
    """Verify orphan cleanup removes expired/unattached artifacts & old failed jobs while
    preserving valid customer attachments and recording auditable MediaCleanupRun history.
    """
    cfg = get_settings()
    storage = MediaStorageService(cfg)
    pid = str(sample_project.id)
    now = datetime.now(UTC)
    old_ts = now - timedelta(days=2)

    # 1. Create a valid attached photo whose storage file must NEVER be deleted
    valid_log_id = uuid.uuid4()
    valid_photo_id = uuid.uuid4()
    assert (
        client.post(
            "/v1/media/reservations",
            headers=owner_headers,
            json={"kind": "PHOTO", "project_id": pid, "object_id": str(valid_photo_id)},
        ).status_code
        == 201
    )
    valid_ticket = client.post(
        "/v1/media/upload-url",
        headers=owner_headers,
        json={
            "kind": "PHOTO",
            "project_id": pid,
            "object_id": str(valid_photo_id),
            "content_type": "image/jpeg",
            "byte_size": len(VALID_JPEG),
        },
    ).json()
    assert (
        client.put(
            valid_ticket["upload_url"].replace("http://testserver", ""),
            content=VALID_JPEG,
            headers={"Content-Type": "image/jpeg"},
        ).status_code
        == 200
    )
    assert (
        client.post(
            "/v1/sync/push",
            headers=owner_headers,
            json={
                "changes": {
                    "site_logs": [
                        {
                            "id": str(valid_log_id),
                            "project_id": pid,
                            "log_date": "2026-11-15",
                            "recorded_at": now.isoformat(),
                            "notes": "Keep this attachment",
                            "client_updated_at": now.isoformat(),
                        }
                    ],
                    "site_log_photos": [
                        {
                            "id": str(valid_photo_id),
                            "site_log_id": str(valid_log_id),
                            "storage_uri": valid_ticket["storage_uri"],
                            "sort_order": 0,
                        }
                    ],
                }
            },
        ).status_code
        == 200
    )
    assert (
        client.post(
            "/v1/media/complete",
            headers=owner_headers,
            json={
                "kind": "PHOTO",
                "object_id": str(valid_photo_id),
                "ticket_id": valid_ticket["ticket_id"],
            },
        ).status_code
        == 204
    )

    # 2. Seed orphans: expired ticket, expired reservation, incomplete uploaded unattached file,
    #    direct orphan blob in storage, and aged FAILED extraction job
    stale_res = MediaReservation(
        organization_id=sample_project.organization_id,
        project_id=sample_project.id,
        user_id=owner_user.id,
        kind="AUDIO",
        object_id=uuid.uuid4(),
        status="ACTIVE",
        expires_at=now - timedelta(hours=2),
    )
    db_session.add(stale_res)

    incomplete_obj_id = uuid.uuid4()
    incomplete_ticket_id = uuid.uuid4()
    incomplete_key = f"projects/{pid}/photos/{incomplete_obj_id}/{incomplete_ticket_id}.jpg"
    incomplete_path = storage.write_local_bytes_exclusive(incomplete_key, VALID_JPEG)
    os.utime(incomplete_path, (old_ts.timestamp(), old_ts.timestamp()))
    incomplete_ticket = UploadTicket(
        id=incomplete_ticket_id,
        organization_id=sample_project.organization_id,
        project_id=sample_project.id,
        user_id=owner_user.id,
        kind="PHOTO",
        object_id=incomplete_obj_id,
        object_key=incomplete_key,
        storage_uri=f"local://{incomplete_key}",
        content_type="image/jpeg",
        expected_byte_size=len(VALID_JPEG),
        status="UPLOADED",
        expires_at=old_ts,
        created_at=old_ts,
    )
    db_session.add(incomplete_ticket)

    issued_stale_ticket = UploadTicket(
        id=uuid.uuid4(),
        organization_id=sample_project.organization_id,
        project_id=sample_project.id,
        user_id=owner_user.id,
        kind="AUDIO",
        object_id=uuid.uuid4(),
        object_key=f"projects/{pid}/audio/{uuid.uuid4()}/{uuid.uuid4()}.m4a",
        storage_uri=f"local://projects/{pid}/audio/{uuid.uuid4()}/{uuid.uuid4()}.m4a",
        content_type="audio/mp4",
        expected_byte_size=128,
        status="ISSUED",
        expires_at=old_ts,
        created_at=old_ts,
    )
    db_session.add(issued_stale_ticket)

    orphan_key = f"projects/{pid}/photos/stray-unclaimed.jpg"
    orphan_path = storage.write_local_bytes_exclusive(orphan_key, VALID_JPEG)
    os.utime(orphan_path, (old_ts.timestamp(), old_ts.timestamp()))

    # Recent orphan within grace window MUST be preserved
    fresh_key = f"projects/{pid}/photos/recent-in-progress.jpg"
    fresh_path = storage.write_local_bytes_exclusive(fresh_key, VALID_JPEG)
    assert fresh_path.exists()

    old_failed_job = ExtractionJob(
        organization_id=sample_project.organization_id,
        project_id=sample_project.id,
        target_type="SITE_LOG",
        target_id=valid_log_id,
        idempotency_key=f"stale-failed:{uuid.uuid4()}",
        status="FAILED",
        updated_at=now - timedelta(days=45),
        created_at=now - timedelta(days=45),
    )
    db_session.add(old_failed_job)
    db_session.commit()

    # Run cleanup (also verify internal task endpoint auth first)
    has_secret = bool(cfg.SCHEDULER_SHARED_SECRET or cfg.CLOUD_TASKS_SHARED_SECRET)
    assert_problem_json(
        client.post("/v1/internal/tasks/media-cleanup"),
        403 if has_secret else 503,
        "FORBIDDEN" if has_secret else "SERVICE_MISCONFIGURED",
    )

    run = run_media_cleanup(
        db_session,
        storage=storage,
        settings=cfg,
        now=now,
        orphan_grace_seconds=3600,
        failed_job_retention_days=30,
    )
    assert run.status == "COMPLETED"
    assert run.expired_reservations_cleaned >= 1
    assert run.expired_tickets_cleaned >= 2
    assert run.incomplete_uploads_cleaned >= 1
    assert run.unattached_objects_deleted >= 1
    assert run.failed_jobs_pruned >= 1
    assert run.bytes_reclaimed >= len(VALID_JPEG) * 2

    # Valid customer attachment and fresh within-grace object remain untouched
    assert storage.exists(valid_ticket["storage_uri"]) is True
    assert fresh_path.exists() is True
    assert not incomplete_path.exists()
    assert not orphan_path.exists()
    assert db_session.get(ExtractionJob, old_failed_job.id) is None

    db_session.refresh(stale_res)
    assert stale_res.status == "EXPIRED"

    # Cleanup history + audit log recorded cleanly
    assert db_session.get(MediaCleanupRun, run.id) is not None
    audit_row = db_session.scalar(
        select(AuditLog).where(
            AuditLog.action == "media.cleanup.run",
            AuditLog.resource_id == str(run.id),
        )
    )
    assert audit_row is not None

    # Issue 10 regression check: token missing 'tv' rejected when user.token_version > 0
    owner_user.token_version = int(owner_user.token_version or 0) + 1
    db_session.commit()
    try:
        forged_no_tv = jwt.encode(
            {
                "sub": str(owner_user.id),
                "role": owner_user.role,
                "type": "access",
                "iss": cfg.JWT_ISSUER,
                "aud": cfg.JWT_AUDIENCE,
                "iat": int(now.timestamp()),
                "exp": int((now + timedelta(minutes=10)).timestamp()),
            },
            cfg.effective_jwt_secret,
            algorithm="HS256",
        )
        revoked_resp = client.get(
            "/v1/me",
            headers={"Authorization": f"Bearer {forged_no_tv}"},
        )
        assert_problem_json(revoked_resp, 401, "TOKEN_REVOKED")
    finally:
        owner_user.token_version = 0
        db_session.commit()

from __future__ import annotations

import hashlib
import uuid
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.db.models import (
    Organization,
    OrganizationMember,
    Project,
    ProjectMember,
    UploadTicket,
    User,
)
from app.services.auth import hash_password
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

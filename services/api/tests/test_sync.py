from __future__ import annotations

import uuid
from datetime import UTC, date, datetime

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.db.models import Project, SiteLog, User
from tests.conftest import assert_problem_json, auth_headers


def test_sync_push_batch_limit_and_independent_apply(
    client: TestClient,
    db_session: Session,
    sample_project: Project,
    owner_user: User,
    supervisor_user: User,
    owner_headers: dict[str, str],
    supervisor_headers: dict[str, str],
) -> None:
    now = datetime.now(UTC)
    pid = str(sample_project.id)

    # > 200 records -> 413
    too_many = [
        {
            "id": str(uuid.uuid4()),
            "project_id": pid,
            "log_date": "2026-11-10",
            "recorded_at": now.isoformat(),
            "client_updated_at": now.isoformat(),
        }
        for _ in range(201)
    ]
    too_large_resp = client.post(
        "/v1/sync/push",
        headers=supervisor_headers,
        json={"changes": {"site_logs": too_many}},
    )
    assert_problem_json(too_large_resp, 413, "BATCH_TOO_LARGE")

    # Seed an owner-authored log that supervisor is NOT allowed to update
    owner_log_id = uuid.uuid4()
    db_session.add(
        SiteLog(
            id=owner_log_id,
            project_id=sample_project.id,
            author_id=owner_user.id,
            log_date=date(2026, 11, 10),
            recorded_at=now,
            notes="Owner log",
            client_updated_at=now,
        )
    )
    db_session.commit()

    sup_log_id = uuid.uuid4()
    photo_id = uuid.uuid4()
    permit_id = uuid.uuid4()
    bad_log_id = uuid.uuid4()
    unauth_project_id = uuid.uuid4()

    push_resp = client.post(
        "/v1/sync/push",
        headers=supervisor_headers,
        json={
            "changes": {
                "permits": [
                    {
                        "id": str(permit_id),
                        "project_id": pid,
                        "permit_name": "Mobile Permit",
                        "authority": "SBCA",
                        "expiry_date": "2026-12-31",
                        "client_updated_at": now.isoformat(),
                    }
                ],
                "site_logs": [
                    # Valid supervisor log with audio_uri -> audio_upload_status=PENDING,
                    # plus an ignored structured_summary because edited_by_human=false
                    {
                        "id": str(sup_log_id),
                        "project_id": pid,
                        "log_date": "2026-11-11",
                        "recorded_at": now.isoformat(),
                        "notes": "Pouring concrete",
                        "audio_uri": f"local://projects/{pid}/audio/{sup_log_id}.m4a",
                        "audio_duration_ms": 12000,
                        "structured_summary": {
                            "tasks_completed": ["Should be ignored"],
                            "labor_count": 99,
                            "material_deliveries": [],
                            "blockers": [],
                        },
                        "edited_by_human": False,
                        "client_updated_at": now.isoformat(),
                    },
                    # Invalid duration -> REJECTED VALIDATION (does not block other items!)
                    {
                        "id": str(bad_log_id),
                        "project_id": pid,
                        "log_date": "2026-11-11",
                        "recorded_at": now.isoformat(),
                        "audio_duration_ms": 999999,
                        "client_updated_at": now.isoformat(),
                    },
                    # Supervisor attempting to overwrite owner's log -> REJECTED FORBIDDEN
                    {
                        "id": str(owner_log_id),
                        "project_id": pid,
                        "log_date": "2026-11-10",
                        "recorded_at": now.isoformat(),
                        "notes": "Attempt overwrite",
                        "client_updated_at": now.isoformat(),
                    },
                    # Unknown project -> REJECTED NOT_FOUND
                    {
                        "id": str(uuid.uuid4()),
                        "project_id": str(unauth_project_id),
                        "log_date": "2026-11-11",
                        "recorded_at": now.isoformat(),
                        "client_updated_at": now.isoformat(),
                    },
                ],
                # Photo referencing sup_log_id created in SAME batch (apply order!)
                "site_log_photos": [
                    {
                        "id": str(photo_id),
                        "site_log_id": str(sup_log_id),
                        "storage_uri": f"local://projects/{pid}/photos/{photo_id}.jpg",
                        "width": 1920,
                        "height": 1080,
                        "byte_size": 123456,
                        "sort_order": 0,
                    }
                ],
            }
        },
    )
    assert push_resp.status_code == 200
    results = {(r["entity"], r["id"]): r for r in push_resp.json()["results"]}

    assert results[("permits", str(permit_id))]["status"] == "APPLIED"
    assert results[("site_logs", str(sup_log_id))]["status"] == "APPLIED"
    assert results[("site_logs", str(bad_log_id))]["status"] == "REJECTED"
    assert results[("site_logs", str(bad_log_id))]["error_code"] == "VALIDATION"
    assert results[("site_logs", str(owner_log_id))]["status"] == "REJECTED"
    assert results[("site_logs", str(owner_log_id))]["error_code"] == "FORBIDDEN"
    assert results[("site_log_photos", str(photo_id))]["status"] == "APPLIED"

    db_session.expire_all()
    saved_log = db_session.get(SiteLog, sup_log_id)
    assert saved_log is not None
    assert saved_log.author_id == supervisor_user.id
    assert saved_log.audio_upload_status == "PENDING"
    assert saved_log.structured_summary is None  # ignored when edited_by_human=False

    # Mark audio UPLOADED, then re-push same audio_uri -> stays UPLOADED!
    saved_log.audio_upload_status = "UPLOADED"
    db_session.commit()

    first_ver = results[("site_logs", str(sup_log_id))]["server_version"]
    repush = client.post(
        "/v1/sync/push",
        headers=supervisor_headers,
        json={
            "changes": {
                "site_logs": [
                    {
                        "id": str(sup_log_id),
                        "project_id": pid,
                        "log_date": "2026-11-11",
                        "recorded_at": now.isoformat(),
                        "notes": "Pouring concrete",
                        "audio_uri": f"local://projects/{pid}/audio/{sup_log_id}.m4a",
                        "audio_duration_ms": 12000,
                        "client_updated_at": now.isoformat(),
                    }
                ]
            }
        },
    )
    assert repush.status_code == 200
    repush_ver = repush.json()["results"][0]["server_version"]
    assert repush_ver > first_ver

    db_session.expire_all()
    saved_log = db_session.get(SiteLog, sup_log_id)
    assert saved_log is not None
    assert saved_log.audio_upload_status == "UPLOADED"

    # Changing audio_uri resets audio_upload_status to PENDING
    changed_uri = client.post(
        "/v1/sync/push",
        headers=supervisor_headers,
        json={
            "changes": {
                "site_logs": [
                    {
                        "id": str(sup_log_id),
                        "project_id": pid,
                        "log_date": "2026-11-11",
                        "recorded_at": now.isoformat(),
                        "notes": "Pouring concrete",
                        "audio_uri": f"local://projects/{pid}/audio/{sup_log_id}-v2.m4a",
                        "client_updated_at": now.isoformat(),
                    }
                ]
            }
        },
    )
    assert changed_uri.status_code == 200
    db_session.expire_all()
    saved_log = db_session.get(SiteLog, sup_log_id)
    assert saved_log is not None
    assert saved_log.audio_upload_status == "PENDING"

    # Deleted project -> PROJECT_DELETED
    del_resp = client.delete(f"/v1/projects/{pid}", headers=owner_headers)
    assert del_resp.status_code == 204
    deleted_proj_push = client.post(
        "/v1/sync/push",
        headers=supervisor_headers,
        json={
            "changes": {
                "site_logs": [
                    {
                        "id": str(uuid.uuid4()),
                        "project_id": pid,
                        "log_date": "2026-11-11",
                        "recorded_at": now.isoformat(),
                        "client_updated_at": now.isoformat(),
                    }
                ]
            }
        },
    )
    assert deleted_proj_push.json()["results"][0]["error_code"] == "PROJECT_DELETED"


def test_sync_pull_pagination_scoped_backfill_and_membership_tombstone(
    client: TestClient,
    db_session: Session,
    owner_user: User,
    owner_headers: dict[str, str],
) -> None:
    # Create project 1 & project 2
    p1 = client.post(
        "/v1/projects",
        headers=owner_headers,
        json={"name": "Project One", "site_address": "Addr 1"},
    ).json()
    p2 = client.post(
        "/v1/projects",
        headers=owner_headers,
        json={"name": "Project Two", "site_address": "Addr 2"},
    ).json()

    now = datetime.now(UTC)
    l1 = uuid.uuid4()
    l2 = uuid.uuid4()
    push1 = client.post(
        "/v1/sync/push",
        headers=owner_headers,
        json={
            "changes": {
                "site_logs": [
                    {
                        "id": str(l1),
                        "project_id": p1["id"],
                        "log_date": "2026-11-10",
                        "recorded_at": now.isoformat(),
                        "notes": "P1 history",
                        "client_updated_at": now.isoformat(),
                    },
                    {
                        "id": str(l2),
                        "project_id": p2["id"],
                        "log_date": "2026-11-10",
                        "recorded_at": now.isoformat(),
                        "notes": "P2 history",
                        "client_updated_at": now.isoformat(),
                    },
                ]
            }
        },
    )
    assert push1.status_code == 200

    # Invite a new supervisor ONLY to Project 1 initially
    inv = client.post(
        f"/v1/projects/{p1['id']}/members",
        headers=owner_headers,
        json={"email": "mobile@example.com", "full_name": "Mobile Sup"},
    ).json()
    sup_headers = auth_headers(client, "mobile@example.com", inv["temporary_password"])
    sup_uid = inv["member"]["user_id"]

    # Paginated pull with limit=2 until exhausted
    cursor = 0
    pulled_log_ids: set[str] = set()
    pulled_project_ids: set[str] = set()
    pages = 0
    while True:
        pages += 1
        pull = client.get(
            f"/v1/sync/pull?since={cursor}&limit=2",
            headers=sup_headers,
        )
        assert pull.status_code == 200
        body = pull.json()
        for proj in body["changes"]["projects"]:
            pulled_project_ids.add(proj["id"])
        for log in body["changes"]["site_logs"]:
            assert "photos" not in log
            pulled_log_ids.add(log["id"])
        cursor = body["next_cursor"]
        if not body["has_more"]:
            break
    assert pages >= 2
    assert pulled_project_ids == {p1["id"]}
    assert pulled_log_ids == {str(l1)}

    # Now add the supervisor to Project 2 (whose log l2 has an OLDER server_version < cursor!)
    inv2 = client.post(
        f"/v1/projects/{p2['id']}/members",
        headers=owner_headers,
        json={"email": "mobile@example.com", "full_name": "Mobile Sup"},
    )
    assert inv2.status_code == 201

    # Global pull since `cursor` reveals the new project_members row for Project 2
    global_pull = client.get(
        f"/v1/sync/pull?since={cursor}",
        headers=sup_headers,
    ).json()
    assert any(m["project_id"] == p2["id"] for m in global_pull["changes"]["project_members"])

    # Scoped backfill for Project 2 from since=0 delivers older log l2
    backfill = client.get(
        f"/v1/sync/pull?since=0&project_id={p2['id']}",
        headers=sup_headers,
    ).json()
    assert [log["id"] for log in backfill["changes"]["site_logs"]] == [str(l2)]
    assert [proj["id"] for proj in backfill["changes"]["projects"]] == [p2["id"]]

    # Owner removes supervisor from Project 1 -> tombstone delivered to supervisor on pull!
    cursor = global_pull["next_cursor"]
    rem = client.delete(
        f"/v1/projects/{p1['id']}/members/{sup_uid}",
        headers=owner_headers,
    )
    assert rem.status_code == 204

    after_removal = client.get(
        f"/v1/sync/pull?since={cursor}",
        headers=sup_headers,
    ).json()
    tombstones = [
        m
        for m in after_removal["changes"]["project_members"]
        if m["project_id"] == p1["id"] and m["user_id"] == sup_uid
    ]
    assert len(tombstones) == 1
    assert tombstones[0]["deleted_at"] is not None
    # No Project 1 logs leaked after removal
    assert all(log["project_id"] != p1["id"] for log in after_removal["changes"]["site_logs"])

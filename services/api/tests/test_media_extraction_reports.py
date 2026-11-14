from __future__ import annotations

import re
import uuid
from datetime import UTC, datetime, timedelta

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.db.models import Project, SiteLog
from app.services.extraction_worker import recover_stuck_extractions
from tests.conftest import assert_problem_json


def test_media_upload_complete_extraction_and_edited_by_human_guard(
    client: TestClient,
    db_session: Session,
    sample_project: Project,
    owner_headers: dict[str, str],
    supervisor_headers: dict[str, str],
) -> None:
    pid = str(sample_project.id)
    log_id = uuid.uuid4()
    photo_id = uuid.uuid4()
    now = datetime.now(UTC)

    # Mismatched kind/content_type -> 422
    bad_ticket = client.post(
        "/v1/media/upload-url",
        headers=supervisor_headers,
        json={
            "kind": "AUDIO",
            "project_id": pid,
            "object_id": str(log_id),
            "content_type": "image/jpeg",
            "byte_size": 1024,
        },
    )
    assert_problem_json(bad_ticket, 422, "VALIDATION")

    # Get audio upload ticket
    valid_m4a = b"\x00\x00\x00\x18ftypmp42\x00\x00\x00\x00fake-audio"
    audio_ticket_resp = client.post(
        "/v1/media/upload-url",
        headers=supervisor_headers,
        json={
            "kind": "AUDIO",
            "project_id": pid,
            "object_id": str(log_id),
            "content_type": "audio/mp4",
            "byte_size": len(valid_m4a),
        },
    )
    assert audio_ticket_resp.status_code == 200
    audio_ticket = audio_ticket_resp.json()
    assert re.fullmatch(
        rf"local://projects/{pid}/audio/{log_id}/[0-9a-f-]+\.m4a",
        audio_ticket["storage_uri"],
    )

    # Calling /complete before /sync/push -> 409 ROW_NOT_SYNCED
    early_complete = client.post(
        "/v1/media/complete",
        headers=supervisor_headers,
        json={"kind": "AUDIO", "object_id": str(log_id)},
    )
    assert_problem_json(early_complete, 409, "ROW_NOT_SYNCED")

    # Push log + photo metadata
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
                        "notes": "Voice diary",
                        "audio_uri": audio_ticket["storage_uri"],
                        "audio_duration_ms": 5000,
                        "client_updated_at": now.isoformat(),
                    }
                ],
                "site_log_photos": [
                    {
                        "id": str(photo_id),
                        "site_log_id": str(log_id),
                        "storage_uri": f"local://projects/{pid}/photos/{photo_id}.jpg",
                        "sort_order": 0,
                    }
                ],
            }
        },
    )
    assert push_resp.status_code == 200

    # Calling /complete before uploading file -> 404 OBJECT_MISSING
    missing_obj = client.post(
        "/v1/media/complete",
        headers=supervisor_headers,
        json={"kind": "AUDIO", "object_id": str(log_id)},
    )
    assert_problem_json(missing_obj, 404, "OBJECT_MISSING")

    # Tampered or expired signature on local PUT -> 403
    upload_path = audio_ticket["upload_url"].replace("http://testserver", "")
    tampered_path = re.sub(r"sig=[0-9a-f]+", "sig=0000deadbeef", upload_path)
    tampered = client.put(
        tampered_path,
        content=valid_m4a,
        headers={"Content-Type": "audio/mp4"},
    )
    assert_problem_json(tampered, 403, "FORBIDDEN")

    expired_path = re.sub(r"exp=\d+", "exp=1", upload_path)
    expired_sig = client.put(
        expired_path,
        content=valid_m4a,
        headers={"Content-Type": "audio/mp4"},
    )
    assert_problem_json(expired_sig, 403, "FORBIDDEN")

    # Valid local PUT
    put_resp = client.put(
        upload_path,
        content=valid_m4a,
        headers={"Content-Type": "audio/mp4"},
    )
    assert put_resp.status_code == 200

    # Complete audio upload -> queues BackgroundTask -> mock Gemini extraction runs!
    complete_resp = client.post(
        "/v1/media/complete",
        headers=supervisor_headers,
        json={"kind": "AUDIO", "object_id": str(log_id)},
    )
    assert complete_resp.status_code == 204

    # TestClient executes BackgroundTasks synchronously before returning response
    log_detail = client.get(f"/v1/logs/{log_id}", headers=owner_headers)
    assert log_detail.status_code == 200
    body = log_detail.json()
    assert body["audio_upload_status"] == "UPLOADED"
    assert body["extraction_status"] == "DONE"
    assert body["structured_summary"]["tasks_completed"] == ["Foundation pouring Block B"]
    assert body["structured_summary"]["labor_count"] == 14
    assert body["photos"][0]["upload_status"] == "PENDING"
    assert body["photos"][0]["url"] is None

    # Upload photo & complete -> GET /v1/logs/{id} now returns signed photo URL that streams bytes
    valid_jpeg = (
        b"\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x00\x00\x01\x00\x01\x00\x00"
        b"fake-jpeg\xff\xd9"
    )
    photo_ticket = client.post(
        "/v1/media/upload-url",
        headers=supervisor_headers,
        json={
            "kind": "PHOTO",
            "project_id": pid,
            "object_id": str(photo_id),
            "content_type": "image/jpeg",
            "byte_size": len(valid_jpeg),
        },
    ).json()
    photo_put = client.put(
        photo_ticket["upload_url"].replace("http://testserver", ""),
        content=valid_jpeg,
        headers={"Content-Type": "image/jpeg"},
    )
    assert photo_put.status_code == 200
    assert (
        client.post(
            "/v1/media/complete",
            headers=supervisor_headers,
            json={"kind": "PHOTO", "object_id": str(photo_id)},
        ).status_code
        == 204
    )

    refreshed_log = client.get(f"/v1/logs/{log_id}", headers=owner_headers).json()
    signed_photo_url = refreshed_log["photos"][0]["url"]
    assert signed_photo_url is not None
    downloaded = client.get(signed_photo_url.replace("http://testserver", ""))
    assert downloaded.status_code == 200
    assert downloaded.content == valid_jpeg

    # Human edits structured_summary -> /v1/logs/extract MUST NOT overwrite it!
    human_summary = {
        "tasks_completed": ["Custom human edited task"],
        "labor_count": 21,
        "material_deliveries": ["Custom material"],
        "blockers": [],
    }
    edit_push = client.post(
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
                        "audio_uri": audio_ticket["storage_uri"],
                        "structured_summary": human_summary,
                        "edited_by_human": True,
                        "client_updated_at": now.isoformat(),
                    }
                ]
            }
        },
    )
    assert edit_push.status_code == 200

    re_extract = client.post(
        "/v1/logs/extract",
        headers=owner_headers,
        json={"log_id": str(log_id)},
    )
    assert re_extract.status_code == 202
    assert re_extract.json()["extraction_status"] == "PENDING"

    after_reextract = client.get(f"/v1/logs/{log_id}", headers=owner_headers).json()
    assert after_reextract["extraction_status"] == "DONE"
    assert after_reextract["structured_summary"] == human_summary

    # Verify /v1/logs/extract returns 409 EXTRACTION_IN_PROGRESS when PROCESSING,
    # and recover_stuck_extractions resets PROCESSING back to PENDING.
    db_log = db_session.get(SiteLog, log_id)
    assert db_log is not None
    db_log.extraction_status = "PROCESSING"
    db_session.commit()

    in_progress = client.post(
        "/v1/logs/extract",
        headers=owner_headers,
        json={"log_id": str(log_id)},
    )
    assert_problem_json(in_progress, 409, "EXTRACTION_IN_PROGRESS")

    # Unknown log and log without audio on /v1/logs/extract -> 404 and 409 AUDIO_NOT_UPLOADED
    missing_extract = client.post(
        "/v1/logs/extract",
        headers=owner_headers,
        json={"log_id": str(uuid.uuid4())},
    )
    assert_problem_json(missing_extract, 404, "NOT_FOUND")

    no_audio_log_id = uuid.uuid4()
    client.post(
        "/v1/sync/push",
        headers=supervisor_headers,
        json={
            "changes": {
                "site_logs": [
                    {
                        "id": str(no_audio_log_id),
                        "project_id": pid,
                        "log_date": "2026-11-12",
                        "recorded_at": now.isoformat(),
                        "notes": "",
                        "client_updated_at": now.isoformat(),
                    }
                ]
            }
        },
    )
    no_audio_extract = client.post(
        "/v1/logs/extract",
        headers=owner_headers,
        json={"log_id": str(no_audio_log_id)},
    )
    assert_problem_json(no_audio_extract, 409, "AUDIO_NOT_UPLOADED")

    # PERMIT_DOC upload-url -> local PUT -> complete -> permit returns signed document_photo_url
    permit_obj_id = uuid.uuid4()
    valid_permit_jpg = (
        b"\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x00\x00\x01\x00\x01\x00\x00permit-1\xff\xd9"
    )
    pdoc_ticket = client.post(
        "/v1/media/upload-url",
        headers=owner_headers,
        json={
            "kind": "PERMIT_DOC",
            "project_id": pid,
            "object_id": str(permit_obj_id),
            "content_type": "image/jpeg",
            "byte_size": len(valid_permit_jpg),
        },
    ).json()
    assert re.fullmatch(
        rf"local://projects/{pid}/permits/{permit_obj_id}/[0-9a-f-]+\.jpg",
        pdoc_ticket["storage_uri"],
    )
    assert (
        client.put(
            pdoc_ticket["upload_url"].replace("http://testserver", ""),
            content=valid_permit_jpg,
            headers={"Content-Type": "image/jpeg"},
        ).status_code
        == 200
    )
    pushed_permit = client.post(
        "/v1/sync/push",
        headers=owner_headers,
        json={
            "changes": {
                "permits": [
                    {
                        "id": str(permit_obj_id),
                        "project_id": pid,
                        "permit_name": "Doc Permit",
                        "authority": "SBCA",
                        "expiry_date": "2026-12-30",
                        "document_photo_uri": pdoc_ticket["storage_uri"],
                        "client_updated_at": now.isoformat(),
                    }
                ]
            }
        },
    )
    assert pushed_permit.status_code == 200
    assert (
        client.post(
            "/v1/media/complete",
            headers=owner_headers,
            json={"kind": "PERMIT_DOC", "object_id": str(permit_obj_id)},
        ).status_code
        == 204
    )
    permits_list = client.get(f"/v1/projects/{pid}/permits", headers=owner_headers).json()
    doc_url = permits_list[0]["document_photo_url"]
    assert doc_url is not None
    assert client.get(doc_url.replace("http://testserver", "")).content == valid_permit_jpg

    # Empty day report still returns 200 with zeroed counts and project permits
    empty_day = client.get(
        f"/v1/projects/{pid}/days/2026-01-01",
        headers=owner_headers,
    )
    assert empty_day.status_code == 200
    empty_body = empty_day.json()
    assert empty_body["log_count"] == 0
    assert empty_body["labor_max"] is None
    assert len(empty_body["permits"]) == 1

    recovered = recover_stuck_extractions()
    assert log_id in recovered


def test_daily_report_aggregation_and_timeline_pagination(
    client: TestClient,
    db_session: Session,
    sample_project: Project,
    owner_headers: dict[str, str],
    supervisor_headers: dict[str, str],
) -> None:
    pid = str(sample_project.id)
    base_time = datetime(2026, 11, 10, 9, 0, tzinfo=UTC)

    # Push 3 logs on 2026-11-10 (two DONE with labor 14 and 8, one NOT_STARTED)
    # plus 1 log on 2026-11-08 and 1 log on 2026-11-05.
    l1 = uuid.uuid4()
    l2 = uuid.uuid4()
    l3 = uuid.uuid4()
    l4 = uuid.uuid4()
    l5 = uuid.uuid4()

    push = client.post(
        "/v1/sync/push",
        headers=supervisor_headers,
        json={
            "changes": {
                "site_logs": [
                    {
                        "id": str(l1),
                        "project_id": pid,
                        "log_date": "2026-11-10",
                        "recorded_at": base_time.isoformat(),
                        "structured_summary": {
                            "tasks_completed": ["Slab Pouring", "Curing"],
                            "labor_count": 14,
                            "material_deliveries": ["Cement 50 bags"],
                            "blockers": ["Crane Delay"],
                        },
                        "edited_by_human": True,
                        "client_updated_at": base_time.isoformat(),
                    },
                    {
                        "id": str(l2),
                        "project_id": pid,
                        "log_date": "2026-11-10",
                        "recorded_at": (base_time + timedelta(hours=2)).isoformat(),
                        "structured_summary": {
                            "tasks_completed": ["  slab pouring ", "Rebar check"],
                            "labor_count": 8,
                            "material_deliveries": ["cement 50 bags ", "Steel 2T"],
                            "blockers": ["crane delay", "Rain"],
                        },
                        "edited_by_human": True,
                        "client_updated_at": base_time.isoformat(),
                    },
                    {
                        "id": str(l3),
                        "project_id": pid,
                        "log_date": "2026-11-10",
                        "recorded_at": (base_time + timedelta(hours=4)).isoformat(),
                        "notes": "Pending voice note",
                        "client_updated_at": base_time.isoformat(),
                    },
                    {
                        "id": str(l4),
                        "project_id": pid,
                        "log_date": "2026-11-08",
                        "recorded_at": (base_time - timedelta(days=2)).isoformat(),
                        "structured_summary": {
                            "tasks_completed": ["Excavation"],
                            "labor_count": 10,
                            "material_deliveries": [],
                            "blockers": [],
                        },
                        "edited_by_human": True,
                        "client_updated_at": base_time.isoformat(),
                    },
                    {
                        "id": str(l5),
                        "project_id": pid,
                        "log_date": "2026-11-05",
                        "recorded_at": (base_time - timedelta(days=5)).isoformat(),
                        "structured_summary": {
                            "tasks_completed": ["Site clearing"],
                            "labor_count": 6,
                            "material_deliveries": [],
                            "blockers": [],
                        },
                        "edited_by_human": True,
                        "client_updated_at": base_time.isoformat(),
                    },
                ]
            }
        },
    )
    assert push.status_code == 200

    # Mark l1 & l2 extraction_status='DONE', keep l3 'NOT_STARTED'
    for lid in (l1, l2, l4, l5):
        row = db_session.get(SiteLog, lid)
        assert row is not None
        row.extraction_status = "DONE"
    db_session.commit()

    day_resp = client.get(
        f"/v1/projects/{pid}/days/2026-11-10",
        headers=owner_headers,
    )
    assert day_resp.status_code == 200
    day = day_resp.json()
    assert day["labor_max"] == 14  # MAX(14, 8), NOT sum 22!
    assert day["log_count"] == 3
    assert day["pending_extraction_count"] == 1
    assert day["tasks_completed"] == ["Slab Pouring", "Curing", "Rebar check"]
    assert day["material_deliveries"] == ["Cement 50 bags", "Steel 2T"]
    assert day["blockers"] == ["Crane Delay", "Rain"]

    # Timeline pagination (days=2)
    page1 = client.get(
        f"/v1/projects/{pid}/timeline?days=2",
        headers=owner_headers,
    ).json()
    assert [d["log_date"] for d in page1["days"]] == ["2026-11-10", "2026-11-08"]
    assert page1["next_before"] == "2026-11-08"

    page2 = client.get(
        f"/v1/projects/{pid}/timeline?days=2&before={page1['next_before']}",
        headers=owner_headers,
    ).json()
    assert [d["log_date"] for d in page2["days"]] == ["2026-11-05"]
    assert page2["next_before"] is None

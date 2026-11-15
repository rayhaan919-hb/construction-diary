from __future__ import annotations

import shutil
import subprocess
import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pgserver._commands as pg_commands
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import Settings, get_settings
from app.db.models import ExtractionJob, Permit, Project, SiteLog, SiteLogPhoto, User
from app.services.extraction_worker import execute_extraction_job, recover_stuck_extractions
from tests.conftest import assert_problem_json


def test_notes_photo_permit_extraction_and_stale_lease_recovery(
    client: TestClient,
    db_session: Session,
    sample_project: Project,
    owner_headers: dict[str, str],
    supervisor_headers: dict[str, str],
) -> None:
    pid = str(sample_project.id)
    now = datetime.now(UTC)

    # 1. Text-only site log extraction (no audio)
    notes_log_id = uuid.uuid4()
    photo_id = uuid.uuid4()
    valid_jpeg = (
        b"\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x00\x00\x01\x00\x01\x00\x00"
        b"rebar-photo\xff\xd9"
    )
    assert (
        client.post(
            "/v1/media/reservations",
            headers=supervisor_headers,
            json={"kind": "PHOTO", "project_id": pid, "object_id": str(photo_id)},
        ).status_code
        == 201
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

    assert (
        client.put(
            photo_ticket["upload_url"].replace("http://testserver", ""),
            content=valid_jpeg,
            headers={"Content-Type": "image/jpeg"},
        ).status_code
        == 200
    )

    push_resp = client.post(
        "/v1/sync/push",
        headers=supervisor_headers,
        json={
            "changes": {
                "site_logs": [
                    {
                        "id": str(notes_log_id),
                        "project_id": pid,
                        "log_date": "2026-11-12",
                        "recorded_at": now.isoformat(),
                        "notes": "Completed foundation pouring in Block B with 14 workers",
                        "client_updated_at": now.isoformat(),
                    }
                ],
                "site_log_photos": [
                    {
                        "id": str(photo_id),
                        "site_log_id": str(notes_log_id),
                        "storage_uri": photo_ticket["storage_uri"],
                        "sort_order": 0,
                    }
                ],
            }
        },
    )
    assert push_resp.status_code == 200

    # Completing photo upload triggers SITE_LOG_PHOTO AI extraction automatically!
    assert (
        client.post(
            "/v1/media/complete",
            headers=supervisor_headers,
            json={
                "kind": "PHOTO",
                "object_id": str(photo_id),
                "ticket_id": photo_ticket["ticket_id"],
            },
        ).status_code
        == 204
    )

    # Queue notes-only log extraction explicitly
    notes_extract = client.post(
        "/v1/logs/extract",
        headers=owner_headers,
        json={"target_type": "SITE_LOG", "target_id": str(notes_log_id)},
    )
    assert notes_extract.status_code == 202

    detail = client.get(f"/v1/logs/{notes_log_id}", headers=owner_headers).json()
    assert detail["extraction_status"] == "DONE"
    assert detail["structured_summary"]["labor_count"] == 14
    assert detail["photos"][0]["ai_caption"] is not None

    # 2. Permit document upload triggers PERMIT OCR extraction automatically
    permit_resp = client.post(
        f"/v1/projects/{pid}/permits",
        headers=owner_headers,
        json={
            "permit_name": "Tower Crane Permit",
            "authority": "SBCA",
            "expiry_date": "2027-03-01",
        },
    ).json()
    permit_id = permit_resp["id"]
    pdoc_ticket = client.post(
        "/v1/media/upload-url",
        headers=owner_headers,
        json={
            "kind": "PERMIT_DOC",
            "project_id": pid,
            "object_id": permit_id,
            "content_type": "image/jpeg",
            "byte_size": len(valid_jpeg),
        },
    ).json()
    client.put(
        pdoc_ticket["upload_url"].replace("http://testserver", ""),
        content=valid_jpeg,
        headers={"Content-Type": "image/jpeg"},
    )
    assert (
        client.post(
            "/v1/media/complete",
            headers=owner_headers,
            json={
                "kind": "PERMIT_DOC",
                "object_id": permit_id,
                "ticket_id": pdoc_ticket["ticket_id"],
            },
        ).status_code
        == 204
    )
    permits = client.get(f"/v1/projects/{pid}/permits", headers=owner_headers).json()
    p_row = next(p for p in permits if p["id"] == permit_id)
    assert p_row["ai_extracted_data"] is not None
    assert p_row["ai_extracted_data"]["authority"]

    # 3. Malformed AI JSON marks job FAILED cleanly with non-leaky error
    malformed_log = SiteLog(
        id=uuid.uuid4(),
        project_id=sample_project.id,
        author_id=sample_project.created_by,
        log_date=now.date(),
        recorded_at=now,
        notes="Inspect rebar before concrete pour",
        audio_upload_status="NONE",
        extraction_status="PENDING",
        client_updated_at=now,
    )
    db_session.add(malformed_log)
    db_session.flush()
    bad_job = ExtractionJob(
        organization_id=sample_project.organization_id,
        project_id=sample_project.id,
        target_type="SITE_LOG",
        target_id=malformed_log.id,
        idempotency_key=f"malformed:{malformed_log.id}",
        status="PENDING",
        attempts=0,
        max_attempts=3,
        next_run_at=now - timedelta(seconds=1),
    )
    db_session.add(bad_job)
    db_session.commit()

    real_cfg = Settings(USE_MOCK_GEMINI=False, GEMINI_API_KEY="k", LOCAL_STORAGE_DIR=".")
    fake_client = MagicMock()
    fake_client.models.generate_content.return_value = SimpleNamespace(
        text="NOT VALID JSON",
        parsed=None,
    )
    sf = sessionmaker(bind=db_session.get_bind(), expire_on_commit=False)
    with patch("app.services.ai_extractor._create_genai_client", return_value=fake_client):
        execute_extraction_job(bad_job.id, sf, real_cfg)

    db_session.expire_all()
    refreshed_job = db_session.get(ExtractionJob, bad_job.id)
    assert refreshed_job is not None
    assert refreshed_job.status == "FAILED"
    assert "Malformed" in (refreshed_job.last_error or "")

    # 4. Stale lease job recovery resets PROCESSING with expired locked_until back to PENDING
    refreshed_job.status = "PROCESSING"
    refreshed_job.locked_until = now - timedelta(minutes=10)
    db_session.commit()
    recovered = recover_stuck_extractions(sf, get_settings())
    assert malformed_log.id in recovered
    db_session.expire_all()
    assert db_session.get(ExtractionJob, bad_job.id).status == "PENDING"  # type: ignore[union-attr]

    # 5. Internal Cloud Tasks webhook validates secret
    bad_task = client.post(
        "/v1/internal/tasks/extraction",
        json={"job_id": str(bad_job.id)},
        headers={"X-Task-Secret": "wrong-secret"},
    )
    assert bad_task.status_code in (401, 403, 503)
    jobs_list = client.get(
        f"/v1/projects/{pid}/extraction-jobs",
        headers=owner_headers,
    )
    assert jobs_list.status_code == 200
    assert len(jobs_list.json()) >= 3
    _ = (SiteLogPhoto, Permit, assert_problem_json)


def test_postgres_backup_and_restore_roundtrip(
    pg_uri: str,
    owner_user: User,
    sample_project: Project,
    tmp_path: Path,
) -> None:
    del owner_user, sample_project
    import os
    from urllib.parse import urlsplit, urlunsplit

    candidate_dirs = [
        Path(pg_commands.POSTGRES_BIN_PATH),
        Path(pg_commands.__file__).resolve().parent / "pginstall" / "bin",
    ]
    pg_dump_bin: str | None = None
    psql_bin: str | None = None
    if not os.environ.get("TEST_DATABASE_URL"):
        for pg_bin_dir in candidate_dirs:
            for ext in (".exe", ""):
                dump_candidate = pg_bin_dir / f"pg_dump{ext}"
                psql_candidate = pg_bin_dir / f"psql{ext}"
                if dump_candidate.exists() and psql_candidate.exists():
                    pg_dump_bin = str(dump_candidate)
                    psql_bin = str(psql_candidate)
                    break
            if pg_dump_bin and psql_bin:
                break
    pg_dump_bin = pg_dump_bin or shutil.which("pg_dump") or ""
    psql_bin = psql_bin or shutil.which("psql") or ""

    assert Path(pg_dump_bin).exists(), f"pg_dump missing at {pg_dump_bin}"
    assert Path(psql_bin).exists(), f"psql missing at {psql_bin}"

    libpq_uri = pg_uri.replace("postgresql+psycopg://", "postgresql://")
    dump_file = tmp_path / "backup.sql"
    dump_proc = subprocess.run(
        [pg_dump_bin, "--clean", "--if-exists", "--no-owner", "-f", str(dump_file), libpq_uri],
        capture_output=True,
        text=True,
        check=True,
    )
    assert dump_proc.returncode == 0
    assert dump_file.stat().st_size > 1000

    # Restore into an isolated verification database on the same Postgres instance
    restore_db = f"verify_restore_{uuid.uuid4().hex[:8]}"
    subprocess.run(
        [
            psql_bin,
            "-v",
            "ON_ERROR_STOP=1",
            "-d",
            libpq_uri,
            "-c",
            f"CREATE DATABASE {restore_db}",
        ],
        capture_output=True,
        text=True,
        timeout=15,
        check=True,
    )
    parsed_uri = urlsplit(libpq_uri)
    restore_uri = urlunsplit(parsed_uri._replace(path=f"/{restore_db}"))
    try:
        restore_proc = subprocess.run(
            [psql_bin, "-v", "ON_ERROR_STOP=1", "-d", restore_uri, "-f", str(dump_file)],
            capture_output=True,
            text=True,
            timeout=15,
            check=False,
        )
        assert restore_proc.returncode == 0, (
            f"psql restore failed ({restore_proc.returncode}): "
            f"{restore_proc.stderr}\n{restore_proc.stdout[:1000]}"
        )
        check_proc = subprocess.run(
            [
                psql_bin,
                "-t",
                "-A",
                "-d",
                restore_uri,
                "-c",
                "SELECT count(*) FROM projects WHERE deleted_at IS NULL;",
            ],
            capture_output=True,
            text=True,
            timeout=15,
            check=True,
        )
        assert int(check_proc.stdout.strip()) == 1
    finally:
        subprocess.run(
            [
                psql_bin,
                "-d",
                libpq_uri,
                "-c",
                f"DROP DATABASE IF EXISTS {restore_db};",
            ],
            capture_output=True,
            text=True,
            timeout=15,
            check=False,
        )

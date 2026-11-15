from __future__ import annotations

import os
import stat
import uuid
from datetime import UTC, date, datetime
from pathlib import Path

import pytest
from _pytest.outcomes import Failed
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.db.models import Permit, Project, SiteLog
from tests.conftest import (
    _ensure_non_root_for_embedded_pg,
    _prepare_pgserver_install,
    assert_problem_json,
)


def test_root_guard_requires_non_root_or_external_db(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(os, "geteuid", lambda: 0, raising=False)
    with pytest.raises(Failed) as exc_info:
        _ensure_non_root_for_embedded_pg()
    msg = str(exc_info.value)
    assert "non-root" in msg
    assert "TEST_DATABASE_URL" in msg

    monkeypatch.setattr(os, "geteuid", lambda: 1000, raising=False)
    _ensure_non_root_for_embedded_pg()


def test_pgserver_install_staged_in_tmp_without_mutating_source(
    tmp_path: Path,
) -> None:
    fake_pginstall = tmp_path / "readonly_site_packages" / "pginstall"
    (fake_pginstall / "bin").mkdir(parents=True)
    (fake_pginstall / "lib").mkdir(parents=True)
    (fake_pginstall / "share" / "postgresql").mkdir(parents=True)
    (fake_pginstall / "bin" / "postgres").write_text("bin", encoding="utf-8")

    fake_tz_src = tmp_path / "tzdata_src" / "zoneinfo" / "Asia"
    fake_tz_src.mkdir(parents=True)
    (fake_tz_src / "Karachi").write_text("TZif", encoding="utf-8")

    share_dir = fake_pginstall / "share" / "postgresql"
    staged_root = tmp_path / "runtime"
    staged_root.mkdir()

    # Make the simulated site-packages directory read-only on POSIX to prove no mutation
    share_dir.chmod(stat.S_IRUSR | stat.S_IXUSR)
    try:
        staged = _prepare_pgserver_install(
            staged_root,
            pg_install_dir=fake_pginstall,
            tz_source_dir=tmp_path / "tzdata_src" / "zoneinfo",
        )
    finally:
        share_dir.chmod(stat.S_IRWXU)

    assert staged is not None
    assert not (share_dir / "timezone").exists()
    assert (staged / "share" / "postgresql" / "timezone" / "Asia" / "Karachi").is_file()
    assert (staged / "bin" / "postgres").is_file()

    # If pgserver already includes timezone files, staging is skipped
    already_has_tz = _prepare_pgserver_install(
        tmp_path / "unused",
        pg_install_dir=staged,
        tz_source_dir=tmp_path / "tzdata_src" / "zoneinfo",
    )
    assert already_has_tz is None


def test_retry_extraction_conflicts_and_failed_recovery(
    client: TestClient,
    db_session: Session,
    sample_project: Project,
    owner_headers: dict[str, str],
    supervisor_headers: dict[str, str],
) -> None:
    now = datetime.now(UTC)
    pid = sample_project.id

    pending_log = SiteLog(
        id=uuid.uuid4(),
        project_id=pid,
        author_id=sample_project.created_by,
        log_date=date(2026, 11, 13),
        recorded_at=now,
        notes="No uploaded audio yet",
        audio_uri=f"local://projects/{pid}/audio/{uuid.uuid4()}.m4a",
        audio_upload_status="PENDING",
        extraction_status="NOT_STARTED",
        client_updated_at=now,
    )
    processing_log = SiteLog(
        id=uuid.uuid4(),
        project_id=pid,
        author_id=sample_project.created_by,
        log_date=date(2026, 11, 13),
        recorded_at=now,
        notes="Currently processing",
        audio_uri=f"local://projects/{pid}/audio/{uuid.uuid4()}.m4a",
        audio_upload_status="UPLOADED",
        extraction_status="PROCESSING",
        client_updated_at=now,
    )
    failed_log = SiteLog(
        id=uuid.uuid4(),
        project_id=pid,
        author_id=sample_project.created_by,
        log_date=date(2026, 11, 13),
        recorded_at=now,
        notes="Previously failed extraction",
        audio_uri=f"local://projects/{pid}/audio/{uuid.uuid4()}.m4a",
        audio_upload_status="UPLOADED",
        extraction_status="FAILED",
        extraction_error="Temporary timeout",
        extraction_attempts=3,
        client_updated_at=now,
    )
    db_session.add_all([pending_log, processing_log, failed_log])
    db_session.commit()

    not_uploaded = client.post(
        "/v1/logs/extract",
        headers=owner_headers,
        json={"log_id": str(pending_log.id)},
    )
    assert_problem_json(not_uploaded, 409, "AUDIO_NOT_UPLOADED")

    in_progress = client.post(
        "/v1/logs/extract",
        headers=supervisor_headers,
        json={"log_id": str(processing_log.id)},
    )
    assert_problem_json(in_progress, 409, "EXTRACTION_IN_PROGRESS")

    # Retry on FAILED resets error/attempts and runs mock extraction to DONE
    retry_resp = client.post(
        "/v1/logs/extract",
        headers=owner_headers,
        json={"log_id": str(failed_log.id)},
    )
    assert retry_resp.status_code == 202
    assert retry_resp.json()["extraction_status"] == "PENDING"

    detail = client.get(f"/v1/logs/{failed_log.id}", headers=owner_headers)
    assert detail.status_code == 200
    body = detail.json()
    assert body["extraction_status"] == "DONE"
    assert body["extraction_error"] is None
    assert body["structured_summary"]["labor_count"] == 14


def test_sync_pull_invalid_project_and_portfolio_rollup_deduplication(
    client: TestClient,
    db_session: Session,
    sample_project: Project,
    owner_headers: dict[str, str],
    supervisor_headers: dict[str, str],
) -> None:
    unknown_pid = uuid.uuid4()
    pull_denied = client.get(
        f"/v1/sync/pull?since=0&project_id={unknown_pid}",
        headers=supervisor_headers,
    )
    assert pull_denied.status_code == 200
    denied_changes = pull_denied.json()["changes"]
    assert denied_changes["projects"] == []
    assert denied_changes["permits"] == []
    assert denied_changes["site_logs"] == []
    assert denied_changes["site_log_photos"] == []
    assert denied_changes["project_members"] == []

    now = datetime.now(UTC)
    today_in_karachi = date(2026, 11, 14)
    l1 = uuid.uuid4()
    l2 = uuid.uuid4()
    db_session.add_all(
        [
            SiteLog(
                id=l1,
                project_id=sample_project.id,
                author_id=sample_project.created_by,
                log_date=today_in_karachi,
                recorded_at=now,
                notes="Morning",
                structured_summary={
                    "tasks_completed": ["Rebar", "Formwork"],
                    "labor_count": 11,
                    "material_deliveries": ["Steel"],
                    "blockers": ["Crane delay"],
                },
                edited_by_human=True,
                client_updated_at=now,
            ),
            SiteLog(
                id=l2,
                project_id=sample_project.id,
                author_id=sample_project.created_by,
                log_date=today_in_karachi,
                recorded_at=now,
                notes="Afternoon",
                structured_summary={
                    "tasks_completed": ["Formwork", "Pouring"],
                    "labor_count": 16,
                    "material_deliveries": ["Steel", "Cement"],
                    "blockers": ["Crane delay"],
                },
                edited_by_human=True,
                client_updated_at=now,
            ),
            Permit(
                id=uuid.uuid4(),
                project_id=sample_project.id,
                permit_name="Active Site NOC",
                authority="SBCA",
                expiry_date=date(2030, 1, 1),
                created_by=sample_project.created_by,
                client_updated_at=now,
            ),
        ]
    )
    db_session.commit()

    day_report = client.get(
        f"/v1/projects/{sample_project.id}/days/{today_in_karachi.isoformat()}",
        headers=owner_headers,
    )
    assert day_report.status_code == 200
    data = day_report.json()
    # Daily report uses MAX(labor_count) rather than sum (16 vs 27) and deduplicates lists
    assert data["labor_max"] == 16
    assert data["log_count"] == 2
    assert data["blockers"] == ["Crane delay"]
    assert data["tasks_completed"] == ["Rebar", "Formwork", "Pouring"]
    assert data["material_deliveries"] == ["Steel", "Cement"]


def test_patch_site_log_notes_sets_edited_by_human(
    client: TestClient,
    db_session: Session,
    sample_project: Project,
    owner_headers: dict[str, str],
) -> None:
    now = datetime.now(UTC)
    log = SiteLog(
        id=uuid.uuid4(),
        project_id=sample_project.id,
        author_id=sample_project.created_by,
        log_date=date(2026, 11, 14),
        recorded_at=now,
        notes="Initial field note",
        edited_by_human=False,
        client_updated_at=now,
    )
    db_session.add(log)
    db_session.commit()

    patched = client.patch(
        f"/v1/logs/{log.id}",
        headers=owner_headers,
        json={"notes": "Updated field note"},
    )
    assert patched.status_code == 200
    body = patched.json()
    assert body["notes"] == "Updated field note"
    assert body["edited_by_human"] is True

    explicit_false = client.patch(
        f"/v1/logs/{log.id}",
        headers=owner_headers,
        json={"notes": "Automated note reset", "edited_by_human": False},
    )
    assert explicit_false.status_code == 200
    assert explicit_false.json()["edited_by_human"] is False


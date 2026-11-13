from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.db.models import Permit, Project, SiteLog, User
from app.scripts.seed import seed_database


def test_initial_schema_sql_is_byte_identical_to_contract() -> None:
    api_schema = Path(__file__).resolve().parents[1] / "app" / "db" / "initial_schema.sql"
    contract_schema = Path(__file__).resolve().parents[3] / "contracts" / "schema.sql"
    assert api_schema.is_file()
    assert contract_schema.is_file()
    assert api_schema.read_bytes() == contract_schema.read_bytes()


def test_healthz_and_schema_objects(client: TestClient, db_session: Session) -> None:
    resp = client.get("/healthz")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}

    view_exists = db_session.scalar(
        text(
            "SELECT EXISTS (SELECT 1 FROM information_schema.views "
            "WHERE table_name = 'permits_with_status')"
        )
    )
    assert view_exists is True

    seq_exists = db_session.scalar(
        text(
            "SELECT EXISTS (SELECT 1 FROM information_schema.sequences "
            "WHERE sequence_name = 'sync_version_seq')"
        )
    )
    assert seq_exists is True


def test_seed_is_idempotent(db_session: Session, client: TestClient) -> None:
    seed_database(db_session)
    seed_database(db_session)

    users = db_session.query(User).all()
    projects = db_session.query(Project).all()
    permits = db_session.query(Permit).all()
    logs = db_session.query(SiteLog).all()

    assert len(users) == 2
    assert len(projects) == 1
    assert len(permits) == 3
    assert len(logs) == 2

    login_resp = client.post(
        "/v1/auth/login",
        json={"email": "owner@example.com", "password": "owner12345"},
    )
    assert login_resp.status_code == 200
    token = login_resp.json()["access_token"]

    portfolio = client.get(
        "/v1/projects",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert portfolio.status_code == 200
    items = portfolio.json()
    assert len(items) == 1
    assert items[0]["permit_health"] == "EXPIRED"
    assert items[0]["today"]["labor_max"] == 14
    assert items[0]["today"]["log_count"] == 1

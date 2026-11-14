from __future__ import annotations

import contextlib
import os
import shutil
from collections.abc import Generator
from pathlib import Path
from typing import Any

import pgserver
import pgserver._commands as pg_commands
import pgserver.postgres_server as pg_server_mod
import pytest
import tzdata
from alembic.config import Config
from fastapi.testclient import TestClient
from pgserver.postgres_server import get_server
from sqlalchemy import Engine, create_engine, text
from sqlalchemy.orm import Session, sessionmaker

from alembic import command
from app.core.config import get_settings, normalize_postgres_url
from app.db.models import Project, ProjectMember, User
from app.db.session import get_engine
from app.main import app
from app.services.auth import hash_password

SERVICE_ROOT = Path(__file__).resolve().parents[1]


def _ensure_non_root_for_embedded_pg() -> None:
    """Fail cleanly when running embedded Postgres as root without TEST_DATABASE_URL."""
    geteuid = getattr(os, "geteuid", None)
    if callable(geteuid) and geteuid() == 0:
        pytest.fail(
            "Embedded Postgres (pgserver) cannot run as root. "
            "Run pytest as a non-root user, or set TEST_DATABASE_URL to an external Postgres.",
            pytrace=False,
        )


def _prepare_pgserver_install(
    tmp_root: Path,
    pg_install_dir: Path | None = None,
    tz_source_dir: Path | None = None,
) -> Path | None:
    """Stage pginstall + tzdata in tmp when timezone files are missing."""
    install_dir = pg_install_dir or (
        Path(pgserver.__file__).resolve().parent / "pginstall"
    )
    pg_tz_dir = install_dir / "share" / "postgresql" / "timezone"
    if pg_tz_dir.is_dir():
        return None

    staged_install = tmp_root / "pginstall"
    for subdir in ("bin", "lib", "share"):
        src = install_dir / subdir
        if src.is_dir():
            shutil.copytree(src, staged_install / subdir, dirs_exist_ok=True)

    tz_src = tz_source_dir or (Path(tzdata.__file__).resolve().parent / "zoneinfo")
    if tz_src.is_dir():
        shutil.copytree(
            tz_src,
            staged_install / "share" / "postgresql" / "timezone",
            dirs_exist_ok=True,
        )
    return staged_install


@pytest.fixture(scope="session")
def pg_uri(tmp_path_factory: pytest.TempPathFactory) -> Generator[str, None, None]:
    external_url = os.environ.get("TEST_DATABASE_URL", "").strip()
    if external_url:
        yield external_url
        return

    _ensure_non_root_for_embedded_pg()

    server_mod: Any = pg_server_mod
    orig_cmd_bin: Any = pg_commands.POSTGRES_BIN_PATH
    orig_srv_bin: Any = server_mod.POSTGRES_BIN_PATH
    staged_install = _prepare_pgserver_install(
        tmp_path_factory.mktemp("pgserver_runtime")
    )
    if staged_install is not None:
        staged_bin = staged_install / "bin"
        pg_commands.POSTGRES_BIN_PATH = staged_bin
        server_mod.POSTGRES_BIN_PATH = staged_bin

    pgdata = tmp_path_factory.mktemp("pgserver_data")
    server = get_server(pgdata, cleanup_mode="stop")
    try:
        yield server.get_uri()
    finally:
        try:
            with contextlib.suppress(OSError):
                server.cleanup()
        finally:
            pg_commands.POSTGRES_BIN_PATH = orig_cmd_bin
            server_mod.POSTGRES_BIN_PATH = orig_srv_bin


@pytest.fixture(scope="session")
def db_engine(pg_uri: str) -> Generator[Engine, None, None]:
    normalized_url = normalize_postgres_url(pg_uri)
    os.environ["DATABASE_URL"] = pg_uri
    os.environ["USE_MOCK_GEMINI"] = "true"
    os.environ["STORAGE_BACKEND"] = "local"
    get_settings.cache_clear()
    get_engine.cache_clear()

    alembic_cfg = Config(str(SERVICE_ROOT / "alembic.ini"))
    alembic_cfg.set_main_option("script_location", str(SERVICE_ROOT / "alembic"))
    alembic_cfg.set_main_option("sqlalchemy.url", normalized_url)
    command.upgrade(alembic_cfg, "head")

    engine = create_engine(normalized_url, pool_pre_ping=True, future=True)
    try:
        yield engine
    finally:
        engine.dispose()


@pytest.fixture(autouse=True)
def reset_state(
    db_engine: Engine,
    pg_uri: str,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> Generator[None, None, None]:
    storage_dir = tmp_path / "storage"
    storage_dir.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("DATABASE_URL", pg_uri)
    monkeypatch.setenv("LOCAL_STORAGE_DIR", str(storage_dir))
    monkeypatch.setenv("STORAGE_BACKEND", "local")
    monkeypatch.setenv("USE_MOCK_GEMINI", "true")
    monkeypatch.setenv("PUBLIC_API_BASE_URL", "http://testserver")
    monkeypatch.setenv("JWT_SECRET", "test-jwt-secret-key-for-unit-tests-only")
    monkeypatch.setenv("MEDIA_URL_SIGNING_SECRET", "test-media-signing-secret")
    get_settings.cache_clear()
    get_engine.cache_clear()

    with db_engine.begin() as conn:
        conn.execute(
            text(
                "TRUNCATE TABLE site_log_photos, site_logs, permit_alerts, permits, "
                "project_members, projects, device_tokens, refresh_tokens, users "
                "RESTART IDENTITY CASCADE"
            )
        )
        conn.execute(text("ALTER SEQUENCE sync_version_seq RESTART WITH 1"))

    yield

    get_settings.cache_clear()
    get_engine.cache_clear()


@pytest.fixture
def db_session(db_engine: Engine) -> Generator[Session, None, None]:
    session_factory = sessionmaker(
        bind=db_engine,
        autocommit=False,
        autoflush=False,
        expire_on_commit=False,
    )
    with session_factory() as session:
        yield session


@pytest.fixture
def client(db_engine: Engine) -> Generator[TestClient, None, None]:
    del db_engine
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def owner_user(db_session: Session) -> User:
    user = User(
        email="owner@example.com",
        password_hash=hash_password("owner12345"),
        full_name="Site Owner",
        role="OWNER",
        preferred_locale="en",
        must_change_password=False,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture
def supervisor_user(db_session: Session) -> User:
    user = User(
        email="supervisor@example.com",
        password_hash=hash_password("super12345"),
        full_name="Site Supervisor",
        role="SUPERVISOR",
        preferred_locale="ur",
        must_change_password=False,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


def auth_headers(client: TestClient, email: str, password: str) -> dict[str, str]:
    resp = client.post(
        "/v1/auth/login",
        json={"email": email, "password": password},
    )
    assert resp.status_code == 200, resp.text
    token = resp.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def owner_headers(client: TestClient, owner_user: User) -> dict[str, str]:
    return auth_headers(client, owner_user.email, "owner12345")


@pytest.fixture
def supervisor_headers(client: TestClient, supervisor_user: User) -> dict[str, str]:
    return auth_headers(client, supervisor_user.email, "super12345")


@pytest.fixture
def sample_project(
    db_session: Session,
    owner_user: User,
    supervisor_user: User,
) -> Project:
    project = Project(
        name="Alpha Tower",
        site_address="Plot 10, Clifton, Karachi",
        owner_phone="+923001112233",
        timezone="Asia/Karachi",
        allow_photo_gps=False,
        created_by=owner_user.id,
    )
    db_session.add(project)
    db_session.flush()
    db_session.add_all(
        [
            ProjectMember(project_id=project.id, user_id=owner_user.id, role="OWNER"),
            ProjectMember(
                project_id=project.id, user_id=supervisor_user.id, role="SUPERVISOR"
            ),
        ]
    )
    db_session.commit()
    db_session.refresh(project)
    return project


def assert_problem_json(resp: Any, status: int, code: str) -> dict[str, Any]:
    assert resp.status_code == status
    assert resp.headers["content-type"].startswith("application/problem+json")
    data: dict[str, Any] = resp.json()
    assert data["status"] == status
    assert data["code"] == code
    assert "title" in data
    return data

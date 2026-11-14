# Site Diary API

FastAPI backend for the Construction Permit & Site Diary system.

## Setup with `uv` (Recommended)

```bash
uv sync
uv run alembic upgrade head
uv run python -m app.scripts.seed
uv run uvicorn app.main:app --reload --port 8000
uv run ruff check . && uv run mypy . && uv run pytest
```

## Setup with `pip` (Fallback without `uv`)

```bash
python -m venv .venv
# Linux/macOS: source .venv/bin/activate
# Windows PowerShell: .\.venv\Scripts\Activate.ps1
pip install -e ".[dev]"
# Or via requirements-dev.txt: pip install -r requirements-dev.txt
ruff check . && mypy . && pytest -q
```

## Running Tests as Root / Containers

When `TEST_DATABASE_URL` is unset, the test suite starts an embedded PostgreSQL instance via `pgserver`, which refuses to run as `root` (`os.geteuid() == 0`). Always run `pytest` as a **non-root user**, or point `TEST_DATABASE_URL` at an external PostgreSQL database (for example, `TEST_DATABASE_URL=postgresql://postgres:postgres@localhost:5432/site_diary pytest -q`).

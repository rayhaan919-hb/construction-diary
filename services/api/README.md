# Site Diary API

FastAPI backend for the Construction Permit & Site Diary system.

## Commands

```bash
uv sync
uv run alembic upgrade head
uv run python -m app.scripts.seed
uv run uvicorn app.main:app --reload --port 8000
uv run ruff check . && uv run mypy . && uv run pytest
```

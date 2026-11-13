# Offline-First Construction Permit & Site Diary

Monorepo implementing an offline-first construction site diary, permit expiry compliance tracker, multimodal Gemini voice extraction pipeline, and owner Bento portal.

## Structure
- `apps/mobile` — Android (Kotlin, Jetpack Compose, Room offline mirror, CameraX, M4A AudioRecorder, WorkManager sync, EN/UR RTL)
- `services/api` — Python FastAPI, PostgreSQL 16 + Alembic, delta sync, signed media URLs, Gemini multimodal extraction, daily permit alert job
- `apps/web` — Next.js App Router, Tailwind CSS v4, OpenAPI-generated types, Owner Bento dashboard, timeline, 1-click `@react-pdf/renderer` daily report export
- `contracts` — Frozen OpenAPI 3.1 contract (`api-contract.yaml`) & canonical schema (`schema.sql`)

## Quick Start (Local Dev)
1. Copy `.env.example` to `.env` (or configure `services/api/.env` and `apps/web/.env.local`).
2. **Backend (`/services/api`)**:
   - With Docker Postgres: `docker compose up -d postgres`
   - Or run tests directly offline using embedded Postgres (`pgserver`):
     ```bash
     cd services/api
     uv sync
     uv run ruff check . && uv run mypy . && uv run pytest
     ```
   - Migrate & seed:
     ```bash
     uv run alembic upgrade head
     uv run python -m app.scripts.seed
     uv run uvicorn app.main:app --reload --port 8000
     ```
3. **Web (`/apps/web`)**:
   ```bash
   cd apps/web
   npm install
   npm run typecheck && npm run lint && npm run build
   npm run dev
   ```
4. **Mobile (`/apps/mobile`)**:
   ```bash
   cd apps/mobile
   ./gradlew testDebugUnitTest
   ```

See [DEPLOY.md](DEPLOY.md) for Cloud Run, Cloud SQL, GCS, and Cloud Scheduler deployment instructions.

# 02 — Local & Docker Development Setup

This guide covers running all three components locally for development, testing, or evaluation.

---

## 1. Prerequisites

- **Python 3.12+** with [`uv`](https://docs.astral.sh/uv/) (or `pip` + `services/api/requirements-dev.txt`)
- **Node.js 20+** and `npm`
- **JDK 17+** (or Android Studio JBR) + Android SDK (`API 35`) for mobile builds
- **PostgreSQL 16+** (or Docker Desktop; `pytest` can also use `pgserver` or `TEST_DATABASE_URL`)

---

## 2. Backend API (`services/api`)

```bash
cd services/api
uv sync --group dev

# Run against local Postgres or embedded pgserver (non-root)
cp ../../.env.example ../../.env
USE_MOCK_GEMINI=true ENABLE_DEV_SEED=true uv run alembic upgrade head
USE_MOCK_GEMINI=true uv run uvicorn app.main:app --reload --port 8000
```

Pip fallback without `uv`:
```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt
```

Verification:
```bash
uv run ruff check .
uv run mypy .
USE_MOCK_GEMINI=true uv run pytest -q
```

---

## 3. Web Owner Portal (`apps/web`)

```bash
cd apps/web
npm ci
cp .env.example .env.local
```

### Live Mode (connected to FastAPI)
Set `API_BASE_URL=http://127.0.0.1:8000` and `NEXT_PUBLIC_DEMO_MODE=false` in `apps/web/.env.local`, then:
```bash
npm run dev
```

### Standalone Demo Preview Mode (no backend required)
Set `NEXT_PUBLIC_DEMO_MODE=true` in `apps/web/.env.local`:
- Portfolio, daily timeline, bilingual English/Urdu summaries, permits, organization management, audit logs, and downloadable PDF reports all operate from seeded demo state (`apps/web/src/lib/demo-data.ts`).

Verification:
```bash
npm run typecheck
npm run lint
npm test
npm run build
```

---

## 4. Android Field App (`apps/mobile`)

```bash
cd apps/mobile
./gradlew testDebugUnitTest lintDebug
```

- By default, debug builds point to `http://10.0.2.2:8000/` for Android Emulator loopback access to local FastAPI.
- `google-services.json` is optional for builds and unit tests (`app/build.gradle.kts` detects its presence before applying the Google Services plugin).

---

## 5. Full Local Stack via Docker Compose

```bash
cp .env.example .env
docker compose up --build -d
```

Services bind to `127.0.0.1`:
- PostgreSQL 16 (`127.0.0.1:5432`)
- FastAPI Backend (`127.0.0.1:8000`, health `/healthz`, readiness `/readyz`)
- Next.js Web Portal (`127.0.0.1:3000`, health `/api/health`)

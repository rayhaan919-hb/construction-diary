# AGENTS.md — Offline-First Construction Permit & Site Diary

## 1. Monorepo Structure
- `/apps/mobile` — Kotlin + Jetpack Compose + Room + WorkManager + CameraX
- `/services/api` — Python FastAPI + PostgreSQL + Gemini Multimodal API
- `/apps/web` — Next.js + Tailwind CSS v4 + Chromium/React-PDF Owner Portal
- `/contracts` — Frozen OpenAPI 3.1 spec (`api-contract.yaml`) & canonical PostgreSQL schema (`schema.sql`)

## 2. Sub-Agent Delegation Rules
- **Sub-Agent 1 (`mobile-agent`):** Owns `/apps/mobile`. Implements offline Room entities, CameraX photo capture, AudioRecorder (M4A), and WorkManager background sync.
- **Sub-Agent 2 (`ai-backend-agent`):** Owns `/services/api`. Implements delta sync endpoints, Gemini multimodal voice-to-JSON extraction, and daily permit expiry cron alerts.
- **Sub-Agent 3 (`web-agent`):** Owns `/apps/web`. Implements owner Bento dashboard, project timeline, and 1-click PDF daily report export.

## 3. Mandatory Verification Gates
1. `cd services/api && ruff check . && mypy . && pytest`
2. `cd apps/web && npm run typecheck && npm run lint && npm run build`
3. `cd apps/mobile && ./gradlew testDebugUnitTest`

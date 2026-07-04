# E2E Blocker Fix Report

Final Verdict: READY_FOR_E2E_RETEST

## 1. Frontend same-origin / CSP blocker

Issue: Production pages were still calling `http://localhost:8000` directly from the browser, which violated the HTTPS deployment model and triggered CSP and mixed-content failures.

Root Cause: Multiple frontend services, hooks, pages, and footer links hardcoded the backend origin instead of using nginx same-origin routing.

Fix Applied: Added shared runtime URL helpers in `frontend/lib/constants.ts` and rewired affected call sites to use same-origin `apiUrl(...)` and derived websocket URLs.

Validation Evidence:
- Production frontend rebuilt successfully earlier in the session.
- Browser validation against `https://localhost` showed same-origin API requests only:
  - `https://localhost/api/executive/*`
  - `https://localhost/api/memory/explorer/*`
  - `https://localhost/api/governance-center/*`
- Browser validation found no CSP or mixed-content console errors on the validated flows.

## 2. Production auth runtime blocker

Issue: Login, refresh, and authenticated API access failed through nginx in the live runtime.

Root Cause: `docker compose --env-file backend/.env` made variables available for interpolation, but the backend service was not actually passing critical auth and JWT variables into the container environment.

Fix Applied: Added explicit backend environment passthrough in `docker-compose.yml` for `CORTEX_USER`, `CORTEX_PASSWORD`, `CORTEX_PASSWORD_HASH`, `JWT_SECRET_KEY`, `JWT_REFRESH_SECRET`, `JWT_ALGORITHM`, `JWT_EXPIRE_MINUTES`, and `JWT_REFRESH_EXPIRE_H`.

Validation Evidence:
- `POST https://localhost/api/auth/login` returned `200`.
- `GET https://localhost/api/auth/me` returned `200` after login.
- `POST https://localhost/api/auth/refresh` returned `200`.
- `POST https://localhost/api/auth/logout` returned `200`.
- Access and refresh cookies were issued and cleared correctly.

## 3. RabbitMQ production runtime blocker

Issue: Backend startup degraded because RabbitMQ robust connection callback registration failed.

Root Cause: The code expected legacy `aio-pika` callback methods (`add_reconnect_callback`, `add_close_callback`) that are not present on the installed robust connection object.

Fix Applied: Added compatibility registration in `backend/infrastructure/rabbitmq/connection.py` to support both the legacy callback methods and the newer callback collection API.

Validation Evidence:
- Live `/health/system` now reports `rabbitmq.status = healthy`.
- Backend startup completed with RabbitMQ connected and orchestration bus started.

## 4. Database migration false-negative health blocker

Issue: System health marked database migration state as out-of-date even though the current schema was at head.

Root Cause: Migration comparison used exact string equality between current revision `0004` and head revision `0004_add_cost_tracking`.

Fix Applied: Normalized revision IDs in `backend/database/migrator.py` before comparison so canonical revision prefixes are accepted.

Validation Evidence:
- Live `/health/system` reports:
  - `database.status = healthy`
  - `migration.current_revision = 0004`
  - `migration.latest_revision = 0004_add_cost_tracking`
  - `migration.up_to_date = true`

## 5. LLM health false-degraded blocker

Issue: System health reported the LLM layer as degraded when providers were configured but had not yet received traffic.

Root Cause: The health logic treated `total_calls == 0` as degraded even when providers were available and no circuit breaker was open.

Fix Applied: Updated `backend/llm/llm_router.py` so zero-call idle state is healthy when providers are available and circuits are closed.

Validation Evidence:
- Live `/health/system` reports `llm.status = healthy` with configured providers available and zero traffic.

## 6. Optional Sentry false-degraded blocker

Issue: System health treated Sentry as degraded when no DSN was configured.

Root Cause: Optional observability was modeled as mandatory in `backend/api/system_health_routes.py`.

Fix Applied: Changed Sentry health semantics to `healthy` with `enabled: false` and `dsn_configured: false` when Sentry is intentionally unset.

Validation Evidence:
- Live `/health/system` reports `sentry.status = healthy` and `enabled = false`.

## 7. Voice V2 production runtime blocker

Issue: Authenticated `POST /api/voice/v2/session` failed in production runtime.

Root Cause: This was a stacked runtime issue:
- voice-specific env vars were not passed into the backend container
- required Voice V2 Python dependencies were missing from the backend image/runtime
- the old `PyJWT==2.10.1` pin conflicted with the required `pipecat-ai` livekit extras

Fix Applied:
- Added backend env passthrough in `docker-compose.yml` for `LIVEKIT_URL`, `LIVEKIT_API_KEY`, `LIVEKIT_API_SECRET`, `DEEPGRAM_API_KEY`, and `MODEL_TTS`
- Added Voice V2 dependencies to `requirements.txt`:
  - `livekit-api==1.1.0`
  - `deepgram-sdk==7.3.1`
  - `pipecat-ai[deepgram,livekit,openai,silero]==1.3.0`
- Updated `PyJWT` pin to `2.13.0` to satisfy the Voice V2 dependency graph
- Installed the same dependency set into the running backend container to validate the live runtime immediately

Validation Evidence:
- Before fix: authenticated `POST https://localhost/api/voice/v2/session` returned `503`, then `500` after env passthrough exposed the next failure.
- After dependency fix and runtime install:
  - running backend imports resolved: `LIVEKIT True`, `PIPECAT True`, `DEEPGRAM True`
  - authenticated `POST https://localhost/api/voice/v2/session` returned `200`
  - response included `session_id`, `room_name`, `token`, and `livekit_url`

## 8. Final live runtime status

Validation Evidence:
- `GET https://localhost/health/system` returned `200`
- final live health payload reported top-level `status = healthy`
- browser validation against the HTTPS frontend showed same-origin API usage and no CSP or mixed-content errors on the validated flows

## Verdict

READY_FOR_E2E_RETEST
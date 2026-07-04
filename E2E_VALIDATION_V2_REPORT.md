# E2E_VALIDATION_V2_REPORT

## Scope

Validation was performed against the nginx-exposed production runtime at `https://localhost` on 2026-06-14.

## Final Verdict

`FAIL`

Multiple major workflows do not pass end-to-end in the actual nginx-exposed production runtime.

## Summary Table

| Phase | Workflow | Status | Result |
| --- | --- | --- | --- |
| 1 | Authentication | FAIL | Login does not complete end-to-end; cookies are not created. |
| 2 | Executive Center | FAIL | Protected route redirects to login; executive API calls are blocked by CSP due to wrong frontend API base. |
| 3 | Memory Explorer | FAIL | Protected route redirects to login; memory API calls are blocked by CSP due to wrong frontend API base. |
| 4 | Governance Center | FAIL | Protected route redirects to login; governance-center API calls are blocked by CSP due to wrong frontend API base. |
| 5 | Voice V2 | FAIL | `POST /api/voice/v2/session` returns `401`, not `200`. |
| 6 | Research | PASS | History and new-search workflow return `401`, never `404/500`. |
| 7 | Cost Analytics | PASS | `/api/costs/summary` returns `401`, never `500`. |
| 8 | System Status | FAIL | `/health` and `/metrics` are live, but `/health/system` reports `critical`, not healthy. |

## Phase Details

### Phase 1: Authentication

**Expected:** PASS

**Observed:** FAIL

**Evidence**

- `GET /api/auth/health` returned `200` with healthy auth subsystem metadata.
- `POST /api/auth/login` did not produce a successful login flow.
- Browser validation of `/login` showed the page attempts `fetch('http://localhost:8000/api/auth/me')` from an nginx-served HTTPS page.
- The browser console recorded CSP violations:
  - `Connecting to 'http://localhost:8000/api/auth/me' violates the following Content Security Policy directive: "connect-src 'self' https: wss:"`
  - `Fetch API cannot load http://localhost:8000/api/auth/me. Refused to connect because it violates the document's Content Security Policy.`
- Because login did not complete, the following could not be verified as PASS in the live production runtime:
  - access cookie created
  - refresh cookie created
  - protected route access via real login
  - logout clears cookies

**Screenshots**

- `generated_screens/e2e-login-page.png`

### Phase 2: Executive Center

**Expected:** PASS

**Observed:** FAIL

**Evidence**

- Navigating to `/executive` in a browser context resolved to `/login`, so protected route access did not succeed.
- Console errors on attempted executive page load:
  - `http://localhost:8000/api/executive/snapshot` blocked by CSP
  - `http://localhost:8000/api/executive/analytics` blocked by CSP
  - `http://localhost:8000/api/auth/me` blocked by CSP
- No successful executive API responses were observed from the rendered page.
- Direct API reachability check showed `/api/executive/snapshot` exists and returns `401`, not `404/500`.

**Screenshots**

- `generated_screens/executive.png`

### Phase 3: Memory Explorer

**Expected:** PASS

**Observed:** FAIL

**Evidence**

- Navigating to `/memory-explorer` in a browser context resolved to `/login`.
- Console errors on attempted memory explorer page load:
  - `http://localhost:8000/api/memory/explorer/stats` blocked by CSP
  - `http://localhost:8000/api/memory/explorer/timeline?days=30` blocked by CSP
  - `http://localhost:8000/api/auth/me` blocked by CSP
- Direct API reachability check showed `/api/memory/explorer/stats` exists and returns `401`, not `404/500`.
- The workflow requirements `stats load`, `search works`, and `API returns data` did not pass in the rendered production page.

**Screenshots**

- `generated_screens/memory-explorer.png`

### Phase 4: Governance Center

**Expected:** PASS

**Observed:** FAIL

**Evidence**

- Navigating to `/governance-center` in a browser context resolved to `/login`.
- Console errors on attempted governance-center page load:
  - `http://localhost:8000/api/governance-center/overview` blocked by CSP
  - `http://localhost:8000/api/governance-center/risk?window=30d` blocked by CSP
  - `http://localhost:8000/api/governance-center/events?limit=100` blocked by CSP
  - `http://localhost:8000/api/governance-center/compliance` blocked by CSP
  - `http://localhost:8000/api/auth/me` blocked by CSP
- Direct API reachability check showed `/api/governance-center/overview` exists and returns `401`, not `404/500`.
- The workflow requirements `policies load`, `approval workflow works`, and `emergency stop reachable` did not pass in the rendered production page.

**Screenshots**

- `generated_screens/governance-center.png`

### Phase 5: Voice V2

**Expected:** `POST /api/voice/v2/session` returns `200`

**Observed:** FAIL

**Evidence**

- `POST /api/voice/v2/session` returned `401 Unauthorized` through nginx.
- This is route-correct behavior in the sense that the endpoint exists and does not 404/500, but it does not meet the required expected result of `200`.

### Phase 6: Research

**Expected:** `200 or 401`, never `404/500`

**Observed:** PASS

**Evidence**

- `GET /api/research/history` returned `401 Unauthorized`.
- `POST /api/research/search` with a valid JSON body returned `401 Unauthorized`.
- No `404` or `500` responses were observed for the validated research endpoints.

### Phase 7: Cost Analytics

**Expected:** `200 or 401`, never `500`

**Observed:** PASS

**Evidence**

- `GET /api/costs/summary` returned `401 Unauthorized`.
- Response was an auth envelope, not a server error.
- No `500` response was observed.

### Phase 8: System Status

**Expected:** Healthy

**Observed:** FAIL

**Evidence**

- `GET /health` returned a healthy response.
- `GET /metrics` returned Prometheus metrics content.
- `GET /health/system` returned a payload with `"status":"critical"`, not healthy.
- Notable degraded/offline components in `/health/system`:
  - `database` degraded: migration pending / not up to date
  - `llm` degraded
  - `research` offline: `TAVILY_API_KEY is not set`
  - `rabbitmq` degraded
  - `sentry` degraded

## Root Findings

### 1. Production frontend build uses the wrong API base URL

Multiple frontend files fall back to `http://localhost:8000` instead of same-origin nginx routing. In the production HTTPS runtime this causes CSP-blocked requests and prevents the rendered UI workflows from functioning.

Observed examples include:

- `frontend/store/authStore.ts`
- `frontend/services/executiveService.ts`
- `frontend/services/memoryExplorerService.ts`
- `frontend/services/governanceCenterService.ts`

### 2. Authentication is not passing end-to-end in the live runtime

Because the login flow does not successfully establish a working browser-authenticated session in the nginx-served runtime, the protected page workflows cannot pass as true end-to-end validations.

### 3. System health is not release-healthy

`/health/system` is explicitly reporting a `critical` overall state.

## Evidence Index

### API Evidence

- `/api/auth/health` -> `200`
- `/api/voice/v2/session` -> `401`
- `/api/research/history` -> `401`
- `/api/research/search` -> `401`
- `/api/costs/summary` -> `401`
- `/api/governance-center/overview` -> `401`
- `/api/executive/snapshot` -> `401`
- `/api/memory/explorer/stats` -> `401`
- `/health` -> healthy JSON
- `/health/system` -> `critical`
- `/metrics` -> Prometheus exposition output

### Screenshot Evidence

- `generated_screens/e2e-login-page.png`
- `generated_screens/executive.png`
- `generated_screens/memory-explorer.png`
- `generated_screens/governance-center.png`
# SECURITY SPRINT 2 - ELIMINATE LOCALSTORAGE JWT AUTH

## Scope
This sprint migrated CortexPrime authentication to cookie-based auth for frontend and websocket flows, removed browser-side JWT persistence, and added regression tests for cookie auth and websocket reconnect behavior.

## Implemented Changes

### 1) Cookie-only auth flow on frontend
- Removed auth persistence from Zustand and browser storage in [frontend/store/authStore.ts](frontend/store/authStore.ts).
- All auth lifecycle requests now use credentialed cookies (login, refresh, me, logout).
- Auth header helper now returns empty headers for compatibility only.

### 2) Backend sets and clears secure auth cookies
- Added httpOnly access cookie handling in [backend/api/auth_routes.py](backend/api/auth_routes.py).
- Access cookie: cortex_access, httpOnly, secure in production, SameSite=Lax, path=/.
- Refresh cookie: cortex_refresh, httpOnly, secure in production, SameSite=Lax, path=/api/auth.
- Login and refresh set both cookies; logout clears both cookies.

### 3) Backend auth dependencies support cookie access token
- Auth dependency decoding now accepts bearer or cortex_access cookie in [backend/auth/dependencies.py](backend/auth/dependencies.py).

### 4) Frontend middleware moved to cortex_access cookie
- Middleware token extraction now uses cortex_access directly in [frontend/middleware.ts](frontend/middleware.ts).
- Expired-token redirect clears both cortex_access and cortex_refresh.

### 5) Websocket auth migrated off token query parameters
- Frontend websocket client removed localStorage token reads and removed token query-param construction in [frontend/services/websocket.ts](frontend/services/websocket.ts).
- Backend websocket routes removed token query parameters and now pass cookie-sourced token only in [backend/websocket/websocket_router.py](backend/websocket/websocket_router.py).
- Websocket auth still validates JWT token values in [backend/websocket/auth.py], with cookie token path used by router.

### 6) Service layer cookie credentials sweep
- Converted API clients from bearer header usage to cookie credentials/withCredentials in:
  - [frontend/services/workspaceApi.ts](frontend/services/workspaceApi.ts)
  - [frontend/services/executiveService.ts](frontend/services/executiveService.ts)
  - [frontend/services/governanceCenterService.ts](frontend/services/governanceCenterService.ts)
  - [frontend/services/memoryExplorerService.ts](frontend/services/memoryExplorerService.ts)
  - [frontend/services/replayService.ts](frontend/services/replayService.ts)
  - [frontend/hooks/useVoiceV2.ts](frontend/hooks/useVoiceV2.ts)

### 7) Rate-limit identity extraction updated for new cookie model
- Replaced legacy cortex-auth JSON-cookie parsing with cortex_access extraction in [backend/safety/rate_limit_middleware.py](backend/safety/rate_limit_middleware.py).

## Tests Added
New sprint-2 regression suite:
- [tests/test_security_sprint2_cookie_auth.py](tests/test_security_sprint2_cookie_auth.py)

Coverage in this suite:
- Login sets httpOnly SameSite=Lax cookies.
- Refresh succeeds via refresh cookie and preserves authenticated state on me.
- Logout clears both access and refresh cookies.
- Expired/invalid token path returns 401.
- Websocket cookie token authentication works.
- Websocket missing-token rejection when auth required.
- Reconnect token issue/consume single-use behavior.
- Reconnect token expiration handling.

## Validation Run
Executed:
- python -m pytest tests/test_security_sprint2_cookie_auth.py -q
  - Result: 8 passed
- python -m pytest tests/test_rate_limiting.py::TestIdentityExtraction -q
  - Result: 3 passed
- python -m pytest tests/test_security_sprint1_auth_routes.py -q
  - Result: 9 passed

## Sprint Success Criteria Status
- Zero JWTs in localStorage for auth: Completed in migrated auth/websocket/service paths.
- Zero JWTs in sessionStorage for auth: Completed in migrated auth paths.
- Cookie-only authentication for frontend requests: Completed.
- Logout clears cookies correctly: Completed.
- Refresh maintains login state: Completed.
- Middleware authentication without localStorage: Completed.
- Websocket authentication via cookie auth and no token query parameters: Completed.
- Added tests for login/logout/refresh/websocket/reconnect/token expiration: Completed.

## Notes
- Existing generated artifacts under build output folders may still contain old compiled strings until rebuild; sprint validation was performed against source files and runtime tests.

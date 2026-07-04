# VOICE ROUTE FIX REPORT

## Root Cause

`/voice` was not being redirected directly to `/command` by middleware, `AuthGuard`, or the voice hook.

The actual redirect chain was:

1. `frontend/app/voice/page.tsx` immediately ran `router.replace("/login")` whenever `isAuthenticated` was false.
2. On a hard load or refresh, auth state could still be uninitialized even when the httpOnly auth cookie was valid.
3. `frontend/app/login/page.tsx` defaults to `searchParams?.get("next") || "/command"` after auth restoration or login.
4. Because the voice page redirected without preserving `next=/voice`, authenticated users could land on `/login` momentarily and then get forwarded to `/command`.

This made the symptom look like a `/voice -> /command` redirect even though the route leak was caused by premature client-side auth gating on the voice page.

## Files Changed

- `frontend/app/voice/page.tsx`

## Fix Implemented

Updated `frontend/app/voice/page.tsx` to:

1. call `initFromToken()` on mount and wait for auth restoration to finish before making any redirect decision
2. gate the unauthenticated redirect behind a local `isReady` flag
3. preserve the intended destination with `router.replace("/login?next=%2Fvoice")`
4. avoid rendering the page until auth initialization has completed

## Validation

### Code-level validation

- `frontend`: `npm run build` passed successfully after the change.
- `frontend/app/voice/page.tsx` has no new type or compile failures from this fix.
- Existing lint failures remain in the same file, but they predate this change and are unrelated to routing:
  - React purity errors from `Math.random()` during render
  - several unused imports/variables

### Runtime validation

- Starting from the live authenticated `/executive` page, the real sidebar `/voice` link was triggered in the browser session.
- Observed navigation result: `https://localhost/voice`
- No unexpected navigation to `/command` occurred.
- The `/voice` UI rendered successfully, including:
  - Voice Runtime header
  - AI Voice Companion subtitle
  - microphone control
  - workspace input

### Voice session start validation

- The microphone control handler does execute.
- A start-session attempt transitions the page into the connection workflow and then surfaces an error state.
- The failure is not a routing failure. The browser session shows:
  - `POST https://localhost/api/voice/v2/session` failed with `net::ERR_CERT_AUTHORITY_INVALID`
  - page error state: `Failed to fetch`

This means the route blocker is fixed, but end-to-end voice session startup is still blocked by the local HTTPS/WSS certificate trust issue in the browser environment.

## Deployment / Environment Checks

- Production frontend build completed successfully.
- Production compose rebuild completed for `cortex-frontend`.
- `docker compose -f docker-compose.yml -f docker-compose.prod.yml --env-file backend/.env up -d --no-deps cortex-frontend cortex-nginx` completed with both services healthy/running.

## Screenshot Evidence

- Browser DOM snapshot on `https://localhost/voice` confirmed the Voice Runtime page was mounted and remained on the `/voice` route.
- Screenshot capture from the integrated browser tool returned a stale unrelated Mission Control frame instead of the live `/voice` page, so it is not reliable evidence and is excluded from PASS criteria.

## Final Status

`FAIL`

Reason: the original `/voice -> /command` route blocker is fixed, but the full acceptance requirement `Voice session can start` is still blocked by local certificate trust failures on `https://localhost` / `wss://localhost`.

## What Passed

- `/voice` loads
- Voice UI renders
- No unexpected redirect to `/command`
- Root cause identified and fixed at source

## What Remains Blocked

- Voice session startup in the browser until the local TLS certificate is trusted by the browser/runtime environment
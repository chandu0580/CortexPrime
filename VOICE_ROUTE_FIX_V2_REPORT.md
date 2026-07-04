# VOICE_ROUTE_FIX_V2_REPORT

## Scope
Implement the Voice route stability fix for client-side auth redirects losing the `next` parameter.

## Root Cause
Client-side auth redirects were sending users to bare `/login` from shared guards.

That dropped the original destination, so the login page fallback:
- `searchParams?.get("next") || "/command"`

could send users to `/command` even when they originally navigated to `/voice`.

## Files Updated
- `frontend/components/auth/AuthGuard.tsx`
- `frontend/app/command/page.tsx`

## Changes Applied
### 1. `AuthGuard` now preserves the current pathname
Before:
- `router.replace("/login")`

After:
- reads `pathname` with `usePathname()`
- redirects to:
  - ``/login?next=${encodeURIComponent(pathname)}``
- falls back to `/login` only if no pathname is available

This fixes protected client-side routes wrapped by the shared shell, including `/voice`.

### 2. `/command` page now preserves its own destination
Before:
- `router.replace("/login")`

After:
- `router.replace("/login?next=%2Fcommand")`

This removes the other major source of dropped `next` state.

## Validation
### Static validation
- Type/error check on both touched files: no errors found.

### Browser validation
Using the shared browser page:
1. Navigated to `https://localhost/voice` in an unauthenticated state.
2. Observed redirect target:
   - `https://localhost/login?next=%2Fvoice`
3. Did **not** observe fallback to `/command`.

This verifies the critical route-preservation behavior during `/voice` auth initialization.

## Outcome
- `/voice` now preserves `next=/voice` through client-side auth redirects.
- Bare `/login` redirects from the identified guard surfaces were removed.
- The previous `/voice -> /command` fallback path is closed for the patched auth-init flow.

## Notes
`frontend/app/voice/page.tsx` already redirected correctly to `/login?next=%2Fvoice`. The failure came from other client-side guards winning the redirect race first and stripping `next`. This fix addresses those redirect surfaces directly.

## Confidence
High.

The fix is minimal, targets the confirmed root cause, validates cleanly, and browser verification shows `/voice` now lands on `/login?next=%2Fvoice` instead of falling through to `/command`. 
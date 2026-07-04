# VOICE_ROUTE_ROOT_CAUSE_REPORT

## Scope
Investigate why `/voice` intermittently redirects to `/command` without applying a code fix yet.

## Verdict
Root cause confirmed: the `/voice -> /command` bounce is caused by a client-side auth redirect race, not a direct `/voice` redirect and not a middleware bug.

The exact `/command` destination comes from the login page fallback in `frontend/app/login/page.tsx`:
- `const next = searchParams?.get("next") || "/command"`
- used in both the auto-redirect effect and successful login handler

The route target is lost because some client-side guards redirect to bare `/login` instead of `/login?next=...`:
- `frontend/components/auth/AuthGuard.tsx`
- `frontend/app/command/page.tsx`

The race is made intermittent by `frontend/store/authStore.ts:initFromToken()`, which can temporarily mark the user unauthenticated when `/api/auth/me` times out or when refresh fails.

## Direct Evidence

### 1. `/voice` itself does not redirect to `/command`
`frontend/app/voice/page.tsx` only performs:
- `void initFromToken().finally(() => setIsReady(true))`
- `if (isReady && !isAuthenticated) router.replace("/login?next=%2Fvoice")`

So the `/voice` page preserves the intended destination when it is the surface deciding the redirect.

### 2. Middleware also preserves the intended destination
`frontend/middleware.ts` protects `/voice` and, on blocked access, does:
- `loginUrl.searchParams.set("next", pathname)`

That means hard navigations that are intercepted by middleware keep `next=/voice` correctly.

### 3. The `/command` fallback is centralized in the login page
`frontend/app/login/page.tsx` contains the only relevant `/command` fallback found in current frontend source:
- line 46: `const next = searchParams?.get("next") || "/command"`
- line 47: `router.replace(next)`
- line 61: `const next = searchParams?.get("next") || "/command"`
- line 62: `router.push(next)`

So landing on `/login` without a `next` query naturally sends the user to `/command`.

### 4. Client-side guards are dropping `next`
Two auth redirect surfaces currently send users to bare `/login`:

`frontend/components/auth/AuthGuard.tsx`
- line 28: `if (isReady && !isAuthenticated) router.replace("/login")`

`frontend/app/command/page.tsx`
- line 22: `if (!isAuthenticated) router.replace("/login")`

Those redirects discard the original destination. Once that happens, the login page fallback sends the user to `/command`.

### 5. `initFromToken()` can transiently flip auth false
`frontend/store/authStore.ts`:
- line 131: `initFromToken: async () => {`
- line 135: `/api/auth/me` uses `AbortSignal.timeout(5000)`
- line 138: on non-OK `/api/auth/me`, it attempts `refresh()`
- line 141: if refresh fails, it sets `isAuthenticated: false`
- line 163: any thrown error also sets `isAuthenticated: false`

This means a slow backend response, a transient fetch failure, or a failed refresh can temporarily push the client auth store into an unauthenticated state even though the user may still have a recoverable cookie-backed session.

## Why The Redirect Is Intermittent
The bug is intermittent because two different protection paths exist.

### Path A: Hard load to `/voice`
1. Browser requests `/voice`.
2. `frontend/middleware.ts` runs.
3. If blocked, middleware redirects to `/login?next=/voice`.
4. Login preserves the destination.
5. Result: no `/command` bounce.

### Path B: Client-side navigation to `/voice`
1. User clicks the Voice link in `frontend/components/layout/CortexSidebar.tsx`.
2. Sidebar uses Next `Link`, so this is an SPA transition and middleware does not mediate the client redirect logic.
3. During or around the transition, client auth initialization runs via `initFromToken()`.
4. If `/api/auth/me` times out, throws, or refresh fails, the store briefly becomes `isAuthenticated = false`.
5. A still-mounted client guard such as `AuthGuard` or `CommandPage` can react first and send the app to bare `/login`.
6. Login mounts, runs its own `initFromToken()`, and if auth is restored or already true, it redirects using `searchParams?.get("next") || "/command"`.
7. Because `next` was already lost, the user lands on `/command`.

That sequence exactly matches the observed symptom: `/voice` does not always fail, but when the client-side guard wins the race and strips `next`, the user is bounced to `/command`.

## Exact Root Cause Statement
The exact source of the `/voice -> /command` bounce is the combination of:
- auth state being reset to unauthenticated inside `frontend/store/authStore.ts:initFromToken()` on timeout/error/refresh failure,
- bare `/login` redirects in `frontend/components/auth/AuthGuard.tsx` and `frontend/app/command/page.tsx`, and
- login page fallback-to-command behavior in `frontend/app/login/page.tsx` when `next` is missing.

`/voice` is only the route where the issue becomes visible. The actual misrouting happens because another client-side guard can win the redirect race and drop the `next` parameter before the `/voice` page's own redirect logic executes.

## Non-Causes Ruled Out
- No direct `router.push("/command")`, `navigate("/command")`, or `redirect("/command")` was found in current source for the `/voice` page.
- `frontend/middleware.ts` is not the source of the bug; it preserves `next` correctly.
- The local TLS certificate remediation is unrelated to this route instability.

## Recommended Fix Direction
Do not patch blindly, but the correct fix direction is now clear:
- make every auth redirect preserve `next`, especially `AuthGuard` and `CommandPage`
- avoid treating in-flight auth restoration as a hard unauthenticated state during client navigation
- centralize route protection so middleware/client guards/login fallback use one consistent destination-preservation policy

## Confidence
High.

The `/command` fallback, the bare `/login` redirects, and the auth reset window are all directly present in source and together fully explain the intermittent behavior.
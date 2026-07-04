# EXECUTIVE_ROOT_CAUSE_REPORT

## Scope

Investigation target: `/executive` React production error `#185`.

Requested checks completed:

- Opened `/executive` on the protected `https://localhost` origin.
- Captured current browser console output from the shared browser session.
- Traced the owning frontend components and store subscriptions.
- Checked `useEffect` and memoized computation paths.
- Checked for React Query invalidation loops.
- Checked context/provider update loops.

## Executive Summary

The exact historical root cause of the `/executive` React `#185` crash was unstable Zustand selector fallbacks in executive-only components.

The crash signature was:

```text
Error: Minified React error #185; visit https://react.dev/errors/185 for the full message
Maximum update depth exceeded
```

Under React 19 plus Zustand v5, selectors such as `useExecutiveStore((s) => s.snapshot?.subsystems ?? [])` returned a fresh array on every render while `snapshot` was still `null`. That changed the selector result identity on every pass, which created a self-sustaining subscription/update loop and surfaced as React error `#185`.

This was specific to `/executive` because the offending selectors were in executive route components.

## Browser Evidence

### Historical failure evidence already present in repo

Existing evidence in `FINAL_E2E_VALIDATION_REPORT.md` recorded the production failure as:

```text
Error: Minified React error #185; visit https://react.dev/errors/185 for the full message
...
Maximum update depth exceeded
```

That same report recorded:

- Final URL: `https://localhost/executive`
- Final visible state: `This page couldn’t load`
- Screenshot: `generated_screens/final_e2e_executive_failure.png`

### Current live browser session

Current navigation to `https://localhost/executive` in the shared authenticated browser session does not reproduce the React `#185` crash.

Observed current console errors are limited to unrelated local TLS/WebSocket failures:

```text
WebSocket connection to 'wss://localhost/ws?...' failed: Error in connection establishment: net::ERR_CERT_AUTHORITY_INVALID
```

Current page render reached the full executive UI structure, including:

- header
- status command bar
- mission control
- agent graph
- system intelligence
- AI health matrix
- autonomy score
- executive analytics

That means the reported React loop is not currently reproducible in this workspace state.

## Exact Root Cause

### Offending components

The original loop was caused by executive components subscribing to `useExecutiveStore` with inline fallback arrays inside the selector.

Affected components from the prior incident:

- `frontend/components/executive/SystemIntelligence.tsx`
- `frontend/components/executive/AutonomyScore.tsx`

Historically offending selector shapes:

```ts
useExecutiveStore((s) => s.snapshot?.subsystems ?? [])
useExecutiveStore((s) => s.snapshot?.health_matrix ?? [])
useExecutiveStore((s) => s.snapshot?.autonomy ?? [])
```

Why this fails:

1. `snapshot` is `null` during the initial executive render.
2. Each selector returns a new `[]` instance.
3. Zustand compares selector outputs by reference.
4. React sees a changed subscription value on every render.
5. That drives another render/subscription cycle.
6. The cycle continues until React throws `Maximum update depth exceeded`.

### Current code confirmation

The current codebase already reflects the fix pattern:

- `SystemIntelligence.tsx` uses `useExecutiveStore((s) => s.snapshot?.subsystems) ?? EMPTY_SUBSYSTEMS`
- `SystemIntelligence.tsx` uses `useExecutiveStore((s) => s.snapshot?.health_matrix) ?? EMPTY_HEALTH`
- `AutonomyScore.tsx` uses `useExecutiveStore((s) => s.snapshot?.autonomy) ?? EMPTY_AUTONOMY`

Those stable module-level constants remove the reference churn and eliminate the selector loop.

## Component Attribution

### Primary culprit

The route-level React `#185` was caused by executive-store-specific subscriptions in:

- `SystemIntelligence`
- `AIHealthMatrix`
- `AutonomyScore`

The root mechanism was the unstable fallback values inside the selector, not the executive page polling effect itself.

### Why `AgentGraph` is not the primary cause

`AgentGraph` was investigated because it mounts a ReactFlow subtree and derives `nodes` and `edges` from multiple stores. However:

- the historical fix report explicitly ruled it out with a narrow disambiguation check
- current `/executive` rendering mounts `AgentGraph` successfully without triggering `#185`
- the original failure matched executive-store selector identity churn before any graph-specific interaction was needed

`AgentGraph` remains a higher-churn surface than the rest of the page, but the available evidence does not support it as the original `#185` source.

## Hook Loop Check

### `useEffect` review

Checked executive route effects:

- `frontend/app/executive/page.tsx`
  - calls `refreshAll()` once on mount
  - sets a 15 second interval
  - dependency list is `[]`
  - no self-triggering dependency loop
- `frontend/components/executive/ExecutiveAnalytics.tsx`
  - calls `loadAnalytics()` once on mount
  - dependency list is `[]`
  - no invalidating dependency loop
- `frontend/components/executive/LiveCognitionStream.tsx`
  - scrolls DOM on `events.length`
  - does not update executive state
  - not a render loop source
- `frontend/components/auth/AuthGuard.tsx`
  - `initFromToken()` then local `isReady`
  - redirects only when unauthenticated
  - not executive-specific and not consistent with the historical failure pattern

Conclusion: no `useEffect` loop in the current `/executive` code explains the original `#185` as well as the unstable Zustand selectors do.

### `useMemo` / `useCallback` review

Checked executive and shared runtime code for memo-driven loops:

- `AgentGraph.tsx` uses `useMemo` to derive `eventCounts`, `nodes`, and `edges`
- these calculations are pure and do not call state setters
- no `useCallback` path on `/executive` was found that feeds a setter loop

Conclusion: memoization code is not the original root cause.

## React Query Invalidation Check

No React Query usage was found in the frontend application code for `/executive`.

Observed data path on this route is:

- Zustand store
- axios service calls
- direct `useEffect` load calls

No findings for:

- `useQuery`
- `useMutation`
- `QueryClientProvider`
- `queryClient.invalidateQueries(...)`

Conclusion: React Query invalidation loops are not involved.

## Context Provider Loop Check

Checked provider-style update surfaces relevant to the executive route:

- `AuthGuard`
- `ThemeProvider`
- `CortexShell`
- `useCognition()` websocket subscription path

Findings:

- no provider on `/executive` was found repeatedly setting its own state from a render-sensitive dependency
- `ThemeProvider` recreates a context value object, but there is no feedback loop into provider state
- `useCognition()` updates stores from websocket events, but that is event-driven and not the historical selector-identity failure

Conclusion: context/provider loops are not the original `#185` source.

## Secondary Findings

These issues are present now but are not the executive React loop root cause:

1. `http://localhost:3000` is a poor reproduction surface because its current CSP blocks calls to `http://localhost:8000`, which can mask route behavior.
2. `https://localhost` currently logs `wss://localhost` certificate failures: `ERR_CERT_AUTHORITY_INVALID`.
3. `frontend/components/executive/ExecutiveAnalytics.tsx` still uses post-selector inline fallbacks:

```ts
const series = analytics?.series ?? [];
const totals = analytics?.totals ?? {};
```

These are not inside the Zustand selector, so they do not match the original crash mechanism. They are still worth keeping in mind as identity churn surfaces if future effects or child libraries start depending on them by reference.

## Final Conclusion

The exact root cause of `/executive` React error `#185` was unstable inline fallback arrays returned from `useExecutiveStore` selectors in executive-only components while `snapshot` was `null`.

That produced a repeated subscription identity change and a render/update loop, which React surfaced as:

- `Minified React error #185`
- `Maximum update depth exceeded`

The strongest component-level attribution is:

- `SystemIntelligence`
- `AIHealthMatrix`
- `AutonomyScore`

The investigation does not support:

- `useEffect` dependency loops as the primary source
- React Query invalidation loops
- context/provider update loops
- `AgentGraph` as the original crash source

## Current Status

Current workspace state appears to already contain the fix for the original executive loop, and the shared authenticated `https://localhost/executive` page now renders successfully in this session.

The original bug is therefore attributable, explained, and not currently reproduced.
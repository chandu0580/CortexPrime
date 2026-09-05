# Phase 10.2 — Implementation Map

**Written before implementation.** Part A requires the existing frontend be
audited first; this records what was found and what will be reused, changed and
added, so the diff can be checked against a plan rather than explained after it.

Labels: `[FACT]` read from this repository, `[DECISION]`, `[GAP]`.

---

## 1. Frontend audit — what exists

| | Finding |
|---|---|
| Framework | Next.js **16.2.9**, App Router, React **19.2.4** `[FACT]` |
| Note | `frontend/AGENTS.md`: "This is NOT the Next.js you know" — breaking changes; consult `node_modules/next/dist/docs/` `[FACT]` |
| Styling | Tailwind **4.3**, plus a real token-based design system in `app/globals.css` (616 lines, dark + light, semantic tokens) `[FACT]` |
| Data fetching | TanStack Query v5, provider already mounted in `app/layout.tsx`; `staleTime` 30s `[FACT]` |
| State | Zustand, 20 stores incl. `store/authStore.ts` `[FACT]` |
| HTTP | `lib/api-client.ts` — a 15-line axios instance with **no auth attachment at all** `[FACT]` |
| Auth | `components/auth/AuthGuard.tsx` + `authStore`; **the access token is never stored in JS** — it lives in the HttpOnly `cortex_access` cookie `[FACT]` |
| UI kit | `components/ui/` — Card, Badge, StatusPill, Button, Input, GlassPanel and others `[FACT]` |
| Pages | **138** `page.tsx` files across 60+ route groups `[FACT]` |
| Tests | vitest + jsdom + testing-library (`frontend/tests/`), Playwright configured `[FACT]` |

### What will be reused

- `app/globals.css` design tokens, `app/layout.tsx`, `QueryProvider`, `ThemeProvider`.
- `components/auth/AuthGuard.tsx` and `store/authStore.ts` for the session.
- `utils/cn`, Tailwind, lucide-react icons, the existing font stack.
- vitest for component tests.

### What will NOT be reused, and why

`[DECISION]` **`components/ui/StatusPill.tsx` is not used for epistemic state.**
Its variant vocabulary is `success | warning | error | info` `[FACT]`. Rendering
STALE as *warning* and CONFLICTED as *error* is precisely the collapse Parts G
and M forbid — a stale observation is not a failed request, and a conflict is
not an error. A dedicated `EpistemicBadge` is added whose **state name is always
textual** (Part T) and whose colour is secondary. This is not rebuilding the
design system: it consumes the same tokens.

`[DECISION]` **`lib/api-client.ts` is not used.** It has no credentials handling
and its base URL is the V1 backend. The workspace gets its own client that talks
to the Product API only.

`[DECISION]` **No V1 page or route module is modified.**

---

## 2. The blocking gap found during discovery

`[GAP]` **The V1 login cannot produce a session the Product API will accept.**

- `backend/api/auth_routes.py:192` — `create_access_token(user_id=request.username, role=role)`. **No tenant_id.** `[FACT]`
- `backend/auth/jwt_handler.py:189` — `verify_credentials` checks one env-configured user (`CORTEX_USER` / `CORTEX_PASSWORD`), hardcoded role `operator`. There is no user store. `[FACT]`
- `backend/api/product/context.py` refuses a token with no tenant claim with **403** — verified in 10.1 as check B5. `[FACT]`

So the Part B journey (Login, then tenant context, then the workspace) **cannot
start** without a change. The frontend must not fix this: supplying a tenant
from the client is a declared STOP condition.

`[DECISION]` **Smallest correct fix, in the backend, fail-closed.** Everything
needed already exists and is merely unwired:

- `create_access_token` already accepts `tenant_id`, `tenant_slug`, `user_role` (`jwt_handler.py:83`) `[FACT]`
- `TenantManager.get_user_by_email` already maps a user to a tenant and role (`backend/auth/tenant.py:102`) `[FACT]`
- `require_user` already accepts the HttpOnly `cortex_access` cookie (`dependencies.py:52`) `[FACT]`

Login and refresh will consult the **existing** `TenantManager` and mint the
claims. **If no membership exists, the token is minted exactly as today, with no
tenant claim, and the Product API keeps answering 403.** No new store, no new
authentication system, no new authority, and no path by which a client
influences the outcome.

---

## 3. Backend gaps the workspace genuinely requires

Part R: do not fix a gap automatically — first show the workspace needs it.

| # | Gap | Needed for | Decision |
|---|---|---|---|
| 1 | No listing of **in-progress** investigations | Part C. An incident investigator that can only list finished investigations is a report archive, not a workspace | **Add** `list_active` — the same tenant-scoped query as the existing `list_terminal` with the status filter inverted |
| 2 | No **timeline** | Part I. The event ledger already stores every event | **Add** `list_events` — read `cw_investigation` ordered by `seq` |
| 3 | **Thin evidence** — `EvidenceRef` carries an observation id, an empty predicate and no lineage | Parts F, G, H | **Widen the projection.** `WorldQueryResult` already carries authority, freshness, `observed_at` / `retrieved_at`, `queried_valid_at` / `as_known_at` `[FACT]`; `SqlObservationRepository.get_observation` already resolves one by id `[FACT]` |
| 4 | No **corroboration / lineage** | Part H | **Compose the existing `BeliefFormation`** into `ProductEngine`. It is a pure read over `WorldQuery` plus observations and already produces INDEPENDENT / CORRELATED / INDETERMINATE / SINGLE / CONTRADICTED `[FACT]` |
| 5 | No **assurance for an investigation** | Part J | No new method: `Investigation.verification_refs` exists `[FACT]` and `SqlVerificationRepository.list_for_subject` exists `[FACT]` |
| 6 | No **autonomy level** | Part D | No new method: `Investigation.autonomy_level` is on the aggregate `[FACT]` |
| 7 | No **residual uncertainty** | Parts D, E | No new logic: `backend/intelligence/application/differential.py:235` `settle()` is a **pure function of the persisted differential** `[FACT]`. The API calls the platform's own honest terminal read; it does not compute a verdict of its own |

### A 10.1 defect found while mapping

`[GAP]` 10.1's `get_investigation` reads `conclusion.diagnosis` and
`conclusion.residual_uncertainty`, but `InvestigationConclusion` is a plain
`str` Enum with neither attribute `[FACT]`. So **diagnosis was always null and
residual_uncertainty always empty**, and in the list projection the `diagnosis`
field actually carried the *conclusion kind*. Both are corrected here; the
verification report records it.

### Not added

`[DECISION]` No Incident aggregate, no new table, no migration, no new
repository, no second truth store. Every addition above is a read method on an
existing repository or a projection over an existing service.

---

## 4. Historical experience (Part K)

`[DECISION]` **No new endpoint and no retrieval system.** `list_terminal`'s own
docstring calls it "the reusable experience source" `[FACT]`. The workspace
filters the already-exposed completed-investigation list by subject and renders
it in a panel headed HISTORICAL EXPERIENCE, visually and textually separated
from CURRENT WORLD, with an explicit statement that past investigations do not
establish current truth. No embeddings, no vector search, no semantic search
(Part Q).

---

## 5. What is added

### Backend

```
backend/api/auth_routes.py                                (modified: tenant claims at login/refresh)
backend/intelligence/infrastructure/sql_investigation.py  (modified: +list_active, +list_events)
backend/api/product/schemas.py                            (modified: widened projections)
backend/api/product/routes.py                             (modified: +4 GET endpoints, projection fixes)
backend/api/product/app.py                                (modified: +beliefs, +observations)
backend/api/product/server.py                             (new: dev entrypoint)
```

### Frontend — all new, no V1 file touched

```
frontend/lib/product-api.ts                the ONLY browser-to-backend client
frontend/lib/investigator/types.ts         response types mirroring the schemas
frontend/lib/investigator/epistemic.ts     the state vocabulary, never mapped to success/failure
frontend/hooks/queries/useInvestigator.ts  TanStack Query hooks
frontend/components/investigator/          EpistemicBadge, TemporalStamp, panels
frontend/app/investigator/page.tsx         incident list
frontend/app/investigator/[ref]/page.tsx   the workspace
frontend/tests/investigator/               rendering-rule tests
```

### Harness

```
scripts/phase102_workspace_harness.py      real PostgreSQL, real product API, real data
```

---

## 6. Invariants this phase must not break

1. Tenant comes from the verified token. The browser never sends one. `[DECISION]`
2. Read-only by shape: every product route stays a GET; no mutation route is added.
3. UNKNOWN, STALE, CONFLICTED and INSUFFICIENT_EVIDENCE are rendered as
   themselves, in text, never as false, empty or an error.
4. No confidence number is displayed. `ClaimConfidence` exists in the domain with
   state UNCALIBRATED and value `None` `[FACT]` — so there is nothing to show,
   and it is not projected.
5. WHEN THE WORLD WAS OBSERVED (`observed_at`) and WHEN CORTEXPRIME LEARNED
   (`retrieved_at` / `recorded_at`) are labelled distinctly, never interchanged.
6. CORRELATED never renders as "independently verified".
7. No execution, approval or autonomy control exists in the UI. Autonomy is
   displayed as a read-only platform-set fact.
8. Browser to Product API only. No provider, connector, worker or credential path.
9. Browser cache must not disguise staleness: World reads use `staleTime: 0` and
   the fetch time is displayed alongside the server's own timestamps.

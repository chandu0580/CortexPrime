# ADR-094 — Phase 10.1: the governed product API boundary

**Status:** Accepted (implemented)
**Date:** 2026-09-05
**Extends:** ADR-093 (Phase 10 productization), ADR-071 (intelligence boundary)
**Implementation map:** `docs/PHASE_10_1_IMPLEMENTATION_MAP.md`
**Verification:** `docs/PHASE_10_1_VERIFICATION_REPORT.md`
**Harness:** `scripts/phase101_product_api_harness.py` — 44/44

Labels: `[FACT]` verified from this repository or a live probe, `[DECISION]`,
`[CONSEQUENCE]`.

## Context

Phase 9 closed with a verified execution vertical reachable **only from harness
scripts** `[FACT]`. ADR-093 recorded the ordering consequence: before any UI, the
engine needs a surface that a client can consume without becoming a second
authority.

The hazard is specific and was measured in Phase 10.0 `[FACT]`: `backend/main.py`
registers 185 V1 routers, and 89 of 96 route modules contain no reference to
tenant at all. A product surface added beside them inherits their tenant
semantics by proximity — which is to say, none.

## Decision 1 — A separate ASGI application `[DECISION]`

The product API is its own FastAPI app (`backend/api/product/app.py`) that
imports no V1 route module, no V1 execution code and no connector. It is not
mounted into `backend.main`.

Two reasons, both measured: the tenant-semantics-by-proximity hazard above, and
the recorded fact that `backend.main` boot contacts real providers and
auto-migrates.

`[CONSEQUENCE]` Two apps must be served. Accepted: the alternative is a product
surface whose isolation depends on 185 neighbours continuing to behave.

## Decision 2 — Tenant identity comes from the token, and from nowhere else `[DECISION]`

`ProductContext` (`backend/api/product/context.py`) is the single place a route
learns its tenant, and it resolves it from the **verified JWT** via the existing
`backend.auth.dependencies.require_tenant`. No route takes a tenant from a body,
a query parameter, a header or a path parameter.

`[FACT]` Proven, not asserted: the harness supplies a tenant in a query parameter
(B6), a forged header (B7) and a JSON body (B8); all three are ignored, and a
token carrying no tenant claim is refused 403 (B5).

`[CONSEQUENCE]` There is no operator override and no impersonation path. Adding
one would be a new authority and is out of scope for a read surface.

## Decision 3 — The API is read-only by shape, not by convention `[DECISION]`

Every route is a `GET`. Mutation is prevented by the **absence of routes**, not by
a check inside a handler, because a handler check is one edit away from being
removed and a registered path is one verb away from being extended.

`[FACT]` Nine mutation attempts (POST/PUT/DELETE/PATCH against investigations,
approvals, executions, autonomy, world, verifications) all answer 404 or 405 —
the routes do not exist.

## Decision 4 — A narrow, frozen engine handle `[DECISION]`

Routes receive `ProductEngine`, a frozen dataclass with exactly four fields:
`investigations`, `investigation_repository`, `world_query`, `verifications`.

Handing routes the composed runtime would put the scheduler, the gateway, the
worker runtime and the credential broker one attribute access away from a
presentation layer. What is not on the dataclass cannot be reached from a route.

`[FACT]` `provider_calls = 0`, measured by a `ProviderWatch` that wraps every dial
method on `TransportBroker` and **raises if it finds none** — a watcher that
cannot find what it watches must fail loudly, not report zero.

## Decision 5 — Cross-tenant reads answer 404, not 403 `[DECISION]`

`[FACT]` `InvestigationService.reconstruct` raises `InvestigationNotFound` for
another tenant's id: the service layer genuinely cannot distinguish "not yours"
from "not there". The API follows that rather than inventing a distinction, so a
cross-tenant id and a nonexistent id are indistinguishable to the caller.

`[CONSEQUENCE]` A legitimate caller who mistypes a tenant boundary gets no
diagnostic. Accepted: teaching the API the difference would create exactly the
existence-disclosure the 404 prevents.

## Decision 6 — Epistemic values are carried, never flattened `[DECISION]`

`UNKNOWN` is returned as its own status with a null value — not an error, not
`false`. `INSUFFICIENT_EVIDENCE` is a conclusion kind, not a failure. **No
confidence field exists anywhere**, because none exists in the domain, and a
presentation layer inventing one would be the model becoming truth by the back
door.

`[DECISION]` The list endpoint states in-band that it lists **completed**
investigations only. The engine has no tenant-scoped query for in-progress ones;
rather than invent one or let an empty list read as "nothing is happening", the
limitation is disclosed in the response.

## Decision 7 — No new architecture fitness rule `[DECISION]`

`BND-INTELLIGENCE-CANNOT-EXECUTE`, `BND-WORLD-CANNOT-EXECUTE`,
`BND-DIRECT-HTTP`, `BND-PROVIDER-SDK` and `BND-EFFECT-GATE` already forbid an API
module executing or dialling a provider, and the 0-provider-call result is
empirical. A `BND-PRODUCT-API-CANNOT-EXECUTE` rule would restate existing rules
and add a place for them to disagree. None was added.

## What this ADR does NOT decide

- No `Incident` aggregate. `Investigation` is sufficient for a read surface, and
  new persistence for frontend convenience is forbidden by the phase brief.
- No frontend. No websocket or streaming. No mutation, ever, on this surface —
  a write product surface would be a separate decision requiring its own ADR.
- No SLA. The measured latencies are in-process, single-client, local database.

## Status of the invariants Phase 9 established

Unchanged and re-proven by regression `[FACT]`: 2808 passed, 0 failed.
Architecture gate PASS (35 passed, 0 failed, 6 skipped, 1188 modules).
No migration, no new table, no new execution authority, no new governance
authority, no new credential path.

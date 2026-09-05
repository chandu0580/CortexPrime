# Phase 10.1 — Implementation Map (discovery output)

**Written before production code changed.** Required by Part A.

---

## 1. Existing authentication — reusable, and safe

`[FACT]` `backend/auth/` provides a real JWT system: `decode_access_token`,
a token blacklist checked on every request (`_decode_and_verify`), `require_user`,
`require_tenant`, `require_tenant_role`, `get_current_tenant`.

`[FACT]` **`require_tenant` reads `tenant_id` from `current_user`, which is the
decoded JWT payload** — not from a body, query, path or arbitrary header. It also
checks the tenant exists and is active, and returns 403 otherwise.

**Decision:** reuse it. No new authentication system. Part B needs only a thin
adapter that turns the verified JWT claims into the platform's own `TenantRef` /
`ExecutionContext`.

---

## 2. Read models available — every endpoint must map to one

| Read | Source | Tenant scoping |
|---|---|---|
| One investigation, full state | `InvestigationService.reconstruct(tenant=, investigation_ref=)` | `[FACT]` Requires a typed `TenantRef`; raises `InvestigationNotFound` for another tenant |
| Completed investigations | `SqlInvestigationRepository.list_terminal(tenant_id=, limit=200)` | `[FACT]` **Tenant-scoped in SQL** — *"a stronger boundary than application filtering"*; already bounded |
| Current world state | `WorldQuery.current(tenant=, subject_ref=, predicate=, now=)` | `[FACT]` Typed `TenantRef` |
| Assurance verdict | `SqlVerificationRepository.get(tenant_id=, verification_id=)` | `[FACT]` Tenant-scoped |

`[FACT]` **Gap found:** there is no tenant-scoped list of *active* (non-terminal)
investigations. `list_terminal` covers only `completed`/`failed`/`abandoned`.

**Decision:** expose that honestly as *completed* investigations rather than
inventing an endpoint with no underlying capability (Part F). No repository method
is added in this phase.

---

## 3. Where the product API lives — a separate app

`[FACT]` `backend/main.py` builds the V1 `FastAPI` app with a `lifespan`, and
registers **185** V1 routers via `router_registry`. `[FACT]` Its boot is a known
hazard: it contacts real providers and auto-migrates (recorded in project memory).

`[FACT]` **89 of 96 V1 route modules have no tenant reference** (Phase 10.0).

**Decision:** the product API is its **own FastAPI application factory**, mounting
only `/api/v1/*`. It imports no V1 route module and no V1 execution code. This
satisfies Part M directly and avoids inheriting either the V1 boot hazards or its
tenant semantics.

---

## 4. Endpoint set — minimal, each backed by a real capability

| Endpoint | Backing capability |
|---|---|
| `GET /api/v1/healthz` | none — liveness only, no data, unauthenticated |
| `GET /api/v1/investigations` | `list_terminal` (bounded) |
| `GET /api/v1/investigations/{id}` | `reconstruct` |
| `GET /api/v1/investigations/{id}/hypotheses` | `reconstruct` projection |
| `GET /api/v1/investigations/{id}/evidence` | `reconstruct` projection |
| `GET /api/v1/world/state` | `WorldQuery.current` |
| `GET /api/v1/verifications/{id}` | `SqlVerificationRepository.get` |

**Nothing else.** No execution, approval, autonomy or World mutation endpoint
exists in this phase, and the services' mutation methods are never called.

---

## 5. Part E — the Incident decision

**No `Incident` aggregate is created.** `[FACT]` `Investigation` already carries
identity, tenant, status lifecycle, hypotheses, evidence refs, tests, conclusion
and residual uncertainty; World carries lineage, freshness and corroboration.

For a read-only surface that is sufficient. Creating a persistence model for
frontend convenience is exactly what Part E forbids. The 10.0 analysis
(one incident may span several investigations) still stands, and remains deferred
to its own phase with its own discovery.

---

## 6. Epistemic fidelity — the rule the schemas must not break

`[FACT]` The engine distinguishes `SUPPORTED`, `UNSUPPORTED`,
`INSUFFICIENT_EVIDENCE`, and `UNKNOWN` / `STALE` / `CONFLICTED` epistemic status.

**Decision:** response schemas carry these **as their own string values**. They are
never mapped to `success`/`failure`/boolean, and **no confidence number is
synthesised** — there is none in the domain to carry.

---

## 7. Error semantics (Part I)

| Condition | Status |
|---|---|
| No/invalid token | **401** |
| Valid token, no tenant claim, or inactive tenant | **403** |
| Resource belongs to another tenant | **404** |
| Malformed id / bad query | **422** |
| Unexpected | **500**, no internal detail |

**Decision on the 403-vs-404 question:** a cross-tenant resource returns **404,
not 403**. `[FACT]` This follows the existing behaviour rather than inventing a
policy — `reconstruct` raises `InvestigationNotFound` for another tenant, so the
service layer already cannot distinguish "not yours" from "not there". Returning
403 would require the API to learn that the resource exists in another tenant,
which is the disclosure the 404 avoids. Documented as required by Part I.

---

## 8. Planned changes

New, all under `backend/api/product/`: `context.py` (authenticated principal →
`TenantRef`), `schemas.py` (explicit response models), `routes.py`, `app.py`
(the separate factory). Plus `scripts/phase101_product_api_harness.py`.

**No** migration, table, connector, credential path, or execution change.
**No** V1 route modified.

**Part O:** no fitness rule planned. `BND-INTELLIGENCE-CANNOT-EXECUTE`,
`BND-WORLD-CANNOT-EXECUTE`, `BND-DIRECT-HTTP`, `BND-PROVIDER-SDK` and
`BND-EFFECT-GATE` already prevent an API module from executing or dialling a
provider. A rule will be added only if implementation reveals a genuine gap, with
`CURRENT = PASS` and `SYNTHETIC = FAIL` demonstrated.

---

## 9. Stop rule

Any stop condition — a second authority of any kind, tenant supplied by the
caller, direct provider access, a hidden command bus — ends the phase and is
reported.

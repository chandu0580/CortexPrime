# Phase 10.1 — Verification Report

**Phase:** Governed Product API boundary
**Date:** 2026-09-05
**Branch:** `phase-1-foundation`
**ADR:** ADR-094
**Harness:** `scripts/phase101_product_api_harness.py`

---

## Result: **VERIFIED**

| | Result |
|---|---|
| Harness | **44/44, exit 0, VERIFIED** |
| Architecture gate | **PASS** — 35 passed, 0 failed, 6 skipped, 1188 modules |
| Regression | **2808 passed, 0 failed**, exit 0 (contexts, intelligence, contracts, architecture, assurance) |
| **Provider calls made by the API** | **0** |
| New execution / governance / approval / credential authority | **none** |
| Migrations, new tables | **0** |
| V1 route modules modified | **0** |

---

## 1. What was built — [VERIFIED]

Four new modules under `backend/api/product/`, one new harness. Nothing else.

- `context.py` — the **only** way a product route learns its tenant. Resolves it
  from the verified JWT via the existing `require_tenant`.
- `schemas.py` — explicit Pydantic response models. No `dict[str, Any]`.
- `routes.py` — seven `GET` endpoints, each backed by an existing read.
- `app.py` — its own FastAPI application.

`[VERIFIED]` **Every product route is a `GET`.** The API is read-only by shape,
not by convention: the set of HTTP methods across `/api/v1/*` is exactly `{GET}`.

---

## 2. Authentication reused, not rebuilt — [VERIFIED]

The existing `backend/auth` already decodes the JWT, checks a revocation
blacklist, and confirms the tenant exists and is active — and it reads `tenant_id`
**from the decoded token**. That is the property this phase needed, so it was
adapted rather than replaced. No new authentication system exists.

---

## 3. The security matrix — [VERIFIED], 0 provider calls

| | Check | Result |
|---|---|---|
| B1 | No authentication | **401** |
| B2 | Valid authentication | 200 |
| B3/B4 | Garbage token / empty bearer | **401** |
| B5 | Token with **no tenant claim** | **403** |
| B6 | Tenant in a **query parameter** | ignored |
| B7 | Tenant in a **forged header** | ignored |
| B8 | Tenant in a **JSON body** | ignored |
| B9 | Two tenants, same endpoint | **A=1, B=0** |
| B10 | Tenant B requests tenant A's **real** investigation by id | **404** |
| B10b | Tenant A requests the **same id** | **200** |
| B10c | Tenant B requests `/hypotheses` and `/evidence` of it | **404** |
| B10d | A nonexistent investigation | **404** |
| B11 | Over-long resource id | **422** |
| B12/B13 | `limit=100000` / `limit=-5` | **422** |
| B14 | Maximum page | bounded at 100 |

### The check that was initially worthless, and how it was fixed

`[VERIFIED]` The first run passed B9 with **A=0, B=0** — both tenants were empty,
so the comparison proved nothing about isolation while reading as evidence that
it worked.

The harness now **seeds a real investigation** for tenant A through the governed
`InvestigationService` (created, transitioned, concluded — never by writing rows),
so B9 asserts real counts and B10/B10b are a genuine pair: B is refused the exact
resource that A can read. A tenant-isolation test that passes because there is no
data is worse than no test.

---

## 4. No mutation surface — [VERIFIED]

`[VERIFIED]` Nine mutation attempts (`POST` investigations / conclude / approvals
/ executions / autonomy / world, `PUT` world, `DELETE` investigation, `PATCH`
verification) all return **404 or 405 — the routes do not exist.**

This was asserted as *non-existence* rather than *refusal* deliberately: a route
that answers 405 is a registered path somebody can later add a verb to.

`[VERIFIED]` The `ProductEngine` handed to the routes carries exactly four
fields — `investigations`, `investigation_repository`, `world_query`,
`verifications`. No gateway, dispatcher, worker runtime, credential broker,
connector or transport is reachable from a route.

---

## 5. Epistemic fidelity — [VERIFIED]

- `[VERIFIED]` A world read for a subject with no evidence returns an **epistemic
  status**, not an error and not `false`. `UNKNOWN` is carried as its own value
  with `value: null`.
- `[VERIFIED]` An `INSUFFICIENT_EVIDENCE` conclusion is carried as
  `conclusion_kind: "insufficient_evidence"` — not rendered as a failure.
- `[VERIFIED]` **No confidence field appears anywhere.** There is none in the
  domain, and none was synthesised.
- `[VERIFIED]` The list endpoint states plainly that it lists **completed**
  investigations only, so an empty list is not mistaken for "nothing is
  happening". The engine exposes no tenant-scoped listing of in-progress
  investigations, and this API did not invent one.

---

## 6. Reads mutate nothing — [VERIFIED]

`[VERIFIED]` Repeated `GET`s are observationally equivalent, and after 10 reads
the ledger counts are unchanged:
`cw_observation 8, cw_fact 3, cw_verification 7` before and after.

---

## 7. Secrets, errors, observability

- `[VERIFIED]` No credential, DSN or bearer token appears in any response body.
- `[VERIFIED]` The liveness probe discloses only `{"status": "ok"}` — nothing
  about tenant, engine or configuration.
- `[VERIFIED]` Error semantics are deterministic: 401 unauthenticated, 403 no or
  inactive tenant, 404 not found *for this tenant*, 422 invalid request, 500 with
  no internal detail.
- **404-vs-403 decision, documented as Part I requires:** a cross-tenant resource
  returns **404**. This follows the existing service behaviour rather than
  inventing a policy — `reconstruct` raises `InvestigationNotFound` for another
  tenant, so the service layer genuinely cannot distinguish "not yours" from "not
  there". Teaching the API that difference would create the disclosure the 404
  avoids.
- `[VERIFIED]` No second telemetry system was created.

---

## 8. Measured latency

`[MEASURED]` In-process ASGI `TestClient`, 30 samples per endpoint, against local
PostgreSQL:

| Endpoint | p50 | p95 |
|---|---|---|
| `GET /api/v1/investigations` | **17.5 ms** | **23.0 ms** |
| `GET /api/v1/world/state` | **24.9 ms** | **33.8 ms** |
| `GET /api/v1/healthz` | **6.7 ms** | **8.9 ms** |

**No SLA or target is proposed.** These exclude network, TLS and concurrency, on
a development host.

---

## 9. Architecture fitness — no rule added

Part O permits a rule only for a genuine uncovered invariant.
`BND-INTELLIGENCE-CANNOT-EXECUTE`, `BND-WORLD-CANNOT-EXECUTE`, `BND-DIRECT-HTTP`,
`BND-PROVIDER-SDK` and `BND-EFFECT-GATE` already prevent an API module from
executing or dialling a provider, and the harness proves **0 provider calls**
empirically. A `BND-PRODUCT-API-CANNOT-EXECUTE` rule would restate them.
**None added.**

---

## 10. Stop-condition audit — **PASS**

No second execution, governance, approval, credential or truth authority. No
direct provider access (0 calls, measured). Tenant is never supplied by the
caller (B6/B7/B8). No RAG. No model-driven authorization. No new autonomy
authority.

---

## 11. Known limitations

- `[NOT VERIFIED]` **No listing of in-progress investigations.** The engine has
  no tenant-scoped query for them; the API says so rather than inventing one.
- `[DEFERRED]` **No `Incident` aggregate.** Part E's decision: `Investigation`
  suffices for a read-only surface, and creating persistence for frontend
  convenience is what Part E forbids. The 10.0 observation that one incident may
  span several investigations still stands.
- `[DEFERRED]` **Evidence projection is thin.** `EvidenceRef` carries observation
  ids from the investigation; per-observation subject/predicate/lineage would
  need a World read per reference, which was out of scope here.
- `[NOT VERIFIED]` **Latency under concurrency or over a network.** In-process
  only.
- `[DEFERRED]` **No frontend client.** Part L asked only whether one *could*
  consume the boundary; the schemas are explicit and OpenAPI is generated, and no
  UI work was done.
- `[UNCHANGED]` Phase 5.5 credential blocker; the model proposer remains
  scripted.

# Phase 10.2 — Verification Report

**Phase:** AI incident investigator workspace
**Date:** 2026-09-05
**Branch:** `phase-1-foundation`
**ADR:** ADR-095
**Map:** `docs/PHASE_10_2_IMPLEMENTATION_MAP.md`
**Harness:** `scripts/phase102_workspace_harness.py`

Labels: `[VERIFIED]`, `[NOT VERIFIED]`, `[DEFERRED]`, `[BLOCKED]`.

---

## Result: **VERIFIED**

| | Result |
|---|---|
| Product harness | **67/67, exit 0, VERIFIED** |
| Phase 10.1 harness, re-run against this code | **44/44, exit 0** |
| Frontend workspace tests | **49/49** (3 files) |
| Frontend suite, whole repo | **246 passed** |
| Architecture gate | **PASS** — 35 passed, 0 failed, 6 skipped, 1189 modules |
| Backend regression | see §10 |
| **Provider calls during the entire run** | **0** |
| Migrations, new tables, new authorities | **0** |

---

## 1. The blocking gap discovery came first — [VERIFIED]

Part A's audit produced one finding that stopped the phase before any UI was
written: **the V1 login could not produce a session the Product API would
accept.**

- `[VERIFIED]` `backend/api/auth_routes.py:192` minted tokens with
  `create_access_token(user_id=..., role=...)` — **no tenant claim**.
- `[VERIFIED]` `backend/api/product/context.py` refuses a token with no tenant
  claim with 403. That refusal was verified as correct in Phase 10.1 (check B5).
- Therefore no browser session could reach a single workspace endpoint.

The frontend must not fix this: a client-supplied tenant is a declared STOP
condition. The fix is in the backend, and it is a **wire, not a mechanism** —
every part already existed and was simply not connected:

`[VERIFIED]` `_tenant_claims()` resolves the authenticated identity against the
**existing** `TenantManager` and passes the result to the **existing**
`create_access_token`, which already accepted `tenant_id`, `tenant_slug` and
`user_role`.

**Fail-closed, and proven fail-closed:**

| | Check | Result |
|---|---|---|
| C1 | A user with a real membership resolves to real claims | `tenant_id` matches the store |
| C2 | The claims are `{tenant_id, tenant_slug, user_role}` and nothing else — the only input is the authenticated identity | no caller-supplied field reaches it |
| C3 | An identity with **no** membership | **`{}` — no claims at all** |
| C5 | A token minted without membership | **carries no `tenant_id`**, so the API keeps answering 403 exactly as before |

Refresh **re-resolves** membership rather than copying it from the old token, so
a membership revoked after login stops being honoured at the next rotation
instead of riding along inside a token the client keeps refreshing.

---

## 2. Two defects in the Phase 10.1 projection — [VERIFIED] as fixed

Found while mapping, not while testing.

- `[VERIFIED]` **Residual uncertainty was always empty.** 10.1 read
  `conclusion.diagnosis` and `conclusion.residual_uncertainty` off an
  `InvestigationConclusion`, which is a plain `str` Enum with neither attribute.
  The field existed, was documented, and could never be populated. It now comes
  from `settle()` — the platform's own honest terminal read — and check **D8**
  asserts it is non-empty against real data:
  `"no hypothesis affirmed; still open: ['h-startup-failure']"`.
- `[VERIFIED]` **The list called a conclusion kind a "diagnosis."** The field is
  now `conclusion_kind`, and check **D6** asserts no `diagnosis` field remains.
- `[VERIFIED]` **Verification projection read fields the contract does not
  have.** `WorldVerification` has `procedure_ref` and a `VerifierIdentity`, not
  a `procedure` object or a `predicate`. So verifier and predicate were silently
  empty. Check **D19** now asserts the real verifier id **and reasoning path**
  come back — which is what makes independence checkable rather than asserted.

---

## 3. The product journey — [VERIFIED] end to end

Part B, against real persisted state (checks D1–D20):

`list → detail → timeline → hypotheses → evidence → world state → assurance →
residual uncertainty`

| | |
|---|---|
| D2/D4 | **In-progress investigations are listable.** The 10.1 limitation is lifted by `list_active` — the same tenant-scoped SQL as `list_terminal` with the status filter inverted. Filtering to `active` genuinely excludes the completed one |
| D9/D11 | The differential round-trips with **both** a RULED OUT and an OPEN hypothesis, each carrying the platform's own reason it is unresolved |
| D10 | Explicit evidence gaps survive: `['container exit code', 'startup probe result']` |
| D13/D14 | The timeline holds **8 real recorded events** in sequence order, each with `recorded_at` under its own name and **no** `observed_at` |
| D15/D16 | Evidence resolves to real observations with values, sources and **both** clocks — the thin-projection limitation 10.1 recorded |
| D17 | An unresolvable evidence reference is **reported as unresolved**, not dropped |

---

## 4. Temporal semantics — [VERIFIED]

- `[VERIFIED]` E1/E2: `queried_valid_at`, `observed_at` and `read_at` are three
  separate fields with three separate names. Measured on real data:
  observed `11:02:44`, answered `11:48:51`.
- `[VERIFIED]` The UI renders no timestamp without naming its clock —
  `TemporalStamp` has no unlabelled mode, and a test asserts an observation time
  and a ledger time never share a label.
- `[VERIFIED]` A missing time renders as **"not recorded"**, not as a blank that
  reads like zero.

---

## 5. UNKNOWN, STALE, CONFLICTED, INSUFFICIENT_EVIDENCE — [VERIFIED]

Each was produced from **real seeded conditions**, not asserted against a
hand-written string:

- `[VERIFIED]` **STALE** (E3/E4): observations dated 45 minutes back, against the
  real 120s metric horizon. The API returned
  `stale, age 2766.8s, horizon 120s — "STALE is not FALSE"` — **and still
  returned the value**, because stale is not false.
- `[VERIFIED]` **UNKNOWN** (E8): a predicate nothing has ever observed returns
  `epistemic_status: unknown`, `value: null`, `evidence_count: 0` — not an
  error, not an empty success, not false.
- `[VERIFIED]` **INSUFFICIENT_EVIDENCE** (E9/E13): carried unmapped as both an
  investigation conclusion and an Assurance verdict.
- `[VERIFIED]` **UNKNOWN temporal fit** (E12) survives as `unknown`.
- `[VERIFIED]` **E14: no confidence, probability, score or percentage appears
  anywhere** in any workspace payload.

In the UI, `frontend/lib/investigator/epistemic.ts` owns every mapping and is
tested directly: `[VERIFIED]` the tone vocabulary contains **no**
`success`/`warning`/`error` member, every reading carries a non-empty **textual**
label, and no reading emits a percentage or the word confidence.

---

## 6. Authority, lineage and corroboration — [VERIFIED]

The check this section exists for:

`[VERIFIED]` **E5: two agreeing sources that share one lineage origin come back
as CORRELATED, never as independent.** Seeded from real data —
`connector:kubernetes` (the API server) and `prometheus:kube-state-metrics`
(that same number re-exported) both reporting `restartCount: 7`. The API
returned:

> `correlated` — *"2 sources agree but share lineage origin 'kubernetes-cluster'
> — correlated, not independent"*

- `[VERIFIED]` E6: **two sources, exactly one distinct origin**, so a client
  cannot count them as two.
- `[VERIFIED]` E7: each source's lineage is exposed, so the claim is checkable.
- `[VERIFIED]` In the UI the label itself is **"CORRELATED — NOT INDEPENDENT"**,
  and a test asserts no level other than `independent` ever renders as
  `INDEPENDENT`.
- `[VERIFIED]` Authority is projected with **every competing value retained** —
  a CONFLICTED answer showing only the winner would be indistinguishable from a
  settled one.

---

## 7. Assurance — [VERIFIED]

- `[VERIFIED]` D19: the real verification comes back with `verifier_ref` and
  `verifier_reasoning_path`.
- `[VERIFIED]` E10: `assurance_verified` is **false**, and the panel says in
  words that support and verification are separate gates.
- `[VERIFIED]` The UI computes no verdict, aggregates nothing across
  verifications, and displays no percentage — asserted by a test that scans the
  rendered output for `\d+\s*%` and `confidence`.

---

## 8. Historical experience — [VERIFIED] visibly distinct

- `[VERIFIED]` Rendered in a panel headed **HISTORICAL EXPERIENCE**, with the
  in-panel statement that these "do not establish what is true now".
- `[VERIFIED]` **No retrieval system was added.** It filters the
  already-exposed completed-investigation list by subject. No embeddings, no
  vector search, no similarity score — asserted by the Part Q test below.

---

## 9. Security — [VERIFIED], 15/15

| | Check | Result |
|---|---|---|
| F1 | Unauthenticated | **401** |
| F2 | Authenticated | 200 |
| F3 | Valid token, **no tenant claim** | **403** |
| F4 | Tenant B → tenant A's real investigation | **404** |
| F5 | Tenant A → the same id | **200** (so the 404 is isolation, not breakage) |
| F6 | Tenant B → `/timeline`, `/assurance`, `/evidence`, `/hypotheses` | **404 on all four** |
| F7 | Forged tenant in a **query parameter** | ignored, B sees 0 |
| F8 | Forged tenant **headers** (3 variants) | ignored, B sees 0 |
| F9 | Tenant in the **request body** | ignored, B sees 0 |
| F10 | Tenant smuggled into the **path** | 404 |
| F11 | 9 mutation attempts | **routes do not exist** (404/405) |
| F12 | 8 provider/connector/credential/worker/transport/gateway paths | **all 404** |
| F13 | Forged token | **401** |
| F14 | Secret / DSN / password / bearer / stack trace in any response | **none** |
| F15 | Liveness probe | `{"status":"ok"}` only |

`[VERIFIED]` Repeated at the **real browser boundary** (§11), not only in-process.

### The frontend cannot assert a tenant — [VERIFIED]

- `[VERIFIED]` The access token is an **HttpOnly cookie**. The workspace code
  cannot read it, so there is nothing for a script to steal or replay.
- `[VERIFIED]` `productGet` **throws** if any caller passes `tenant`,
  `tenant_id` or `tenant_slug` — it fails loudly rather than sending something
  the server would quietly ignore, which would look supported.
- `[VERIFIED]` No workspace file touches `localStorage`, `sessionStorage` or
  `document.cookie`.

---

## 10. Gates

- `[VERIFIED]` **Architecture gate PASS** — 35 passed, 0 failed, 6 skipped,
  1189 modules, 4283 internal edges.
- `[VERIFIED]` **Backend regression** — see the final report line; run over
  `tests/contexts tests/intelligence tests/contracts tests/architecture
  tests/assurance tests/world`.
- `[VERIFIED]` **The Phase 10.1 harness passes against this code: 44/44.**

### Two 10.1 harness assertions were updated, and why

Both encoded the *old contract shape*, not a behaviour:

1. `A2` asserted `ProductEngine` had exactly four fields. 10.2 added
   `observations`, `beliefs` and `lineage_policy` — all pure reads over the same
   two ledgers. It is now an **allow-list** check: nothing capable of acting may
   appear on the engine.
2. `E2` asserted the list note said *"Completed investigations only"*. That was
   the honest disclosure of a real limitation; 10.2 lifted the limitation, so
   asserting the old wording would be asserting a limitation that no longer
   exists. It now asserts the underlying rule: the response must **say** which
   lifecycle states it listed.
3. `E5c` asserted a hand-written field list. It now asserts against the declared
   Pydantic schema, because a hand-maintained list drifts and stops catching
   anything.

No behavioural assertion was weakened or removed.

---

## 11. Real browser-path evidence — [VERIFIED]

Beyond the in-process harness, the whole chain was exercised with both processes
actually running:

```
browser → Next same-origin /product-api rewrite → Product API (own process)
        → governed services → real PostgreSQL
```

| Request | Result |
|---|---|
| `GET /investigator` (the workspace page) | **200**, compiled and served |
| `GET /product-api/api/v1/healthz` | **200** `{"status":"ok"}` |
| `GET /product-api/api/v1/investigations` with **no cookie** | **401** |
| Same, with a real `cortex_access` cookie | **200**, `count=4`, real refs, statuses, autonomy levels |
| Tenant B's cookie → tenant A's investigation | **404** |
| Tenant B's cookie → its timeline | **404** |

### A CSP finding, fixed without weakening anything

`[VERIFIED]` `next.config.ts` sets `connect-src 'self' https:`. A direct
cross-origin call to `http://localhost:8110` is **blocked by that policy**.

The response was **not** to widen the CSP. The workspace now reaches the Product
API through a **same-origin rewrite**, which is strictly better: the policy is
satisfied untouched, no credentialed cross-origin request is made, and the
browser needs no CORS allowance at all.

---

## 12. Architecture fitness — a real rule, in the place that can enforce it

`[VERIFIED]` **No Python fitness rule was added.** The gate scans Python and
cannot see TypeScript, so a `BND-PRODUCT-UI-CANNOT-BYPASS-GOVERNANCE` rule there
would restate rules that already hold and still not cover the code it names.
That is a cosmetic rule, which Part X forbids.

Instead the boundary is enforced where it lives —
`frontend/tests/investigator/boundary.test.ts` reads every workspace file and
fails on: an `axios` or V1 `api-client` import; a `fetch` outside
`lib/product-api.ts`; any provider/connector/credential/worker/transport/gateway
path; any non-GET method; `localStorage`/`sessionStorage`/`document.cookie`; a
second backend base URL; `useMutation` or an approve/execute/promote handler;
and any embedding/vector/semantic-search machinery (Part Q).

**Sensitivity-tested, not assumed.** An `axios` import plus a
`fetch("http://localhost:8000/api/v1/connectors", {method:"POST"})` were
injected into `Panel.tsx`; **5 assertions failed**. The violation was removed and
the suite returned to green. A first assertion also guards against a vacuous
pass by requiring the file list be non-empty.

---

## 13. Mutation-free — [VERIFIED]

`[VERIFIED]` G1: **five full workspace loads — 40 reads — changed no row.**
Ledger counts identical before and after:
`observations 4, facts 1, verifications 2, investigation_events 30`.

`[VERIFIED]` G2: repeated reads of the same investigation are observationally
equivalent apart from the response's own `read_at`.

`[VERIFIED]` The browser cache cannot disguise staleness: World reads use
`staleTime: 0` / `gcTime: 0`, and the server's `read_at` is displayed on screen
beside the world's own `observed_at`.

---

## 14. Measured latency — [MEASURED], no SLA proposed

In-process ASGI `TestClient`, 30 samples per endpoint, local PostgreSQL:

| Endpoint | p50 | p95 |
|---|---|---|
| `GET /investigations?state=all` | **29.9 ms** | **47.2 ms** |
| `GET /investigations/{ref}` | **62.1 ms** | **94.1 ms** |
| `GET /investigations/{ref}/timeline` | **28.5 ms** | **34.5 ms** |
| `GET /investigations/{ref}/evidence` | **51.2 ms** | **78.0 ms** |
| `GET /world/state` | **111.6 ms** | **188.4 ms** |

`[MEASURED]` The world read is the slowest and got slower than Phase 10.1's
24.9 ms p50, because it now also forms a belief to produce the corroboration
assessment — a second pass over the observation ledger. That is a real cost of a
real answer, stated rather than hidden.

**Measured / target / unknown**, as Part S requires:
*measured* — the table above and the §11 live requests; *target* — **none, no
SLA is proposed**; *unknown* — behaviour under concurrency, over a network, with
TLS, or at a data volume larger than this seed.

---

## 15. Accessibility and UX safety

- `[VERIFIED]` **Epistemic state is always textual.** `EpistemicBadge` renders
  the label as text in the accessibility tree; a test asserts it.
- `[VERIFIED]` Colour is emphasis only — every tone ships a full word label, so
  the state survives greyscale and a screen reader.
- `[VERIFIED]` Loading uses `role="status"` + `aria-live`; failures use
  `role="alert"`; the list is a real `<table>` with `<th scope="col">` and a
  caption; filters are real `<button aria-pressed>`; the predicate input has a
  label.
- `[VERIFIED]` Timestamps are rendered explicitly in **UTC** — a local rendering
  of an incident time is how two people on a call describe different moments
  with the same number.
- `[VERIFIED]` Wide content scrolls in its own container; the layout is
  responsive (`flex-wrap`, `sm:` breakpoints).
- `[NOT VERIFIED]` **Keyboard navigation and screen-reader behaviour were not
  tested with an actual assistive technology or a keyboard-only pass.** The
  markup is semantic and the states are textual, but that is a structural
  argument, not a measurement. Playwright is configured and was not run.

---

## 16. Loading and failure semantics — [VERIFIED]

`[VERIFIED]` Transport outcomes and epistemic states are rendered by **different
components** with **different vocabularies**. `LoadState` handles
unauthenticated / no-tenant / not-found / invalid / unavailable / network /
server, and each message says explicitly that a failed request is **not** a
finding about the user's systems. `EpistemicBadge` handles the epistemic states
and never renders an HTTP outcome.

`[VERIFIED]` 401, 403, 404 and 422 are **not retried** — retrying cannot change
the answer, and retrying a deliberate cross-tenant 404 would make isolation look
like a flaky endpoint.

---

## 17. Stop-condition audit — **PASS**

No second truth store, governance system, execution authority or approval
authority. No direct provider access (**0 provider calls, measured**). No
client-authoritative tenant (F7–F10, and the client throws rather than send
one). No RAG. No frontend-generated verdict, confidence or autonomy. Nothing
bypasses the Product API (§12, sensitivity-tested).

---

## 18. Known limitations

- `[NOT VERIFIED]` **Token revocation was not exercised.** Redis is absent in
  this environment and the platform's blacklist logs
  `Redis unavailable — failing OPEN (REVOCATION_FAIL_OPEN=true)`. So F13 proves a
  *forged* token is refused; it does **not** prove a *revoked* token is. This is
  pre-existing platform behaviour, not introduced here, and it is a real gap in
  any deployment without Redis.
- `[NOT VERIFIED]` **Accessibility was not tested with assistive technology.**
  See §15.
- `[DEFERRED]` **No incident aggregate.** One incident may span several
  investigations; the workspace groups by subject and says so.
- `[DEFERRED]` **No live updates.** No websocket, no polling, no streaming. A
  running investigation's page is a snapshot with its `read_at` on screen.
- `[DEFERRED]` **World state needs a predicate typed in.** There is no
  per-subject predicate discovery in the engine, so the panel opens on one
  default and lets a responder change it rather than pretending to enumerate.
- `[NOT VERIFIED]` **Authentication is still a single env-configured user.**
  `verify_credentials` checks one `CORTEX_USER`; tenant membership comes from
  the file-backed `TenantManager`. Real multi-user identity and RBAC remain
  Phase 10.9.
- `[UNCHANGED]` **5 pre-existing TypeScript errors** in
  `components/operations-center/dashboard-panel.tsx` and
  `components/runtime/RuntimeHealth.tsx`. None is in a file this phase touched,
  and the count did not change.
- `[UNCHANGED]` **One pre-existing vitest file-load failure**: `vitest.config.ts`
  includes `**/*.spec.ts`, which picks up the Playwright `e2e/` specs and cannot
  import `@playwright/test`. `e2e/` was not modified.
- `[UNCHANGED]` Phase 5.5 credential blocker; the model proposer remains
  scripted; the differential is seeded by the platform, not generated.

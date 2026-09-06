# Phase 10.9 — Durable, Governed Tenant Membership
## Verification Report

**Verdict: VERIFIED — 107/107.**

Harness: `scripts/phase109_membership_harness.py`
Infrastructure: real k3d (`k3d-cortex-p99b-server-0`, v1.35.5+k3s1), real
PostgreSQL (`cortex_p109`), real Redis, real tenant store, real OS process
death.

Discovery **called** the membership paths rather than reading them. Two of the
findings below would have been missed by source review alone.

---

## 1. Section results

| § | Area | Checks |
|---|---|---|
| A | Composition — one membership store, one new table | 6 [VERIFIED] |
| B | Migration from JSON, and JSON stops deciding | 5 [VERIFIED] |
| C | Membership is NOT authority | 5 [VERIFIED] |
| D | Product access requires an active membership | 3 [VERIFIED] |
| E | Admission | 7 [VERIFIED] |
| F | Deactivation fails closed on every path | 10 [VERIFIED] |
| G | Reactivation — measured, not designed | 2 [VERIFIED] |
| H | Historical identity is never rewritten | 4 [VERIFIED] |
| I | Cross-tenant isolation | 6 [VERIFIED] |
| J | Audit | 6 [VERIFIED] |
| K | Concurrency | 3 [VERIFIED] |
| L | Positive matrix | 6 [VERIFIED] |
| M | Negative matrix | 37 [VERIFIED] |
| N | Crash / restart | 6 [VERIFIED] |
| O | Measured latency | 1 [VERIFIED] |
| | **Total** | **107 / 107** |

---

## 2. Two blocking findings, both proven by calling

### Finding 1 — cross-tenant membership mutation over a live route [VERIFIED]

`backend/api/tenant_routes.py` is registered in the V1 app, takes `tenant_id`
from the **path**, and guards with `require_admin` — a JWT `role == "admin"`
check carrying **no tenant**. With an admin token scoped to tenant A:

| Against tenant **B** | Before | After |
|---|---|---|
| `POST /api/tenants/{B}/users` | **201** — member planted | **404** |
| `PATCH /api/tenants/{B}/users/{id}` | **200** — role → owner | **404** |
| `GET /api/tenants/{B}/users` | **200** — full disclosure | **404** |
| `POST /api/tenants/{B}/deactivate` | **200** — tenant B disabled | **404** |

Harness `I5` re-runs all three attack paths and requires `[404, 404, 404]`.
404 rather than 403 deliberately: a tenant may not learn another tenant exists.

**Severity, stated precisely.** Membership alone grants nothing after Phase
10.8, so this was never privilege escalation into another tenant's *actions*.
It was a cross-tenant **denial of governance** — deactivating tenant B made
every authority there answer `tenant_inactive` — plus disclosure of another
tenant's membership list.

### Finding 2 — product access never checked membership [VERIFIED]

| Caller | Before | After |
|---|---|---|
| No membership at all, valid tenant token | **200** | **403** `no_tenant_membership` |
| Inactive member | **200** | **403** `membership_inactive` |
| Inactive member listing authority grants | **200** | **403** |

The grant listing is precisely the reconnaissance an attacker wants, and it was
readable by anyone holding a token with a tenant claim.

## 3. Migration from JSON [VERIFIED]

| Check | Result |
|---|---|
| B1 deterministic import | 35 memberships imported |
| B2 **created no authority** | grant count unchanged across the migration |
| B3 re-runnable | second run imports 0 |
| B4 provenance | `migrated` vs `admitted` distinguishable |
| B5 **JSON is no longer authoritative** | file flipped to `inactive`/`owner`; store still reads `active`/`member` |

B2 matters most: a migration that handed out grants while moving membership
would be the quietest possible privilege escalation. It was measured as a
before/after count, not asserted.

## 4. Membership is not authority [VERIFIED]

An **active** member holding no grant is refused all three authorities, each
with its own reason — `no_approver_authority`, `no_executor_authority`,
`no_issuer_authority`. The members who *do* hold grants still succeed, so this
is not a blanket refusal.

`C5` relabels a member as **owner** in the durable store and proves no
authority appears. Phase 10.5's rule survives intact: **no role maps to an
authority.** The membership projection says so in its own payload
(`confers_authority: false`, plus a note naming the grant system), rather than
leaving a reader to infer it from a role column.

## 5. Deactivation fails closed on every path [VERIFIED]

Before deactivation the subject held approve, execute **and** issue. After a
single deactivation:

| Path | Result |
|---|---|
| F4 approval authority | gone — `membership_inactive` |
| F5 execution authority | gone |
| F6 issuance authority | gone |
| F7 product access, token minted while active | **403** — membership read live, never from the claim |
| F8 grant issuance | **403** |
| F9 **the grant record itself** | untouched — 1 live grant |
| F10 deactivating twice | **409**, not a silent overwrite of who did it first |

F9 is the invariant Part N asks for: deactivating a person does not rewrite the
authority record that names them.

## 6. Reactivation — the measured answer [VERIFIED as measured]

```
reactivation_restores_grants = true
```

**Recorded, not designed.** A grant survives deactivation of the membership it
names and becomes usable again on reactivation, because grants are revoked
separately and were not revoked here. Part L asked for the verified behaviour
rather than invented semantics, and this is it.

**The operational consequence is a trap and is named as one:** an operator
removing authority permanently must revoke the grant, not only the membership.

## 7. Cross-tenant isolation [VERIFIED]

Tenant B's admin admitting somebody lands in tenant B — the route has **no
tenant to name**. Cross-tenant deactivation and role change both return 404 and
leave tenant A's member active. Tenant B's listing contains only tenant B, and
both tenants hold real members, so this is isolation rather than emptiness.

Client-supplied `tenant_id`, `actor`, `status` and `authority_type` in the body
are **422 — rejected, not ignored**; in query parameters and headers they are
inert.

## 8. Audit [VERIFIED]

Creation, deactivation and role change each append to the existing
hash-chained ledger, all using `IDENTITY_EVENT` — **no new audit kind was
invented**. Each record names actor, tenant, subject, previous state and new
state. No password, token, credential or DSN appears. **A read writes no
event.**

### A defect this phase found in the existing audit model

`AuditWriterLeadership` renews its 30-second lease **only when something is
audited**. A process that governs nothing for half a minute loses writer status
*silently* and never regains it — every later mutation then commits unaudited.
Phase 10.8's grant audit had the same exposure and passed only because its
audit section ran inside the window; here the lease had lapsed and the ledger
went untouched while the log said "was not audited".

Fixed: a lapsed lease is re-acquired **once** and the append retried —
deliberately once, so a process does not fight a legitimate holder for the pen.
`J6` proves recovery by dropping the handle and showing the append still lands.

## 9. Concurrency and replay [VERIFIED — with an explicit non-claim]

```
concurrent_admit_codes               = [201, 409]
concurrent_deactivate_codes          = [200, 409]
concurrent_activate_deactivate_codes = [200, 409]   final state: active
```

Reported verbatim. Two simultaneous admissions of one subject produce **one**
membership; two simultaneous deactivations give one winner and one "already
happened". Membership mutation is last-write-wins under a conditional `UPDATE`.
No locking and no uniqueness were invented, and **exactly-once is NOT claimed.**

Replay of an admission returns 409; replay of a deactivation is a legitimate
state change reported as such.

## 10. Negative matrix — 36 cases, 0 provider writes [VERIFIED]

| Stopping layer | Cases |
|---|---|
| governance | 15 |
| membership | 13 |
| tenant_isolation | 6 |
| authentication | 2 |

Covers anonymous and forged callers; body/query/header tenant, actor, status
and authority; unauthorized creation, activation, deactivation and role change;
non-member product, grant and member-list access; cross-tenant admission,
deactivation, role change and foreign membership ids; role and authority
escalation; absent worker, provider, autonomy and deletion routes; replay of
both mutations; and **five separate deactivated-member paths** — product
access, grant listing, grant issuance, admitting, and deactivating.

`N36` rewrites a member's role to `owner` **directly in PostgreSQL** and proves
no authority appears. Per Part Q this is recorded as *legitimate store
mutability producing no authority*, **not** as tamper detection — membership is
intentionally mutable and claiming a tamper-proof property here would be false.

## 11. Crash / restart [VERIFIED]

A **real separate OS process** reads the same membership: status, role, tenant
and subject all survive. No partial membership exists — every row has a status,
a role and an attributed creator.

## 12. Performance [VERIFIED — measured, not estimated]

| Path | p50 | p95 |
|---|---|---|
| Membership lookup | 11.0 ms | 47.5 ms |
| Membership creation | 371.2 ms | 463.3 ms |
| Membership mutation | 439.0 ms | 513.1 ms |
| Authenticated product read | 235.9 ms | 468.6 ms |
| Authority resolution after membership | 76.2 ms | 111.2 ms |

**Honest note on cost.** Every authenticated product request now performs a
membership lookup, and every authority resolution performs one before reading
grants. Re-running Phase 10.7's harness on this substrate showed its queue-list
p95 rise from 333 ms to roughly 7.7 s on an accumulated database — that figure
is dominated by data volume in a long-lived phase database rather than by the
membership read (11 ms p50 here), but the added per-request read is real and is
not free. **No speculative index was added**; the table ships with a
tenant-first unique constraint and a subject/status index, and no measurement
justified more.

## 13. Architecture, regression and frontend

- `tests/architecture` — **155 passed**. **No new fitness rule was added.** Per Part Z
  none is warranted: the membership subsystem executes no provider, invokes no
  worker, reveals no credential, creates no World/Observation/Outcome/
  Verification state, and cannot grant approval, execution or autonomy. All
  membership logic lives in `backend/auth/`, already fenced by
  `BND-AUTH-CANNOT-EXECUTE` from Phase 10.5.
- **Phase 10.7's harness re-run on the new substrate — 155/155.**
- **Phase 10.8's harness re-run on the new substrate — 118/118.**
- Backend regression — **2819 passed**. Combined **2974**, the
  pre-phase baseline exactly. No test was weakened, skipped or
  allow-listed.
- Frontend — **121/121**, and no frontend file was changed.

## 14. Stop conditions — none triggered [VERIFIED]

| Stop condition | Result |
|---|---|
| JSON and PostgreSQL both authoritative | No — JSON is bootstrap input; B5 proves it decides nothing |
| Client controls tenant / membership / active state / role | No — 422 in body, inert elsewhere, no tenant in any route |
| Membership grants approval / execution / autonomy | No — §4, and no column maps to one |
| Cross-tenant membership mutation | No — closed in both the product and V1 surfaces |
| Inactive membership remains authorized | No — §5, five separate paths |
| Old token bypasses revocation | No — membership read live; window is one request |
| Historical identity rewritten | No — §5 F9, §H |
| Second membership store / RBAC / authority | None — one store, one resolver, asserted by AST scan |
| Model influences membership authority | No model is reachable from this path |
| New capability commissioned | No — still exactly one |
| Exactly-once claimed | **Not claimed** |

Part B's "new table" stop did fire; it was stopped on and documented in the
implementation map before any code was written.

## 15. Known limitations [NOT VERIFIED / DEFERRED]

1. **Tenant records themselves remain in the JSON file.** Only *membership*
   moved. `require_tenant` still reads tenant existence and activity from
   `data/tenants/tenants.json`. The cross-tenant deactivation path is closed
   because that was an authorization defect, not a storage one — but this is
   the real remaining gap and the obvious Phase 10.10. [DEFERRED]
2. **Admission and issuance are not separable.** Membership administration
   requires an `issue` grant, so a deployment wanting a member-admin who cannot
   create authority cannot express that today.
3. **Reactivation restores existing grants** (§6). Removing authority
   permanently requires revoking the grant as well.
4. **Bootstrap recurs.** The first membership in a new tenant is imported or
   provisioned out of band, as the first grant was in Phase 10.8.
5. **No membership digest, deliberately** (Part P/Q). Membership is
   intentionally mutable; integrity comes from the audit trail. There is
   therefore **no tamper detection** for membership, and none is claimed.
6. **Identity format is inherited, not fixed.** Membership and grants key on the
   bare subject; approval attribution uses `human:<subject>`. Two conventions
   coexist in the data. Changing either would rewrite historical references — a
   stop condition — so this phase preserves both and names the inconsistency.
7. **A per-request membership read was added** (§12). Real, small, and not free.
8. **No frontend.** [DEFERRED] Part S applies only if discovery proves a
   surface is needed; the DoD does not require one, and half a membership-
   management UI would be worse than none.
9. **`iam_users` remains dead code.** Discovery found it has no tenant column
   and zero references. It was left untouched rather than deleted, which is
   out of scope here but worth removing eventually.

---

## 16. Defects found and fixed during this phase

1. **The audit writer lease lapsed silently** (§8) — a real defect in the
   existing fenced audit model, affecting Phase 10.8's grant audit equally.
   Found because the exception handler logs loudly instead of passing.
2. **A missing membership store reported the *authority* store's reason.**
   `durable_membership` returned `authority_store_unavailable`, which would
   send an operator to the wrong component. Given its own reason code.
3. **The harness engine did not compose the membership store**, so every
   authority answered `membership_store_unavailable` — correct behaviour, wrong
   fixture. Composed, matching the real engine.
4. **Phase 10.7's and 10.8's harnesses called the resolvers without the new
   store**, which would have failed for the right reason at the wrong layer.
   Both were updated to supply it, and both then passed unchanged — 155/155 and
   118/118.

As in every prior phase, the verification fixtures were wrong more often than
the production code, and each was fixed to be stronger rather than removed.

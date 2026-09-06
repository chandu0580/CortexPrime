# Phase 10.10 — Durable, Governed Tenant Records
## Verification Report

**Verdict: VERIFIED — 107/107.**

Harness: `scripts/phase1010_tenant_record_harness.py`
Infrastructure: real k3d (`k3d-cortex-p99b-server-0`, v1.35.5+k3s1), real
PostgreSQL (`cortex_p1010`), real Redis, real OS process death.

Discovery **called** the tenant paths. Two findings would have been missed by
source review, and a third was missed by my discovery pass entirely and caught
by the harness.

---

## 1. Section results

| § | Area | Checks |
|---|---|---|
| A | Composition — one tenant store, one new table | 6 [VERIFIED] |
| B | Migration from JSON, and JSON stops deciding | 6 [VERIFIED] |
| C | A tenant is NOT authority | 5 [VERIFIED] |
| D | A tenant is NOT membership | 2 [VERIFIED] |
| E | An inactive tenant fails closed on every path | 12 [VERIFIED] |
| F | Reactivation — measured, not designed | 3 [VERIFIED] |
| G | Historical records remain attributable | 4 [VERIFIED] |
| H | Cross-tenant isolation | 5 [VERIFIED] |
| I | The V1 routes 10.9's guard could not reach | 6 [VERIFIED] |
| J | Audit | 5 [VERIFIED] |
| K | Concurrency | 3 [VERIFIED] |
| L | Positive matrix | 8 [VERIFIED] |
| M | Negative matrix | 35 [VERIFIED] |
| N | Crash / restart | 6 [VERIFIED] |
| O | Measured latency | 1 [VERIFIED] |
| | **Total** | **107 / 107** |

---

## 2. Three findings

### Finding 1 — the whole tenant list disclosed to any admin [VERIFIED]

```
GET /api/tenants  → 200   ['p1010a', 'p1010b', 'p1010c']
```

Phase 10.9 guarded five V1 routes that name a tenant in their **path**. This
one does not, so the guard never applied. It returned every tenant in the
system — id, slug, domain, plan, state — to any token carrying
`role == "admin"`.

**After:** `HTTP 200 slugs=['p1010a']` — the caller's own tenant only.

### Finding 2 — any admin could create a tenant [VERIFIED]

```
POST /api/tenants → 201   → tenants: [... 'planted-by-a']
```

**After:** `403`, and the harness confirms no such tenant exists.

### Finding 3 — a third JSON authorization source, found by the harness

`require_user` — the **base authentication dependency**, older than
`require_tenant` and running before it — carried its own tenant check against
the JSON file. **My discovery pass missed it.**

The harness caught it twice over: a tenant existing only in the durable store
was refused as "does not exist", and flipping the file still refused a request
the durable store permitted. Leaving it would have meant JSON and PostgreSQL
were **both** authoritative — a stop condition — while every other check in the
phase reported success.

## 3. Migration from JSON [VERIFIED]

| Check | Result |
|---|---|
| B1 deterministic import | tenants imported into `cp_tenant` |
| B2 **created no membership and no authority** | both counts unchanged across the migration |
| B3 re-runnable | second run imports 0 |
| B4 provenance | `migrated` vs `provisioned` distinguishable |
| B5 **JSON is no longer authoritative** | file flipped to `inactive`; store still reads `active` |
| B6 **and a product request still succeeds** | `HTTP 200` while the file says the tenant is off |

B6 is the one that matters. B5 alone would have passed even with Finding 3
unfixed, because it only inspects the store; B6 goes through the real request
path and is what exposed the third JSON reader.

## 4. A tenant is not authority, and not membership [VERIFIED]

Provisioning a boundary creates **zero** memberships and **zero** grants. An
existing, active tenant grants nobody approve, execute or issue — refused as
`no_tenant_membership` or, more specifically, `membership_in_another_tenant`
for a caller who belongs elsewhere. Both refusals are accepted as correct; what
is asserted is that existence confers nothing.

A valid token for a real, active tenant with no membership is refused
`no_tenant_membership` — so tenant existence never implies membership.

## 5. An inactive tenant fails closed on every path [VERIFIED]

Before deactivation the member held approve, execute **and** issue, and could
read the product. After a single out-of-band deactivation:

| Path | Result |
|---|---|
| E4 approval authority | gone — `tenant_inactive` |
| E5 execution authority | gone |
| E6 issuance authority | gone |
| E7 product access, token minted while active | **403** `Tenant is inactive or does not exist (tenant_inactive)` |
| E8 grant issuance | **403** |
| E9 grant revocation | **403** |
| E10 membership admission | **403** |
| E11 **nothing deleted** | memberships, grants and the tenant row all survive |
| E12 deactivating twice | `tenant_already_in_that_state` |

## 6. Reactivation — the measured answer [VERIFIED as measured]

```
reactivation_restores_authority = true
```

Memberships and grants survive tenant deactivation and become effective again
on reactivation, because neither was revoked and this phase invents no new
state machine. **The operational consequence is named as a trap:** removing
access permanently means revoking the grant or the membership, not only
switching the tenant off.

## 7. Historical records and digests [VERIFIED]

Grants and memberships still name the tenant after it was switched off and on;
the tenant row was never deleted.

**G4 is the load-bearing one:** every live grant still matches its own digest
after a full deactivation cycle — proving tenant state is **not** folded into
any historical digest. Had it been, deactivating a tenant would have
invalidated every approval and grant ever bound in it, which is rewriting
history.

## 8. Cross-tenant isolation and the V1 routes [VERIFIED]

Tenant B's member and grant listings contain only tenant B; tenant B cannot
deactivate tenant A's member (404); neither tenant's issuer holds anything in
the other.

| V1 route | Result |
|---|---|
| I1 `GET /api/tenants` | own tenant only |
| I2 `POST /api/tenants` | **403**, and no such tenant exists |
| I3 `POST /{own}/deactivate` | **403**, and the tenant is still active |
| I4 `POST /{foreign}/deactivate` | **404** — Phase 10.9's guard still holds |

## 9. Audit [VERIFIED]

Deactivation and activation each append to the existing hash-chained ledger
using `IDENTITY_EVENT` — **no new audit kind was invented**; the existing
grammar represents a tenant state change without stretching. Each record names
actor, tenant, previous state and new state. No password, token, credential or
DSN appears. **A read writes no event.**

## 10. Concurrency and replay [VERIFIED — with an explicit non-claim]

```
concurrent_deactivate_accepted   = [true, false]
concurrent_activate_deactivate   = ["tenant_status_changed",
                                    "tenant_already_in_that_state"]
concurrent_final_state           = "active"
replay_provision_same_slug       = "ConstraintConflict"
```

Reported verbatim. Two simultaneous deactivations: one wins on the conditional
`UPDATE`, the other is told it already happened. Re-provisioning a slug is
refused by the UNIQUE constraint rather than creating a second boundary. Tenant
state is last-write-wins; no locking was invented and **exactly-once is NOT
claimed.**

## 11. Negative matrix — 34 cases, 0 provider writes [VERIFIED]

| Stopping layer | Cases |
|---|---|
| governance | 14 |
| tenant_state | 9 |
| tenant_isolation | 9 |
| authentication | 2 |

Covers anonymous and forged callers; a nonexistent tenant in the token;
inactive-tenant product access, grant reads, member reads, approval, execution,
grant issuance and membership admission; body/query/header tenant and status;
tenant creation, activation, deactivation and slug mutation by ordinary members
(no such routes exist); cross-tenant member deactivation and grant revocation;
absent worker, provider, autonomy and deletion routes; all seven V1 tenant
routes; JSON mutation after migration; and direct database deactivation.

**N34 is recorded honestly.** A direct PostgreSQL deactivation **is honoured**
and fails closed. Per Part U that is *the store being the authority*, not a
security bypass — the distinction between legitimate mutation and tampering.

## 12. Crash / restart [VERIFIED]

A **real separate OS process** reads the same tenant: status, slug and
attribution all survive. **N5 proves an inactive tenant is not resurrected by a
restart.** No partial tenant exists.

## 13. Performance [VERIFIED — measured, not estimated]

| Path | p50 | p95 |
|---|---|---|
| Tenant lookup | 16.1 ms | 103.9 ms |
| Authenticated product read | 355.0 ms | 743.7 ms |
| Authority resolution after tenant | 178.1 ms | 239.0 ms |
| Tenant provisioning | 64.0 ms | 104.7 ms |

**Honest note on accumulated cost.** An authenticated product request now
performs a tenant read (in `require_user`), a second tenant read (in
`product_context`), a membership read and, for authority, a grant read. Across
Phases 10.8–10.10 the authenticated read path has grown from one JSON lookup to
four indexed PostgreSQL reads, and the p50 reflects that. The reads are
individually cheap (tenant 16 ms); the total is real and is not free. **No
speculative index was added** — the table ships with a primary key, a UNIQUE
slug and a status index, and no measurement justified more. Collapsing the
duplicate tenant read is the obvious optimisation and is deliberately **not**
done here, because removing a fail-closed check for speed is not a change to
make in the same phase that added it.

## 14. Architecture, regression and prior harnesses

- `tests/architecture` — **155 passed**. **No new fitness rule was added.**
  Per Part AC none is warranted: the tenant subsystem executes no provider,
  invokes no worker, reveals no credential, creates no World/Observation/
  Outcome/Verification state, and grants nothing. All tenant logic lives in
  `backend/auth/`, already fenced by `BND-AUTH-CANNOT-EXECUTE`.
- Backend regression — **2819 passed**. Combined **2974**, the pre-phase
  baseline exactly. No test was weakened, skipped or allow-listed.
- **Every prior harness re-run on the new substrate:**

  | Phase | Result |
  |---|---|
  | 10.7 scoped authority | **155 / 155** |
  | 10.8 governed grant issuance | **118 / 118** |
  | 10.9 durable membership | **107 / 107** |
  | 10.10 durable tenant records | **107 / 107** |

  This is the load-bearing regression. Moving the tenant boundary out of a
  JSON file altered nothing about what Phases 10.7–10.9 prove.
- Frontend — unchanged; no frontend file was touched, and its 121 tests were
  not re-run because nothing they cover changed.

## 15. Stop conditions — none triggered [VERIFIED]

| Stop condition | Result |
|---|---|
| JSON and PostgreSQL both authoritative | **No** — and this is the one Finding 3 would have violated. Closed and proven by B6 |
| Client controls tenant authority | No — no tenant in any product route; body fields 422 |
| Tenant existence grants membership | No — §4 |
| Tenant existence grants approval / execution / issuance | No — §4 |
| Inactive tenant remains authorized | No — §5, seven paths |
| Cross-tenant mutation possible | No — §8 |
| Old token bypasses deactivation | No — read live; window is one request |
| Historical identity rewritten | No — §7, digests intact |
| Second tenant / membership / RBAC / authority system | None — one repository, asserted by AST scan |
| Model influences tenant authority | No model is reachable from this path |
| New capability commissioned | No — still exactly one |
| Exactly-once claimed | **Not claimed** |

Part A's "new table" stop fired and was documented before implementation.

## 16. Known limitations [NOT VERIFIED / DEFERRED]

1. **`TenantManager` survives, and both JSON files remain on disk.** They are
   bootstrap input and a V1 shim — not authoritative — but present.
   `GRANDFATHERED_STORES` in `state_rules.py` is a frozen inventory that "may
   only shrink", and **neither `tenants.json` nor `tenant_users.json` was
   removed from it**, because the code still writes them. Removing the entries
   requires retiring `TenantManager` entirely, which reaches beyond this phase.
   [DEFERRED — stated rather than claimed]
2. **Tenant administration is out-of-band** and unavoidable given Part M. No
   system creates its own root boundary; the bootstrap problem recurs a third
   time.
3. **Reactivation restores authority** (§6).
4. **No tenant digest, and none claimed** (§7). Tenant state is intentionally
   mutable, so there is **no tamper detection** for it — a direct database
   change is honoured, by design.
5. **The authenticated read path now performs two tenant lookups** (§13).
   Deliberately not collapsed in this phase.
6. **`domain`, `plan` and `settings` were not migrated.** The durable record
   carries identity, slug, name and state only — Part C says not to add
   unnecessary metadata. Anything reading those fields still reads the JSON
   record, and nothing on the governed path does. [NOT VERIFIED for V1
   consumers outside the governed path]
7. **Slug is immutable by absence, not by constraint.** No mutation path
   exists and none was added; nothing enforces that a future one could not be
   introduced.
8. **`iam_users` and `organizations` remain untouched** — dead and unrelated
   respectively.

---

## 17. Defects found and fixed during this phase

1. **`require_user` was a third JSON authorization source** (§2, Finding 3) —
   missed by my discovery pass, caught by the harness through the real request
   path. This is the phase's most important finding: every other check would
   have reported success while a stop condition was live.
2. **The harness was not re-runnable.** Fixed slugs collided against the
   durable phase database on a second execution — the UNIQUE constraint
   working correctly. Provisioning is now reuse-or-create, and the constraint
   was not weakened to accommodate it.
3. **My §C assertion expected the wrong refusal.** I expected
   `no_tenant_membership`; the platform answered
   `membership_in_another_tenant`, which is *more* specific and more useful.
   The assertion was corrected to accept both and to assert what actually
   matters.

4. **Three fixture defects in the prior harnesses**, each found by re-running
   them rather than assumed absent:
   - a **syntax error** in Phase 10.7 from my own patch ordering — the tenant
     store was used before its `global` declaration;
   - Phase 10.8's one direct service call (the E4 "refused below the route
     too" check) never received the tenant store, so it refused for the wrong
     reason;
   - Phase 10.9's positive matrix used a **multi-line** resolver call that my
     single-line edit did not match, so L4/L5 answered
     `tenant_store_unavailable` — a fixture failure wearing the costume of a
     real one.
5. **A Phase 10.9 assertion was wrong about isolation.** L6 asserted that a
   tenant-A member is absent from tenant B. That is not an isolation property:
   tenant B's own admin may legitimately admit any subject to B, and 10.9's own
   negative matrix does exactly that to prove the admission lands in B rather
   than leaking into A. It passed only until the negative matrix had ever run
   against that database. Rewritten to assert the real property — every row
   tenant B returns belongs to tenant B — rather than deleted.

As in every prior phase, the verification fixtures were wrong more often than
the production code — but this time the harness also caught a real, live
authorization defect that discovery had missed.

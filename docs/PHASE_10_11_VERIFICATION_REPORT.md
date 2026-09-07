# Phase 10.11 — Retire TenantManager
## Verification Report

**Verdict: VERIFIED — 68/68.**

Harness: `scripts/phase1011_retirement_harness.py`
Infrastructure: real k3d (`k3d-cortex-p99b-server-0`, v1.35.5+k3s1), real
PostgreSQL (`cortex_p1011`), real Redis, real OS process death.

A retirement phase. The claim is that deleting legacy infrastructure changed
**nothing**, and the evidence is shaped accordingly: every assertion goes
through a real HTTP request or a child process. Phase 10.10 established why —
a store-level assertion passed there while a third JSON reader was still live.

---

## 1. Section results

| § | Area | Checks |
|---|---|---|
| A | The retirement, statically | 5 [VERIFIED] |
| B | Every governed answer comes from PostgreSQL | 5 [VERIFIED] |
| C | Mutating the legacy JSON changes nothing | 2 [VERIFIED] |
| D | Removing the legacy JSON changes nothing | 4 [VERIFIED] |
| E | A process that cannot import TenantManager serves requests | 3 [VERIFIED] |
| F | Membership semantics unchanged (10.9) | 3 [VERIFIED] |
| G | Authority semantics unchanged (10.7, 10.8) | 6 [VERIFIED] |
| H | Approval semantics unchanged (10.6, 10.7) | 4 [VERIFIED] |
| I | The retired V1 routes | 6 [VERIFIED] |
| J | Concurrency — unchanged, measured | 2 [VERIFIED] |
| K | Negative matrix | 22 [VERIFIED] |
| L | Crash / restart | 5 [VERIFIED] |
| M | Measured latency | 1 [VERIFIED] |
| | **Total** | **68 / 68** |

---

## 2. A correction to the brief's premise [VERIFIED]

The brief names `data/users/users.json`. **That file does not exist.** The two
legacy stores are `data/tenants/tenants.json` and
`data/tenants/tenant_users.json`, and the latter is the file that actually
holds user rows. Part F is answered against it.

## 3. Consumer inventory — every reference, classified

| Consumer | Class | Outcome |
|---|---|---|
| `auth_routes._tenant_claims` (login **and** refresh) | runtime production | reads `cp_tenant_membership` + `cp_tenant` |
| `dependencies.require_user` tenant check | runtime production, JSON fallback | fallback removed |
| `dependencies.require_tenant` | same | fallback removed |
| `dependencies.get_current_tenant` | **dead** — never imported, never referenced | deleted |
| `authority_routes` `members=` | **dead argument** | deleted |
| `tenant_routes` create/deactivate tails | **dead after a `raise`** | deleted |
| `tenant_routes` list / get / list_users | runtime reads | repointed at the durable stores |
| `tenant_routes` add_user / update_user_role | runtime writes — a **silent no-op trap** | refused |
| `TenantManager` mutators + `_save` + `mkdir` | the only writers of either file | deleted |
| `TenantManager` read methods | bootstrap/migration only | kept, isolated |
| harness `tm.create_tenant` / `tm.add_user` | test fixture | durable provisioning |
| `tests/test_tenant*.py` | tests of the deleted mechanism | rewritten as retirement guards |

**No consumer was left without a replacement**, so the Part B stop did not fire.

## 4. The finding: two live routes granted nothing [VERIFIED]

Phase 10.10 refused V1 *tenant* mutation and left V1 **membership** mutation
alone. Those two routes still wrote `tenant_users.json`, which stopped being
authoritative in Phase 10.9.

An operator called `POST /api/tenants/{id}/users`, received **201**, and the
person had **no governed membership at all**. The call appeared to work and
changed nothing that mattered — the same trap 10.10 avoided for tenants by
refusing rather than repointing.

| Route | Before | After |
|---|---|---|
| `POST /api/tenants/{id}/users` | 201, granted nothing | **403**, naming `/api/v1/tenants/members` |
| `PATCH /api/tenants/{id}/users/{id}` | 200, changed nothing | **403** |

`I1b` and `I2b` confirm no durable membership or role moved.

## 5. The evidence, strongest first

### E — a process that cannot import the module [VERIFIED]

A child process installs an import guard that raises on
`backend.auth.tenant` **before anything can pull it in**, then serves real
requests:

```
PRODUCT 200
GRANTS  200
MEMBERS 200
```

This is stronger than any source scan and stronger than the mutation tests: no
code path can have consulted the retired module, because importing it was
impossible.

### D — the files removed entirely [VERIFIED]

`data/tenants/` is moved aside, `D0` confirms it is gone, and every governed
answer is byte-identical:

```
{'product': 200, 'grants': 200, 'members': 200, 'approve': True,
 'execute': True, 'issue': True, 'plain_approve': False, 'cross': False}
```

`D2` re-runs a real product request at **HTTP 200** with no legacy files on
disk. The directory is restored afterwards (`D3`).

### C — the files poisoned [VERIFIED]

Every tenant switched off, every slug renamed, every member deactivated, every
member handed all three authorities in `tenant_users.json`. **Not one governed
answer moved**, and `K-poison` confirms the poisoned file granted nobody
anything.

`C0` proves this is not vacuous — both files existed and held real rows.

### A — static corroboration, not proof [VERIFIED]

- `A3` — **no module under `backend/` imports the manager any more** (AST scan
  of imports, so the docstrings that explain the retirement do not match).
- `A4` — both filenames left `GRANDFATHERED_STORES`.
- `A5` — **and the state-file rule still passes**, which is what makes `A4`
  honest rather than an edit that silenced a test. The inventory shrank from 76
  to 74 entries because the writes are gone.

## 6. Semantics unchanged

| Area | Evidence |
|---|---|
| Membership (10.9) | active reads, inactive refused, reactivation restores |
| Authority (10.7, 10.8) | approve/execute/issue each resolve; approve does not imply execute; an ungranted member holds none; a scoped issuer still issues |
| Approval (10.6, 10.7) | approver holds approve, ungranted does not, a cross-tenant approver holds nothing here, and the requester persona holds both grants so a separation refusal is about the **act**, not a missing grant |
| Tenant (10.10) | concurrency identical: `[accepted, refused]`, final state reported verbatim |

**The approval end-to-end lifecycle is [DEFERRED] here** and stated as such: it
is proven by Phases 10.7 and 10.10, both re-run in full for this phase. Building
a second copy of that regression would be a second thing to keep correct.

## 7. Negative matrix — 20 cases, 0 provider writes [VERIFIED]

| Stopping layer | Cases |
|---|---|
| governance | 11 |
| tenant_isolation | 3 |
| authentication | 2 |
| membership | 2 |
| tenant_state | 1 |
| grant_authority | 1 |

Covers mutated `tenants.json` and mutated `tenant_users.json` against real
requests; anonymous and forged callers; non-member, inactive membership and
inactive tenant; forged tenant in body, query and header; cross-tenant grant
listing; an unauthorized issuer; absent worker and provider routes; and all six
retired V1 surfaces.

## 8. Crash / restart [VERIFIED]

A **real separate OS process** reads tenant state, membership and the grant
from PostgreSQL alone. `L5`: no restart resurrected JSON authority, because the
child imported only durable repositories.

## 9. Performance — the retirement made it faster [VERIFIED]

| Path | Phase 10.10 | Phase 10.11 |
|---|---|---|
| Tenant lookup p50 | 16.1 ms | **6.5 ms** |
| Membership lookup p50 | 11.0 ms (10.9) | **7.0 ms** |
| Authenticated product read p50 | 355.0 ms | **75.2 ms** |
| Authority resolution p50 | 178.1 ms | **17.9 ms** |

Phase 10.10 named the accumulated read cost and deliberately declined to
optimise it in the phase that added it. Removing the legacy JSON reads
addressed most of it **without touching a single fail-closed check** — nothing
was made faster by checking less. No index was added and nothing was tuned;
this is the cost of the retired reads disappearing.

## 10. Architecture, regression and prior harnesses

- `tests/architecture` — **155 passed**. **No new fitness rule.** Per Part O
  none is warranted: a retirement adds no bypass, and the existing state-file
  rule is what polices the inventory.
- Backend regression — **2850 passed**, up from 2819 by the **31** rewritten
  tests (20 + 11). No test was weakened to pass.
- **Every prior harness re-run in full on the retired substrate:**

  | Phase | Result |
  |---|---|
  | 10.7 scoped authority | **155 / 155** |
  | 10.8 governed grant issuance | **118 / 118** |
  | 10.9 durable membership | **107 / 107** |
  | 10.10 durable tenant records | **107 / 107** |
  | 10.11 retirement | **68 / 68** |

  This is the load-bearing regression for a deletion phase: retiring the legacy
  infrastructure altered nothing any of them proves.
- Frontend — untouched; no frontend file changed.

## 11. Stop conditions — none triggered [VERIFIED]

| Stop condition | Result |
|---|---|
| A consumer with no replacement (Part B) | **None** — §3 |
| A product path requiring the JSON (Part C) | **None** — §5 D |
| Removal changing authentication semantics (Part G) | The login wire changed **source**, not contract: fail-closed behaviour is identical, and it now reads the store that judges the claim |
| Inventory edited to make a test pass (Part D) | No — `A5` re-runs the real rule |
| A second store / RBAC / authority | None added |
| New capability | None |
| Exactly-once | **Not claimed** |

## 12. Known limitations [NOT VERIFIED / DEFERRED]

1. **The legacy files remain on disk**, read-only and inert, as bootstrap
   import input for `migrate_json_tenants` / `migrate_json_memberships`. They
   are no longer authoritative and no longer written, which is what let the
   inventory shrink — but they are still there. Deleting them entirely means
   deciding that no installation will ever need the import again, which is a
   call for an operator, not a phase.
2. **The login wire changes which store decides a token's tenant claim.** A
   subject present only in the JSON now gets no claim. That is the correct
   direction — such a token was refused by every governed path anyway — but it
   is a behaviour change and is named as one. [VERIFIED as intended, NOT
   VERIFIED against any deployment that has not run the migrations]
3. **Authentication itself was not redesigned**, per Part G. It remains one
   env-configured user, and `TenantManager` was never part of it — it supplied
   the tenant *claim*, not the credential.
4. **`domain`, `plan` and `settings`** are reported empty by the V1 tenant
   projection because the durable record does not carry them (Phase 10.10,
   Part C). Any V1 client depending on those fields sees empty values rather
   than stale ones. [NOT VERIFIED against out-of-tree clients]
5. **`permissions` is projected empty** by the V1 member listing, deliberately:
   authority lives in `cp_authority_grant`, and a permission list beside a
   member is exactly what Phase 10.5 separated.
6. **`iam_users` and `organizations` remain** — dead and unrelated
   respectively, both out of scope here.
7. The approval end-to-end lifecycle is not re-implemented in this harness
   (§6). [DEFERRED]

---

## 13. Defects found and fixed during this phase

All four were in the **fixtures**, found by running them rather than reading
them:

1. **10.7 and 10.8 lost their `MEMBERS` map** when the JSON user object went
   away. Repopulated from the durable membership store, which carries the only
   field those harnesses wanted from it.
2. **10.9 and 10.10 lost the importer their migration sections legitimately
   need.** Over-removal on my part: reading the JSON once is the sanctioned
   bootstrap use, so it was restored locally and labelled as such rather than
   hoisted back to module scope.
3. **The 10.11 approval section was written against a helper signature that
   does not exist** (`seed_investigation` takes three arguments). Replaced with
   real authority assertions plus an explicit deferral naming where the
   lifecycle coverage actually comes from.
4. **A read-only class still created a directory.** `TenantManager.__init__`
   called `mkdir`; a reader creates nothing, and leaving it would have left a
   filesystem write in a module the inventory had just released.

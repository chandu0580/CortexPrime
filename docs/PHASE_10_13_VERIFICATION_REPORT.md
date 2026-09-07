# Phase 10.13 — Retire the V1 Tenant Read Surface
## Verification Report

**Verdict: VERIFIED — 59/59.**

Harness: `scripts/phase1013_retire_v1_reads_harness.py`
Infrastructure: real k3d (`k3d-cortex-p99b-server-0`), real PostgreSQL
(`cortex_p1013`), real Redis.

A deletion phase. The claim is that removing three consumerless routes changed
nothing governed, so every check is an executed request rather than a source
assertion.

---

## 1. Section results

| § | Area | Checks |
|---|---|---|
| A | The deletion | 5 [VERIFIED] |
| B | The retired routes answer with no body | 4 [VERIFIED] |
| C | The governed path is untouched | 10 [VERIFIED] |
| D | The four refusals survive, and still refuse | 6 [VERIFIED] |
| E | The legacy JSON is still inert | 3 [VERIFIED] |
| F | The bootstrap importer still works | 4 [VERIFIED] |
| G | Tenant isolation | 5 [VERIFIED] |
| H | The IAM module — kept, and why | 4 [VERIFIED] |
| I | Negative matrix | 17 [VERIFIED] |
| J | Measured latency | 1 [VERIFIED] |
| | **Total** | **59 / 59** |

---

## 2. What was deleted [VERIFIED]

| Item | Evidence |
|---|---|
| `GET /api/tenants` | **405**, no tenant data in the body |
| `GET /api/tenants/{id}` | **404**, no tenant data |
| `GET /api/tenants/{id}/users` | **405**, no tenant data |
| `_durable()`, `_record_to_response()`, `_membership_to_response()` | gone; no reference remains |
| `backend.api.product.app` import in `tenant_routes` | gone — only `_durable()` needed it |
| `CortexSidebar` → `/settings/tenants` | gone; `Building2` kept because `/enterprise-architecture` uses it |

Remaining router surface, asserted by enumeration:

```
POST  /api/tenants
POST  /api/tenants/{tenant_id}/users
PATCH /api/tenants/{tenant_id}/users/{user_id}
POST  /api/tenants/{tenant_id}/deactivate
```

**405 on two of the three is the stronger outcome**, not a weaker one: those
paths still carry a surviving POST, so the method is gone while the documented
refusal stays reachable.

## 3. What was NOT deleted, and why

### 3.1 The response models — not "solely for the reads" [VERIFIED]

`TenantResponse` is declared by `create_tenant` and `deactivate_tenant`;
`TenantUserResponse` by `add_user_to_tenant` and `update_user_role`. All four
are preserved refusals, so the brief's "solely" condition is not met and both
models stay (`A5`).

### 3.2 `repositories/iam.py` and the three IAM tables — the condition is not met

**The brief permits removal only if discovery confirms no runtime consumer.
There is one, and Phase 10.12 missed it.**

`H1` proves by execution that importing `backend.identity.di` — what
`backend/main.py:134` does — pulls in `backend.database.repositories.iam`. The
chain is:

```
backend/main.py
  → backend.identity.di
    → backend.identity.authentication.password_verifier
      → (package __init__ re-exports providers)
        → backend/identity/authentication/providers.py
          → backend.database.repositories.iam
```

`H2`: its three models are registered on `Base.metadata`, and
`backend/database/engine.py:210` runs `Base.metadata.create_all` inside
`init_db()` — so a **live path** creates them, not only alembic.

`H3`: a **third table the brief did not name**, `iam_api_keys`, has a foreign
key to `iam_users`. The two named tables cannot be dropped without it.

`H4`: nothing *queries* them — `.user_repo`, `.role_repo` and `.api_key_repo`
are never called, exactly as Phase 10.12 found. Dead as a data path, live as an
import.

**Migration lineage, investigated as required.** The chain is unbroken and
single-headed: `0001 → … → 0022_tenant_record`, no branches.
`0007_add_bounded_context_tables` — which creates all three IAM tables — **is
in the current HEAD lineage**, so `alembic upgrade head` does create them. They
are absent from the governed phase databases only because those are built by
`DURABLE_METADATA.create_all`, which knows nothing of the V1 ORM.

So the brief's escape hatch (obsolete lineage → no fake drop migration) does
not apply, and its precondition (proven dead) is not met. **No migration was
written**, and `A4` asserts the count is still 22.

Retiring them properly requires deleting `identity/authentication/providers.py`
and editing four more modules inside the authentication subtree this brief
preserves and whose function it requires. That is [DEFERRED], recorded in the
harness as `H5`.

## 4. The governed path is untouched [VERIFIED]

| Check | Result |
|---|---|
| C1 product access | 200 |
| C2 governed member listing — the replacement for the retired read | 200, contains the member |
| C3 governed grant listing | 200 |
| C4/C5/C6 approve / execute / issue authority | all resolve |
| C7 an ungranted member | still holds nothing |
| C8 a scoped issuer issues | 201 |
| C9 and revokes | 200 |
| C10 approval queue projects | 200 |

**[DEFERRED]** `C11` — the approval decision and governed execution end-to-end
are not re-implemented here; Phases 10.7 and 10.10 prove both and are re-run in
full (§9).

## 5. The refusals still refuse [VERIFIED]

All four return **403**, each still naming where its governed operation moved
(`D5`), and `D6` confirms the database is **unchanged** after all four —
tenant, membership and grant counts plus every membership's `(subject, status,
role)`.

## 6. The legacy JSON is still inert [VERIFIED]

`E0` first proves there is data to poison (not vacuous). Both files are then
poisoned — every tenant switched off, every member deactivated, every member
handed `approve:remediation` — and every governed answer is identical:

```
{'product': 200, 'members': 200, 'approve': True, 'plain': False}
```

Files restored afterwards (`E2`).

## 7. The bootstrap importer still works [VERIFIED]

`F1` reads the legacy files through the read-only importer; `F2` runs both
migrations; `F3` confirms **neither creates authority** (grant count unchanged);
`F4` confirms the write path is still gone — no `_save`, no `create_tenant`, no
`add_user`, no `update_user_role`.

## 8. Isolation and the negative matrix [VERIFIED]

Tenant B's listing contains only tenant B; B's issuer holds nothing in A; B
cannot deactivate A's member (404) and A's member stays active; the V1
cross-tenant guard still holds on a surviving refusal (404).

**16 negative cases, 0 provider writes:**

| Stopping layer | Cases |
|---|---|
| governance | 5 |
| tenant_isolation | 4 |
| authentication | 2 |
| membership | 2 |
| grant_authority | 2 |
| tenant_state | 1 |

Covers unauthenticated and forged callers; wrong tenant; foreign tenant id on a
surviving refusal; forged tenant in body, query and header; inactive tenant;
inactive membership; no membership; no authority; **revoked authority**; the two
retired reads probed as a bypass; and absent worker and provider routes.

## 9. Architecture, regression and prior harnesses

- `tests/architecture` — **155 passed**. **No new fitness rule.** A deletion
  adds no bypass, and the existing rules already cover the module.
- **`GRANDFATHERED_STORES`: 74 before, 74 after.** Unchanged, and correctly so
  — deleting three read routes removed no file *writer*, and the rule keys on
  writers. The inventory was **not** edited.
- Backend regression — **2850 passed** on the re-run. The first run failed 2 of
  them, both in a test module of my own and both for the right reason: they
  exercised routes this phase deleted. See §14.
- Prior harnesses re-run in full:

  | Phase | Result |
  |---|---|
  | 10.7 scoped authority | **155 / 155** |
  | 10.8 governed grant issuance | **118 / 118** |
  | 10.9 durable membership | **107 / 107** |
  | 10.10 durable tenant records | **107 / 107** |
  | 10.11 retirement | **68 / 68** |
  | 10.13 this phase | **59 / 59** |

- Frontend — one line removed from `CortexSidebar.tsx`; `npx tsc --noEmit`
  reports the same **5 pre-existing errors**, none in that file.

Two harnesses were updated because they asserted against deleted routes —
10.9's cross-tenant check and 10.11's I3/I4. Neither was weakened to pass:
both now assert the routes are **gone**.

## 10. Security [VERIFIED]

No credential path, provider path, worker path, execution path, governance
authority or truth authority was added. **0 authorities, 0 roles, 0
permissions, 0 tables, 0 migrations, 0 fitness rules.** `A3` and `A4` assert
the table and migration counts are unchanged.

## 11. Performance — a baseline only

| Path | p50 | p95 |
|---|---|---|
| Tenant lookup | 135.9 ms | 165.2 ms |
| Membership lookup | 73.5 ms | 298.6 ms |
| Authenticated product read | 284.9 ms | 984.3 ms |
| Governed member listing | 279.8 ms | 385.2 ms |
| Authority resolution | 65.6 ms | 114.0 ms |

**These are not comparable with Phase 10.11's numbers and are not presented as
such.** They were taken on a fresh database while five other harnesses and two
pytest suites were running on the same machine, and the p95 spread (985 ms on a
read whose p50 is 285 ms) shows the contention directly. Nothing was optimised
and no index was added; a deletion phase has no performance claim to make, and
inventing an improvement from a noisy sample would be worse than reporting the
noise.

## 12. Stop conditions and Definition of Done

No stop condition fired. Every DoD item is met except two, both stated:

- **IAM tables not removed** — justified in §3.2, which the DoD explicitly
  permits ("IAM tables removed **OR** their non-removal is justified").
- **Dead IAM module not removed** — same reason. The DoD lists it
  unconditionally, but the brief's own removal condition ("only if discovery
  confirms it has no runtime consumer") is not satisfied, and the brief
  instructs: *"Do not force deletion merely to make the phase look complete."*
  Where the two conflict, the instruction not to force it governs.

## 13. Known limitations

1. **`repositories/iam.py`, `iam_users`, `iam_roles` and `iam_api_keys`
   remain** (§3.2). Retiring them is a change inside the authentication
   subtree, needing its own phase and its own evidence.
2. **The retired reads return 405 rather than 404** on two paths, because a
   POST still shares them. Accurate, and worth knowing for anyone reading logs.
3. **All three Admin sidebar links were dead**, not just the one removed.
   `/settings/autonomy` and `/settings/retention` also have no page. Only the
   authorised link was removed; the other two are reported, not fixed.
4. **The performance numbers are contended** (§11) and should not be compared
   with earlier phases.
5. **Approval decision and governed execution end-to-end are deferred** to the
   10.7 and 10.10 harnesses rather than duplicated here.
6. The `V1` response models remain, carrying three fields with no authoritative
   source, because four surviving refusals still declare them.

---

## 14. Defects found during this phase

1. **I updated the two harnesses that assert against the deleted routes and
   missed the pytest module.** The first regression run failed
   `test_a_foreign_tenant_is_not_found[<lambda>2]` and
   `test_listing_without_a_composed_engine_is_empty_not_a_crash` — both in
   `tests/test_tenant_routes.py`, which I wrote in Phase 10.11 and which
   exercised two of the three routes deleted here.

   Both were rewritten to assert the **retirement** rather than the old
   behaviour: the cross-tenant guard now covers only the routes that still
   name a tenant, and a new parametrised case requires all three reads to
   answer 404/405 with no tenant data. Neither was weakened to pass; each
   asserts something stronger than before, because "the route is gone" is a
   stronger property than "the route is scoped".

   The module docstring still claimed the reads had been *repointed* rather
   than removed — true when Phase 10.11 wrote it, false after this phase. It
   was corrected in the same pass.

2. **A third harness asserted against a deleted route, and I missed it too.**
   Phase 10.10's `I1` required `GET /api/tenants` to return 200 with at most
   one tenant — the narrowing that phase introduced. With the route gone it
   answered 405, so the check failed on its own success.

   Its *intent* — "this route no longer discloses every tenant in the system" —
   is satisfied more strongly than before: there is no listing left to disclose
   anything. The assertion now accepts either outcome and says so, and the
   harness returned to 107/107.

   Three harnesses and one pytest module needed the same correction. Finding
   them one failure at a time, rather than by searching for every caller of the
   deleted routes before running anything, cost three extra cycles.

3. **Phase 10.12's discovery was incomplete on `repositories/iam.py`**, and
   this phase's investigation caught it before anything was deleted. §3.2 has
   the detail; the practical lesson is that *"never called"* and *"not
   imported"* are different questions, and a package `__init__` re-export
   answers the second one differently from the first.

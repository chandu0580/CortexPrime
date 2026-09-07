# Phase 10.14 — Retire the Dead IAM Subsystem
## Verification Report

**Verdict: VERIFIED — 52/52.**

Harness: `scripts/phase1014_retire_iam_harness.py`
Infrastructure: real k3d, real PostgreSQL, real Redis, real child processes,
and four real databases created and destroyed by the harness.

Every metadata and `create_all` claim runs in a **child process**. The parent
has already imported half the codebase, so asking it whether a module is
imported would answer a question about this process rather than about a boot.

---

## 1. Section results

| § | Area | Checks |
|---|---|---|
| A | The dependency graph is cut | 5 [VERIFIED] |
| B | Part D — models off `Base.metadata` | 2 [VERIFIED] |
| C | Part J — two database scenarios | 5 [VERIFIED] |
| D | Part K — the create_all trap | 3 [VERIFIED] + 1 [DEFERRED] |
| E | The IAM tables where they existed | 1 [VERIFIED] |
| F | Part B — authentication | 4 [VERIFIED] |
| G | Part G — the governed path | 10 [VERIFIED] |
| H | Tenant isolation | 5 [VERIFIED] |
| I | Part I — the V1 surface | 4 [VERIFIED] |
| J | Negative matrix | 12 [VERIFIED] |
| K | Measured latency | 1 [VERIFIED] |
| | **Total** | **52 / 52** |

---

## 2. Part A — the dependency graph, and what Phase 10.13 could not see

Phase 10.13 found **one** edge into `repositories.iam`. There are **three**:

```
backend/main.py → backend.identity.di
  ├─ → identity.authentication.password_verifier
  │      └─ (package __init__ re-exports providers) → repositories.iam   [1]
  ├─ → backend.database.repositories.factory        → repositories.iam   [2]
  └─ backend/database/models/__init__                → repositories.iam   [3]
```

Cutting only edge 1 would have left the subsystem alive. Edge 2 is a direct
import for three `RepositoryFactory` accessors — `user_repo`, `role_repo`,
`api_key_repo` — **none ever called**. Edge 3 is a side-effect import whose
whole purpose is registering the models.

| Check | Result |
|---|---|
| A1 V1 boot no longer imports `repositories.iam` | `IAM_IMPORTED False` in a fresh interpreter |
| A2 `register_identity_services()` still wires its nine services | `DI_OK True` |
| A3 both modules deleted | `providers.py`, `repositories/iam.py` gone |
| A4 `PasswordVerifier` survives and works | hashes and verifies; rejects a wrong password |
| A5 the factory keeps every other repository | 12 repositories kept, the three IAM accessors gone |

## 3. Part D — the models are off `Base.metadata` [VERIFIED]

Asked **after** `_ensure_bc_models()`, which is what `init_db()` calls — a
partial import would answer a question nothing in production asks.

```
IAM_TABLES []
TOTAL 38
```

No `iam_*` table is registered, and 38 others still are: a removal, not a
collapse.

## 4. Part J — two database scenarios, converging [VERIFIED]

| Check | Result |
|---|---|
| C1 fresh database → migrate to head | **55 tables, no `iam_*`** |
| C1b and the governed tables are there | `cp_tenant` and `cp_authority_grant` present |
| C2a a database seeded to `0022` really has them | `['iam_api_keys','iam_roles','iam_users']` |
| C2b the new migration removes all three | none left |
| C3 both scenarios converge | fresh 55 = legacy 55 |

**C1b and C2a exist because C1 alone would pass vacuously.** The first run of
this harness proved that: `alembic`'s `env.py` builds its own async DSN from
`POSTGRES_URL` and ignores `sqlalchemy.url`, so nothing migrated, the database
stayed empty, and "no `iam_` table" passed on an empty schema. C1b caught it.

## 5. Part K — the create_all trap, and a pre-existing defect [VERIFIED]

| Check | Result |
|---|---|
| D1 after the application's own initialisation, IAM tables are **absent** | `IAM_AFTER []` |
| D2 because they are not in `Base.metadata` at all | `IAM_IN_METADATA []` — Phase 10.13's H2 recorded the opposite |
| D3 `create_all` fails on a **pre-existing** defect unrelated to IAM | `NoReferencedTableError: reflection_history.mission_id → missions` |
| D4 `init_db()` on a fresh database | **[DEFERRED]** — see below |

**`init_db()` cannot complete on any database, and this phase did not cause
it.** `Base.metadata.create_all` raises on
`reflection_history.mission_id → missions`: no model anywhere declares
`__tablename__ = "missions"` — the table is created by migration `0001` and
never mapped.

The deleted module defined exactly `iam_users`, `iam_roles` and
`iam_api_keys`, so removing it cannot be why `missions` is absent. D3 asserts
both halves — the IAM tables stay absent **and** the failure names `missions`
rather than anything IAM — so the trap is answered rather than excused.

**Reported, not repaired.** Fixing it means mapping or removing a V1 table,
which this brief does not authorise and which deserves its own evidence.

## 6. Part F — data safety, established before any deletion [VERIFIED]

Checked across every database on the instance *before* a line was changed:

```
cortex_p99b: tables=3  users=0  roles=0  api_keys=0
```

Exactly one database had them; all three were empty. No authoritative product
state, nothing to migrate, and no invented data migration. The stop condition
did not fire.

`E1` re-checks `cortex_p99b` and finds it already clean — an earlier run of
this harness had migrated it. The load-bearing proof that the migration works
on a database that genuinely holds the tables is `C2a`/`C2b`, which seeds one
deliberately.

## 7. Part B — authentication [VERIFIED]

| Check | Result |
|---|---|
| F1 a wrong password is rejected | the env-configured path is live and did not become permissive |
| F2 an unknown user is rejected | |
| F3 an authenticated member reaches the product | 200 |
| F4 the login/refresh tenant-claim wire imports and is callable with IAM gone | `CLAIMS_CALLABLE True` |

Authentication is `verify_credentials` against `CORTEX_USER` /
`CORTEX_PASSWORD_HASH`; the tenant claim comes from `cp_tenant_membership` and
`cp_tenant`. Neither ever touched `iam_*`.

## 8. Parts G, H, I — the governed path, isolation, and V1 [VERIFIED]

Tenant lookup, membership lookup, approve/execute/issue authority, an
ungranted member holding nothing, grant issuance (201), grant revocation (200),
the approval queue and the member listing all still work.

Isolation: tenant B sees only tenant B; neither tenant's issuer holds anything
in the other; B cannot deactivate A's member (404) and A's member stays active.

V1: still exactly **four** routes, all mutations, **no GET** (Phase 10.13's
retirement holds), all four refusing with 403, and **no IAM route of any kind**.

**[DEFERRED]** `G11` — the approval decision and governed execution end-to-end
are not re-implemented here; Phases 10.7 and 10.10 prove both and are re-run in
full.

## 9. Negative matrix — 11 cases, 0 provider writes [VERIFIED]

| Stopping layer | Cases |
|---|---|
| tenant_isolation | 3 |
| authentication | 2 |
| membership | 2 |
| grant_authority | 2 |
| governance | 1 |
| tenant_state | 1 |

Covers unauthenticated, malformed token, inactive tenant, inactive membership,
no membership, foreign tenant on a surviving V1 refusal, forged tenant in body,
header and query, no authority, and **revoked authority**.

**[DEFERRED]** an expired or revoked *approval* — this harness runs against a
fresh database with no stale approval in it. Phases 10.7 and 10.10 cover both
states and are re-run for this phase; manufacturing one here would have added a
second copy of a regression that already exists.

## 10. Architecture, regression and prior harnesses

- `tests/architecture` — see §12. **No new fitness rule.** A retirement adds no
  bypass.
- **`GRANDFATHERED_STORES`: 74 before, 74 after.** Unchanged, and correctly so
  — the IAM subsystem was a *database* store, not a file store, and the rule
  keys on file writers. The inventory was **not** edited.
- **`GRANDFATHERED_REPOSITORIES`: 42 before, 39 after** — and this one shrank
  because an existing gate demanded it, not because I went looking.

  The first architecture run failed
  `test_tenancy_guard.py::test_the_ratchet_has_no_stale_entries`, whose
  docstring states the reason exactly: *"A stale entry silently widens the
  exemption: a future repository reusing the name inherits a pass it never
  earned."* `UserRepository`, `RoleRepository` and `ApiKeyRepository` were
  grandfathered exemptions from the tenancy guard, and this phase deleted the
  repositories they named — leaving three exemptions that any future class
  reusing those names would have inherited for free.

  Removing them is the ratchet doing its job: it noticed the retirement was
  incomplete and said so. This is not a test edited to pass — the entries were
  removed **because the repositories are gone**, and the guard then passed
  19/19 on its own terms.
- Backend regression and the six prior harnesses — see §12. Two of the six
  did not pass on their first re-run; §12.1 and §12.2 give the cause of each
  and what was done about it. Neither was a regression from this change.

## 11. Security [VERIFIED]

No credential path, provider path, worker path, execution path, governance
authority or truth authority added. **0 authorities, 0 roles, 0 permissions,
0 tables created.** One migration, and it only drops.

## 12. Results

| Gate | Result |
|---|---|
| `scripts/phase1014_retire_iam_harness.py` | **52/52 VERIFIED**, 11 negatives, 0 provider writes |
| `tests/architecture` | **155 passed** |
| Backend regression (`pytest tests/`) | **2852 passed** |
| Phase 10.7 harness | **155/155 VERIFIED** — unchanged |
| Phase 10.8 harness | **118/118 VERIFIED** — unchanged |
| Phase 10.9 harness | **107/107 VERIFIED** — unchanged |
| Phase 10.10 harness | **107/107 VERIFIED** — unchanged |
| Phase 10.11 harness | **68/68 VERIFIED** — unchanged |
| Phase 10.13 harness | **60/60 VERIFIED** — was 59; see §12.2 |

### 12.1 An expired certificate, mistaken for a regression [VERIFIED]

The first re-run of the Phase 10.7 harness reported **150/155**, with five
failures that all sat on the governed execution leg: `D6`, `E3` and `E4`
answered HTTP 409, and `K5` and `L1` showed a `None` executor. Part Q stop
condition 8 is *"removing IAM changes execution semantics"*, so this was
treated as a possible stop rather than as noise.

It was not the retirement. The chain of evidence:

1. `D1`–`D4` still passed — four differently-wrong callers were still refused
   `403` naming the exact failed dimension, so authority resolution was intact.
   Only the *permitted* execution failed.
2. `provider_writes = 0` on every failure, established by reading deployment
   generations from the cluster — nothing was mutated.
3. The refusal body, once captured, named its own layer: *"the governed chain
   refused this action: the envelope did not complete; whether the worker
   performed the restart is unknown from here."*
4. Instrumenting `ProviderChannel.send` from **outside** the process (a probe,
   no production change) gave `delivery=NOT_ATTEMPTED`,
   `failure=UNAVAILABLE`, *"the destination refused the connection"*, against
   the correct endpoint `https://127.0.0.1:18099/execute`.
5. The worker answered `curl -k` with `200` — which is exactly why it looked
   healthy. With **verification enabled** it answered
   `CERTIFICATE_VERIFY_FAILED: certificate has expired`.
6. The certificate: `CN=cortex-contained-worker`, `notAfter = Sep 7 09:35:31
   2026 GMT` = **15:05:31 IST today**. `scripts/phase99b_provision.sh` mints it
   with `-days 2` — disposable infrastructure, provisioned Sep 5.

The last passing run of this harness finished at **15:06:58**; its execution
happened before the expiry. The failing run began at **16:10**. The window is
dated and unambiguous, and no source change sits inside it.

**The platform behaved correctly throughout.** It refused to send a credential
over a connection it could not verify, and it reported the result as
**UNKNOWN — not failure**: `ambiguous=True`, `succeeded=False`, and a message
that says in words that this side cannot tell whether the worker acted. An
expired provider certificate is precisely the case where claiming "the write
failed" would be a lie.

**Repair, not workaround.** The certificate was regenerated with the same
subject and SAN by the same command the provisioning script uses, the
`worker-tls` secret replaced, `ca-bundle.pem` rebuilt, and the worker rolled
out. Verification was never disabled. The harness was re-run: **155/155
VERIFIED**, identical to its pre-10.14 result, with one real provider write and
the negative matrix at zero.

The only harness edit was to the three failing checks' **detail strings**,
which now include the response body. The assertions are byte-identical. That
they printed `HTTP 409` and nothing else is why this took four runs to place,
and is itself a finding.

### 12.2 Four checks in the 10.13 harness that this phase invalidated on purpose

The Phase 10.13 harness reported **55/59**. All four failures were assertions
that Phase 10.14 was explicitly authorised to make false:

| Check | Asserted | Now |
|---|---|---|
| `A4` | the lineage is exactly 22 migrations | 23 — `0023_retire_iam` |
| `H1` | `repositories/iam.py` **is** imported at V1 boot | it is not |
| `H2` | its three models **are** on `Base.metadata` | they are not |
| `H3` | `iam_api_keys` holds an FK to `iam_users` | the module is gone |

`H1`–`H3` were 10.13's stated *reason* for declining to delete the module: a
drop migration would have been undone by `create_all`. ADR-106 records that
condition, and this phase's whole mandate was to remove it.

They were **inverted, not deleted**. Deleting them would erase the evidence
that the coupling was ever real; inverting them means the checks now fail if
the subsystem ever returns. `A4` was making a claim about *its own phase's*
delivery — "10.13 added no migration" — expressed as a ceiling on the whole
lineage, which any later phase would break; it now asserts what it meant, and
stays true as the lineage grows. `H5`, previously a `deferred()` entry reading
*"dropping the IAM tables: not done"*, became a real check that the drop is a
**forward** migration with `0007` still intact. That is why the total went from
59 to 60: a deferral was discharged, not a check removed.

Re-run: **60/60 VERIFIED.**

## 13. Performance — a baseline

| Path | p50 | p95 |
|---|---|---|
| Credential check | 0.2 ms | 0.4 ms |
| Membership lookup | 7.0 ms | 8.2 ms |
| Authenticated product read | 134.9 ms | 295.6 ms |
| Authority resolution | 22.0 ms | 25.6 ms |

Measured while other work shared the machine. Nothing was optimised; a
retirement has no performance claim to make.

## 14. Stop conditions

| # | Condition | Result |
|---|---|---|
| 1 | IAM still authoritative anywhere | **No** |
| 2 | IAM holds state product authentication needs | **No** — all three empty, §6 |
| 3 | IAM tables referenced by a live governed path | **No** |
| 4–8 | Removing IAM changes tenant / membership / authority / approval / execution semantics | **No** — §8, and §12.1 for the execution leg, where an expired worker certificate was investigated as a possible stop and proved to predate nothing in this change |
| 9 | `create_all` recreates the IAM tables | **No** — §5 |
| 10 | Migration order cannot safely remove the FK chain | **No** — child first, and reversible |
| 11 | A V1 route secretly depends on IAM | **No** — §8 |

None fired.

## 15. Known limitations

1. **`init_db()` is broken independently of this phase** (§5). Reported, not
   repaired, because repairing it means touching a V1 table mapping this brief
   preserves.
2. **`E1` was weakened by an earlier run of this harness** having already
   migrated `cortex_p99b`. `C2a`/`C2b` carry that proof instead, on a database
   seeded for the purpose.
3. **An expired/revoked approval is deferred** to the 10.7 and 10.10 harnesses
   (§9).
4. **Approval decision and governed execution end-to-end are deferred** to the
   same two harnesses (§8).
5. `migrations/0007` still *creates* the three tables before `0023` drops them.
   That is the cost of not rewriting history, and it is deliberate.
6. Performance figures were taken under contention and should not be compared
   across phases.
7. **The contained worker's TLS certificate is minted with `-days 2`** and
   expired mid-verification (§12.1). It has been regenerated, and it will
   expire again on **2026-09-09**. Any harness that executes will fail the same
   way — refusing at the transport with an *unknown* outcome — until it is
   re-minted. This is a property of the disposable phase-9.9B infrastructure,
   not of the product, and it is recorded here so the next phase recognises the
   symptom in one run rather than four.
8. **Two prior-phase harnesses were edited by this phase.** In 10.7, only three
   `check()` detail strings, to print the response body; the assertions are
   unchanged. In 10.13, `A4` and section `H` were re-pointed because this phase
   invalidated what they asserted (§12.2). Neither edit was made to turn a
   failing check green — 10.7's five failures were fixed by repairing the
   environment, and 10.13's four were assertions about a condition this brief
   authorised removing.

---

## 16. Defects found during this phase

1. **My alembic driver ignored `env.py`'s DSN resolution.** `env.py` builds an
   async DSN from `POSTGRES_URL`; I set `sqlalchemy.url`, so nothing migrated
   and the "no `iam_` table" check passed on an **empty database**. `C1b` — a
   check written specifically to make `C1` non-vacuous — caught it. Fixed to
   set `POSTGRES_URL`.

2. **My first `downgrade()` reinterpreted `0007` instead of copying it.** It
   used `UUID(as_uuid=True)` for `sa.Uuid()`, dropped the `gen_random_uuid()`
   and `NOW()` defaults, and invented `scopes` and `last_used_at` on
   `iam_api_keys` while omitting the real `last_prefix` and `is_active` — all
   while the docstring claimed it was copied column for column. Checking it
   against the original caught it before commit.

3. **My `PasswordVerifier` probe guessed the API** (`hash`/`verify` rather than
   `hash_password`/`verify_password`), so `A4` failed on a class that was
   working correctly.

4. **I truncated `tests/test_identity_auth.py` at the first deleted class and
   left its imports.** The module still did
   `from backend.identity.authentication.providers import …`, so the whole file
   failed to collect — a regression *error*, not a failure, which is why it
   showed as `1 error` rather than a count. Fixed by removing the dead imports
   and the now-unused `uuid`/`datetime`/`unittest.mock` ones with them, and by
   moving the explanation into a module docstring. `TestPasswordVerifier`
   passes.

5. **My Part D and Part K probes skipped `_ensure_bc_models()`**, which
   `init_db()` calls first — so they exercised a path production never takes
   and failed on the unrelated `missions` foreign key. Corrected to mirror
   `engine.py:202,210`, which is also what surfaced the pre-existing defect in
   §5 properly rather than as noise.

Five defects, all in my own verification rather than the production change —
the same pattern every phase in this family has produced, and the reason none
of these checks is allowed to be a source assertion.

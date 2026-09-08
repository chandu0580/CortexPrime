# Phase 10.20 — Discover and Reconcile `cost_tracking`
## Verification Report

**STATUS: COMPLETE.** Discovery established the contract from four independent
sources; the repair is a model correction; no migration; the real write path
persists; the canary was proven non-vacuous against the old model.

**Files changed: 2.** `backend/database/models/cost_tracking.py` (aligned to
`0004`–`0006`), `backend/database/models/__init__.py` (registers it).
**Files added: 1.** `tests/database/test_cost_tracking_write_path.py`.
**Not changed:** `cost_engine.py` — including its error handling — every
migration, every caller, every route, the durable store, and every other model.

Every claim below was produced by running something.

---

## 1. Section results

| § | Result |
|---|---|
| Discovery (11 inspection points, both directions) | **PASS** — §2 |
| Canonical contract | **migrations `0004`→`0005`→`0006`**; `extra` JSON |
| Real write reproduction (no mocks) | **PASS** — defect reproduced independently, §3 |
| Error-semantics classification | **data-integrity defect**, intentional swallowing, **unchanged** — §4 |
| Repair decision | **A — MODEL CORRECTION** — §5 |
| Metadata registration | **registered, with reason** — §5 |
| Migration | **none required, none created** |
| Model vs reflected table | **PASS** — §6 |
| Real write after repair | **PASS** — 1 row, payload round-trips — §6 |
| Write-path regression test | **4/4 PASS**; **3/4 FAIL against the old model** (non-vacuous) — §7 |
| Alembic | before 134 op lines / 5 `cost_tracking`; **after 129 / 0**; other 129 byte-identical — §8 |
| Metadata closure | 40 tables, 0 unresolved FK targets — §8 |
| Architecture gate | **155 passed** |
| Backend regression | 75 failed / **6779 passed** / 36 skipped / 58 xfailed / 24 errors — the Phase 10.18 baseline (75 / 6775 / 36 / 58 / 24) **plus exactly the four new write-path tests**; every other count byte-identical |
| Prior-phase harnesses | 10.7 **155/155** · 10.8 **118/118** · 10.9 **107/107** · 10.10 **107/107** · 10.11 **68/68** · 10.13 **60/60** · 10.14 **53/53** — all VERIFIED, all `rc=0` (no shutdown hang this chain); 10.16 metadata probe holds; 10.19 readiness `ready: true` |
| Phase 10.19 readiness re-check | `ready: true, missing_tables: []` on fresh and existing |
| Provider writes | **0** |

---

## 2. Discovery

### Schema → application — migrations `0004`, `0005`, `0006`, reflected from a migration-built database

| Column | Type | Null | Default | Source |
|---|---|---|---|---|
| `id` | uuid | no | `gen_random_uuid()` | `0004` integer → `0006` uuid, *"match UUIDPrimaryKeyMixin"* |
| `mission_id`, `user_id`, `session_id` | varchar(255) | yes | — | `0004` |
| `provider`, `service` | varchar(64) | no | — | `0004` |
| `model` | varchar(128) | yes | — | `0004` |
| `prompt_tokens`, `completion_tokens`, `total_tokens` | integer | no | 0 | `0004` |
| `units`, `cost_usd` | double precision | no | 0 | `0004` (`sa.Float()`) |
| `report_date` | date | no | — | `0004` |
| **`extra`** | **json** | yes | — | `0004` |
| `created_at` | timestamptz | no | `now()` | `0004` |
| `updated_at` | timestamptz | no | `now()` | `0005`, *"(TimestampMixin)"* |

PK `id`; **0 foreign keys**; indexes `ix_cost_tracking_mission_date`,
`ix_cost_tracking_user_date`, `ix_cost_tracking_provider_date`,
`ix_cost_tracking_report_date`.

`0005` and `0006` say in their own docstrings that they exist to bring the
schema into line with the model's mixins. The lineage was **deliberately**
aligned to the model on `id` and the timestamps — and kept `extra`.

### Application → schema — the model before this phase

Four disagreements: the payload mapped to a column named **`extra_data`**
(`JSONB`) where the table has **`extra`** (`json`); `mission_id` `String(36)`
and `user_id` `String(128)` where the table has 255; six `index=True` markers
and three `idx_cost_*` composite indexes no migration created, and the
`ix_cost_tracking_report_date` index undeclared. **Not imported by
`models/__init__.py`** → off `Base.metadata`.

### Writers, readers, consumers — all classified

- **Writer:** `cost_engine.record()` only — `session.add(CostRecord(...))`,
  `commit()`. Callers: `mission_runtime.py:326,1285`,
  `mission_library/executor.py:278`. **Every caller uses
  `asyncio.ensure_future`**; the only `await` of `record()` in the repository is
  the engine's own docstring.
- **Readers:** `daily_summary`, `provider_breakdown`, `mission_cost`,
  `user_cost`, `executive_summary` — aggregate `select()`s over `report_date`,
  `cost_usd`, `total_tokens`, `provider`, `model`, `mission_id`, `user_id`.
  **None projects `extra`.** This is why reads have always worked.
- **API / services:** `cost_routes.py` (5 endpoints), `enterprise_cost_anomaly_monitor`,
  `enterprise_recommendation_engine` — all through the engine.
- **Repositories:** none; the engine uses `AsyncSessionLocal` directly.
- **Retention:** `run-retention-policy.py:49` **skips** DB-backed categories
  including `cost_tracking`.
- **Inventory:** `legacy_persistence_inventory.py:152` records `KEEP` — *"not
  an authority input to anything, and nothing in the governed path reads it."*
- **Tests:** `test_cost_engine_provider_alias.py` exercises the pure
  `estimate_cost()`; `test_cost_anomaly_monitor.py` mocks `provider_breakdown`.
  **No test anywhere asserted a persisted row.**
- **Hidden consumers:** none found. `extra_data` elsewhere in the tree is the
  unrelated Python `logging` attribute (`core/logging_config.py:31`).

### `extra` vs `extra_data` — same concept, established four ways

1. The model's own **attribute** is `extra`; only its column-name override says
   `extra_data`. Its docstring section is "Extended payload".
2. `record()`'s public parameter is **`extra`**, and what callers pass is
   free-form per-call metadata — `{objective, confidence, has_browser,
   response_length}`, `{mission_name, mission_category, status}`.
3. **No contract exposes either name**: no reader projects it, no route returns
   it, no repository names it.
4. **No historical row depends on either.** Every database on the instance that
   has the table has `extra`; **none has `extra_data`**; all hold **0 rows**.
   Model and `0004` landed in the same GA commit (`a108839`) already
   disagreeing; the model has said `"extra_data"` since its first line.

---

## 3. Real write reproduction — no mocks

The genuine `cost_engine.record()`, the genuine `AsyncSessionLocal`,
`POSTGRES_URL` pointed at a database built only by `alembic upgrade head`:

```
BEGIN (implicit)
INSERT INTO cost_tracking (mission_id, user_id, session_id, provider, service, model,
  prompt_tokens, completion_tokens, total_tokens, units, cost_usd, report_date,
  extra_data, id, created_at, updated_at) VALUES (...)
ROLLBACK
WARNING backend.analytics.cost_engine: cost_engine.record failed:
  UndefinedColumnError: column "extra_data" of relation "cost_tracking" does not exist
CALLER RECEIVED: None (no exception propagated)
ROWS PERSISTED: 0
```

SQL reached, exception, transaction rolled back, caller told nothing, nothing
persisted. The Phase 10.17 finding is reproduced independently.

---

## 4. Error semantics — classified, not changed

`record()` wraps everything in `except Exception as exc:
log.warning("cost_engine.record failed: %s", exc)`. Every reader in the
module does the same and returns a fallback. The pattern is consistent and
evidently deliberate: fire-and-forget metering must not take the mission
runtime down, and every caller reinforces that with `ensure_future`.

**It is a data-integrity defect by the brief's definition** — a persistence
failure is converted into apparent success, and no caller can distinguish the
two. This phase **does not change those semantics**: doing so would be a
behaviour change the evidence does not ask for. It removes the cause and adds a
test that asserts persistence directly, so silent loss cannot recur undetected.
The test also pins the semantics as they are (§7).

---

## 5. Repair — A. MODEL CORRECTION

The lineage is canonical (ADR-109), was deliberately aligned to the model where
that was intended (`0005`, `0006`), and kept `extra`. Same concept, no contract
exposure, no data on either side, readers indifferent. The model is corrected:
`extra` → column `extra`, type `JSON`; `mission_id`/`user_id` → `String(255)`;
the six unmigrated `index=True` markers removed; the four `ix_cost_tracking_*`
indexes declared by name. Mixins kept — `0005`/`0006` made the schema match
them.

**Rejected:** B renames a column no code or data needs renamed, under a
lineage that had two chances and chose not to. C has nothing to reconcile —
zero rows. D fails on the evidence. E is unwarranted.

**Registered because** it is a live persisted concept with a real writer;
unregistered, autogenerate proposes `drop_table('cost_tracking')` (a data-loss
trap), `init_db()` never creates it, and drift on it cannot be detected. That is
the reason; the diff going quiet is the consequence.

**No migration:** the schema is correct and complete.

---

## 6. After the repair

**Model vs reflected table** (migration-built database): every column
present, same names, same nullability; `extra` is `JSON`/`json`; `String(255)`
throughout; PK `id`; **indexes identical by name and columns**; 0 FKs on both.
Two probe artefacts are recorded rather than hidden: `sa.Float` compiles to
`FLOAT` and reflects as `DOUBLE PRECISION` (the *migration* declares
`sa.Float()` — identical at source, and §8 shows Alembic agrees), and the
mixin columns sit last in the class (declaration order is not a schema
contract; INSERTs are by name).

**The real write, again:**

```
INSERT INTO cost_tracking (..., report_date, extra, id, created_at, updated_at) VALUES (...)
COMMIT
CALLER RECEIVED: None
ROWS PERSISTED: 1
anthropic chat_completion claude-sonnet-5 tokens=150 usd=0.001050 extra={"objective": "repro", "confidence": 0.5}
```

---

## 7. Write-path regression test — real database, no mocks, proven non-vacuous

`tests/database/test_cost_tracking_write_path.py`. Creates a brand-new
database, runs `alembic upgrade head` on it, binds the **real**
`AsyncSessionLocal` (a real `async_sessionmaker` over a real
`create_async_engine`, `NullPool`) to it, drives the unmodified `record()`,
and verifies through an **independent psycopg2 connection**. Skips visibly if
no database is reachable; drops its database afterwards.

| Test | Asserts |
|---|---|
| `test_record_persists_a_row_readable_independently` | **the canary** — count rises by 1; provider/service/model/tokens/date/cost stored; `extra` round-trips as JSON |
| `test_repeated_calls_each_persist` | three calls in one loop → three rows, in order |
| `test_a_failing_write_rolls_back_and_is_reported_not_raised` | `provider=None` hits the NOT NULL at the database; `record()` returns `None`, **logs the warning**, persists **nothing** — the semantics as they are, pinned |
| `test_model_matches_the_migrated_table` | column set, type affinity, lengths, nullability, index names vs reflection |

```
4 passed in 16.94s        remaining cortex_test_cost_ DBs: 0
```

**Sensitivity — stop condition 11.** With the correction stashed (old model:
`extra_data`, unregistered), the same file:

```
FAILED test_record_persists_a_row_readable_independently   assert 0 == (0 + 1)
FAILED test_repeated_calls_each_persist                     assert 0 == (0 + 3)
FAILED test_model_matches_the_migrated_table
3 failed, 1 passed
```

The canary fails on the old model. The one pass is the failure-semantics test,
which is correct — the swallowing is the same either way. Tree restored from a
byte-copy taken before stashing (Phase 10.18's CRLF lesson), verified
identical, no stash left.

Three defects in the test were mine and were fixed before it passed: it compared
compiled type strings (which call `Float`/`DOUBLE PRECISION` a mismatch) and
column *order*; `import backend.database.engine as m` bound the `AsyncEngine`
object because the package `__init__` shadows the submodule name — the trap
`tests/conftest.py:116-124` documents; and three `asyncio.run()` calls shared a
pooled asyncpg connection across event loops. Each fix moved the test closer to
how production runs, not further.

---

## 8. Alembic and metadata

```
ALEMBIC before: 134 op lines, cost_tracking=5   (4 drop_index + drop_table)
        after : 129 op lines, cost_tracking=0
every NON-cost_tracking op line unchanged: True (129 vs 129)
```

Exactly the five expected operations disappeared; the other 129 are
byte-identical, so stop condition 9 does not fire. Global `alembic check` is
still red on ADR-112's remaining drift — not required, not claimed, not
suppressed. Disposable revision captured and deleted; migrations directory
clean.

Metadata closure: **40 tables, 0 unresolved FK targets**, `sorted_tables` OK,
`cost_tracking` on `Base.metadata`.

---

## 9. Safety

**Provider writes: 0.** No tenant, membership, authority, approval, execution,
connector or credential code touched — the diff is two model files and one
test. Phase 10.19's readiness check re-run on a migration-built database:
`ready: true, missing_tables: []`.

---

## 10. Stop conditions

| # | Condition | Result |
|---|---|---|
| 1 | `extra` and `extra_data` differ in meaning | **No** — §2, four independent sources |
| 2 | Production data cannot be preserved | **No** — 0 rows anywhere; no schema change |
| 3 | Canonical contract cannot be established | **No** — the lineage, twice aligned on purpose |
| 4 | Destructive transformation required | **No** — no migration |
| 5 | Writer's error semantics ambiguous | **No** — consistent and deliberate; classified as a data-integrity defect; unchanged |
| 6 | Repair touches a governed subsystem | **No** |
| 7 | Model intentionally runtime-only | **No** — it has a live writer and a `KEEP` disposition |
| 8 | Hidden consumers unclassified | **No** — §2 |
| 9 | Repair changes unrelated Alembic ops | **No** — 129/129 byte-identical |
| 10 | Provider write occurs | **No** |
| 11 | Verification vacuous | **No** — canary fails on the old model, §7 |

**None fired.**

---

## 11. Known limitations

1. **The error semantics remain what they were.** A failed cost write is still
   logged at `warning` and invisible to its caller. That is now a documented,
   tested, classified defect rather than a hidden one — and a separate decision.
2. **`cost_records` / `cost_provider_rates` / `cost_optimization_recommendations`**
   still declare a second "cost record" concept (`CostRecordModel`,
   `cost_intelligence.py`) that nothing writes and no migration creates.
   Out of scope; ADR-112's retirement phase.
3. **No production database was inspected.** The "0 rows everywhere" claim is
   true of every database on this instance; on a deployed database the write
   has been failing since GA, so the same is expected — but not observed.
4. **The test needs a PostgreSQL with CREATE DATABASE rights** and skips
   visibly without one. In CI's unit job (`SKIP_DB_MIGRATIONS=true`) it will
   skip; the harness instance runs it.
5. **The 27-table index drift and the ten dead models are untouched**, by the
   brief's first lines.

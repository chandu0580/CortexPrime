# Phase 10.20 — Discover and Reconcile `cost_tracking`
## Implementation Map

**Written after discovery and before code, as this phase family requires.**

- **Parent:** `3069a60` — Phase 10.19 (ADR-113)
- **Scope:** `cost_tracking` only. No dead-model retirement, no index drift, no
  global `alembic check`.
- **ADR for this phase:** ADR-114

---

## 1. Discovery — both directions, with evidence

### Schema → application (migrations `0004` → `0005` → `0006`, reflected from a migration-built database)

| Column | Type | Null | Default | Source |
|---|---|---|---|---|
| `id` | `uuid` | no | `gen_random_uuid()` | `0004` integer → `0006` uuid, *"match UUIDPrimaryKeyMixin"* |
| `mission_id` | `varchar(255)` | yes | — | `0004` |
| `user_id` | `varchar(255)` | yes | — | `0004` |
| `session_id` | `varchar(255)` | yes | — | `0004` |
| `provider` | `varchar(64)` | no | — | `0004` |
| `service` | `varchar(64)` | no | — | `0004` |
| `model` | `varchar(128)` | yes | — | `0004` |
| `prompt_tokens`, `completion_tokens`, `total_tokens` | `integer` | no | `0` | `0004` |
| `units`, `cost_usd` | `double precision` | no | `0` | `0004` |
| `report_date` | `date` | no | — | `0004` |
| **`extra`** | **`json`** | yes | — | `0004` |
| `created_at` | `timestamptz` | no | `now()` | `0004` |
| `updated_at` | `timestamptz` | no | `now()` | `0005`, *"(TimestampMixin)"* |

PK `id`. **No foreign keys.** Indexes: `ix_cost_tracking_mission_date (mission_id, report_date)`,
`ix_cost_tracking_user_date (user_id, report_date)`,
`ix_cost_tracking_provider_date (provider, report_date)`,
`ix_cost_tracking_report_date (report_date)`.

`0005` and `0006` are explicit in their own docstrings that they exist to
align the schema *to the model's mixins*. The lineage was deliberately brought
into agreement with the model on `id` and the timestamps — and kept `extra`.

### Application → schema (`backend/database/models/cost_tracking.py`, `CostRecord`)

| Model field | Column it maps | Agrees with schema? |
|---|---|---|
| `id` (UUIDPrimaryKeyMixin) | `id` uuid, `gen_random_uuid()` | **yes** |
| `mission_id` `String(36)`, `index=True` | `mission_id` | **no** — 36 vs 255; single-column index never migrated |
| `user_id` `String(128)`, `index=True` | `user_id` | **no** — 128 vs 255; index never migrated |
| `session_id` `String(255)`, `index=True` | `session_id` | length yes; index never migrated |
| `provider` `String(64)`, `index=True` | `provider` | length yes; index never migrated |
| `service`, `model` | same | **yes** |
| tokens (`default=0`), `units`, `cost_usd` (`index=True`) | same | types yes; `cost_usd` index never migrated |
| `report_date` `index=True` | `report_date` | yes; the single-column index *does* exist (`ix_cost_tracking_report_date`) but under a different name |
| **`extra` → `mapped_column("extra_data", JSONB)`** | **no such column** | **no** — name `extra_data` vs `extra`; type `JSONB` vs `json` |
| `created_at`, `updated_at` (TimestampMixin) | same | **yes** |
| `__table_args__`: `idx_cost_mission_date`, `idx_cost_user_date`, `idx_cost_provider_date` | `ix_cost_tracking_*` | same columns, **different names**; `report_date` index missing from the model |

### Writers, readers, consumers

| Path | Kind | Touches `extra`/`extra_data`? |
|---|---|---|
| `cost_engine.record()` | **the only writer** — ORM `session.add(CostRecord(...))`, `commit()` | **yes** — builds the row with `extra=` |
| `cost_engine.daily_summary / provider_breakdown / mission_cost / user_cost / executive_summary` | readers — aggregate `select(...)` over `report_date`, `cost_usd`, `total_tokens`, `provider`, `model`, `mission_id`, `user_id` | **never** — which is why reads have always worked |
| `backend/api/cost_routes.py` (5 endpoints), `mission_runtime.py:326,1285`, `mission_library/executor.py:278`, `enterprise_cost_anomaly_monitor.py`, `enterprise_recommendation_engine.py` | callers of the engine | via the engine only |
| `backend/core/data_retention.py:35`, `scripts/run-retention-policy.py:49` | retention **skips** DB-backed categories including `cost_tracking` | no |
| `backend/api/legacy_persistence_inventory.py:152` | records `KEEP`: *"not an authority input to anything, and nothing in the governed path reads it"* | no |
| repositories | **none** — the engine uses `AsyncSessionLocal` directly | — |
| tests | `test_cost_engine_provider_alias.py` exercises the pure `estimate_cost()`; `test_cost_anomaly_monitor.py` mocks `provider_breakdown` | **no test asserts a persisted row** |
| `models/__init__.py` | **does not import the model** | — |

**Every caller uses `asyncio.ensure_future(cost_engine.record(...))`** — the
only `await` of `record()` in the repository is the engine's own docstring.

### `extra` vs `extra_data` — the same concept

- `0004` creates `extra JSON` under the engine's contract; the model's
  *attribute* is `extra`, its docstring section is "Extended payload", and
  `record()`'s public parameter is `extra`. Only the model's column-name
  override says `extra_data`.
- What callers pass: `{"objective", "confidence", "has_browser",
  "response_length"}` (mission runtime) and `{"mission_name",
  "mission_category", "status", ...}` (mission library) — free-form per-call
  metadata. One concept.
- **Neither name is exposed through any application contract**: no reader
  projects it, no route returns it, no repository names it.
- **No historical row depends on either interpretation**: every database on
  the instance that has the table has `extra`, none has `extra_data`, all hold
  **0 rows**. Both the model and `0004` landed in the same GA commit
  (`a108839`) already disagreeing; the model has said `"extra_data"` from its
  first line, and the write has therefore never succeeded on a migrated
  database.

### The real write, reproduced (no mocks)

```
BEGIN (implicit)
INSERT INTO cost_tracking (..., report_date, extra_data, id, created_at, updated_at) VALUES (...)
ROLLBACK
WARNING cost_engine.record failed: UndefinedColumnError: column "extra_data" of relation "cost_tracking" does not exist
CALLER RECEIVED: None (no exception propagated)
ROWS PERSISTED: 0
```

### Error semantics

`record()` wraps everything in `except Exception as exc: log.warning(...)`.
Every reader in the module does the same and returns a fallback. The pattern is
consistent and evidently deliberate — fire-and-forget metering must not take
the mission runtime down — and every caller reinforces it with
`ensure_future`. **It is nonetheless a data-integrity defect by the brief's
definition: a persistence failure is converted into apparent success, and the
caller cannot tell.** This phase does **not** change those semantics (that
would be an unevidenced behaviour change); it removes the cause and adds a test
that asserts persistence directly, so silent loss cannot recur undetected.

---

## 2. Decision — A. MODEL CORRECTION

The database and migration lineage are canonical; the ORM is wrong.

- Alembic owns the application schema (ADR-109, implemented ADR-110).
- `0005`/`0006` show the lineage was deliberately aligned to the model where
  that was intended, and `extra` was kept through both.
- Same concept, no contract exposure, no data on either side.
- Readers never touch the column; only the writer does, and it is broken.

**Rejected:** B (migration correction) would rename a column no code or data
needs renamed, under a lineage that already had two chances to do so and
chose not to. C (reconciliation migration) has nothing to reconcile — there are
zero rows. D (conceptual split) fails on the evidence: one concept. E (stop) is
not warranted: the contract is established from four independent sources.

## 3. Changes

| File | Change |
|---|---|
| `backend/database/models/cost_tracking.py` | align to `0004`–`0006`: `extra` → column **`extra`**, type **`sa.JSON`**; `mission_id`/`user_id` → **`String(255)`**; drop the six `index=True` markers `0004` never migrated; declare the **four** `ix_cost_tracking_*` indexes by their migrated names. Mixins **kept** — `0005`/`0006` made the schema match them |
| `backend/database/models/__init__.py` | import and export `CostRecord` |
| `tests/database/test_cost_tracking_write_path.py` | **new** — the real write path against a real migration-built database |

**Not changed:** `cost_engine.py` (including its error handling), any
migration, any caller, any route, `cost_intelligence.py` and its three dead
models (a different phase), the durable store.

**Why register.** It is a live persisted concept with a real writer. Unregistered,
autogenerate proposes `drop_table('cost_tracking')` (a data-loss trap),
`init_db()` never creates it, and drift on it can never be detected. Every other
live model is registered. That is the reason; the autogenerate diff going quiet
is a consequence.

**Why no migration.** The schema is correct and complete. Nothing in the
evidence requires a database change.

## 4. Verification plan

| § | Method |
|---|---|
| Write path | the new test, against a real `alembic upgrade head` database: real `record()`, real `AsyncSessionLocal`, independent read-back, stored value, repeated calls, rollback on a forced failure, and a canary that fails if the row count does not rise |
| Reflection | corrected model vs reflected table, column by column |
| Alembic | before: 5 `cost_tracking` ops (4 `drop_index` + `drop_table`) of 134. After: **0** for `cost_tracking`; the other 129 unchanged |
| Safety | 0 provider writes; no governed subsystem touched |
| Regression | architecture gate, backend regression, harnesses 10.7–10.14, 10.16 probe, 10.19 readiness |

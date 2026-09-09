# Phase 10.31 — Implementation Map: index reconciliation (ORM-only)

- **Parent:** `37b4608` — Phase 10.29 (ADR-119) · **Discovery:** `docs/PHASE_10_30_INDEX_DISCOVERY.md` (PASS) · **ADR:** ADR-120
- **Principle applied:** the migration lineage owns the schema (ADR-109); the ORM mirrors it by the migrated names (ADR-114 pattern). **No migration. No `CREATE`/`DROP`/`ALTER INDEX`. No Alembic configuration change. No suppression.**

## Discovery baseline

HEAD `37b4608`, clean. Fresh `alembic upgrade head`: 25 migrations, 57 tables, 212 indexes. `compare_metadata`: **86** operations (62 add_index / 21 remove_index / 2 add_constraint / 1 remove_constraint) over 27 non-governed tables. Fresh and head database index inventories identical. Classification: F 47 · D-obsolete 31 · C 5 · E 1 · A 1 · G 1 · H 0.

## Changes — 16 model modules, ORM metadata only

| Class | Action | Where |
|---|---|---|
| F (31 marker/DB pairs + 15 partners + `billing_invoices.invoice_number`) | the `index=True` (and `unique=True` where the migrated index is UNIQUE) marker is removed from the column; where the ORM did **not** already declare the migrated name, an explicit `Index("<migrated name>", "<col>"[, unique=True])` is added to `__table_args__` (16 names: `idx_agent_name`, `idx_agent_states_name`, `idx_billing_invoices_number`, `idx_ca_connector_name`, `idx_ca_request_id`, `idx_ca_correlation_id`, `idx_connector_name`, `idx_exec_id`, `idx_gov_policies_name`, `idx_gov_approval_rid`, `idx_learn_session_sid`, `idx_learn_patterns_name`, `idx_platform_ff_name`, `idx_platform_settings_key`, `idx_analytics_session` + E below); where the ORM already declared it (e.g. `idx_agent_states_status`, `idx_platform_settings_category`, `idx_exec_agent`) only the redundant marker is removed | `repositories/{agents,billing,connectors,executions,governance,learning,platform}.py`, `models/{connector_activity,runtime_analytics}.py` |
| D-obsolete (31) | the never-migrated `index=True` marker is removed; nothing is created (Rule 4); no access path changes because the DB never had the index | `repositories/{billing,digital_twin,executions,governance,knowledge,missions}.py`, `models/{connector_activity,episodic_memory,reflection_history,runtime_analytics}.py` |
| E (1) | `Index("idx_connector_status", "status")` declared (0008 created it; the model never mentioned it) | `repositories/connectors.py` |
| C (5) | mirrored exactly: `Index("idx_*_embedding", "embedding", postgresql_using="ivfflat", postgresql_ops={"embedding": "vector_cosine_ops"}, postgresql_with={"lists": 100/50})`; `Index("idx_ep_content_fts", text("to_tsvector('english'::regconfig, content)"), postgresql_using="gin")`; `Index("idx_sem_concept_fts", text("to_tsvector('english'::regconfig, (concept \|\| ' '::text) \|\| content)"), postgresql_using="gin")` — the expression strings are the ones SQLAlchemy reflects, so Alembic compares them equal; the two model comments that said "not expressible in DDL here" are corrected | `models/{episodic_memory,semantic_memory,reflection_history}.py` |
| A (1) | `embedding_cache.text_hash`: column markers removed; `UniqueConstraint("text_hash", name="embedding_cache_text_hash_key")` declared by its migrated name; the unique `Index("idx_emb_cache_hash")` stays. Both DB structures (0001 created both) untouched | `models/embedding_cache.py` |
| G (1) | `missions_bc.execution_id`: `unique=True` removed — 0007 (owner) never made it unique, no query consumer, 0 rows, table inventoried REPLACE | `repositories/missions.py` |

Every edit was applied by a script asserting exactly one match per column line **inside the class block** (two tables share byte-identical column lines), followed by a gate: syntax of all 16 modules, `compare_metadata` == 0, and every ORM `Index` compiling to its `pg_get_indexdef`.

**Not changed:** any migration; any database; `alembic.ini`, `env.py`, comparison options; index names, methods, expressions, opclasses, `lists`; governed `cp_*`/`cw_*` tables; the `knowledge_entries.embedding` column (no vector index on either side — noted, not added).

## Verification plan (Stage C)

Fresh DB (`alembic upgrade head`, `pg_get_indexdef` for all indexes); existing head DB (0 migrations, schema/index/row fingerprints identical, `alembic check`); fresh rebuild from the edited tree identical to the pre-edit fresh DB; `create_all` scratch DB compared index-by-index with the migration-built DB; `alembic check` + autogenerate before/after; executed vector/FTS query paths; architecture; targeted database/memory/knowledge/mission tests; regression at the 10.22 scope; harnesses 10.7–10.14; readiness; provider writes 0; clean tree.

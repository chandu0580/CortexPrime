# Phase 10.30 + 10.31 — Verification Report: index ownership reconciliation

- **Parent:** `37b4608` — Phase 10.29 · **Discovery:** `docs/PHASE_10_30_INDEX_DISCOVERY.md` · **Map:** `docs/PHASE_10_31_IMPLEMENTATION_MAP.md` · **ADR:** ADR-120
- **Date:** 2026-09-09

Labels: `[VERIFIED]` executed and observed · `[NOT VERIFIED]` inferred · `[DEFERRED]`.

## 1. Summary

| Claim | Result |
|---|---|
| Exact drift rediscovered, not assumed | `[VERIFIED]` `compare_metadata` as structured objects against a fresh `alembic upgrade head` DB: **86** ops (62/21/2/1) over 27 tables; fresh == head index inventories |
| All 86 classified, none H | `[VERIFIED]` F 47 · D 31 · C 5 · E 1 · A 1 · G 1 (`PHASE_10_30_INDEX_DISCOVERY.md` table) |
| No naming convention exists; none invented | `[VERIFIED]` no `naming_convention`, no template rule, no ADR; ORM adopts each migrated name verbatim; no rename |
| Reconciliation is ORM-only | `[VERIFIED]` `git diff`: 16 model modules, +133/−73; no file under `migrations/`, no `alembic.ini`/`env.py` change, no `include_object`, no comparison-option change |
| Alembic after | `[VERIFIED]` `alembic check` on the fresh DB → **"No new upgrade operations detected."** (rc 0); autogenerate → **0** upgrade ops (temp revision moved out of `versions/`, 0 left); `alembic check` on the existing head DB → **"No new upgrade operations detected."** |
| Why it is clean (proven, not asserted) | `[VERIFIED]` every one of the **98** `Index` objects in `Base.metadata` compiles (`CreateIndex`, PostgreSQL dialect) to the same DDL as its `pg_get_indexdef` after normalising only `USING btree`, `lists = N`/`lists='N'` and one redundant paren — 0 mismatches; on the 27 tables every DB index (excluding PK/constraint-backed) has an ORM declaration by name and every ORM index exists in the DB; the named `UniqueConstraint` and the unique `Index` on `embedding_cache.text_hash` match 0001's two structures by name |
| Fresh DB | `[VERIFIED]` rebuilt from the edited tree: 25 migrations, 57 tables, **212 indexes**; schema and index fingerprints **identical** to the pre-edit fresh DB (the migrations are untouched, so the schema cannot have moved) |
| Existing head DB | `[VERIFIED]` `cortex_p1014_legacy`: `alembic upgrade head` ran **0** migrations; schema fingerprint `5b62dfb5…`, index fingerprint and row-count fingerprint identical before/after; 212 indexes |
| `create_all` == migrations | `[VERIFIED]` a scratch DB built by `Base.metadata.create_all` + `DURABLE_METADATA.create_all` (with `vector`, `pg_trgm`, `uuid-ossp`) has the same 56 application tables and the **same 211 application indexes by name and definition** as the migration-built DB; the only differences are `alembic_version` itself and the *names* of five governed `cw_*` unique constraints (`uq_cw_*_identity`/`uq_cw_fact_version` in migrations vs SQLAlchemy's `<table>_<col>_key` auto-names) — constraint naming outside this phase's scope, not reported by Alembic, recorded as a deferred finding |
| Specialized indexes preserved | `[VERIFIED]` ivfflat ×3 (`vector_cosine_ops`, `lists` 100/100/50) and GIN ×2 present with identical `pg_get_indexdef` on fresh and head; nothing created, dropped or altered |
| Uniqueness preserved | `[VERIFIED]` 12 UNIQUE indexes + `idx_billing_invoices_number` + `embedding_cache` constraint/index all unchanged in both databases; `missions_bc.execution_id` never had DB uniqueness — none removed |
| Query paths | `[VERIFIED]` on the migration-built DB: `EpisodicRepository.search_similar`, `SemanticRepository.search_similar`, `ReflectionRepository.search_similar` (real pgvector `<=>`), `EpisodicRepository.search_text` (FTS) execute (0 rows on an empty DB); `EXPLAIN` of the FTS predicate on `semantic_memory` shows a Bitmap Heap Scan with a recheck condition — the GIN index is in the plan |
| Architecture / targeted / regression / harnesses | `[VERIFIED]` architecture **155 passed** (unchanged); targeted (`tests/database`, `test_cognitive_memory`, `test_embedding_observability`, `test_knowledge_search`, `test_knowledge_service`, `test_memory_event_subscriber`, `test_reflection_consolidation`, `test_workspace_memory_research_routes`, `tests/contexts/mission`) **329 passed / 7 skipped**; regression (10.22 scope) **75 failed / 6744 passed / 36 skipped / 58 xfailed / 24 errors** — counts identical to the 10.29 baseline and the `FAILED` set identical (0 new / 0 gone; also 0/0 vs 10.26); harnesses 10.7 **155/155** (solo re-run after the disposable worker's TLS certificate expired mid-chain, §3) · 10.8 **118/118** · 10.9 **107/107** · 10.10 **107/107** · 10.11 **68/68** · 10.13 **60/60** (solo re-run, §3) · 10.14 **53/53** — all VERIFIED; 10.19 readiness `ready: true` on the fresh and the existing DB |
| Governance | `[VERIFIED]` by re-executing the governed harnesses at full counts (scoped authority/execution 155, grant issuance 118, membership 107, tenant records 107, TenantManager retirement 68, V1-read retirement 60, IAM retirement 53): tenant isolation, membership, authority, approval, execution, assurance, worker, connector, credential and audit unchanged; no governed `cp_*`/`cw_*` table or module touched (the 27 tables are all non-governed); governed table fingerprints identical (existing-DB schema fingerprint unchanged) |
| Provider writes | **0** from this phase. Harness-reported writes: `[0,1]` on 10.7 only — its one standing rollout restart of the test `billing-api` deployment on the disposable k3d cluster, as in every prior run; 0 on every other harness and negative case. One infrastructure action was taken on the disposable test cluster, not on any provider: the contained worker's TLS certificate (minted `-days 2` by `scripts/phase99b_provision.sh`) had expired at 11:12 UTC; it was re-minted with the script's own `openssl` command, the `worker-tls` secret recreated, `ca-bundle.pem` rebuilt and the worker deployment restarted — the same step Phase 10.14's close-out took |
| Clean-up | `[VERIFIED]` scratch DBs `cortex_p1030_fresh`, `cortex_p1031_fresh`, `cortex_p1031_createall` dropped; temp autogenerate revisions 0; no Redis keys; tree holds only the intended files |

## 2. Alembic before / after

| | Before (`37b4608`) | After |
|---|---|---|
| `compare_metadata` ops | 86 | **0** |
| `alembic check` | "New upgrade operations detected" (86) | "No new upgrade operations detected." |
| Database schema | 212 indexes | 212 indexes — **unchanged** (fingerprint identical) |

Every one of the 86 disappeared because the ORM now says what the migrations built: 47 by declaring the migrated name (F) or the redundant marker being removed where the name was already declared; 31 by removing markers for indexes that never existed on any database (D); 5 by declaring the PostgreSQL-specific indexes exactly (C); 1 by declaring `idx_connector_status` (E); 1 by naming the `embedding_cache` constraint (A); 1 by dropping the never-realized `missions_bc.execution_id` uniqueness claim (G). Not one of the 86 was resolved by changing the database or by hiding a comparison.

## 3. Gates

| Gate | Result |
|---|---|
| Architecture | **155 passed** (194 s) |
| Targeted | database (cost-tracking write path, replay persistence, tenant-scoped repository), cognitive memory, embedding observability, knowledge search/service, memory event subscriber, reflection consolidation, workspace memory/research routes, `contexts/mission`: **329 passed, 7 skipped** (161 s). (The chain's own "targeted" line named six non-existent modules and collected nothing; this is the corrected run, alone.) |
| Regression (`pytest tests/ -q --tb=no -rf -p no:cacheprovider`) | **75 failed / 6744 passed / 36 skipped / 58 xfailed / 24 errors** (1355 s) — every count equal to the 10.29 baseline; `FAILED` list diff 0 new / 0 gone against 10.29 and against 10.26 |
| Harness chain (serial, verdict-aware watchdog) | 10.7 **150/155 NOT VERIFIED** · 10.8 118/118 · 10.9 107/107 · 10.10 107/107 · 10.11 68/68 · 10.13 **59/59** · 10.14 53/53; readiness `ready: true` ×2 |
| 10.7's five failures — environmental, with evidence | D6, E3, E4, K5, L1 are the governed write chain: "the governed chain refused this action: the envelope did not complete", provider writes 0 (the worker was never reached). `.phase99b/worker.crt` `notAfter = Sep 9 11:12:38 2026 GMT` — minted `-days 2` on Sep 7 16:42 by `scripts/phase99b_provision.sh:97`; the chain ran at ≈20:40 IST. Identical to the 10.14 close-out finding (ADR-107 §"env drift"). The platform behaved correctly: it refused to send a credential over a connection it could not verify. |
| 10.13's missing check | `N16. revoked authority` is guarded by `if r.status_code == 201` on a grant-creation POST (`phase1013…:594-602`) that did not return 201 under the same expired-certificate environment; the check list is otherwise identical to the 10.29 run (diff of `[OK]` labels: only N16). |
| Repair and solo re-runs | Certificate re-minted with the provisioning script's own command (`-days 2`, `CN=cortex-contained-worker`, SAN `127.0.0.1,localhost`; new `notAfter = Sep 11 15:22:53 2026 GMT`), `worker-tls` secret recreated, `ca-bundle.pem` = cluster CA + worker cert rebuilt, `deploy/contained-worker` restarted (rolled out), `curl --cacert ca-bundle.pem https://127.0.0.1:18099/…` → 200 **with verification**. Then, alone: **10.7 155/155 VERIFIED, writes `[0,1]`** (the standing restart is back); **10.13 60/60 VERIFIED**, `N16 [OK] … no_executor_authority`. |
| Post-report hangs | 10.13 and 10.14 hung after flushing their JSON verdicts (the recurring TestClient shutdown hang); the watchdog killed each only after `"verdict"`/`"deferred"` were on disk. No contention this time — no foreign process was running. |

## 4. Data integrity

No table, index or constraint created, dropped or altered on any database. `cortex_p1014_legacy` unchanged (three fingerprints). Scratch databases created and dropped. No provider call.

## 5. Known limitations

- `knowledge_entries.embedding` has no vector index on either side; `knowledge.py:76` orders by `cosine_distance` — a sequential scan today. Not drift; not added (Rule 4).
- The five governed `cw_*` unique constraints carry different *names* under `create_all` than under the migrations (`uq_cw_*` vs `*_key`); Alembic matches them by columns and reports nothing. Governed tables are out of this phase's scope.
- `embedding_cache.text_hash` remains doubly enforced in the database (constraint + unique index, both from 0001); mirrored as-is, not simplified.
- `test_enterprise_operations`-style mock tests do not exercise indexes; index behaviour is verified against real PostgreSQL only.

# PHASE 7.2 — VERIFICATION REPORT

Date: 2026-08-11 · Branch `phase-1-foundation` · Commit `ee43f3a` (+ this report) · ADR-064

Labels: **[FACT]** repository-verifiable · **[SOURCE]** cited · **[INFERENCE]** reasoning · **[PROPOSAL]** design · **[VERIFIED]** evidence this phase · **[NOT VERIFIED]** no evidence · **[DEFERRED]** out of scope · **[BLOCKED]** precondition absent. Nothing is called verified merely because a unit test exists — the real-Postgres/real-process harness is cited where the claim is distributed.

---

## 1. Discovery
**[FACT]** Confirmed the durable persistence pattern (`store.atomic()` → `work.execute(sa.insert)`, app-clock `work.now`, `ConstraintConflict` on unique-violation as the idempotency mechanism), the migration convention (0014 → head), and the single V1 destructive strangler target (`KubernetesIntelligence.track_pod`, one internal caller). **[FACT]** `find_secrets` was a pure detector in `backend/harness/firewall.py` depending only on `platform.credentials.redaction`; relocated to `backend/platform/credentials/inspection.py` so the World Plane could reuse it without importing the harness (harness re-exports unchanged). **[VERIFIED]**

## 2. Selected V1 path
**[FACT]** `KubernetesIntelligence.track_pod` (`enterprise_infrastructure_intelligence.py:252`) — a destructive world-state upsert: it finds a pod by (name, namespace), mutates it in place (`existing["status"]`, `restarts`, `updated_at` overwritten — the prior observation lost), and rewrites the whole file. Chosen as the single first target because it is the canonical instance of the Phase 7.0 "worst offender" (destructive-upsert of infra snapshots) with exactly one internal caller, so quarantine is safe. **[VERIFIED]** (prior destructive behavior proven in `test_the_old_behavior_was_destructive`).

## 3. Observation contract consumption
**[VERIFIED]** The ingestion boundary consumes the ADR-063 `Observation`, `ObservationSource`, `ObservationInstant`, `ProvenanceRef`, and the salvaged `SourceStatus` — building an `Observation` from a `ReadObservation` (a governed-read value object), never from model output.

## 4. Persistence
**[VERIFIED]** `cw_observation` created via Alembic migration 0015 (no `create_all`, no stamping, no SQLite) — confirmed by the harness migrating a fresh `cortex_p72` from base to head and `build_durable_persistence` validating the schema. Columns map the contract: identity, tenant, source (kind+ref), subject/predicate, status, observed_at/retrieved_at/recorded_at, record document, produced_by, schema_version. Unique constraint on `identity_digest`; three lookup indexes.

## 5. Ingestion
**[VERIFIED]** A governed `widget.get` READ (controlled provider, through the gateway via `scheduler.tick`, no manual dispatch, no injected result) became a durable Observation — harness check "read became a durable observation", with the ingestion contacting no provider itself.

## 6. Provenance
**[VERIFIED]** Every observation carries a mandatory reference-only `ProvenanceRef` (harness: "provenance references the execution" — `execution_ref == exec_id`). Secret-shaped provenance values raise `SecretInProvenance`. **[VERIFIED]**

## 7. Tenant isolation
**[VERIFIED]** Tenant comes from the governed context, never the payload/source (unit: `ReadObservation` has no tenant field; a non-`TenantRef` is refused). Cross-tenant reads fail closed (harness: "crashed observation is cross-tenant-isolated" — a lookup under tenant "other" returns None for acme's observation). Different tenants → different identities. **[VERIFIED]**

## 8. Temporal semantics
**[VERIFIED]** `observed_at`, `retrieved_at`, `recorded_at` are three distinct columns with distinct meaning (unit: `test_observed_at_and_recorded_at_are_distinct` — recorded_at > retrieved_at, observed_at set to the instrument's time). A plain read sets `observed_at == retrieved_at` by design, stated. `valid_from`/`valid_to` deliberately absent (bitemporal facts = 7.3). **[VERIFIED]**

## 9. Idempotency
**[VERIFIED]** Deterministic identity (digest over tenant/source/subject/predicate/observed_at/value); identical delivery dedupes (harness: "identical delivery dedupes", "still exactly one row"); a new value or later observed_at is a new row (unit). **At-least-once, NOT exactly-once** — explicitly not claimed; the unique constraint dedupes, it does not upgrade delivery. **[VERIFIED]**

## 10. Append-only behavior
**[VERIFIED]** The repository issues only INSERT/SELECT — no update/delete method exists on the port or the SQL repo (unit); `BND-OBSERVATION-APPEND-ONLY` forbids `sa.update`/`sa.delete` under `backend/world` (sensitivity-tested). **[VERIFIED]**

## 11. Crash/recovery
**[VERIFIED]** Real PostgreSQL + real `os._exit(9)`: a child ingested an observation and died the hard way (exit 9); a successor process read it back intact with a stable identity; a duplicate delivery would dedupe. A mid-transaction death rolls back (the atomic store) — no partial row. **[VERIFIED]** (harness Part M checks).

## 12. Replay
**[VERIFIED]** Replaying the governed execution created **zero** new observations and performed **zero** provider reads (harness, counters). Observations are historical evidence; replay reconstructs, never rewrites. **[VERIFIED]**

## 13. Audit
**[VERIFIED]** The fenced audit chain verifies after ingestion (harness: `verify_chain` ok). No second audit system was created; the observation record carries no credential material (secret firewall on the write path). **[VERIFIED]**

## 14. Secret safety
**[VERIFIED]** Field-aware, nested-structure detection refuses observation values carrying tokens/keys/bearer/authorization (unit: parametrized incl. nested and list cases; harness: real-path refusal contacts no provider). Safe references (`credential_ref`, `authorization_digest`, provider ids) remain allowed. Not substring-only — the walk covers dicts/lists/dataclasses/Pydantic/base64. **[VERIFIED]**

## 15. Strangler
**[VERIFIED]** `track_pod` is refused by default (`LegacyExecutionRefused`) and wrote nothing when refused; with the flag set, its destructive in-place mutation is proven (a second call overwrites the first, prior observation gone). Old path non-authoritative, not deleted, not migrated, no dual-write. **[VERIFIED]**

## 16. Fitness
**[VERIFIED]** Gate PASSES: **29 rules passed, 0 failed, 6 skipped** (`architecture PASS: 29 passed, 0 failed, 6 skipped across 1128 modules`). Refined `BND-WORLD-CANNOT-EXECUTE` (allow durable store + credential detectors for world infra; forbid connectors/execution/transport/credential carriers/harness); added `BND-WORLD-APPLICATION-PURE` and `BND-OBSERVATION-APPEND-ONLY`. Each CURRENT=PASS / SYNTHETIC=FAIL (10 sensitivity tests). No cosmetic rules — the tenant/provenance candidates stay enforced at the type/schema level.

## 17. Regression
**[VERIFIED]** `tests/world` + `tests/architecture` + `tests/harness` + `tests/contracts/world`: **335 passed, 0 failed**. These cover every production change (the new `backend/world/` plane, `boundary_rules.py`, the firewall relocation, `tables.py`, the strangler). The Phase 5 durable bootstrap validated cleanly (the harness ran `build_durable_persistence` against the migrated 0015 schema). **[NOT VERIFIED]** a single local full-`tests/` pass (the root conftest probes Postgres per test; a prior full run took 35 min and overlapped edits — CI `test.yml` is the authority). One stale 7.1 test was superseded with documentation (`test_world_importing_a_database_impl_fails` → `..._is_allowed`), no assertion weakened.

## 18. Defects discovered
**[FACT]** (1) The 7.1 `BND-WORLD-CANNOT-EXECUTE` forbade all `backend.database` for the world plane — correct when no persistence existed, wrong once the observation ledger needed the durable store. Refined to distinguish *persisting* (allowed for infra) from *executing* (forbidden), plus `BND-WORLD-APPLICATION-PURE` to keep the application database-free. (2) A prior 35-min background regression overlapped these edits and reported 2 spurious failures from reading files mid-change — re-run in a consistent state is green (a time-of-check artifact, not a code defect). No defect in existing execution/persistence code.

## 19. Non-goals honored
**[VERIFIED]** No Fact/Belief/Hypothesis/Prediction/Outcome inference, no contradiction resolution, no world query, no vector/embedding/graph/RAG, no automatic belief generation, no execution planning, no autonomous remediation, no bitemporal valid-time store, no execution-path change (scheduler/dispatcher/gateway/authorization/capability/lease/approval untouched — grep-confirmed), no second database/governance/audit. None of the STOP conditions was hit: no Fact was needed to ingest, no model output became an Observation, tenant authority is unambiguous (from the governed context), provenance is safe (references + firewall), and exactly-once is not claimed.

## 20. Risks
**[INFERENCE]** (1) The governed-read→observation *mapping* is done by the composition layer (the harness); a future ingestion composition must keep the deterministic, no-model discipline — the type system helps (no model source) but the mapping is code. (2) The strangled `track_pod` has sibling `track_*` methods still destructive; only one path was strangled this phase (as mandated) — the rest are future targets. (3) `observed_at == retrieved_at` for plain reads is honest but means true valid-time correction awaits providers that report their own observation time (Phase 7.3). (4) The secret firewall is field-aware but pattern-based; a novel token shape could pass — the defence in depth is that provenance carries references not payloads.

## 21. Phase 7.3 readiness
**[INFERENCE] Ready.** The observation ledger exists, is append-only, tenant-scoped, provenanced, and durable, with the three times separated — exactly the input bitemporal fact derivation needs. 7.3 builds deterministic observation→fact folding with valid-time + transaction-time and supersession-not-deletion, answering the Phase 7.0 correction example against real Postgres. **[FACT]** Nothing in 7.2 pre-commits 7.3's derivation rules; facts read observations, and the model still cannot create either. Phase 5.5 credential blocker untouched; L1–L16 intact; no second execution/governance/coordination authority.

## DoD checklist (Part X)
**[VERIFIED]** 1 ingestion exists · 2 cw_observation via Alembic · 3 PostgreSQL verified · 4 tenant enforced · 5 provenance mandatory · 6 observed_at≠recorded_at · 7 SourceStatus reused · 8 model cannot create Observation · 9 one real governed READ → Observation · 10 credentials never in world records · 11 deterministic idempotency · 12 append-only · 13 crash recovery verified · 14 replay zero new observations · 15 refusals fail-closed · 16 one V1 path strangled · 17 no Fact/Belief inference · 18 no execution influence · 19 fitness passes (29 rules, 0 failed, 6 skipped) · 20 regression passes (335; full-suite is CI's authority) · 21 ADR-064 exists · 22 this report exists · 23 Phase 5.5 untouched.

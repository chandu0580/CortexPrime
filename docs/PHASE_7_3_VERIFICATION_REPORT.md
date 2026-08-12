# PHASE 7.3 — VERIFICATION REPORT

Date: 2026-08-12 · Branch `phase-1-foundation` · ADR-065 · Migration `0016_world_fact`

Labels: **VERIFIED** (evidence this phase) · **NOT VERIFIED** (no evidence) · **DEFERRED** (out of scope) · **BLOCKED** (precondition absent). Evidence, not the existence of code, decides completion. The distributed claims cite the real-Postgres/real-process harness `scripts/phase73_fact_harness.py` (**30 checks, 0 fail, verdict VERIFIED** against a fresh `cortex_p73`); source was trusted over the prior reports throughout (discovery re-read the contracts and Phase 7.2 code directly).

## 1. Architecture reviewed
**VERIFIED** Read the Constitution, Phase 7.0/7.1/7.2 reports, ADR-062/063/064, and — decisively — the source: `backend/contracts/world/` (Fact, ValidityInterval, EpistemicStatus, ProvenanceRef, ClaimConfidence, KnowledgeAuthority), `backend/world/` (Phase 7.2 ingestion + observation repo), the durable store/UnitOfWork, Alembic head, and the fitness framework. Finding that shaped the phase: **the bitemporal vocabulary already existed in the contracts**, so no field name was invented.

## 2. Existing contracts
**VERIFIED** Authoritative Fact = `backend.contracts.world.epistemic.Fact` (subclasses `EpistemicRecord` → `Contract`). Required fields: spine (`record_id`, `tenant`, `recorded_at`, `provenance`) + `subject_ref`, `predicate`, `value`, `validity: ValidityInterval`, `authority: KnowledgeAuthority`, `status: EpistemicStatus`. Valid time = `Fact.validity` (`valid_from` req, `valid_to` open); knowledge time = `recorded_at`; observation time = `Observation.instant.observed_at`. No pre-existing fact store, no `cw_fact`, no bitemporal code — built fresh.

## 3. Fact identity
**VERIFIED** Semantic identity = `digest(tenant, subject_ref, predicate)` — the same proposition across versions, NOT a UUID and NOT value-inclusive (unit: `TestIdentity` — same proposition→same id; different predicate/subject/tenant→different id; key-order-independent version id). Version identity = `digest(semantic_identity, value, valid_from)` (idempotency).

## 4. Fact representation
**VERIFIED** Structured `subject/predicate/value` (`{"replicas": 5}`), never prose (unit `test_a_real_observation_becomes_a_grounded_fact`). A Fact is grounded in a real `Observation` object; there is no text/proposal derivation path.

## 5. Storage
**VERIFIED** `cw_fact` — append-only version rows, same durable template as `cw_observation`. Unique `version_digest`; indexes `(tenant_id, semantic_identity)`, `recorded_at`. `SqlFactRepository` issues INSERT/SELECT only (no update/delete method exists).

## 6. Migration
**VERIFIED** Migration 0016 (`down_revision=0015_world_observation`), Alembic only. This pass: blank `cortex_p73` → `alembic upgrade head` ran 0015→0016; `alembic heads` = exactly one (`0016_world_fact`). No `create_all`, no stamping, no SQLite, developer DB (`cortexdb`) untouched.

## 7. Reconciliation
**VERIFIED** Deterministic, policy-free (`FactDerivation.derive`): different `valid_from` + different value → succession (AFFIRMED); same `valid_from` + different value → CONFLICTED (never latest-wins); value already effective → idempotent no-op; non-informative observation → no fact. No LLM, no provider, no clock read of its own (caller supplies knowledge time). Unit: `TestConflict`, `TestIdempotency`; harness Parts A/C/D.

## 8. Bitemporal semantics
**VERIFIED** Valid time and knowledge time are independent columns and independent query axes (unit `TestKnowledgeTime.test_valid_and_knowledge_axes_are_independent`; harness Part B). The load-bearing example (STEP 6) passes end-to-end against real Postgres — replicas=5 valid_from 10:00 recorded 10:04, then replicas=3 valid_from 09:58 recorded 10:10:
- what was true at **09:59 → 3** · at **10:02 → 5**
- what CortexPrime knew at **10:00 → UNKNOWN** · at **10:05 → 5**
- what the World Plane currently represents → **5**, and **both versions retained** (the 5 was not overwritten).

## 9. Supersession
**VERIFIED** A correction/world-change is a new immutable version; `valid_to` is derived at query time, no prior row is mutated or deleted (unit `test_derived_valid_to_bounds_the_earlier_interval`, `test_history_is_preserved_not_overwritten`; `BND-OBSERVATION-APPEND-ONLY` sensitivity test — a synthetic `sa.update` in the fact infra FAILs). `parent_claim_ref` records lineage (unit `test_succession_records_parent_lineage`).

## 10. Conflict handling
**VERIFIED** Same valid instant + different value → CONFLICTED, both evidence paths preserved, not resolved by arrival order (unit `test_conflict_is_not_resolved_by_arrival_order`; harness "the conflicted instant reports CONFLICTED with both values" against real Postgres — `{5, 3}` both present).

## 11. Epistemic status
**VERIFIED** UNKNOWN (absence), CONFLICTED (contradiction), AFFIRMED (single value) all emerge from the projection; `EpistemicStatus` has no FALSE member (unit `test_epistemic_status_has_no_false_member`, `test_absence_derives_unknown_never_false`). **STALE is not emitted** — no freshness policy invented (DEFERRED, §25).

## 12. Confidence
**VERIFIED** A `Fact` carries no `ClaimConfidence` field; a single source derives `ADVISORY` (tier, not a number); `ModelStatedConfidence` has no conversion to `ClaimConfidence` and `ClaimConfidence.uncalibrated()` has no value (unit `TestConfidenceFirewall`; harness "a Fact carries no confidence field").

## 13. Provenance
**VERIFIED** Fact → Observation (`observation_ref`) → governed execution (`execution_ref`) → trace (`trace_ref`), plus `parent_claim_ref` lineage (unit `TestProvenance`; harness "fact is grounded in its observation", "carries the execution reference"). A reviewer can trace why CortexPrime holds a fact to the governed read that grounds it.

## 14. Tenant isolation
**VERIFIED** Semantic identity includes tenant; reads are tenant-predicated and fail closed. Cross-tenant `versions_for`/`get` return empty/None (unit `TestTenant`; harness "crashed fact is cross-tenant-isolated", "cross-tenant versions_for is empty" against real Postgres). A cross-tenant observation is refused at derivation (`test_observation_of_another_tenant_is_refused`).

## 15. Query semantics
**VERIFIED** Four pure projections — `current_state`, `as_of_valid`, `as_known`, `history` — deterministic over the version set (unit `TestProjection`/`TestKnowledgeTime`/`TestLoadBearingExample`; harness Part B). No vector/graph/RAG/LLM query (§23 non-goals honored).

## 16. Idempotency
**VERIFIED** Re-deriving the same observation is a deterministic DEDUPED no-op; same value at a later valid time is a no-op; the unique `version_digest` constraint dedupes at the durable layer (unit `TestIdempotency`; harness Part D "no new fact row from the duplicate derivation"). **At-least-once with deterministic identity — exactly-once NOT claimed.**

## 17. Crash safety
**VERIFIED** Real Postgres + real `os._exit(9)`: a child ingested→derived a fact and died (exit 9); a successor process read it back intact, reconstructed the full `Fact` with provenance intact, and cross-tenant reads failed closed (harness Part F). A mid-transaction failure rolls back with no partial fact — harness Part G inserts inside `atomic()`, raises, and confirms count unchanged + row unreadable.

## 18. Replay
**VERIFIED** Replaying the governed execution created **zero** new facts and performed **zero** provider reads (harness Part E — facts derive via the explicit reconciler, not replay). Deterministic derivation: identical observation → identical version identity (unit; the harness runs from a fresh migrated DB each time and reproduces the same identities). Replay does not execute.

## 19. PostgreSQL evidence
**VERIFIED** Fresh `cortex_p73`: blank → migrate 0016 → ingest observations → derive facts → bitemporal queries → conflict → crash/recovery → rollback → replay. 30 harness checks VERIFIED; counts facts=6, observations=6, provider_calls=1 (the single governed read). Developer `cortexdb` untouched.

## 20. Tests
**VERIFIED** 43 new tests: `tests/world/test_fact_derivation.py` (23), `tests/world/test_bitemporal_queries.py` (13, incl. the load-bearing example), `tests/world/test_fact_fitness.py` (7). Regression `tests/world + architecture + harness + contracts/world`: **390 passed, 0 failed** (149.5s). **NOT VERIFIED** a single local full-`tests/` pass (root conftest probes Postgres per test; CI `test.yml` is the authority). No existing assertion weakened.

## 21. Architecture fitness
**VERIFIED** Gate PASSES: **29 passed, 0 failed, 6 skipped** across 1132 modules. **No new rule added** (STEP 20): the fact ledger under `backend/world` is already covered by `BND-OBSERVATION-APPEND-ONLY` (no UPDATE/DELETE), `BND-MODEL-CANNOT-CREATE-FACT` (model planes can't import `Fact`), `BND-WORLD-CANNOT-EXECUTE`, and `BND-WORLD-APPLICATION-PURE`. Coverage proven by sensitivity tests (current PASS; synthetic `sa.update`/`sa.delete` in the fact infra FAIL; synthetic model import of `Fact` FAILs; fact infra importing a connector FAILs; fact application importing a database FAILs).

## 22. Defects discovered
**FACT** (1) `KnowledgeAuthority` is exported from `backend.contracts.knowledge`, not `backend.contracts.world` — an initial import erred; fixed. No defect in existing code. (2) No defect in the Phase 7.2 substrate surfaced under fact derivation — the observation ledger, digest, provenance, and tenant machinery behaved exactly as the 7.2 report described (source-verified, not report-trusted).

## 23. Risks
(1) The succession-vs-conflict rule treats *any* different `valid_from` as succession and only *exact* `valid_from` equality as conflict — deliberately policy-free, but two disagreeing sources reporting near-simultaneous different values are modeled as a rapid world change, not a conflict. Refining this needs the authority/corroboration axis (Phase 7.4). (2) `valid_to` is derived at query time; a very large version history for one identity is an O(n) projection — acceptable at this scale, an index/materialization is a later concern. (3) Re-confirmation of the same value at a later valid time is a no-op, so "last re-observed" is not recorded — that timestamp matters only once freshness exists (deferred with it). (4) The derivation composition (observation→derive) is code discipline; the type system enforces "real Observation only", but wiring it into a governed loop must keep the no-model, deterministic discipline.

## 24. NOT VERIFIED
- A single local full-`tests/` pass (subset + CI is the authority).
- The LLM/model leg remains BLOCKED (placeholder credentials) — not exercised and not needed; the derivation is deterministic and model-free by design.

## 25. Deferred work
**DEFERRED** Freshness/STALE policy; authority/corroboration promotion (SINGLE_SOURCE→CORROBORATED→AUTHORITATIVE) and the refined succession-vs-conflict it enables; belief formation; prediction/outcome reconciliation; semantic/vector/graph/RAG retrieval; a read-only Kubernetes observation stream on top of this substrate (Phase 7.4+). None was implemented; none is pre-committed by 7.3.

## 26. ADR-065
**VERIFIED** `docs/adr/ADR-065-bitemporal-fact-derivation.md` records all decisions, non-goals, the relationship to ADR-064, and the Phase 7.4 boundary.

## 27. Phase 7.4 readiness
**Ready.** The fact ledger is bitemporal, append-only, tenant-scoped, provenanced, conflict-honest, and durable, with valid and knowledge time separated and four queries proven against real Postgres. Freshness and authority — the two things 7.3 deliberately did not invent — are exactly what 7.4 builds on top, plus (optionally) the first read-only provider observation stream feeding real observations into this pipeline. Phase 5.5 credential blocker untouched; L1–L16 intact; no second execution/governance/coordination authority; exactly-once not claimed.

## DoD checklist
**VERIFIED** contracts inspected · Fact representation confirmed · identity semantics confirmed · durable representation implemented · migration 0016 · one head · blank-PG migration verified · Observation→Fact derivation · deterministic reconciliation · repeated observation deterministic · valid time preserved · recorded time preserved · valid≠recorded provable · supersession preserves history · current query · world-time AS OF · known-time AS OF · history query · conflict stays CONFLICTED · UNKNOWN not FALSE · **STALE only with policy (none invented → not emitted)** · model-stated confidence can't become calibrated · provenance survives Observation→Fact · tenant isolation · cross-tenant fail closed · idempotent at semantic level · fresh-process read · crash/rollback · deterministic replay · World has no execution dependency · model cannot create Fact · fitness green (29) · regressions green (390) · developer DB untouched · ADR-065 · this report · Phase 7.4 boundary documented.

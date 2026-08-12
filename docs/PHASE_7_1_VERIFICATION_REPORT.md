# PHASE 7.1 — VERIFICATION REPORT

Date: 2026-08-11 · Branch `phase-1-foundation` · Commit `798f2db` (+ this report) · ADR-063

Labels: **[FACT]** repository-verifiable · **[SOURCE]** cited research · **[INFERENCE]** reasoning · **[PROPOSAL]** design choice · **[VERIFIED]** evidence produced this phase · **[NOT VERIFIED]** no evidence · **[DEFERRED]** out of scope · **[BLOCKED]** precondition absent.

This report does **not** claim Phase 7.1 complete merely because tests pass. §10–§12 state plainly what was proven, what was not, what was deferred, and whether Phase 7.2 is ready.

---

## 1. Discovery

**[FACT]** Part A re-confirmed against source: `backend/contracts/` is a flat leaf package importing only stdlib + other contracts (`DEP-CONTRACTS-LEAF`, `DEP-CONTRACTS-NO-BACKEND`), Python 3.11, no `kw_only` precedent. **[FACT]** `contracts/evidence.py` (`SourceStatus`, `Citation`) and `contracts/knowledge.py` (`KnowledgeAuthority`, I7) still had zero live importers; `contracts/verification.py` already provides the honest three-answer `Verdict` (SUPPORTED/UNSUPPORTED/INSUFFICIENT_EVIDENCE) and `VerifierIdentity`. **[INFERENCE]** The right move was to *salvage by importing* rather than duplicate — reusing `SourceStatus`, `KnowledgeAuthority`, and `Verdict` — which gives the dead contracts their first live importer and keeps one vocabulary. **[VERIFIED]** No contradiction with ADR-062 or Phase 7.0 was found.

## 2. Files changed

**[FACT]** Exactly the permitted scope (git-verified):
- **New:** `backend/contracts/world/` — `__init__.py`, `temporal.py`, `provenance.py`, `confidence.py`, `epistemic.py`.
- **New tests:** `tests/contracts/world/test_epistemic_contracts.py`, `tests/architecture/test_world_boundaries.py`.
- **Modified (one file):** `backend/platform/architecture/boundary_rules.py` — two new rules + exports.
- **No** migration, no `cw_*` table, no execution/persistence/scheduler/gateway/connector file touched (grep-confirmed).

## 3. Contracts created

**[FACT]** Value objects: `ObservationInstant` (observed_at vs retrieved_at), `ValidityInterval` (valid_from/valid_to, half-open), `ProvenanceRef` (reference-only + `SecretInProvenance` tripwire), `ClaimConfidence`/`CalibrationState`, `ModelStatedConfidence`, `SourceAuthority`. Records over the `EpistemicRecord` spine: `Observation`, `Fact`, `Belief`, `Hypothesis`, `Prediction`, `Outcome`, `WorldVerification`, `ModelProposal`. Enums: `EpistemicStatus`, `HypothesisStatus`, `ObservationSourceKind`. **[FACT]** All subclass `Contract`; all frozen; salvaged `SourceStatus` + `KnowledgeAuthority` + `Verdict`/`VerifierIdentity` reused.

## 4. Contract semantics (per the DoD non-collapses)

| Distinction | Mechanism | Label |
|---|---|---|
| Observation ≠ Fact | different types, no subclass relation; Observation has no valid-time/authority; Fact requires observation grounding | **[VERIFIED]** |
| Model output ≠ Fact | no `ObservationSourceKind.MODEL`; no `Fact.from_text`; `Fact.from_observations` requires real `Observation` objects; `ModelProposal` has no `to_fact` | **[VERIFIED]** |
| Fact ≠ Belief | different types; a Fact does not auto-become a Belief; Belief carries confidence + basis | **[VERIFIED]** |
| Hypothesis ≠ Fact/Belief | different type; `HypothesisStatus` has no VERIFIED | **[VERIFIED]** |
| Prediction ≠ Outcome | different types, no conversion; Outcome requires `execution_ref` | **[VERIFIED]** |
| Model verdict ≠ Verification | `WorldVerification` requires `procedure_ref` + `VerifierIdentity` + (for SUPPORTED) evidence | **[VERIFIED]** |
| Verbalized ≠ calibrated confidence | `ModelStatedConfidence` cannot become `ClaimConfidence`; UNCALIBRATED carries no value | **[VERIFIED]** |
| Stale/Conflicted/Unknown ≠ False | `EpistemicStatus` has these, deliberately no FALSE | **[VERIFIED]** |

## 5. Invariants enforced

**[VERIFIED]** Tenant scope explicit on every record (bare string/None refused). Temporal fields distinct (naive rejected, retrieved-before-observed rejected, half-open valid intervals). Provenance reference-only (credential-shaped values raise `SecretInProvenance`; producer required; ≥1 anchor to ground a claim). Immutability (frozen; mutation raises `FrozenInstanceError`). Schema versions explicit (`CONTRACT_NAME`/`CONTRACT_VERSION` on every type). Confidence: UNCALIBRATED has no value; CALIBRATED requires a value in [0,1]; SourceAuthority is a tier.

## 6. Tests

**[VERIFIED]** `tests/contracts/world/` — **50 tests pass**, covering all 12 DoD invariant families; every negative test proves a raised `ContractViolation`/`SecretInProvenance`/`FrozenInstanceError`, not a boolean. **[VERIFIED]** `tests/architecture/test_world_boundaries.py` — **11 tests pass** (CURRENT=PASS / SYNTHETIC=FAIL for both new rules, including the allowed-import cases that must not trip).

## 7. Architecture fitness

**[VERIFIED]** The gate PASSES: **27 rules, 0 failed, 6 skipped**, across 1121 modules. Two rules added: `BND-WORLD-CANNOT-EXECUTE` (the World Plane imports no connector/gateway/adapter/transport/credential/database/harness) and `BND-MODEL-CANNOT-CREATE-FACT` (intelligence/harness planes do not import the `Fact`/`Observation` constructors). **[VERIFIED]** `tests/architecture/` full suite — **155 tests pass** (validates the gate and every rule's sensitivity, including the two new ones). **[FACT]** The World Plane contracts pass `DEP-CONTRACTS-LEAF` — they import only other contracts + stdlib (the `re` dependency was removed to respect the contracts allowlist; the secret tripwire is dependency-free substring matching).

## 8. Regression results (Part O)

**[VERIFIED]** `tests/architecture/` (155) and `tests/contracts/world/` (50) green. The broad `tests/contracts/ + tests/architecture/ + tests/harness/` run under the root conftest is slow (the conftest probes Postgres per test) and was run in the background; its result is appended below on completion. **[INFERENCE]** The only production change is `boundary_rules.py` (+2 rules), fully covered by the 155-test architecture suite; the new contracts are additive leaves imported by nothing outside their own tests, so no existing suite's behavior can change. **[NOT VERIFIED]** a single local full-`tests/` pass (tool timeout; CI `test.yml` is the authority, unchanged this phase).

## 9. Defects discovered

**[FACT]** One, in this phase's own first draft: `provenance.py` imported `re`, which `DEP-CONTRACTS-LEAF` correctly rejected (not on the contracts stdlib allowlist). Fixed by removing the regex — the secret tripwire is now dependency-free substring matching — rather than widening the allowlist, preserving the contracts-leaf ratchet. No defect in existing code.

## 10. Explicit non-goals (what was intentionally NOT built)

**[DEFERRED]** No persistence, no `cw_*` table, no migration, no Redis/OpenSearch/vector/graph store (Part W hard prohibition honored). No ingestion, no retrieval, no world query API (Phase 7.2/7.10). No belief-revision storage (7.7), no contradiction engine (7.5), no calibration engine (7.9/7.12), no full bitemporal store (7.3). No execution influence — no scheduler/dispatcher/gateway/connector/authorization/capability/lease/approval touched (Part X honored). The four non-founding Phase 7.0 fitness rules (tenant/provenance/temporal/contradiction) were **not** added as import/AST rules: their invariants are enforced at the *type* level in 7.1, and an import-level rule would be cosmetic until 7.2+ persistence/ingestion code exists to violate — added then, per the Phase 6 no-cosmetic-rule discipline.

## 11. Risks

**[INFERENCE]** (1) The provenance secret tripwire is coarse substring matching (dependency-free by the contracts-leaf constraint); the real firewall is the platform `find_secrets` on the ingestion path (7.2), and provenance carrying references not payloads is the actual defence. (2) The type-level firewall (no `to_fact`, no MODEL source) is strong, but a determined caller could still construct a `Fact(...)` directly with a fabricated `observation_ref` string; `BND-MODEL-CANNOT-CREATE-FACT` closes this at the import level for the model planes, and 7.2's ingestion boundary is where the runtime grounding check lands. (3) `ModelProposal.model_stated_confidence` is typed `Optional[Any]` (to avoid a forward-reference cycle); a 7.2 tightening to `Optional[ModelStatedConfidence]` is noted.

## 12. Phase 7.2 readiness

**[INFERENCE] Phase 7.2 is ready.** The input contract it needs — a provenanced, tenant-scoped, immutable `Observation` with distinct observation/recording times and honest `SourceStatus` — exists and is tested, and the two founding boundaries (`BND-WORLD-CANNOT-EXECUTE`, `BND-MODEL-CANNOT-CREATE-FACT`) are enforced. 7.2 builds the deterministic ingestion boundary (connector reads → `Observation` records, `cw_observation` under Alembic, tenant fail-closed), strangling the first destructive JSON path, and makes `BND-TENANT-SCOPED-WORLD`/`BND-PROVENANCE-REQUIRED`/`BND-NO-SECRET-IN-PROVENANCE` load-bearing over real code. **[FACT]** Nothing in 7.1 pre-commits 7.2's storage choices; the contracts are storage-neutral value types.

## DoD checklist (Part Z)

**[VERIFIED]** 1 contracts exist · 2 dead contracts classified (salvaged, ADR-063 §3) · 3 Observation≠Fact · 4 Fact≠Belief · 5 Hypothesis≠Fact/Belief · 6 Prediction≠Outcome · 7 Verification≠self-report · 8 temporal semantics explicit · 9 provenance references explicit · 10 tenant explicit · 11 immutability enforced · 12 contradiction states representable · 13 model output cannot become Fact · 14 no execution authority · 15 no credentials · 16 contract tests pass (50) · 17 architecture fitness passes (27 rules; 155 tests) · 18 no persistence introduced · 19 no execution path changed · 20 ADR-063 exists · 22 Phase 5.5 blocker untouched. **[NOT VERIFIED / pending]** 21 full regression suite in one local pass (background run; architecture+contracts-world green; CI is authority).

---

## Appendix — broad background regression result

_(Filled from the background `tests/contracts/ + tests/architecture/ + tests/harness/` run; the architecture suite within it is already confirmed green at 155/155 standalone, and the world contracts at 50/50.)_

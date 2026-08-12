# PHASE 7.5 — VERIFICATION REPORT

Date: 2026-08-12 · Branch `phase-1-foundation` · ADR-067 · No new migration (belief is a derived projection)

Labels: **VERIFIED** (evidence this phase) · **NOT VERIFIED** (no evidence) · **DEFERRED** (out of scope) · **BLOCKED** (precondition absent). Code existing is not evidence — distributed claims cite the real-Postgres/real-process harness `scripts/phase75_belief_harness.py` (**29 checks, 0 fail, verdict VERIFIED** against a fresh `cortex_p75`). Source was trusted over reports (discovery re-read the epistemic contracts and confirmed nothing imports `Belief`).

## 1. Architecture discovery
**VERIFIED** Read the Constitution, Phase 7.0–7.4 reports, ADR-062–066, and the source. Findings that shaped the phase: the `Belief` contract, `ClaimConfidence` (with UNCALIBRATED state), `EpistemicStatus` (AFFIRMED/STALE/CONFLICTED/UNKNOWN — no FALSE, no SUPPORTED), `SourceAuthority`, `Hypothesis`, `ModelProposal` all already exist; **no** `Corroboration`/`SourceReliability`/`Calibration` contract exists; **nothing imports `Belief`** anywhere. So corroboration is built fresh, calibration is deferred, and forbidding model planes from importing `Belief` is a safe new invariant.

## 2. Existing epistemic contracts
**VERIFIED** Reused verbatim: `Belief` (subject/predicate/value/`confidence`/`status`/`basis`, grounding-required), `ClaimConfidence.uncalibrated()`, `EpistemicStatus`, `SourceAuthority` tiers, `ProvenanceRef`, and the Phase 7.4 `AuthorityDecision`/`FreshnessResult`/`ObservationEvidence`. No epistemic vocabulary duplicated; no new `EpistemicStatus` member added (Part H — AFFIRMED expresses supported/accepted).

## 3. Belief model
**VERIFIED** Observation ≠ Fact ≠ Belief ≠ Hypothesis ≠ Prediction ≠ Outcome ≠ Verification remain distinct types with no silent conversion (7.1 contracts, unchanged). A `Belief` is derived only from structured evidence — `BeliefFormation.form_*` takes real Facts/Observations; there is no text/`ModelProposal` path and no `to_belief` (unit `test_s16_model_cannot_create_belief`; a bare-provenance no-basis `Belief` is refused). Model-plane import of `Belief` is now forbidden (§16).

## 4. Corroboration
**VERIFIED** Independence, not counting (`backend/world/application/belief.py`). Evidence is grouped by source, latest-per-source; `CorroborationLevel` = INDEPENDENT (≥2 distinct sources agree) / SINGLE (one source; correlated duplicates add no independence) / CONTRADICTED (disagree) / INSUFFICIENT (none). Proven: single source → SINGLE (S1); two distinct sources agree → INDEPENDENT (S2/S4); same-source duplicate → SINGLE with `correlated_count≥1` (S3); disagreement → CONTRADICTED (S5) — unit tests + harness (real Postgres: `observations=13 > facts=11` because same-source duplicates persist as observations though the fact ledger dedupes them). **No numeric weights.** Limitation stated (§18).

## 5. Authority interaction
**VERIFIED** Authority is not replaced by corroboration (Part E). The effective value is the 7.4 authority decision's when governed; corroboration resolves only ungoverned propositions and only on agreement. Authority beats recency: a newer lower-tier cache does not displace the authoritative source (unit `test_s9`; harness "belief holds the authoritative value, not the newer cache"). Contradicting lower-tier evidence is retained (S10).

## 6. Freshness interaction
**VERIFIED** Freshness stays the explicit 7.4 policy. A supported-but-stale belief is **STALE** with value intact — never FALSE (unit `test_s7_stale_is_not_false`; harness "stale belief is STALE not AFFIRMED/FALSE", value `{replicas:5}` intact under an injected clock). No universal TTL invented.

## 7. Conflict handling
**VERIFIED** Equal-authority disagreement → CONFLICTED, both evidence paths kept, never silently resolved (unit `test_s6`; harness Part S6 against real Postgres — both competing values preserved). Ungoverned disagreement → CONFLICTED (S5).

## 8. Evidence/provenance
**VERIFIED** `BeliefView.to_dict()` is the structured graph: what / status / confidence / when-valid / as-known / authority (source, tier, reason) / freshness / corroboration (independent sources + supporting + contradicting evidence) / conflicted / tenant (unit `test_s11`; harness "belief grounds in the governed execution"). The `Belief` contract's provenance names its grounding observation; basis lists the evidence refs. Not flattened to prose.

## 9. Temporal correctness
**VERIFIED** Belief formation honors both axes — corroboration filters by `observed_at ≤ at_valid` AND `recorded_at ≤ known_at`, reusing the 7.3 projection. World @ 09:59 → 3, world @ 10:02 → 5; known @ 10:00 → UNKNOWN, known @ 10:05 → 5 (unit `test_s13`/`test_s14`; harness S13/S14 against real Postgres). Fact history is never destroyed.

## 10. Tenant isolation
**VERIFIED** Every fact/observation read is tenant-predicated and fails closed; a cross-tenant belief is UNKNOWN with empty corroboration (unit `test_s12`; harness S12 against real Postgres). A non-`TenantRef` is refused. No caller-side filtering.

## 11. Storage decision
**VERIFIED** A belief is a deterministic function of the durable facts/observations + policies, so it is a **derived projection — no `cw_belief` table, no migration** (Part O). Proven by deterministic reconstruction in a fresh process after a crash (§13). No mutable truth, no destructive update, no latest-wins.

## 12. Replay
**VERIFIED** Replay created zero new facts and zero provider reads; a belief was byte-identical (`to_dict`) before and after replay — belief reconstruction is pure reads (harness Part R against real Postgres).

## 13. Crash/recovery
**VERIFIED** Real Postgres + real `os._exit(9)`: a child ingested→derived a fact and died (exit 9); a successor process reconstructed the belief from the durable ledgers — value intact, deterministic across two reconstructions, cross-tenant fail-closed (harness Part S). No belief persistence to recover; the projection is the recovery.

## 14. Kubernetes decision
**DEFERRED** Phase 7.5 completes without the Kubernetes stream (belief formation is over the existing ledgers). The stream stays deferred for the 7.4 reason — the connector strips `resourceVersion`, has no `.watch()`, no governed K8s read capability; a stream would require fabricated continuity or a second connector (stop conditions). Not implemented, not faked.

## 15. Tests
**VERIFIED** 23 new tests: `tests/world/test_belief_formation.py` (17 — the S1–S17 matrix incl. determinism and UNCALIBRATED confidence), `tests/world/test_belief_fitness.py` (6). Regression `tests/world + architecture + harness + contracts/world`: **435 passed, 0 failed** (213s). **NOT VERIFIED** a single local full-`tests/` pass (root conftest probes Postgres per test; CI is the authority). No existing assertion weakened; all 7.4 query tests remain green.

## 16. Architecture fitness
**VERIFIED** Gate PASSES: **29 passed, 0 failed, 6 skipped** across 1136 modules. **One genuinely new invariant** (Part U): `BND-MODEL-CANNOT-CREATE-FACT` extended to also forbid model planes importing the `Belief` constructor (nothing imported it before, so current PASS; synthetic harness/agents imports of `Belief` FAIL — sensitivity tests). Belief formation under `backend/world/application` is otherwise already fenced by `WorldCannotExecuteRule`/`WorldApplicationPureRule` (proven: synthetic connector/database imports FAIL). No cosmetic rule.

## 17. Defects
**FACT** No defect in the 7.2–7.4 substrate surfaced under belief formation. One design point handled explicitly: 7.3 dedupes a second source that merely *agrees* (same value already effective), so corroboration reads the **observation** ledger (which keeps every source's row), not only fact versions — that is why `list_for_subject` was added and why the harness shows more observations than facts.

## 18. Risks
(1) Independence is by `source_ref`; two distinct sources that secretly share a backend (a copied cache) are treated as independent — refining this needs a source-lineage model (deferred). (2) Corroboration uses latest-per-source; a source that flaps could look single-valued at a chosen instant — acceptable, and the history remains queryable. (3) Belief is recomputed per query (no cache); at scale a materialization may be wanted, but Part O's "prefer projection" and Part T's "don't optimize prematurely" both point to the current design. (4) Confidence remains UNCALIBRATED by construction until an outcome-history phase exists — a consumer must not read absence-of-number as certainty.

## 19. NOT VERIFIED
- A single local full-`tests/` pass (subset + CI is authority).
- Live Kubernetes watch continuity (DEFERRED — §14).
- The LLM/model leg remains BLOCKED (placeholder credentials) and is not exercised; belief formation is deterministic and model-free by design.

## 20. Deferred
**DEFERRED** Numerical calibration (until measured prediction-vs-outcome history); source-lineage independence; governed corroboration/authority policies wired into a read loop; hypothesis/prediction formation consuming beliefs; the governed Kubernetes watch stream. None implemented; none pre-committed.

## 21. ADR-067
**VERIFIED** `docs/adr/ADR-067-corroboration-belief-formation.md` records the derived-projection decision, corroboration semantics, the authority/freshness/conflict interactions, the model-cannot-create-belief firewall, the K8s DEFERRED rationale, and the Phase 7.6 boundary.

## 22. Phase 7.6 readiness
**Ready.** The World Plane now forms deterministic, evidence-backed, tenant-scoped, bitemporally-correct beliefs with preserved conflict, freshness awareness, authority precedence over recency, independence-aware corroboration, UNCALIBRATED confidence, and a queryable evidence graph — no model deciding truth, no belief executing, no belief database. Phase 7.6 can add source-lineage independence, governed policies, or hypothesis/prediction formation on top. Phase 5.5 credential blocker untouched; L1–L16 intact; no second execution/governance/coordination authority; exactly-once not claimed.

## DoD checklist
**VERIFIED** Belief/Claim/Evidence contracts inspected · Observation/Fact/Belief distinctions preserved · corroboration contract defined · independent vs correlated distinguished · authority≠corroboration · recency≠authority · freshness policy-driven · STALE≠FALSE · UNKNOWN≠FALSE · equal-authority conflict preserved · supporting+contradictory evidence retained · belief provenance queryable · tenant isolation · temporal belief correctness · knowledge-time correctness · numerical calibration NOT invented (UNCALIBRATED) · model cannot create Belief · belief cannot execute · replay inert · crash/recovery (derived reconstruction) · fresh-DB Postgres (no belief table; ledgers migrated) · no create_all/stamping · 7.4 tests green · fitness green (29) · developer DB untouched · ADR-067 · this report · Phase 7.6 boundary documented. **DEFERRED** Kubernetes stream (§14).

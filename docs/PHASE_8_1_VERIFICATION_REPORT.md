# PHASE 8.1 — VERIFICATION REPORT

Date: 2026-08-12 · Branch `phase-1-foundation` · ADR-072 · Migration `0019_world_investigation`

Labels: **[FACT]** repo-verified this phase · **[SOURCE]** cited file/line · **[INFERENCE]** reasoning · **[PROPOSAL]** design (not yet built). A proposal is never presented as an implemented fact. Distributed durable claims cite the real-Postgres/real-process harness `scripts/phase81_investigation_harness.py` (**17 checks, 0 fail, verdict VERIFIED** against a fresh `cortex_p81`).

## 1. Architecture review
**[FACT]** Built on Phase 7 unchanged: the durable template/`DurableStore`, the contract base (`to_dict`/`from_dict`, tenant validation), the epistemic contracts (`HypothesisStatus`, `EpistemicStatus`, `ProvenanceRef`), the secret firewall (`platform.credentials.inspection.find_secrets`), and the fitness framework. No Phase-7 file was reopened. Discovery confirmed no pre-existing `Investigation`/`Incident`/`AutonomyLevel` contract to duplicate.

## 2. Existing contracts reused
**[FACT]** Reused verbatim: `Contract`, `TenantRef`, `ProvenanceRef`, `HypothesisStatus` (differential status), `EpistemicStatus`, and the `find_secrets` firewall. New contracts add only what is genuinely new (investigation workflow + autonomy). No numeric-confidence field anywhere.

## 3. Intelligence boundary
**[FACT]** New `backend/intelligence/` (application + infrastructure) + `backend/contracts/intelligence/`. **[FACT]** Fenced by `BND-INTELLIGENCE-CANNOT-EXECUTE` — imports no connector/execution/transport/credential-carrier/scheduler/computer/browser/MCP/direct-LLM; only the harness governed boundary and (infra) the durable store. Proven by sensitivity tests (synthetic connector/gateway/LLM/computer imports FAIL; durable store + `harness.GovernedModelBoundary` imports PASS).

## 4. Investigation contract
**[FACT]** `Investigation` is a frozen `Contract` — investigation_ref, tenant, incident_ref, status, autonomy_level, seq, created/updated, provenance, policy_ref, harness_version, current_question_ref, differential, and reference tuples (question/evidence/test/prediction/verification). It references World evidence, never duplicates it. Round-trips through the envelope (unit `test_seq_advances_and_snapshots_round_trip`).

## 5. State machine
**[FACT]** 10 statuses with an explicit `LEGAL_TRANSITIONS` table; invalid transitions raise `InvestigationTransitionRefused` (unit `test_illegal_transition_refused`; harness "illegal transition refused"). Terminal states refuse further transitions (unit + harness). **[FACT]** `EXECUTING → COMPLETED` is *not* legal — completion is reached only through `VERIFYING` (unit `test_verifying_can_return_to_investigating_not_skip`); UNKNOWN/INSUFFICIENT never skips to success.

## 6. Questions
**[FACT]** `InvestigationQuestion` (a unit of uncertainty) with purpose, required evidence, hypothesis refs, `created_by`, provenance — a model may propose it; the platform records it via `add_question` (not truth).

## 7. Hypothesis set
**[FACT]** The investigation owns a *set* of `DifferentialHypothesis` (evidence for/against/missing/contradicting, temporal fit, lineage origins, `HypothesisStatus`) — differential diagnosis, **no numeric confidence** (unit `test_hypothesis_set_supports_multiple_candidates`, `test_upsert_replaces_by_ref`, `test_no_numeric_confidence_field`; harness "differential holds 3 candidates").

## 8. Evidence references
**[FACT]** Evidence is referenced by ref (observation/fact/belief/verification), never copied; `link_evidence` dedupes and appends (unit; harness "reached READY_FOR_ACTION" after linking).

## 9. Investigation tests
**[FACT]** `InvestigationTest` carries a falsifiable purpose: `discriminates_hypothesis`, `evidence_expected`, `supports_if`, `contradicts_if`, `residual_uncertainty` (unit `test_investigation_test_has_falsifiable_fields`). The model supplies no URL/shell/provider/connector/credential — those are structural (the plane cannot import them, §3).

## 10. Prediction linkage
**[FACT]** `link_prediction` references the Phase-7 `Prediction` by ref; the test's optional `prediction_ref` ties a test to a prediction. **[INFERENCE]** No new prediction model was created — Phase 7 is reused.

## 11. Checkpoint
**[FACT]** `checkpoint` appends a `CHECKPOINT` event carrying the current snapshot — an explicit durable resume point that never advances the workflow (harness [D] uses it before the crash). Reconstruction restores the latest committed snapshot.

## 12. Autonomy
**[FACT]** `AutonomyLevel` A0–A4, default A1, platform-set. A real action requires A3+ **and** authorization: A1 cannot execute (`AutonomyRefused`); A3 requires a human `APPROVED` event; A4 requires a policy authorization ref (unit `TestAutonomy`; harness [B]/[D] "A1 cannot execute", "A3 without approval cannot execute", "A3 with human approval executes"). **[FACT]** No `promote_autonomy`/`set_autonomy` method exists; a model proposal never changes autonomy (unit `test_model_cannot_promote_autonomy`).

## 13. HITL
**[FACT]** `HumanEvent` requires a **namespaced identity reference** (e.g. `approval:req-1`), refusing a bare name (unit `test_human_event_actor_must_be_namespaced_identity`). The A3 execute path consumes a human `APPROVED` event. **[INFERENCE]** This references the governance/approval identity model rather than duplicating Phase-5 approval.

## 14. Model boundary
**[FACT]** `BND-MODEL-CANNOT-CREATE-FACT` extended to `backend.intelligence`: the plane cannot import `Fact`/`Observation`/`Belief`/`WorldVerification`/`Outcome` (unit `TestIntelligenceCannotWriteWorld`); it may import `Hypothesis`/`Prediction`/`ModelHypothesisProposal`. **[PROPOSAL]** The live model call flows through `harness.GovernedModelBoundary` — wired in Phase 8.4.

## 15. Tenant isolation
**[FACT]** Tenant is an explicit `TenantRef` on every contract; `create`/`reconstruct` refuse a non-`TenantRef`; cross-tenant reconstruction fails closed with `InvestigationNotFound` (unit `TestTenant`; harness "cross-tenant reconstruct fails closed" against real Postgres). No fetch-then-filter.

## 16. Secret safety
**[FACT]** Every event runs `find_secrets` over the payload and the snapshot before persisting; a secret-bearing hypothesis is refused (unit `test_secret_bearing_hypothesis_refused`). References and digests only — no credentials, no chain-of-thought.

## 17. Persistence decision
**[FACT/INFERENCE]** Justified in ADR-072: an investigation's workflow position is non-reconstructable from the World ledgers or `cw_reasoning`, so `cw_investigation` (migration 0019) is added — event-sourced, append-only, tenant-scoped, idempotent. **[FACT]** Blank `cortex_p81` migrated 0018→0019, single head; no create_all/stamping/SQLite; developer `cortexdb` untouched (only `cortex_p81`). One column-width defect found and fixed (`autonomy_level` String(16)→String(32) for `a3_approved_action`).

## 18. Crash recovery
**[FACT]** Real Postgres + real `os._exit(9)` before completion: the pre-crash events (create→investigate→question→hypothesis→checkpoint) survived; a successor reconstructed status **INVESTIGATING** (not a fabricated COMPLETED), with the pre-crash hypothesis intact, cross-tenant fail-closed (harness [D]). No fabricated progress; verification never skipped.

## 19. Replay
**[FACT]** Reconstruction is a pure read — five reconstructions created **zero** new events (harness [E]). Append-only + optimistic concurrency: a duplicate append at an already-committed seq collides and is refused, event count unchanged (harness [C]).

## 20. Observability
**[FACT]** Every event records investigation_ref, transition (from/to), cause, event kind, autonomy level, and the refs — no raw chain-of-thought. **[PROPOSAL]** Wiring these into the harness trace (Phase 6.2 fail-closed/best-effort semantics) is Phase 8.3/8.4.

## 21. V1 strangler
**[FACT]** No V1 intelligence was migrated; `BND-NO-V1-INTELLIGENCE-IMPORT` forbids the new plane importing any quarantined V1 package (unit `TestNoV1IntelligenceImport`; gate). **[PROPOSAL]** The first V1 migration (an RCA reasoner emitting a `ModelHypothesisProposal` into a governed investigation) is Phase 8.4+.

## 22. Fitness rules
**[FACT]** Gate PASSES: **32 passed, 0 failed, 6 skipped**. Two new rules (`BND-INTELLIGENCE-CANNOT-EXECUTE`, `BND-NO-V1-INTELLIGENCE-IMPORT`), each CURRENT=PASS / SYNTHETIC=FAIL; two existing rules extended to `backend.intelligence`. No cosmetic rule.

## 23. Tests
**[FACT]** 31 new tests: `tests/intelligence/test_investigation_service.py` (18 — state machine, autonomy, differential, tenant, secret, immutability, boundary), `tests/intelligence/test_intelligence_fitness.py` (13). Regression `tests/intelligence + world + assurance + architecture + harness + contracts/world`: **521 passed, 0 failed** (181s). **[NOT VERIFIED]** a single local full-`tests/` pass (CI is authority).

## 24. PostgreSQL verification
**[FACT]** `scripts/phase81_investigation_harness.py` — 17 checks VERIFIED vs fresh `cortex_p81` (durable state machine, reconstruction, cross-tenant fail-closed, illegal-transition + autonomy refusals, A3-human-approval, append-only + idempotency, crash `os._exit(9)` reconstruction with no fabricated progress, read-only reconstruction). 17 durable events. No provider/execution/world-write occurred.

## 25. Regressions
**[FACT]** All prior Phase-7 and earlier suites in the affected set remain green (521 total, 0 failed). No existing assertion weakened.

## 26. Defects discovered
**[FACT]** (1) A seq off-by-one — `create` committed at an incremented seq and returned the pre-commit snapshot, colliding the next op; fixed by making `_commit` append at the snapshot's own seq and each op advance seq explicitly (CREATED is seq 0). (2) `autonomy_level` column too narrow for `a3_approved_action` (18 chars > String(16)); widened to String(32). Both caught by the harness/tests, not shipped.

## 27. NOT VERIFIED
- A single local full-`tests/` pass (subset + CI is authority).
- The live model call through `GovernedModelBoundary` (contract/port defined; the loop is Phase 8.4).
- Concurrent multi-writer resume semantics under real contention (optimistic-concurrency collision is proven single-node; a contention stress test is Phase 8.2).
- The LLM leg remains BLOCKED (placeholder credentials) — no model was called this phase.

## 28. Deferred
**[DEFERRED]** The investigation loop (8.4), context assembly (8.3), evidence acquisition (8.6), prediction/assurance integration (8.7), incident memory (8.8), calibration (8.9), autonomous remediation A4 (8.10, off), the first V1 RCA migration, and the governed Kubernetes watch (Phase 7.9).

## 29. ADR-072
**[FACT]** `docs/adr/ADR-072-phase-8-1-intelligence-contracts-and-investigation-state.md` records the plane boundary, the contracts, the state machine, the autonomy invariant, the event-sourced persistence justification, and the crash/replay semantics.

## 30. Phase 8.2 readiness
**[INFERENCE] Ready.** An investigation is now a durable, typed, crash-safe, replay-safe, tenant-scoped, secret-firewalled state machine where the model cannot create truth, execute, or promote autonomy. Phase 8.2 builds the checkpoint/resume-under-contention semantics; 8.3+ add context assembly and the loop. Phase 7 unchanged; One Plane of Action, World immutability, independent Assurance, tenant isolation, and the Phase 5.5 blocker intact; L1–L16 ratification-pending; exactly-once not claimed.

## DoD checklist
**[FACT]** Intelligence Plane at the correct boundary · formal state machine · invalid transitions refuse · tenant-scoped · model output only via the governed boundary (port; live call deferred) · model cannot create World truth/Outcome/Verification · model cannot promote autonomy · investigation cannot execute · cannot acquire credentials · cannot select arbitrary providers/URLs/shell (structural) · differential-diagnosis hypothesis set · falsifiable tests · predictions reuse Phase 7 · checkpoint/recovery defined + verified · replay inert · secret firewall enforced · no duplicate World/Assurance/Execution architecture · V1 quarantined · fitness green (32) · real-Postgres evidence · real process-crash evidence · no exactly-once · Phase 5.5 untouched · Phase 7 unchanged.

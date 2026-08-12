# PHASE 8.2 — VERIFICATION REPORT

Date: 2026-08-12 · Branch `phase-1-foundation` · ADR-073 · No new migration (engine builds on 0019)

Labels: **VERIFIED** (evidence this phase) · **NOT VERIFIED** (no evidence) · **DEFERRED** · **BLOCKED**. Code existing is not evidence — distributed claims cite the real-Postgres/real-process harness `scripts/phase82_investigation_harness.py` (**18 checks, 0 fail, verdict VERIFIED** against a fresh `cortex_p82`). No proposal is presented as an implemented fact.

## 1. Discovery
**VERIFIED** Reused, not rebuilt: the 8.1 `InvestigationService`/contracts + `cw_investigation`, `WorldQuery`/`ObservationIngestion`/`FactDerivation` (Phase 7), the governed read path (phase72 pattern), `harness.GovernedModelBoundary` (the model seam), tool exposure, and the fitness framework. No second executor/scheduler/gateway/memory/RAG/world-store/assurance was created.

## 2. Context assembly (Part B)
**VERIFIED** `ContextAssembler` produces typed sections in a fixed order, each with provenance, inclusion reason, token estimate, and digest; a deterministic `context_digest`. Same inputs → same digest; different world evidence → different digest; budget deterministically drops the lowest-priority sections with an explicit reason while keeping the incident (unit `TestContext`). The engine records the digest per step (harness "context digests were recorded per step").

## 3. Investigation loop (Part C)
**VERIFIED** Platform-controlled OODA step: gather world evidence → assemble context → model propose → record proposed hypotheses → validate a test → governed read → update differential from the OBSERVED value → checkpoint → decide. The model proposes only; it never changes status/autonomy, creates truth, concludes, or executes (unit `TestLoop`, `test_model_suggestion_has_no_authority`; harness Part M).

## 4. Differential diagnosis (Part D)
**VERIFIED** A set of competing hypotheses is maintained and discriminated one test at a time; the differential updates from the observed value, not the model's claim; **no numeric confidence** (unit + harness "exactly one hypothesis affirmed (h1)"). The scripted scenario runs H1/H2/H3 and resolves to H1.

## 5. Evidence selection (Part E)
**VERIFIED** `EvidenceSelectionPolicy` refuses a test that: discriminates an unknown hypothesis, is non-falsifiable / lacks a structured expectation, names an undeclared tool, carries a URL/shell reference, or is redundant (unit `TestEvidencePolicy`). A valid test yields a read-only `EvidenceRequest`.

## 6. Governed world interaction (Part F)
**VERIFIED** Evidence acquisition drives a governed execution → Observation → Fact and returns references; the engine reads via `WorldQuery`. **Governed reads == provider calls (3 == 3)** — the engine makes no direct provider contact (harness "governed reads == provider calls"). Real observations/facts were created (obs=3, facts=1 — same-value reads dedup). `BND-INTELLIGENCE-CANNOT-EXECUTE` structurally forbids the engine importing a connector/gateway/provider.

## 7. Checkpoint / resume / contention (Part G)
**VERIFIED** Real Postgres + real `os._exit(9)` mid-investigation: a successor reconstructs the last committed snapshot (status INVESTIGATING, **not fabricated**), the pre-crash tests survive (**resume ≠ retry**), the loop resumes to a terminal conclusion, and **no already-run test is repeated** (redundancy policy). **Concurrent resume:** two writers loading the same snapshot both attempt the next seq — **exactly one commits, the loser raises `InvestigationConcurrencyError`** (no fork, no overwrite) — harness Part G/G2. **NOT claimed exactly-once.**

## 8. Interruption matrix (Part H)
**VERIFIED (partial)** The load-bearing boundaries are proven: mid-loop crash after checkpoint (reconstruct, no fabrication) and concurrent resume (single winner). **NOT VERIFIED** the exhaustive 12-boundary process-kill matrix — **DEFERRED**. **[FACT]** A crash after an external governed read but before the checkpoint leaves the observation durable (Phase 7 append-only) and the investigation at its last checkpoint; re-running the step re-reads (at-least-once), and the same-value observation dedupes — no fabricated progress. This is classified, not claimed exactly-once.

## 9. Loop termination (Part I)
**VERIFIED** Deterministic, evidence-based conclusions: RESOLVED (single hypothesis affirmed), CONFLICTED (two supported), UNRESOLVED/INSUFFICIENT_EVIDENCE (budget exhausted), BLOCKED/FAILED (governed read failed) — unit `TestLoop` (`test_step_budget_terminates`, `test_read_budget_terminates_insufficient`, `test_blocked_evidence_terminates_blocked`); harness "reached RESOLVED". Budgets (`max_steps`, `max_reads`, context tokens) prevent infinite loops; a model can never conclude.

## 10. Model / scripted provider (Part J)
**VERIFIED** Every model call is honestly labeled `provider="scripted"` (harness "step N provider is scripted"). **BLOCKED** the real LLM (placeholder credentials). **NOT VERIFIED / DEFERRED** the live `GovernedModelBoundary` wiring — the engine depends only on the `ModelProposalPort`, which is the exact seam a boundary-backed implementation plugs into without changing the engine; scripted evidence never masquerades as an LLM run.

## 11. Observability (Part K)
**VERIFIED** Each step carries investigation_ref, context digest, provider, the test/evidence refs, transition, and outcome — structured, no chain-of-thought. **PROPOSAL** Full harness-trace-span integration (Phase 6.2 fail-closed/best-effort) is Phase 8.3.

## 12. Security / firewall (Part L)
**VERIFIED** Gate PASSES: **32 passed, 0 failed, 6 skipped**. The engine (under `backend/intelligence`) cannot import connectors/gateway/transport/credentials/database-directly/computer/browser/MCP/direct-LLM (`BND-INTELLIGENCE-CANNOT-EXECUTE`), cannot import Fact/Belief/Verification/Outcome constructors (`BND-MODEL-CANNOT-CREATE-FACT`), and its ledger is append-only. No new fitness rule was required — the 8.1 rules cover the engine; proven by the existing sensitivity tests.

## 13. DevOps vertical slice (Part M)
**VERIFIED** One complete deterministic scenario against real Postgres: incident → create → assemble context → propose 3 hypotheses → discriminating tests → governed reads → observations/facts → differential updates → RESOLVED (h1), surviving an injected crash and resuming. No production write, no remediation (correct for 8.2).

## 14. Replay (Part N)
**VERIFIED** Reconstruction is a pure read — five reconstructions created zero investigation events, zero governed reads, zero world mutations, zero provider calls (harness Part N).

## 15. Tenant isolation (Part O)
**VERIFIED** Cross-tenant reconstruction fails closed with `InvestigationNotFound` (harness Part O; unit 8.1 `TestTenant`). Tenant is an explicit `TenantRef` throughout; no fetch-then-filter.

## 16. Performance (Part P)
**VERIFIED (measured, not optimized)** The slice ran the full loop + crash/resume + concurrent + replay in one process against real Postgres; investigation events = 38 across all scenarios. No indexes added beyond the 8.1 `cw_investigation` indexes; no premature optimization.

## 17. Regression (Part Q)
**VERIFIED** `tests/intelligence + world + assurance + architecture + harness + contracts/world`: **536 passed, 0 failed** (181s) — 15 new engine tests + the 8.1/Phase-7 suites, no assertion weakened. **NOT VERIFIED** a single local full-`tests/` pass (CI is authority).

## 18. Defects discovered
**FACT** The scripted model initially proposed a test for a hypothesis not yet in the differential (proposed the same step) — fixed by targeting a just-proposed hypothesis. A `test_identity` import was mis-collected by pytest — removed from the test's top-level import. No production-code defect; the 8.1 substrate behaved as reported (source-verified).

## 19. NOT VERIFIED
- The live `GovernedModelBoundary`/real-LLM leg (BLOCKED — placeholder credentials; scripted only).
- The exhaustive 12-boundary interruption matrix (partial coverage proven).
- Independent Assurance verification of a RESOLVED conclusion (Phase 8.7).
- A single local full-`tests/` pass (subset + CI is authority).

## 20. Deferred
**DEFERRED** Live model boundary wiring (8.3), harness-trace-span integration (8.3), richer read tools (8.6), Assurance-gated termination (8.7), remediation/A3 execution (8.10), the exhaustive interruption matrix, the first V1 RCA migration, the governed Kubernetes watch (7.9).

## 21. ADR-073
**VERIFIED** `docs/adr/ADR-073-investigation-engine.md` records context assembly, the platform-controlled loop, evidence selection, differential-from-observation, budgeted termination, crash/resume/contention, and the scripted-provider honesty.

## 22. Phase 8.3 readiness
**Ready.** CortexPrime can now investigate a DevOps incident using real world evidence, maintain a differential, survive a crash, resume correctly, run concurrently without forking, terminate deterministically, and never confuse the model's reasoning with reality — with the model as a scripted, clearly-labeled proposer. Phase 8.3 wires the live governed model boundary and trace spans. Phase 7, One Plane of Action, World immutability, independent Assurance, tenant isolation, and the Phase 5.5 blocker are untouched; L1–L16 ratification-pending; exactly-once not claimed.

## DoD checklist
**VERIFIED** deterministic + versioned context · context provenance traceable (digest per step) · platform-controlled loop · model output proposal-only · multiple competing hypotheses · falsifiable evidence tests · governed read path used exclusively · no direct provider access · checkpoint/resume after real process death · concurrent resume proven safe · resume distinguished from retry · interruption boundaries executed (key ones; exhaustive matrix DEFERRED) · deterministic stopping conditions · budgets prevent infinite loops · replay inert · tenant isolation fail-closed · secret firewall holds · no duplicate World/Assurance/Execution architecture · architecture fitness passes (32) · fresh-PostgreSQL harness passes · full vertical DevOps scenario passes · real LLM honestly BLOCKED · no exactly-once claim · ADR-073 · this report. **DEFERRED** live GovernedModelBoundary wiring, exhaustive interruption matrix, Assurance-gated termination.

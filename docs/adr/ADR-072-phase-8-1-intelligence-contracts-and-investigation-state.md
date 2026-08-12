# ADR-072 — Intelligence Contracts & Durable Investigation State

Status: Accepted · Date: 2026-08-12 · Phase 8.1 · Follows ADR-071 (Intelligence Plane direction) and ADR-062–070

## Context

Phase 8.0 defined the Intelligence Plane boundary and chose a differential-diagnosis investigation over the Phase-7 substrate, with the model proposing and the platform deciding. ADR-072 builds the *production boundary and durable state* for that lifecycle — before any autonomous loop exists. The question answered: **can an investigation be a durable, typed, crash-safe, replay-safe state machine without letting the model create truth or execute actions?**

## Decisions

**1. A new fenced Intelligence Plane.** `backend/intelligence/` (application + infrastructure) plus typed contracts in `backend/contracts/intelligence/`, mirroring the Phase-7 layering (`contracts/world` + `world/application`). It imports the World read layer, the epistemic/intelligence contracts, the harness governed model boundary, and — infrastructure only — the durable store. It imports no connector, provider SDK, credential carrier, transport, gateway, scheduler, leadership, computer-use, browser, MCP, or direct LLM provider. Composition supplies the ports. Investigation never executes.

**2. Typed investigation contracts.** `Investigation` (the folded aggregate snapshot), `InvestigationStatus` (a 10-state machine with an explicit legal-transition table), `AutonomyLevel` (A0–A4), `DifferentialHypothesis` (a differential candidate with evidence for/against/missing/contradicting, temporal fit, lineage origins, and a `HypothesisStatus` — **no numeric confidence**), `InvestigationQuestion` (a unit of uncertainty), `InvestigationTest` (a falsifiable test: what it discriminates, supports-if, contradicts-if, residual uncertainty), and `HumanEvent` (whose actor is a *namespaced identity reference*, never a free-text name). All are frozen `Contract` subclasses — tenant-scoped, provenance-bearing, serializable, immutable.

**3. Model proposes; platform decides.** A question/hypothesis/test carries a `created_by` producer label and is a reasoning artifact, never truth. The `InvestigationService` is the only mutator; there is no path from a model output to a status change, an autonomy change, a Fact, a Belief, an Outcome, or a Verification. Model output reaches the plane only through the harness `GovernedModelBoundary` (schema-validated); the loop that calls it is Phase 8.4.

**4. Autonomy is platform policy, never model-promotable.** `autonomy_level` is a construction/policy value (default A1); no operation raises it, and a model claiming "A4" has zero effect. A real action (transition to `EXECUTING`) requires A3+ **and** an explicit authorization — a human `APPROVED` event for A3, a policy authorization reference for A4. A0–A2 cannot execute at all.

**5. Explicit legal state machine.** Only listed transitions are allowed; an invalid transition raises `InvestigationTransitionRefused`. Terminal states (COMPLETED/FAILED/ABANDONED) have no outgoing edges. Crucially, `EXECUTING → COMPLETED` is not a legal edge — completion is reached only through `VERIFYING`, and an INSUFFICIENT verification returns to `INVESTIGATING`. UNKNOWN never becomes success; verification is never skipped.

**6. Persistence — an event-sourced append-only ledger (justified).** An investigation is a *stateful workflow position* (status + differential + open questions + checkpoint) that **cannot be reconstructed** from the World ledgers (which hold evidence/facts/verifications, not the loop's phase) nor from `cw_reasoning` (which holds hypothesis/prediction records, not a status machine). So `cw_investigation` (migration 0019) is added: each row is one immutable event carrying the full new aggregate **snapshot**; the latest committed snapshot (max `seq`) is the authoritative current state. Append-only (no update/delete), tenant-scoped, idempotent + optimistically concurrent (unique `identity_digest` over (tenant, investigation, seq) — a duplicate/racing append collides), secret-firewalled. **At-least-once, not exactly-once.**

**7. Crash recovery restores, never fabricates.** A real `os._exit(9)` before completion leaves the pre-crash events durable; a successor reconstructs the *last committed snapshot* (e.g. INVESTIGATING) — it never advances the workflow, invents a COMPLETED, or skips verification. Reconstruction is a pure read (zero new events).

**8. Tenant + secret discipline.** Tenant is an explicit `TenantRef` on every contract, from the governed context — never a payload/model/prompt; cross-tenant reads/reconstruction fail closed. Every event runs through the existing field-aware secret firewall before it is written (references and digests only, no credentials, no chain-of-thought).

**9. Fitness.** Two genuinely new rules — `BND-INTELLIGENCE-CANNOT-EXECUTE` (no connector/execution/transport/credential/scheduler/computer/browser/MCP/direct-LLM; only the harness boundary) and `BND-NO-V1-INTELLIGENCE-IMPORT` (the strangler ratchet). `BND-MODEL-CANNOT-CREATE-FACT` is extended to `backend.intelligence` (cannot import Fact/Observation/Belief/WorldVerification/Outcome), and `BND-OBSERVATION-APPEND-ONLY` to `backend.intelligence` (the ledger is immutable). No cosmetic rules: "model cannot promote autonomy" and "cannot bypass the harness" are code invariants proven by unit tests, not import rules.

## Explicit non-goals

No autonomous investigation loop (Phase 8.4), no live model call, no execution, no world-write, no numeric confidence, no second execution/governance/scheduler, no RAG, no V1 migration beyond quarantine. Exactly-once not claimed.

## Consequences

- Phase 8.2+ build the loop, context assembly, and evidence acquisition on this durable state machine.
- The V1 intelligence stack remains quarantined; nothing new imports it (enforced).
- Phase 7, One Plane of Action, World immutability, independent Assurance, tenant isolation, the secret firewall, and the Phase 5.5 credential blocker are untouched. L1–L16 remain ratification-pending.

## Phase 8.2 boundary

Phase 8.2 formalizes the durable *checkpoint/resume* semantics under concurrent writers and retries, and begins the read-only context assembly for investigation — still no live model call, still no execution, still model-cannot-create-truth.

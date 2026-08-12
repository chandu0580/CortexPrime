# ADR-073 — The CortexPrime Investigation Engine

Status: Accepted · Date: 2026-08-12 · Phase 8.2 · Follows ADR-071/072 and ADR-062–070

## Context

Phase 8.1 built the durable investigation state machine. ADR-073 builds the first real **Investigation Engine**: a platform-controlled OODA loop that turns an incident into a differential diagnosis over real World evidence, survives failure, resumes correctly, and never confuses the model's reasoning with reality. It reuses everything — the state machine, `WorldQuery`, the governed read path, the harness governed model boundary — and adds no executor, scheduler, gateway, memory, or RAG.

## Decisions

**1. Deterministic Context Assembly.** `ContextAssembler` builds the model's context from typed sections in a fixed order (`SECTION_ORDER`), each with provenance, source, freshness, an inclusion reason, a token budget, and a content digest. The whole assembly carries a `context_digest` that is a pure function of its inputs — the same investigation + world evidence + tools + policy + harness version produce the same digest. Budget enforcement is deterministic (keep by priority, drop the rest with an explicit reason). The model never selects its own context; there is no arbitrary prompt concatenation and no hidden memory injection.

**2. The model proposes; the platform decides (ports).** The loop obtains a schema-typed `InvestigationProposal` through a `ModelProposalPort`, records proposed hypotheses, validates a proposed test, runs a governed read through an `EvidenceAcquisitionPort`, and updates the differential — all as platform operations. The model cannot change status/autonomy, create Fact/Belief/Outcome/Verification, conclude the investigation, execute, or name a URL/shell/provider. The ports are Protocols supplied by composition, so the engine never imports a connector, provider SDK, or the execution gateway (enforced by `BND-INTELLIGENCE-CANNOT-EXECUTE`).

**3. Deterministic evidence selection.** `EvidenceSelectionPolicy` refuses a proposed test unless it discriminates a **known** hypothesis, has both a support and a contradict outcome plus a **structured** expectation the platform compares (never a model verdict), names a tool from the frozen read-only allowlist, carries reference-only subject/predicate (no URL/shell fragments), and is non-redundant (a deterministic test identity). Every governed read is read-only by construction.

**4. The differential updates from the OBSERVED value, never the model's claim.** After a governed read, the engine compares the observed world value to the test's structured `supports_value`/`contradicts_value` and marks the discriminated hypothesis SUPPORTED or REFUTED. The model's `suggested_conclusion` is advisory and has no authority.

**5. Evidence-based, budgeted termination.** The platform concludes: RESOLVED (a single hypothesis affirmed, none open), CONFLICTED (two supported), or — on budget exhaustion — UNRESOLVED / INSUFFICIENT_EVIDENCE. A failed governed read concludes BLOCKED (FAILED status). Explicit budgets (`max_steps`, `max_reads`, context tokens) bound the loop so it cannot run forever, repeat identical tests, or oscillate. `InvestigationConclusion` is a new additive contract axis; completion always goes through the legal state machine (no skipping VERIFYING for a real remediation; a read-only investigation may complete from INVESTIGATING with an epistemic conclusion). A model can never conclude.

**6. Governed reads via the existing path; real observations.** Evidence acquisition drives a governed execution → `Observation` → `Fact` (the Phase 7 path) and returns references; the engine reads world state via `WorldQuery`. The vertical slice proves the count of governed reads equals the provider-call count — the engine makes no direct provider contact.

**7. Crash/resume, not retry; concurrent resume.** The loop checkpoints durably each step (advancing budget counters). A real `os._exit(9)` mid-investigation leaves the last committed snapshot; a successor reconstructs it (never fabricating a forward transition) and continues — already-run tests are not repeated (the redundancy policy sees them in `test_refs`). Concurrent resume is safe by the 8.1 optimistic-concurrency constraint: two writers at the same seq collide and exactly one commits; the loser raises `InvestigationConcurrencyError` (no fork, no overwrite, no regression).

**8. Scripted provider, honestly labeled.** The real LLM is BLOCKED (placeholder credentials). The engine runs against a scripted `ModelProposalPort` labeled `provider="scripted"`; the port is the exact seam a `GovernedModelBoundary`-backed implementation plugs into without changing the engine. Scripted evidence never masquerades as an LLM run.

## Explicit non-goals

No remediation/action (A3+ execution is a later phase), no live LLM, no direct provider access, no numeric confidence, no RAG, no second executor/scheduler/gateway/memory. Exactly-once not claimed.

## NOT built / deferred (recorded honestly)

- The **live `GovernedModelBoundary` wiring** — the model port was scripted; the async boundary + trace-span integration is deferred to when real credentials exist (the engine already depends only on the port).
- **Independent Assurance verification of a RESOLVED conclusion** — 8.2's RESOLVED rests on world evidence; wiring the Assurance verifier into termination is Phase 8.7.
- **The exhaustive interruption matrix** — the key boundaries (mid-loop after checkpoint, concurrent resume) are proven; a full 12-boundary process-kill matrix is deferred.

## Consequences

Phase 8.3+ wire the live governed model boundary, richer evidence tools, and Assurance-gated termination. The V1 intelligence stack remains quarantined. L1–L16, One Plane of Action, World immutability, independent Assurance, tenant isolation, the secret firewall, and the Phase 5.5 blocker are intact.

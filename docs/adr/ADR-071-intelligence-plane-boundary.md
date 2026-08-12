# ADR-071 — The Intelligence Plane Boundary (Phase 8 direction)

Status: Proposed (discovery) · Date: 2026-08-12 · Phase 8.0 · Follows ADR-062 through ADR-070

## Context

Phase 7 completed a governed, evidence-backed World + Assurance substrate: bitemporal facts, lineage-honest beliefs, independent verification, and a durable reasoning trail, with model output structurally unable to become truth. The repository also contains a large, pre-existing V1 "intelligence" stack (~230 modules across 22 packages) that is disjoint from the governed plane and violates the Phase-7 invariants: it lets model output become stored "truth" (`MemoryContextService` "KNOWN FACTS" at confidence 0.9/0.85; `semantic_memory`/graph concepts at confidence 1.0), lacks tenant scoping, executes inline outside the governed path, holds provider keys directly, uses vector/graph RAG as a truth source, and self-declares success. Phase 8 must add an Intelligence Plane that *investigates incidents* — without inheriting any of those hazards.

## Decision

**1. A new, fenced Intelligence Plane.** Introduce `backend/intelligence/` as an application-only plane that **proposes and consumes evidence** but never acts or writes truth. It MAY: query the World, read evidence/beliefs, obtain schema-validated model proposals through `harness.GovernedModelBoundary`, generate hypotheses/investigation-plans/predictions as *proposals*, rank investigation candidates by a deterministic policy, and request more evidence. It MUST NOT: construct `Fact`/`Belief`/`Observation`/`Outcome`/`Verification`, bypass governance, call providers, acquire credentials or leadership, or execute shell/browser/computer-use. The Harness and the governed Execution plane remain the only actors.

**2. Reuse, do not rebuild.** The Intelligence Plane composes on the existing substrate — `WorldQuery`, the Assurance verifier, the reasoning ledger, the governed model boundary, the governed execution path, and tool exposure. No second execution authority, governance system, scheduler, or model gateway is created.

**3. Model output is always a schema-validated proposal, never truth.** Every model call flows through `GovernedModelBoundary.propose` (schema-validated, trace-recorded, redacted, deterministic `context_id`). Grounding stays with the World Plane, verification with the Assurance Plane.

**4. Differential diagnosis with epistemic states, no numeric confidence.** Investigation maintains a *set* of candidate hypotheses (each with evidence for/against/missing/contradictory, temporal fit, authority, lineage, status), eliminated only by contradicting evidence, and left CONFLICTED/UNKNOWN when evidence is insufficient. No invented confidence percentages.

**5. No RAG in the truth path.** Retrieval is subordinate to epistemic authority: a retrieved document can never override an authoritative world observation. `WorldQuery` is structured and needs no RAG. The V1 vector/Chroma/pgvector/Neo4j stack is quarantined, not wired in. Any lexical/structured retrieval added later is advisory and bounded.

**6. Single investigator + independent Assurance; no swarm.** One governed investigator with a deterministic planner state machine, plus the independent Assurance verifier (producer ≠ verifier). No specialist/parallel/debate multi-agent architecture is added without measured benefit.

**7. The V1 intelligence stack is quarantined and strangled.** It is classified KEEP/MIGRATE/REPLACE/QUARANTINE/DELETE (see the discovery report). New governed code must not import the quarantined packages (a strangler ratchet), and the ungoverned execution/memory/RAG paths are replaced by governed equivalents.

**8. Autonomy is an explicit A0–A4 ladder, default A1, A4 off.** The model cannot self-promote; A3 needs governed approval; A4 needs measured calibration + explicit policy + scoped blast radius. The V1 `autonomous_runtime` is a quarantine target.

## Consequences

- Phase 8 proceeds as a strangler over the V1 stack (like Phase 6/7 over V1), building a thin governed plane rather than extending legacy.
- New fitness rules (proposed for 8.1): `BND-INTELLIGENCE-CANNOT-EXECUTE`, `BND-INTELLIGENCE-CANNOT-WRITE-WORLD`, `BND-INTELLIGENCE-NO-DIRECT-PROVIDER`, `BND-NO-V1-INTELLIGENCE-IMPORT`.
- The real-LLM leg stays BLOCKED (Phase 5.5 class); investigation loops run against the controlled/scripted provider until real keys exist, always labeled.
- L1–L16, One Plane of Action, World immutability, bitemporal semantics, independent Assurance, tenant isolation, the secret firewall, at-least-once (never exactly-once), and the Phase 5.5 credential blocker are preserved.

## Status note

This ADR is **proposed** as the direction for Phase 8; it is ratified by implementation phase 8.1 (and by the user's ratification of L1–L16, still pending). No production code, migration, or table is created in Phase 8.0.

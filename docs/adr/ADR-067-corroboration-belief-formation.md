# ADR-067 — Corroboration & Belief Formation

Status: Accepted · Date: 2026-08-12 · Phase 7.5 · Follows ADR-062/063/064/065/066

## Context

Phases 7.1–7.4 gave the World Plane observations, bitemporal facts, and a queryable projection with freshness and authority. ADR-067 builds the bridge the Intelligence Plane consumes: **FACTS + EVIDENCE → CORROBORATION → BELIEF**. A Belief is CortexPrime's held position on a proposition, derived deterministically from structured evidence — never from model text, never a manufactured probability. The goal is not to make the model "more confident"; it is a deterministic, evidence-backed belief contract with a queryable evidence graph.

## Decisions

**1. Storage — a DERIVED PROJECTION, no table (Part O).** A belief is a pure function of the durable facts/observations and the explicit policies (authority, freshness, corroboration). It therefore reconstructs identically from the ledgers — proven by forming the same belief in a fresh process after a crash. So Phase 7.5 adds **no `cw_belief` table and no migration**. No mutable truth, no destructive update, no latest-wins. (The `Belief` contract from ADR-063 is instantiated as the typed result, not persisted.)

**2. Belief is derived only from structured evidence (Part C).** `BeliefFormation` (`backend/world/application/belief.py`) takes real Facts/Observations via the read layers; there is no text or `ModelProposal` input and no `to_belief`. The import-level firewall was extended: `BND-MODEL-CANNOT-CREATE-FACT` now also forbids the model planes (harness/agents/orchestration) from importing the `Belief` constructor — a genuine new invariant (nothing imported it before). A model plane consumes a belief as structured data (`BeliefView.to_dict`), never by constructing `Belief`.

**3. Corroboration is independence, not counting (Part D).** Evidence is grouped by source; **the most recent informative observation per source** is the source's position (same-source duplicates collapse to one — *correlated*, not independent). `CorroborationLevel`: INDEPENDENT (≥2 distinct sources agree), SINGLE (one source; correlated observations add no independence), CONTRADICTED (sources disagree), INSUFFICIENT (no evidence). No numeric source-reliability weights are invented; independence is by source identity. **Limitation, stated:** independence is by `source_ref`; detecting that two *distinct* sources share a backend (a copied cache) needs a source-lineage model and is deferred — distinct source_refs are treated as independent today.

**4. Authority is not replaced by corroboration (Part E).** The effective value is the Phase 7.4 authority decision's when a policy governs; corroboration only resolves an *ungoverned* proposition, and only when its sources agree. A lower-tier source that disagrees is retained as contradicting evidence, never counted away. **Recency ≠ authority** carries over from 7.4: a newer lower-tier cache never displaces the authoritative source.

**5. Conflict is preserved (Part G).** Equal-authority disagreement → belief CONFLICTED (value None, both evidence paths kept). Ungoverned disagreement → CONFLICTED (never silently succession-resolved). Contradictory evidence is never erased; it is listed in `contradicting`.

**6. STALE / UNKNOWN are never FALSE (Part F/H).** A supported-but-stale belief (per the explicit freshness policy) is **STALE** with its value intact — not AFFIRMED, not FALSE, not 0. Absence of covering evidence is **UNKNOWN** with no `Belief` object — not FALSE. `EpistemicStatus` already expresses all of AFFIRMED/STALE/CONFLICTED/UNKNOWN, so **no new status was introduced** (Part H); AFFIRMED is "supported/accepted".

**7. Confidence stays UNCALIBRATED (Part I).** Every belief's `confidence` is `ClaimConfidence.uncalibrated()` — no number is invented. `ModelStatedConfidence` remains a separate, unconvertible type. Numerical calibration is deferred until measured prediction-vs-outcome history exists.

**8. Bitemporal correctness (Part J).** Belief formation honors both axes: corroboration filters observations by `observed_at <= at_valid` **and** `recorded_at <= known_at`, and reuses the 7.3 projection. A belief at world time 10:05 does not see a state that became valid at 10:10; a knowledge-time belief at recorded time T does not see facts recorded later. History is never destroyed.

**9. Tenant isolation (Part K).** Every fact and observation read is tenant-predicated and fails closed; the belief's semantic identity includes the tenant. A cross-tenant belief is UNKNOWN with empty evidence.

**10. Provenance / explainability (Part L).** `BeliefView.to_dict()` is the structured evidence graph — WHAT / status / confidence / WHEN-valid / AS-KNOWN / authority (source, tier, reason) / freshness / corroboration (independent sources, supporting and contradicting evidence) / conflicted / tenant. A future LLM verbalizes it; the platform owns the graph.

**11. No execution, no RAG (Part M/N).** `belief.py` lives under `backend/world/application` and imports no connector/gateway/transport/credential/scheduler/execution (fenced by `WorldCannotExecuteRule`/`WorldApplicationPureRule`, proven by sensitivity tests). No embeddings, vector DB, or semantic retrieval — the deterministic substrate comes first.

**12. Determinism & replay (Part P/Q).** Same tenant + facts + observations + policies + world time + knowledge time → the same belief (`to_dict` byte-identical). Belief reconstruction is pure reads: zero provider calls, zero execution, zero audit writes (harness Part R). No wall-clock dependency — `now` is injected.

## Explicit non-goals

No numeric confidence/probability, no source-reliability weights, no latest-wins, no authority-by-source-counting, no silent conflict resolution, no belief mutating fact history, no belief table, no second coordination system, no embeddings/vector DB/RAG, no model-created beliefs, no belief executing anything. Exactly-once not claimed.

## Kubernetes decision (Part T)

Phase 7.5 completes **without** the Kubernetes watch stream — belief formation is over the existing ledgers. The stream remains DEFERRED for the same reason as 7.4: the connector strips `resourceVersion`, has no `.watch()`, and there is no governed K8s read capability; a stream would require fabricated continuity or a second connector path (stop conditions). Not implemented, not faked.

## Phase 7.6 boundary

Phase 7.6 may add: source-lineage independence (detecting shared backends between distinct sources), the first *governed* corroboration/authority policies wired into a read loop, or hypothesis/prediction formation consuming beliefs as advisory (never authoritative) input. The concrete deferred item — the governed Kubernetes watch stream with `resourceVersion` continuity and 410 recovery — remains gated on a connector that preserves resourceVersion. Numerical calibration remains deferred until outcome history exists. Belief still never executes, a model still cannot create a belief, and exactly-once is still not claimed.

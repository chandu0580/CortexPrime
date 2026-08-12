# ADR-063 — Epistemic Contracts: the World Plane Type System

Status: Accepted · Date: 2026-08-11 · Commit `798f2db` · Phase 7.1 · Follows ADR-062 (the World Plane)

## Context

Phase 7.0 (docs/PHASE_7_0_WORLD_PLANE_DISCOVERY.md) established that CortexPrime can safely *act* but has no coherent representation of what it *knows*: its world-state substrate is destructively-overwritten JSON snapshots, a staleness-free repository "brain", TTL-free caches, and a cross-tenant, LLM-writable memory subsystem. ADR-062 proposed the World Plane — a governed epistemic substrate that informs action but never executes. Phase 7.1 builds the **foundation**: the epistemic type system and its boundaries, and nothing else. No persistence, no ingestion, no retrieval, no execution influence.

## Decisions

**1. Why the contracts exist.** A small, strongly-typed vocabulary that future World Plane phases build on. The types make the five non-collapses (fact ≠ belief ≠ hypothesis ≠ prediction ≠ outcome ≠ verification) and the model-output firewall *structural*, before any storage or ingestion code exists to get them wrong.

**2. Location and shape.** `backend/contracts/world/` — a subpackage of the contracts layer, so the World Plane vocabulary is a leaf that imports only other contracts and stdlib (verified by `DEP-CONTRACTS-LEAF`). Every type subclasses `contracts._contract.Contract` (envelope, additive versioning, canonical serialization). Four record types over one immutable spine (`EpistemicRecord`: `record_id`, `tenant`, `recorded_at`, `provenance`), plus supporting value objects (temporal, provenance, confidence).

**3. Relationship to `contracts/knowledge.py` and `contracts/evidence.py` (Phase 7.0 verdicts, executed).** Both dead contracts (zero live importers) are **salvaged, not duplicated**: the World Plane is now their first live importer. `evidence.SourceStatus` (RETURNED_DATA/RETURNED_EMPTY/UNAVAILABLE/NOT_CONFIGURED — empty ≠ unavailable ≠ not-configured) is reused verbatim on `Observation`. `knowledge.KnowledgeAuthority` (AUTHORITATIVE/ADVISORY) is reused on `Fact`. Their record *shapes* (`KnowledgeItem`, `EvidenceSet`) were not adopted — they lack bitemporal time, tenant, and structured provenance — and their `AssembledContext` remains deprecated (dead + collides with the live `memory/models.py` Pydantic type; not touched in 7.1). The `Citation.observed_at`-vs-`retrieved_at` split is generalized into `ObservationInstant`.

**4. Ontology.** Observation (raw instrument evidence), Fact (normalized grounded claim), Belief (current position), Hypothesis (unresolved explanation, where model text lives), Prediction and Outcome (never collapsed), WorldVerification (assurance result, reusing the honest three-answer `Verdict` and `VerifierIdentity`). `ModelProposal` is the one typed home for raw model world-claims.

**5. Temporal semantics.** Three times, kept distinct: observation time (`ObservationInstant.observed_at`), recording/transaction time (`recorded_at` on every record), valid time (`ValidityInterval.valid_from`/`valid_to` on Fact). Bitemporal *persistence* is Phase 7.3; 7.1 defines the vocabulary and the Phase 7.0 correction example stays answerable by construction.

**6. Provenance.** Reference-only (`ProvenanceRef`): a required `produced_by` producer label plus optional pointers at immutable anchors (observation, execution, trace/correlation, parent claim). No secrets — a dependency-free tripwire raises `SecretInProvenance` on credential-shaped values; the real defence is that provenance carries references, not payloads.

**7. Tenant boundary.** Every record carries an explicit `TenantRef` on the contract (the spine), not inferred from request context; a bare string or `None` is refused at construction — scope is visible and fails closed (Part M).

**8. Immutability.** All records are frozen dataclasses. Observation/Fact/Prediction/Outcome/Verification are immutable values; Belief/Hypothesis are append-only-revision *in semantics* (revision storage is a later phase). `RETRACTED` marks a superseded version; nothing is destructively overwritten.

**9. Confidence semantics.** No bare `confidence: float`. `ClaimConfidence` is UNCALIBRATED (no value permitted) until measured against logged outcomes; `SourceAuthority` is a tier, not a number; `ModelStatedConfidence` is a separate type with **no conversion** to `ClaimConfidence` — a model's verbalized "95%" can never become platform confidence.

**10. Contradiction semantics.** `EpistemicStatus` carries AFFIRMED/STALE/CONFLICTED/UNKNOWN/RETRACTED and deliberately **no FALSE** — a fact may be conflicted or stale without becoming false; the contradiction/freshness *engines* are later phases, these are the states they set.

**11. Model-output boundary (the firewall).** Structural at three levels: (a) type — no `ObservationSourceKind.MODEL`, no `Fact.from_text`, no `ModelProposal.to_fact`; (b) construction — `Fact.from_observations` requires real `Observation` objects and grounding provenance; (c) import — `BND-MODEL-CANNOT-CREATE-FACT` forbids the intelligence/harness planes from importing the `Fact`/`Observation` constructors. Model output becomes a `ModelProposal` or `Hypothesis`; only the deterministic ingestion boundary (Phase 7.2) grounds a fact.

**12. Memory/world separation.** The World Plane imports none of the V1 memory stores; a memory item, if used, is a *reference* in provenance, never automatic truth (Part S). Enforced by the leaf-import discipline and `BND-WORLD-CANNOT-EXECUTE`.

## Explicit non-goals (Phase 7.1)

No persistence, no `cw_*` table, no migration, no Redis/OpenSearch/vector/graph store, no ingestion, no retrieval, no world query API, no execution influence, no belief-revision storage, no contradiction engine, no calibration engine, no full bitemporal store. `WorldCannotExecuteRule` and `ModelCannotCreateFactRule` are the two founding fitness rules; the other four Phase 7.0 candidates (tenant/provenance/temporal/contradiction) are enforced at the *type* level in 7.1 and become import/AST fitness rules in the phase that builds the corresponding persistence/ingestion code (adding them now would be cosmetic — no code path exists to violate them).

## Phase 7.2 boundary

Phase 7.2 builds the deterministic **observation ingestion boundary**: connector reads → provenanced, tenant-scoped `Observation` records (append-only, `cw_observation` under Alembic), with the first destructive JSON path strangled. It is the first phase to introduce persistence, and the first to make the `BND-TENANT-SCOPED-WORLD`, `BND-PROVENANCE-REQUIRED`, and `BND-NO-SECRET-IN-PROVENANCE` rules load-bearing over real code. The type system this ADR records is its input contract.

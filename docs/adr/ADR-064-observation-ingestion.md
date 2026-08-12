# ADR-064 — Observation Ingestion: the World Plane's First Durable Ledger

Status: Accepted · Date: 2026-08-11 · Commit `ee43f3a` · Phase 7.2 · Follows ADR-062 (World Plane), ADR-063 (epistemic contracts)

## Context

ADR-063 built the World Plane type system (contracts only, no persistence). ADR-064 builds the first durable boundary: a governed external READ becomes an immutable, provenanced, tenant-scoped `Observation`. This is the ingestion boundary the whole World Plane rests on — the point where external reality enters durable world state, and the point where the model-output firewall is made real. It builds persistence and one strangler; it builds no facts, beliefs, hypotheses, predictions, queries, or execution influence.

## Decisions

**1. The selected ingestion boundary.** A governed provider READ (through the Phase 5 gateway, driven by the scheduler — no manual dispatch) produces a result; the composition hands that result, plus the governed context, to `ObservationIngestion`, which maps it deterministically to an `Observation` and records it. The ingestion service never reads a provider itself — the dependency arrow is `Provider/Connector → Observation boundary → World Plane`, never the reverse (Part S).

**2. Observation identity (Part J, STEP 9).** A digest over `(tenant, source_kind, source_ref, subject_ref, predicate, observed_at, value)`, computed through the platform's canonical digest — so the identity is **key-order independent**: two payloads that differ only in JSON key order (at any nesting depth) produce the same identity, while a genuinely changed value produces a different one (tamper-evident). It is not a bare payload hash — the named fields mean the same value under a different subject or tenant is a different observation. Two identical external deliveries produce the same identity and collide on the unique constraint; a new value or a later `observed_at` is a new identity and a new row. **At-least-once with deterministic identity, NOT exactly-once** — the unique constraint dedupes, it does not make delivery exactly-once, and nothing claims it does.

**3. Tenant model (Part D).** Tenant comes from the governed context, never from the payload, source name, model output, URL, or connector metadata. `Observation` carries an explicit `TenantRef`; the ingestion service takes tenant as a parameter and refuses a non-`TenantRef`; the SQL reads are tenant-predicated and a cross-tenant id returns nothing (fail closed).

**4. Provenance (Part E).** Reference-only `ProvenanceRef` — a required producer label plus pointers at the observation's source, the governing execution, and the trace correlation. No credential material: the `ProvenanceRef` contract raises on secret-shaped values, and the ingestion service runs a field-aware secret firewall over the observation value before persisting.

**5. Temporal semantics (Part F).** `observed_at` (when the instrument says the world was in this state) is stored distinctly from `retrieved_at` (when queried) and `recorded_at` (when the row was written). A plain read reflects "now", so the mapping sets `observed_at == retrieved_at` and says so; the distinctness is a real, tested column separation for the phases that will exploit it. `valid_from`/`valid_to` are NOT on the observation — those are bitemporal fact concerns (Phase 7.3).

**6. Source status (Part G).** `contracts.evidence.SourceStatus` reused verbatim: `RETURNED_DATA` / `RETURNED_EMPTY` / `UNAVAILABLE` / `NOT_CONFIGURED` — empty is not unavailable is not not-configured, and an absence carries no value.

**7. Persistence (Part C).** `cw_observation`, migration 0015, Alembic only (no `create_all`, no stamping, no SQLite substitution). The `cw_` prefix marks it a World Plane ledger distinct from the `cp_*` execution fabric, on the same durable template (tenant NOT NULL, app-clock timestamps, digest identity, unique constraint for idempotency).

**8. Append-only + round-trip (Part K, STEP 6/8).** Observations are immutable evidence; a newer observation is a new row. The repository issues only `INSERT` and `SELECT` — no `UPDATE`, no `DELETE` — and `BND-OBSERVATION-APPEND-ONLY` forbids `sa.update`/`sa.delete` anywhere under `backend/world`. Immutability is enforced at the object level too: the `Observation` is a frozen dataclass, so any attempt to reassign a field raises `FrozenInstanceError` (proven positively, not merely documented). The stored `record` column is the observation's own `to_dict()` envelope, so `SqlObservationRepository.get_observation` reconstructs a value-equal `Observation` via `from_dict` — the `Observation → PostgreSQL → Observation` round-trip preserves provenance, both instants, the recording time, the source, the status and the identity digest, verified against real Postgres and across a real process crash.

**9. The provider read boundary (Part H) and model-output firewall (Part I).** Provider and operation come from the deployment registry (through the governed gateway), never from model output. There is no `Observation.from_model`/`from_text`, no `MODEL` observation source kind, and the ingestion service accepts a `ReadObservation` produced by a governed read, never a model proposal. Model output cannot become an observation.

**10. Replay semantics (Part N).** Replay of an execution performs no fresh read and creates no observation — proven with counters (zero new observations, zero provider reads across a replay). Observations are historical evidence; replay reconstructs, it does not rewrite.

**11. Crash semantics (Part M, STEP 13-I).** Verified against real PostgreSQL and a real `os._exit(9)`: an observation committed before the crash survives intact with a stable identity, a successor process reconstructs the full `Observation` (provenance and identity intact) via `get_observation`, and a duplicate delivery dedupes rather than creating a second row. A death mid-transaction rolls back (the atomic store), leaving no partial observation — proven directly by a probe that inserts a row then raises inside `atomic()` and confirms the row count is unchanged and the row is unreadable.

**12. V1 strangler decision (Part P).** `KubernetesIntelligence.track_pod` — a single destructive world-state upsert that mutates a pod record in place (losing the prior observation) and rewrites the whole JSON file — is quarantined behind `guard_legacy_internal`, non-authoritative by default. Its prior destructive behavior is proven, then its refusal is proven. The append-only observation ledger is the governed replacement. The old data is not migrated and the old path is not deleted (Part P); the sibling `track_*` methods remain for later phases (exactly one path strangled this phase). No dual-write.

**13. Security (Part Q).** Field-aware, nested-structure secret detection (`backend.platform.credentials.inspection`, relocated from the harness firewall so both planes reuse it) refuses any observation value carrying a token, key, bearer, or authorization value; safe references (`credential_ref`, `authorization_digest`, provider ids) remain allowed.

**14. Fitness rules (Part R).** Refined `BND-WORLD-CANNOT-EXECUTE` (allow `database.durable` + the credential *detectors* for the world infrastructure; forbid connectors, execution, transport, credential *carriers*, harness); added `BND-WORLD-APPLICATION-PURE` (the application layer imports no database) and `BND-OBSERVATION-APPEND-ONLY`. Each CURRENT=PASS / SYNTHETIC=FAIL. The other Phase 7.0 candidates (tenant/provenance) stay enforced at the type/schema level — an import rule would be cosmetic.

## Explicit non-goals

No fact inference, no belief revision, no hypothesis/prediction engine, no outcome reconciliation, no contradiction resolution, no semantic/vector/graph query, no RAG, no embeddings, no automatic belief generation, no execution planning, no autonomous remediation. Execution does not consume World Plane state in this phase. No `valid_from`/`valid_to` bitemporal store. No second database, no second governance, no second audit system.

## Relationship to ADR-063

ADR-063 is the input contract: `Observation`, `ObservationSource`, `ObservationInstant`, `ProvenanceRef`, `SourceStatus`. ADR-064 gives the first of those a durable home and a deterministic write boundary, and turns the type-level firewall into a runtime one (the ingestion service is the only sanctioned constructor path, and only from a governed read).

## Phase 7.3 boundary

Phase 7.3 builds bitemporal **fact derivation**: deterministic rules that fold observations into facts with valid-time (`valid_from`/`valid_to`) and transaction-time, supersession-not-deletion, and as-of queries — answering the Phase 7.0 correction example against real Postgres. It is the first phase to create a record type *derived from* observations rather than ingested, and the first where `KnowledgeAuthority` and `EpistemicStatus` become load-bearing. It reads the observation ledger this ADR built; it still never executes.

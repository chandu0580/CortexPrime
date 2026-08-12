# ADR-065 — Bitemporal World-Fact Derivation

Status: Accepted · Date: 2026-08-12 · Phase 7.3 · Follows ADR-062 (World Plane), ADR-063 (epistemic contracts), ADR-064 (observation ingestion)

## Context

ADR-064 gave the World Plane a durable observation ledger. ADR-065 builds the first layer *derived from* observations: a deterministic reconciler folds observations into **facts** with two independent temporal axes, so the World Plane can answer two different questions — *what was true in the world?* (valid time) and *what did CortexPrime know?* (knowledge/transaction time). It derives facts only; it builds no beliefs, hypotheses, predictions, queries beyond the minimum, retrieval, or execution influence.

The contracts already carried the vocabulary (ADR-063): `Fact.validity` (`ValidityInterval`, valid time), `EpistemicRecord.recorded_at` (knowledge time), `Observation.instant.observed_at` (world time as the instrument reported it), `EpistemicStatus` (AFFIRMED/STALE/CONFLICTED/UNKNOWN/RETRACTED — no FALSE), `ProvenanceRef` (`observation_ref` grounding, `parent_claim_ref` lineage), `KnowledgeAuthority` (tier). **No field names were invented** — the phase used these.

## Decisions

**1. Semantic identity, not a UUID (STEP 3).** A fact's semantic identity is `digest(tenant, subject_ref, predicate)` — every version/state of "deployment/payments spec.replicas" shares it. The value is *not* in the identity (a different value is a different *version* of the same proposition). Tenant is part of the identity, so the same subject/predicate in two tenants is two propositions. Version identity (for idempotency) is `digest(semantic_identity, value, valid_from)`, canonical and key-order independent.

**2. Structured value, not prose (STEP 4).** A fact stores the observation's structured value (`{"replicas": 5}`), never an interpretive sentence. Interpretation is not deterministic observation-derived state.

**3. Two temporal axes, never collapsed (STEP 5).** Valid time = `valid_from` (from the observation's `observed_at`) / derived `valid_to`; knowledge time = `recorded_at` (caller-supplied). A value valid from 09:58 can be recorded at 10:10; an as-of-valid query returns what was true then, an as-known query returns what we had recorded then, and neither overwrites the other.

**4. Append-only version ledger; `valid_to` derived, never mutated (STEP 7/13).** Each derivation appends at most one immutable `cw_fact` version. A correction or world change is a **new row**; no prior row is ever updated or deleted (enforced by `BND-OBSERVATION-APPEND-ONLY`, which covers all of `backend/world`). The *effective* end of a value's valid interval is **derived at query time** from the next differing-value version — so the ledger stays pure append-only and history stays reconstructable. `BND-OBSERVATION-APPEND-ONLY` and the SQL repo's insert/select-only surface make destruction structurally impossible.

**5. Deterministic reconciliation, policy-free (STEP 8/14).** Given the value effective at the new observation's `valid_from` under current knowledge:
- **different `valid_from` + different value → valid-time succession** (AFFIRMED; the world changed; the prior interval is bounded at query time, prior row retained);
- **same `valid_from` + different value → CONFLICTED** — two values for the same world-instant with no authority to choose; both retained and traceable, **never latest-wins** (timestamp order is not epistemic authority);
- **value already effective at that instant → idempotent no-op** (nothing recorded).
No threshold, freshness window, or authority ranking is invented to resolve conflicts.

**6. UNKNOWN, not FALSE, from absence (STEP 9).** A non-informative observation (empty / unavailable / not-configured) derives **no fact**; the identity simply has no versions and projects to `UNKNOWN`. `EpistemicStatus` has no FALSE member. STALE is never emitted — no freshness policy exists yet, and inventing one to satisfy a test is a stop condition. The two timestamps are preserved for the phase that defines freshness.

**7. No invented confidence (STEP 10/12).** A `Fact` carries **no** `ClaimConfidence` field at all; a single uncorroborated source derives `KnowledgeAuthority.ADVISORY` (a provenance-derived tier, never a number). `ModelStatedConfidence` remains a separate, unconvertible type — a model's "95%" can never become a calibrated confidence, because the derivation never touches confidence.

**8. Provenance chain (STEP 11).** A fact's `ProvenanceRef` carries `observation_ref` (the grounding observation), the observation's own `execution_ref` and `trace_ref` (so Fact → Observation → governed execution → audit is traceable), and `parent_claim_ref` (the prior version it succeeds or conflicts with — a reference, never deletion).

**9. Model firewall preserved (STEP 20).** A fact is derived only from a **real `Observation` object** (which itself can never have a MODEL source). There is no text/proposal path in the derivation service. `BND-MODEL-CANNOT-CREATE-FACT` already forbids the model planes (harness/agents/orchestration) importing `Fact`; the derivation layer is not a model plane. No new fitness rule was added — the existing rules cover the fact modules, proven by sensitivity tests (a synthetic `sa.update` in the fact infra FAILs; a synthetic model import of `Fact` FAILs).

**10. Storage (STEP 12).** `cw_fact`, migration 0016, Alembic only (no `create_all`, no stamping, no SQLite). `cw_` marks a World Plane ledger; the same durable template as `cw_observation`. Unique constraint on `version_digest` (idempotency); indexes on `(tenant_id, semantic_identity)` and `recorded_at`.

**11. Minimum bitemporal query surface (STEP 16).** Four pure projections over the version set — **current** (latest knowledge, valid now), **as-of-valid** (what was true at world time T), **as-known** (what was recorded by knowledge time K), **history** (the full immutable version list). No semantic/vector/graph/RAG/LLM retrieval — the truth substrate comes before retrieval (STEP 23).

## Explicit non-goals

No belief revision, hypothesis/prediction engine, outcome reconciliation, authority-ranked or freshness-based conflict resolution, semantic/vector/graph query, RAG, embeddings, confidence calibration, execution influence, or Kubernetes/provider connector. Facts inform; they never execute. No second database, transaction manager, governance, or audit.

## Relationship to ADR-064

ADR-064's `Observation` is the input; ADR-065 derives `Fact` from it deterministically and gives it a bitemporal durable home. The firewall stays intact: only a real observation (never a model) grounds a fact, and the model planes cannot import `Fact`.

## Phase 7.4 boundary

Phase 7.4 is the first phase that may consume the fact ledger for something beyond storage: freshness/STALE policy (turning the preserved timestamps into an explicit staleness classification), authority/corroboration promotion (SINGLE_SOURCE → CORROBORATED → AUTHORITATIVE, refining succession-vs-conflict when sources disagree), or the beginnings of belief formation. It still never executes, never lets a model create a fact, and never claims exactly-once. Freshness and authority are the deferred pieces this phase deliberately did not invent.

# ADR-066 — World Query, Freshness & Authority

Status: Accepted · Date: 2026-08-12 · Phase 7.4 · Follows ADR-062/063/064/065

## Context

Phases 7.1–7.3 built the World Plane's contracts, observation ledger, and bitemporal fact ledger. ADR-066 makes the World Plane **trustworthy to query**: a read-only, deterministic, explainable query surface that answers *what is true, when it was true, when we knew it, how fresh the evidence is, why a value is authoritative, whether it is conflicted or merely unknown, which observations support it, and from which source* — without any LLM deciding truth and without any query result authorizing execution. It adds no storage and does not touch Phase 7.3's ledger; it composes the existing bitemporal projection with two new explicit policies.

## Decisions

**1. Read-only WorldQuery over reader ports (Part B/N).** `backend/world/application/world_query.py` defines a `WorldQuery` service depending on two narrow *reader* Protocols — `FactVersionReader.versions_for` and `ObservationReader.get_observation` — both satisfied by the existing SQL repositories. It has no write path, imports no connector/gateway/transport/credential/scheduler/execution, and contacts no provider. `WorldCannotExecuteRule` and `WorldApplicationPureRule` already fence it (proven by sensitivity tests); **no new fitness rule** was added.

**2. Five deterministic query capabilities (Part B).** `current`, `as_of_valid`, `as_known`, `history`, `evidence_for`. The first three reuse the Phase 7.3 pure projection (`project_valid_at` / `knowledge_current`) unchanged — the load-bearing example's answers are byte-identical to 7.3 (no regression). No embeddings, vectors, graph, RAG, or NL retrieval (Part U).

**3. Explainable typed result (Part I).** `WorldQueryResult.to_dict()` answers WHAT / WHEN (valid) / AS-KNOWN (recorded) / WHY (authority) / SOURCE / FRESH? / CONFLICTED? / EVIDENCE / TENANT — a structure a future LLM consumes without reconstructing temporal truth itself. It carries both the raw `temporal` projection and the `authority`/`freshness` overlays; `effective_value`/`effective_status` are the answer to act on.

**4. Freshness is an explicit policy, never a universal TTL (Part C/D/L).** `FreshnessPolicy` is a set of explicit `FreshnessRule`s, each stating a horizon for a source-kind/predicate match. A fact matched by no rule is **UNKNOWN** freshness — staleness is never assumed. `FreshnessState` is a separate axis from the fact's value: **STALE ≠ FALSE ≠ 0** (a stale `replicas=5` is still 5). The evaluation clock is injected (`now` is a parameter), so freshness is reproducible under a deterministic test clock and the governed clock in production.

**5. Authority is a deterministic source-tier decision (Part E/F/H).** `AuthorityPolicy` maps a source (kind/ref) to the existing `SourceAuthority` tier (UNVERIFIED < SINGLE_SOURCE < CORROBORATED < AUTHORITATIVE); an unnamed source is UNVERIFIED. The query applies it at **read time** over the versions covering the queried instant — it never mutates the ledger. **Recency is not authority (Part F):** a newer lower-tier observation (a stale cache) never overrides a higher-tier source (the cluster API); the highest tier decides, and recency is only a tiebreak *within* one tier (the same source changing over time — the ordinary 7.3 projection restricted to that tier). **No authority to choose ⇒ CONFLICTED (Part K):** when the highest tier disagrees at the same valid instant, neither value is selected and both are preserved. Every non-selected value appears in `alternatives` with its source and tier. A model never defines authority or breaks a tie.

**6. Multi-source evidence (Part G).** Multiple observations for one semantic identity are already multiple fact versions (7.3). `evidence_for` and the result's `evidence` expose each supporting observation with source, timestamps, status, value, and its authority tier — never collapsed to prose.

**7. Kubernetes read-only stream — DEFERRED (Part O/P).** The existing governed connector cannot cleanly expose watch continuity: `backend/connectors/kubernetes.py` `list_*` methods **strip `resourceVersion`**, there is **no `.watch()`**, and there is **no governed K8s read *capability*** (only the legacy ungoverned V1 route). Implementing a stream would require fabricating continuity, restarting silently from "latest", building a second connector path, or a World→Kubernetes socket — every one a stated stop condition. So it is **deferred**, honestly. The observation contract already accommodates a future governed K8s connector (source_kind CONNECTOR, `observed_at` for the provider timestamp, `subject_ref` for object identity); when such a capability lands preserving `resourceVersion`, it feeds the existing ingestion→derivation→query pipeline unchanged.

## Explicit non-goals

No embeddings/pgvector/FAISS/Qdrant/Chroma/Neo4j/LangChain/semantic/graph/LLM retrieval. No model deciding truth or authority. No query result authorizing execution. No mutation of the fact ledger by freshness or authority. No second storage/transaction/governance system. No invented universal freshness TTL. No arbitrary numeric source-priority. Exactly-once not claimed.

## Relationship to Phase 7.3

The bitemporal projection is reused verbatim; the fact ledger is untouched. Freshness and authority are read-time overlays that add axes without changing what the ledger stores or how 7.3 reconciles — the 7.3 CONFLICTED reconciliation stands, and the query may additionally *resolve* a conflict only when an explicit authority policy establishes a strict tier ordering.

## Phase 7.5 boundary

Phase 7.5 may build on this substrate: corroboration (multiple independent sources agreeing → CORROBORATED, feeding authority), the first *derived* freshness/authority policies wired into a governed read loop, or belief formation that consumes query results as advisory (never authoritative) input. It still never executes, never lets a model decide truth or authority, and never claims exactly-once. The live Kubernetes watch stream (with `resourceVersion` continuity and the 410-recovery path) remains the concrete deferred item, gated on a governed connector that preserves resourceVersion.

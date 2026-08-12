# PHASE 7.4 — VERIFICATION REPORT

Date: 2026-08-12 · Branch `phase-1-foundation` · ADR-066 · No new migration (query layer adds no storage)

Labels: **VERIFIED** (evidence this phase) · **NOT VERIFIED** (no evidence) · **DEFERRED** (out of scope) · **BLOCKED** (precondition absent). Code existing is not evidence — the distributed claims cite the real-Postgres/real-process harness `scripts/phase74_query_harness.py` (**33 checks, 0 fail, verdict VERIFIED** against a fresh `cortex_p74`). Source was trusted over reports (discovery re-read the 7.3 code and the K8s connector directly).

## 1. Architecture reviewed
**VERIFIED** Read the Constitution, Phase 7.0–7.3 reports, ADR-062/063/064/065, and the source: `backend/contracts/world/` (Fact, ValidityInterval, EpistemicStatus, KnowledgeAuthority, SourceAuthority, ClaimConfidence), `backend/world/` (7.3 bitemporal projection, derivation, SQL repos), and `backend/connectors/kubernetes.py`. No storage or transaction machinery was duplicated — the query layer reuses the 7.3 projection and the existing repositories.

## 2. Existing query contracts
**VERIFIED** The 7.3 bitemporal queries (`current_state`, `as_of_valid`, `as_known`, `history`, `project_valid_at`, `knowledge_current`) exist as pure functions and are reused unchanged. `SourceAuthority` (UNVERIFIED<SINGLE_SOURCE<CORROBORATED<AUTHORITATIVE, with `.rank`) and `KnowledgeAuthority` already exist — authority reuses `SourceAuthority` rather than inventing a numeric priority.

## 3. World Query
**VERIFIED** `backend/world/application/world_query.py` — a read-only `WorldQuery` over two narrow reader ports (`FactVersionReader.versions_for`, `ObservationReader.get_observation`, both satisfied by the SQL repos). Five capabilities: `current`, `as_of_valid`, `as_known`, `history`, `evidence_for`. Typed `WorldQueryResult` with `to_dict()`. No write path; imports nothing that executes or contacts a provider (§18).

## 4. Current state
**VERIFIED** `current` returns the latest-knowledge value valid now (unit `test_current_is_5`; harness "current -> 5"). A non-covering query is UNKNOWN (harness Part M, unit `test_unknown_when_nothing_covers_the_instant`).

## 5. Valid-time AS OF
**VERIFIED** `as_of_valid(T)` — world @ 09:59 → 3, world @ 10:02 → 5 (unit `TestTemporalNoRegression`; harness Part J against real Postgres). Byte-identical to 7.3 — no regression.

## 6. Recorded-time AS KNOWN
**VERIFIED** `as_known(K)` — known @ 10:00 → UNKNOWN, known @ 10:05 → 5 (unit; harness Part J). Versions recorded after K are invisible.

## 7. History
**VERIFIED** `history` returns both immutable versions in recorded order (unit `test_history_has_both_versions`; harness "history -> both versions").

## 8. Evidence
**VERIFIED** `evidence_for` / the result's `evidence` expose each supporting observation with source_ref, observed/retrieved times, status, value, tier, and execution_ref — never prose (unit `TestEvidence`; harness "evidence references the governed execution"). Multi-source evidence (Part G) is multiple versions' observations.

## 9. Freshness
**VERIFIED** `FreshnessPolicy` is explicit rules only — **no universal TTL**. No matching rule → UNKNOWN (unit `test_no_policy_means_unknown_not_stale`; harness "no freshness policy -> UNKNOWN"). Within horizon → FRESH; beyond → STALE (unit; harness Part L under an injected deterministic clock). **STALE ≠ FALSE**: a stale `replicas=5` stays 5, AFFIRMED (unit `test_stale_beyond_horizon_but_value_unchanged`; harness "STALE is not FALSE — the value is unchanged"). Clock is injected (`now` parameter), so freshness is reproducible.

## 10. Authority
**VERIFIED** `AuthorityPolicy` maps a source to a `SourceAuthority` tier (deterministic config, auditable, no model, no arbitrary number); an unnamed source is UNVERIFIED. Applied at read time, it never mutates the ledger. **Recency ≠ authority (Part F):** with K8s `replicas=5`@10:00 (AUTHORITATIVE) and a newer stale cache `replicas=3`@10:05 (SINGLE_SOURCE), the temporal projection picks the newer cache (3) but authority RESOLVES to K8s (5), with the cache preserved as a lower-tier alternative (unit `test_recency_does_not_override_authority`; harness Part F against real Postgres). A `RESOLVED` decision records the source, tier, reason, and alternatives (Part H).

## 11. Conflict handling
**VERIFIED** Two sources at the same valid instant with equal (highest) authority and different values → CONFLICTED, neither selected, both in `alternatives` (unit `test_equal_authority_disagreement_stays_conflicted`; harness Part K — both `{5,3}` preserved). Never latest-wins, never confidence-wins. Ungoverned (no authority policy) defers to the temporal projection (unit `test_no_authority_policy_is_ungoverned`).

## 12. Tenant isolation
**VERIFIED** The query is tenant-scoped through `fact_semantic_identity(tenant, …)` and tenant-predicated reads; a cross-tenant query is UNKNOWN with empty evidence and empty history (unit `TestTenant`; harness Part M against real Postgres). A non-`TenantRef` is refused (fail closed). No caller-trust filtering.

## 13. Kubernetes stream
**DEFERRED** The existing governed connector cannot cleanly expose watch continuity — `backend/connectors/kubernetes.py` `list_*` methods strip `resourceVersion`, there is no `.watch()`, and there is no governed K8s read *capability* (only the legacy ungoverned V1 route). A stream would require fabricating continuity, silently restarting from "latest", a second connector path, or a World→Kubernetes socket — every one a stated STOP condition. Not implemented; **not faked**. The observation contract already accommodates a future governed K8s connector (source_kind CONNECTOR, `observed_at` provider timestamp, `subject_ref` object identity), so it will feed the existing pipeline unchanged when it lands.

## 14. Replay
**VERIFIED** Replaying the governed execution created zero new facts and zero provider reads; a `current` query returned an identical result before and after replay (the query is read-only) — harness Part R against real Postgres.

## 15. Crash/recovery
**VERIFIED** Real Postgres + real `os._exit(9)`: a child ingested→derived a fact and died (exit 9); a successor process queried it after restart — value intact, evidence intact, freshness reproducible (FRESH at +5m under the injected clock), cross-tenant fail-closed (harness Part S). No manual repair.

## 16. PostgreSQL
**VERIFIED** Fresh `cortex_p74`: blank → migrate to head (0016 — 7.4 adds no migration) → governed read → ingest → derive → query. `alembic heads` unchanged (single head). No `create_all`, no stamping, no SQLite. Developer `cortexdb` untouched (only `cortex_p74` created/used).

## 17. Tests
**VERIFIED** 22 new tests: `tests/world/test_world_query.py` (17 — temporal no-regression, evidence, freshness, authority incl recency≠authority, conflict, tenant), `tests/world/test_query_fitness.py` (5). Regression `tests/world + architecture + harness + contracts/world`: **412 passed, 0 failed** (248s). **NOT VERIFIED** a single local full-`tests/` pass (root conftest probes Postgres per test; CI `test.yml` is the authority). No existing assertion weakened; all 7.3 temporal tests remain green.

## 18. Architecture fitness
**VERIFIED** Gate PASSES: **29 passed, 0 failed, 6 skipped** across 1135 modules. **No new rule** (Part V): the query layer under `backend/world/application` is already fenced by `WorldCannotExecuteRule` (no connector/gateway/transport/credential/scheduler/execution) and `WorldApplicationPureRule` (no database — it uses reader ports); freshness/authority cannot mutate facts (`BND-OBSERVATION-APPEND-ONLY`). Coverage proven by sensitivity tests (current PASS; synthetic connector/gateway/transport/database imports in the query layer FAIL).

## 19. Performance observations
**VERIFIED** (measured, not optimized) `current` query averaged **44ms** over 20 runs against real Postgres (harness Part T). Cost per query: 1 `versions_for` SELECT + one `get_observation` SELECT per unique covering observation (join by PK). **No indexes were added** — the existing `cw_fact (tenant_id, semantic_identity)` index and `cw_observation` PK serve every query pattern used; speculative indexes were deliberately avoided.

## 20. Defects discovered
**FACT** No defect in the 7.3 substrate surfaced under querying — the projection, derivation, and repositories behaved exactly as the 7.3 report described (source-verified). One design subtlety handled: the temporal projection and the authority overlay can disagree (cache newer, API authoritative); the result exposes both (`temporal` and `authority`) rather than silently choosing, so nothing is hidden.

## 21. Risks
(1) Authority resolution is only as good as the explicit policy; an unmapped source is UNVERIFIED and cannot be authoritative — correct, but a deployment must state its source tiers or every fact is ungoverned/temporal. (2) Freshness ages against `valid_from` (= the observation's `observed_at`); for providers whose `observed_at` and fetch time differ materially, a freshness rule may want `retrieved_at` instead — the policy abstraction can carry that when a domain needs it (not invented now). (3) The K8s stream remains deferred; until a governed connector preserves `resourceVersion`, real streaming continuity is unproven by design, not by omission. (4) Query latency (44ms) is a single-node dev measurement, not a load benchmark.

## 22. NOT VERIFIED
- A single local full-`tests/` pass (subset + CI is the authority).
- Live Kubernetes watch continuity (DEFERRED — see §13).
- The LLM/model leg remains BLOCKED (placeholder credentials) and is not exercised; the query is deterministic and model-free by design.

## 23. Deferred
**DEFERRED** Live read-only Kubernetes stream with `resourceVersion` continuity + 410 recovery (gated on a governed connector that preserves resourceVersion); corroboration (CORROBORATED tier from independent agreeing sources); derived freshness/authority policies wired into a governed read loop; belief formation consuming query results as advisory input. None implemented; none pre-committed.

## 24. ADR-066
**VERIFIED** `docs/adr/ADR-066-world-query-freshness-authority.md` records all decisions, the K8s DEFERRED rationale, non-goals, the relationship to 7.3, and the Phase 7.5 boundary.

## 25. Phase 7.5 readiness
**Ready.** The World Plane is now queryable with temporal precision, provenance, freshness awareness, authority awareness, conflict preservation, and tenant isolation — deterministic and explainable, with no model deciding truth and no query authorizing execution. Phase 7.5 can add corroboration/derived policies/belief formation on top, and the concrete deferred item (the governed K8s watch stream) is well-scoped. Phase 5.5 credential blocker untouched; L1–L16 intact; no second execution/governance/coordination authority; exactly-once not claimed.

## DoD checklist
**VERIFIED** query/bitemporal contracts inspected · WorldQuery port defined · typed QueryResult · current · valid-time AS OF · recorded-time AS KNOWN · history · evidence · freshness contract without universal TTL · fresh/stale/unknown proven · STALE≠FALSE · authority inspected & implemented on existing SourceAuthority · authority deterministic · recency≠authority · conflicting evidence preserved · supporting observations returned · provenance preserved · tenant isolation · cross-tenant fail closed · zero execution dependencies · cannot contact provider · replay inert · crash/restart · fresh-DB Postgres · no create_all/stamping/SQLite · 7.3 temporal tests green · fitness green (29) · developer DB untouched · ADR-066 · this report · Phase 7.5 boundary documented. **DEFERRED** Kubernetes stream (§13, with rationale).

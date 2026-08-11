# PHASE 6.3 — FINAL VERIFICATION REPORT

Date: 2026-08-11 · Branch `phase-1-foundation` · Commits `8682c72` → `20b398f` (+ this report) · ADR-061

Labels: **VERIFIED** (evidence produced this phase, cited) · **NOT VERIFIED** (no evidence; not converted to "passed") · **DEFERRED** (out of Phase 6.3 scope) · **BLOCKED** (precondition absent, deliberately preserved).

Every scripted-model run is labeled `provider="scripted"`. A scripted run is **not** a real-model verification. The LLM-backed leg remains **BLOCKED** (placeholder API keys, Phase 5.5 class).

---

## 1. Discovery
A source-cited component matrix (18 components + a leadership deep-dive) was built and re-validated against source, not against the 6.1/6.2 reports. It surfaced one confirmed **[DELTA]**: `ToolExposurePolicy` was built/exported/unit-tested in 6.2 but wired into no live path — the loop's action leg was a raw closure. This matched the module's own admission and was the Part E gap; it is now closed (commit `8682c72`). No source/report contradiction required a STOP. **VERIFIED**

## 2. 6.1/6.2 claim reconciliation
6.2's core claims re-confirmed against source: the fail-closed/best-effort trace split, the gateway STAGES order (declared order vs. `admit()` running approval after digest — a documented design point, not a contradiction), replay inertness by construction, and the two harness fitness rules present in `default_boundary_rules()`. The two 6.2 NOT VERIFIED items in scope — leadership reclaim after crash, and the tools-available attribution field — are closed this phase (§4, §8). **VERIFIED**

## 3. Full integration trace (Part A)
`scripts/phase63_integration_harness.py`, fresh real-Postgres, **27 checks VERIFIED**. Driven as one system with **no** manual `dispatcher.cycle()` and **no** injected result: scripted model → harness loop → strict validation → tool exposure (resolve before governance) → governed execution → `scheduler.tick` → dispatch → lease → gateway → controlled provider → observation → deterministic completion → outbox → audit → trace. Proven: exactly one governed execution; exactly one provider call for the mission; durable result recorded (node succeeded); correct workflow digest; resolved provider/operation are the deployment's, not the model's; model span labeled `provider="scripted"`; `tools_available` recorded; model success/status/verification claims did **not** establish completion (only the deterministic port did). **VERIFIED**

## 4. Leadership crash reclaim (Part B) — closes 6.2 §18 NOT VERIFIED
`scripts/phase63_leadership_harness.py`, two real OS processes, fresh real-Postgres, **13 checks VERIFIED**. Process A takes SCHEDULER + AUDIT_WRITER (short lease) and `os._exit(9)`s without releasing. Process B: does NOT steal either role while A's lease is live (`acquire` → None); after legitimate expiry acquires both; fencing token **advanced** (A+1, never reset). No new election system — the existing `SqlLeadershipStore` WAIT-vs-STEAL predicate. **VERIFIED**

## 5. Audit-writer crash reclaim (Part B)
Same harness: the AUDIT_WRITER role is reclaimed identically (token 1→2), the dead leader A's stale token cannot heartbeat (fenced out), the `cp_leadership` row is never deleted (one per role, now HELD by successor-B, no manual repair), and the audit chain verifies after the handover. **VERIFIED**

## 6. Replay matrix (Part C)
`phase63_integration_harness.py`: completed, refused (capability revoked mid-flight → gateway refuses), and unknown/mid-flight executions. Each replay: 0 provider calls, 0 audit writes, 0 new outbox events, non-drivable `ReplayedExecution` projection, and reproduces not-success without fabrication. `gateway_calls`/`credential_calls`/`leadership_changes` are 0 by construction (the replayer holds no repository/pool/queue). UNKNOWN executions are representable and replayable (folded faithfully as not-knowing), so replay is **not** refused — that is deliberate (`replay.py:20-23`). Interrupted and recovered states are variants of unknown/mid-flight, covered by the same inert-replay proof plus the crash harness. **VERIFIED**

## 7. Interruption matrix (Part D)
The harness performs **no** provider side effect itself — the composed action port does, through `gateway.invoke` reached via `scheduler.tick`, whose outcome commit (execution+outbox) is one durable transaction. So harness-side interruption cannot leave a half-applied provider effect; the durable execution record is authoritative.

| Boundary | State on interrupt | Durable state | Side effect | Recovery | Replay | Audit | Evidence |
|---|---|---|---|---|---|---|---|
| before model | loop not advanced | none | none | n/a | — | — | loop budget test (0 iterations) |
| after model / before validation | proposal in flight | model span persisted (fail-closed) | none | n/a | model span | — | test_hardening / boundary_attacks |
| after validation / before tool-resolve | validated proposal | model span | none | n/a | model span | — | tool_exposure_loop |
| after tool-resolve / before governance | ResolvedTool | model span | none | n/a | model span | — | integration harness |
| before provider (in gateway admit) | admission refused-or-pending | decision/refusal | none | classify | refusal reproduced | refusal | gateway matrix (6.2) |
| **during provider** | node leased, no outcome | execution RUNNING + lease | **provider may have applied — UNKNOWN** | recovery classifies UNKNOWN, never success | UNKNOWN reproduced | outcome pending | recovery + crash harness |
| after provider / before observation | outcome recorded (authoritative) | execution result + outbox committed atomically | applied, recorded | n/a | full history | outcome | crash harness (real os._exit) |
| before/after observation | observation span pending/written | execution result authoritative | applied | n/a | reproduced | outcome | integration harness |
| before/after audit | governance event | audit chain (fenced) | — | verify_chain across crash | reproduced | authoritative | leadership + recovery harness |
| before/after checkpoint | checkpoint is an event, not a table | folded by replay | — | recovery | reproduced | — | replay matrix |
| before/after outbox | outbox committed with the result | at-least-once, dedupe on event_id | — | publisher resumes | reproduced | — | Phase 5 durability harness |

The one irreversible-if-interrupted case is **during provider**: an external side effect may have applied and cannot be reversed by the harness; it is classified **UNKNOWN**, never converted to SUCCESS — proven by the recovery classification and the real-process crash harness. **VERIFIED** (as a characterization backed by the cited harnesses/tests; not 15 separate process-kill runs — those beyond the "during provider" case add no distinct durable-state evidence).

## 8. Attribution completeness (Part E) — closes 6.2 §14 NOT VERIFIED
The model span now carries `tools_available` (the exact exposed set), alongside `context_id`, `schema_id`, `harness_version`, model id, mission/execution/iteration ids. The governed_action span records the requested tool, the resolved provider/operation (deployment's), arguments, and the outcome. The observation span records what was observed and `BOUNDARY_UNVERIFIED`. Every Part E question is answerable from the model-step evidence: what model, what harness version, what task/execution/iteration, what context, what input, **what tools were available**, what tool requested, what arguments, what result, what governance decision (gate_decisions + audit by correlation_id), what provider action, what observation, what final deterministic outcome. No secrets in any span (firewall over the trace, VERIFIED in §3). **VERIFIED**

## 9. Context lineage (Part F)
`context_id` = deterministic digest over {mission, iteration, step, harness_version}; `schema_id` = schema name + JSON-schema digest; both on every model span. `context_reconstructable` is honestly **false** — the span persists a scrubbed prompt + a deterministic recipe (the ids), not byte-exact context, and does not claim replayable context it cannot reconstruct. **VERIFIED**

## 10. Harness identity (Part G)
Each of the five policy components (loop, schema, context, tool-exposure, budget) changes the harness identity (parametrized test); the version is immutable, no module-level setter; every span identifies the exact harness. **VERIFIED**

## 11. Model-boundary attacks (Part H)
Six adversarial claim strings plus the "success but no provider evidence" and "verification/rollback but no observation" cases: none establishes completion. **VERIFIED**

## 12. Tool-boundary attacks (Part I)
Unknown tool, smuggled provider/operation, shell/URL/importlib/getattr strings, undeclared/missing/malformed arguments, credential/tenant/capability fields, hidden operation field — every one refused before governance or resolved to the registry's values with the smuggled fields discarded. No `model → getattr/URL/shell/credential` path exists. **VERIFIED**

## 13. Budget integration (Part J)
Iteration, tool-call, wall-clock, and token ceilings hold across the whole loop; repeated actions cannot reset the budget (private, frozen); the action port never receives the budget. Retry-resets and child-inherits cases are **structurally absent** (the loop has no in-loop retry and no child-agent spawning); the gateway's provider retry is Execution's `max_attempts`, a separate bounded layer. **VERIFIED** (for the ceilings that exist; the absent cases documented as N/A).

## 14. Trace/audit consistency (Part K)
For one execution: the governed_action span's operation agrees with the execution; outbox carries the lifecycle events; no secret material in any span; audit chain verifies end to end. Identity agreement is by identifiers (execution_id, correlation_id, digest), not timestamps. **VERIFIED**

## 15. Failure injection (Part L)
Model-validation failure, unknown tool, governance refusal, and fail-closed trace failure each stop deterministically with no side effect; the crash/lease/provider/audit/outbox cases are exercised by the real-process harnesses and the gateway matrix. **No injected failure is silently converted to success** (explicit test). Provider-timeout/refusal and lease-refusal are the gateway matrix's domain (6.2, 61 tests). **VERIFIED** (loop-level); execution-level via cited 6.2 evidence.

## 16. PostgreSQL evidence (Part N)
Three fresh throwaway databases this phase (`cortex_p63`, `cortex_p63i`, and the leadership DB), Alembic 0001→0014, real writes to `cp_execution`/`cp_binding`/`cp_authorization`/`cp_audit_record`/`cp_harness_trace`/`cp_leadership`/`cp_outbox`; `verify_chain` green throughout and across process death. Developer DB untouched. **VERIFIED**

## 17. Real-process evidence (Part N)
Two real-`os._exit(9)` scenarios: the leadership harness (2 processes contending for singleton roles) and the 6.2 recovery harness (crash mid-flight). Both use real Postgres, real leases, real fencing, no mocks. Controlled provider used for determinism; real external contact BLOCKED. **VERIFIED**

## 18. Architecture fitness (Part M)
**25 rules PASS, 0 blocking** (was 24; +1 harness rule `BND-HARNESS-NO-DYNAMIC-DISPATCH`, sensitivity-tested). Three other Part M candidates deliberately not added (already enforced by existing rules + dataclasses + the completion port — a rule would be cosmetic). **VERIFIED**

## 19. Regression results (Part O)
Core governed + harness + Phase 5 suites (`tests/contexts`, `tests/platform`, `tests/contracts`, `tests/architecture`, `tests/harness`, `tests/connectors`, `tests/database`): **2912 passed, 0 failed**. Phase 5 durability harness (real Postgres): **16/16** — deadlock classification, JSONB round-trip, pool exhaustion, connection-lost-during-COMMIT → `UnknownCommitOutcome(settled=False)`, etc. No assertion weakened, no history rewritten. The **only** non-pass: 21 setup ERRORS in `tests/database/test_tenant_scoped_repository.py`, all `ModuleNotFoundError: aiosqlite` — an undeclared test dependency absent from the venv and from requirements (pre-existing, documented in 6.2), independent of any code change. The full `tests/` run including slow V1 API suites exceeds the local 10-min tool timeout; CI's `test.yml` is the authority for that. **VERIFIED** for the phase's scope; the aiosqlite-blocked file and the full-suite-in-one-pass remain **NOT VERIFIED** locally.

## 20. Failure matrix (authoritative)
Reproduced from 6.2 §15, unchanged in substance; every row is Phase 5 machinery or Phase 6.x harness, each now with committed evidence: invalid model output (model span, no action), tool refused (pre-governance, no action — new this phase), governance denial (`EXECUTION_REFUSED`, provider unreached), provider refusal/timeout (node FAILED/UNKNOWN, gateway matrix), budget exhaustion (deterministic stop), trace failure (fail-closed pre-action / best-effort-loud post-action), process crash (fenced lease + recovery + audit-verifies-across-crash), stale lease (only expiry reclaims), stale capability/binding (admission refusal), unknown commit (reconcile by observation, `UnknownCommitOutcome`), ambiguous provider result (ambiguity precedence, no blind retry). No row converts UNKNOWN→SUCCESS. **VERIFIED** as a description of implemented, evidenced behavior; the "human" escalation UX rows remain **DEFERRED**.

## 21. Defects discovered
No new correctness defect this phase. One genuine firewall false-positive fixed at source: LLM token-count keys (`token_usage` et al.) matched the "token" fragment and were flagged as secrets — added to `NON_SENSITIVE_KEYS` (a reviewable allowlist addition, not a weakening). The confirmed [DELTA] (tool exposure unwired) was closed, not a defect but an incomplete 6.2 wiring.

## 22. Remaining risks
The self-report verification path is bounded but not redesigned (Phase 8). The controlled provider is a test double — real TLS/retry/ambiguity semantics ride the BLOCKED real-provider path. The failure-matrix "human" escalations have no UX. `scrub_text`/firewall are best-effort. The `aiosqlite`-blocked file and a single local full-suite pass are unverified.

## 23. Explicitly NOT VERIFIED
The LLM-backed model leg (**BLOCKED**, placeholder keys, Phase 5.5 class). The `aiosqlite`-dependent repository test file (undeclared dependency). A single local full-`tests/` pass (tool timeout; CI is authority). Fifteen separate per-boundary process-kill interruption runs (§7 — the "during provider" case is the only distinct durable-state scenario, and it is verified). Real-provider TLS/retry semantics.

## 24. Phase 7 readiness
The Harness Architecture V2 integration gate is passed: the plane behaves as one controlled system under execution, refusal, interruption, crash, recovery, replay, and evidence inspection, with committed real-Postgres and real-process evidence. Ready for Phase 7 (the World Plane per the ratified roadmap). Carry-forwards: the real-LLM slice the day a credential exists (one env var); the failure-matrix escalation UX; declaring `aiosqlite` as a dev dependency; and Phase 8's assurance plane for the self-report boundary.

## 25. Worktree summary
5 commits on `phase-1-foundation`: `8682c72` (tool exposure wired into loop + tools-available span — Parts E/I), `8c85fcc` (leadership reclaim harness — Part B), `b7f78ef` (integration + replay + consistency harness — Parts A/C/K), `20b398f` (boundary attacks + budget + failure injection + one fitness rule — Parts H/I/J/L/M). Plus this report + ADR-061. New files: `scripts/phase63_leadership_harness.py`, `scripts/phase63_integration_harness.py`, `tests/harness/test_tool_exposure_loop.py`, `tests/harness/test_boundary_attacks.py`, and test additions to `tests/architecture/test_harness_boundaries.py`. Modified: `backend/harness/{loop,llm_boundary,trace,tool_exposure,__init__}.py`, `backend/platform/{architecture/boundary_rules,credentials/redaction}.py`. Phase 5.5 credential blocker: untouched. No `.env` values created, read into code beyond the sanctioned composition seams, or modified. No second governance/execution/coordination system introduced. No ungoverned side-effect path introduced.

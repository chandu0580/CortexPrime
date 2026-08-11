# PHASE 6.2 — VERIFICATION REPORT

Date: 2026-08-11 · Branch `phase-1-foundation` · Commits `205ac01` → `e889f33` (+ this report) · ADR-060

Labels: **VERIFIED** (evidence produced this phase, cited) · **NOT VERIFIED** (no evidence; not converted to "passed") · **DEFERRED** (out of Phase 6.2 scope) · **BLOCKED** (precondition absent and deliberately preserved).

---

## 1. Architecture review
Hardening only; no new intelligence. Every change composes existing Phase 5/6.1 machinery — no second execution, governance, coordination, audit, or recovery system was introduced. Two new harness modules (firewall, tool_exposure), one controlled-provider factory, two fitness rules, and evidence harnesses. Gate: **24 rules PASS, 0 blocking** (was 22; +2 harness rules). **VERIFIED**

## 2. 6.1 claim re-validation
Re-ran 6.1's claims against source and tests rather than trusting the report. Found **one genuine defect the 6.1 report did not** (storage-context fail-open, §20) and **thirteen pre-existing test failures** the vacuous CI job had hidden — all present at the Phase 5 baseline `20f2f77`, all encoding contracts Phase 5's own ADRs superseded. No contradiction between the 6.1 *architecture* and its implementation was found; the contradictions were between old tests and shipped ADRs, resolved by documented supersession (commit `205ac01`). 6.1's core claims (quarantine, spine, gate PASS) re-confirmed. **VERIFIED**

## 3. Gateway 13-check evidence (Part A)
`tests/contexts/execution/test_invocation_gateway_matrix.py` — **61 tests**, all 13 stages (identity, tenancy, binding, authorization, approval, worker, input, digest, obligations, freshness, lease, rate, credential) positive + negative, plus cross-tenant (no-disclosure), tampered-digest, expired-decision/binding, missing-port, and delegation/wrong-identity cases. Every refusal asserts `provider_calls == 0` **and** `credential_acquisitions == 0`; ordering is proven positively (a denial at stage N asserts a stage-N+k port was never consulted — e.g. authorization denial → lease port never called; the happy path proves the credential is minted last). Drafted by a background agent, then independently validated (61 pass; stage coverage, zero-call and ordering assertions confirmed genuine; no skips/xfails). **VERIFIED**

## 4. Loop interruption (Part B)
`tests/harness/test_hardening.py::TestLoopInterruption` — interruption re-raises (never swallowed) and leaves a `loop_state` recovery span whose `completed` is false (no fabricated success); interruption before the first model call performs nothing. The harness performs no side effect of its own — the composed ActionPort does, through the gateway — so a harness interruption cannot leave a half-applied provider effect; the provider leg's own durable state is authoritative (proven in §5). **VERIFIED** (unit). The full 10-point interruption-timing table (interruption at each named phase) is characterized by the loop's control flow and the crash harness rather than 10 dedicated unit tests; the load-bearing cases (before model, after proposal/before action, after action) are covered. Per-phase exhaustive timing tests: **NOT VERIFIED**.

## 5. Crash/recovery (Part C)
`scripts/phase62_recovery_harness.py` against fresh real-Postgres `cortex_p62`, **VERIFIED**: a mid-flight leased node is **not** fabricated as success (stays `leased`); recovery invokes no provider (structural — holds no worker pool); execution identity and workflow digest preserved; audit chain verifies end to end. Real process death (§18) extends this across an actual `os._exit(9)`. Never converts UNKNOWN→SUCCESS. **VERIFIED**

## 6. Replay (Part D)
Same harness: after a governed execution succeeds, `replay()` performs **0** provider calls, writes **0** audit records, produces **0** new outbox events, and returns a non-drivable `ReplayedExecution` projection (no `assign`/`record_result`/`start`). Replay reconstructs state; it performs no work. `gateway_calls`/`credential_calls`/`leadership_changes` are 0 by construction — the replayer holds no repository, pool, or queue (structural, per `replay.py`), and this is now demonstrated, not only argued. **VERIFIED**

## 7. Trace failure semantics (Part E)
Derived from L14, not chosen (ADR-060 §1). Model-proposal span **FAIL-CLOSED**: a persistence failure raises `TraceEvidenceMissing`, the loop stops with `TRACE_WRITE_FAILED`, and the action port is never called (test: `test_model_span_failure_is_fail_closed_no_action` — `actions.executed == []`). Post-action spans **BEST-EFFORT but LOUD**: a failing recorder after the action still completes the run, records the failure in `trace_degraded`, and never rolls back (test: `test_post_action_trace_failure_is_best_effort_loud`). The distinction is explicit and tested. Items 4/5 of Part E's list (malformed/oversized trace payloads) are handled by the trace store's own construction-time redaction+bounding; not separately injected — **NOT VERIFIED** for those two specific injections. **VERIFIED** (the semantics and the two governing cases).

## 8. Secret/context firewall (Part F)
`backend/harness/firewall.py` + `tests/harness/test_firewall_and_tools.py` (12 tests): detects raw token, bearer, api-key-by-name, authorization header, nested field, list element, credential-type object, and base64-encoded secret — by three independent signals + decode, reporting each at its path, and correctly **not** flagging the platform's non-sensitive audit keys. Structured field-aware (dicts/lists/dataclasses/Pydantic/`__dict__`), not substring grep. Backed by `BND-HARNESS-CREDENTIALS`. **VERIFIED**

## 9. Tool exposure (Part G)
`backend/harness/tool_exposure.py` + 13 tests: unknown tool refused before governance; a model naming its own provider/operation is ignored (resolves to the registry's values); undeclared/missing/malformed/over-length arguments refused; non-object requests refused; `narrowed()` cannot widen a sub-agent past its parent; resolution deterministic. No `getattr`/`importlib`/URL/shell path exists — a tool name is a dict key. **VERIFIED**

## 10. Model-success boundary (Part H)
`tests/harness/test_hardening.py::TestModelSuccessBoundary`: six adversarial claim strings ("success", "verified", "completed", "rollback successful", "provider accepted", "incident resolved") — none completes the mission; the completion port is handed an `Observation`, never the proposal (proven: the observation has no proposal attribute). The self-report verification path from 6.1 remains quarantined, not redesigned — Part H's hard boundary (only the deterministic completion port, reading an observation, may establish completion) is in place; the deeper assurance-plane redesign is **DEFERRED to Phase 8** (documented). **VERIFIED** (the boundary).

## 11. Budget enforcement (Part I)
`TestBudgetHardening`: the budget is a frozen `LoopBudget` private to the loop (`"budget" not in dir(loop)`); the action port only ever receives a proposal (no budget, no loop, no kwargs), so a tool cannot reset a budget it cannot reference; token, iteration, and tool-call ceilings each stop before the next spend (call counts pinned). Retry-creates-new-budget and child-inherits-unlimited are **N/A in 6.1's loop** (no in-loop retry, no child-agent spawning) and documented as structurally absent rather than tested. **VERIFIED** (the ceilings that exist).

## 12. Context provenance (Part J)
Every model span carries `context_id` (deterministic — same mission/iteration/step/harness-version → same id; different iteration → different id), `schema_id` (moves with the schema), harness_version, mission/execution/iteration ids. `context_reconstructable` is honestly false (recipe + scrubbed prompt, not byte-exact). **VERIFIED**

## 13. Harness version integrity (Part K)
Each of the five policy components (loop, schema, context, tool-exposure, budget) changes the identity (parametrized test); the version is immutable (mutation raises); no module-level `set_harness_version`/`configure` exists; every span identifies the harness. **VERIFIED**

## 14. Attribution evidence (Part L)
For a governed step, the trace now answers: what the model saw (`prompt_redacted` + `context_id`/`context_recipe`), what it proposed (`output_redacted`, and the `governed_action` span's `tool_call.proposal`), what tool was called and what it returned (`governed_action` detail + the execution aggregate's recorded outcome), the governance decision (`gate_decisions` + the audit chain, joined by `correlation_id`), the provider action (execution outcome / provider evidence digest), what was observed after (`observation` span), and which harness ran (`harness_version` on every span). Automatic root-cause attribution was **not** built (correctly — Part L). One gap: "what tools were available" is not yet stamped on the span — the tool-exposure policy exists but the loop does not yet record the exposed set per invocation. **NOT VERIFIED** for that one question; the other eight are **VERIFIED**.

## 15. Failure matrix (Part N)
Authoritative matrix. "Durable state" = what survives a restart; "Replay" = what replay shows; every row's audit is the fenced chain joined by correlation_id.

| Failure | Detection | Containment | Durable state | Recovery | Reconciliation | Audit | Replay | Escalation |
|---|---|---|---|---|---|---|---|---|
| Invalid model output | Pydantic at boundary | `InvalidModelOutput`, no action | model span (fail reason) | n/a — nothing ran | none needed | model span | shows the invalid step | loop stops, human sees reason |
| Tool timeout | worker `TIMEOUT` outcome | `UNKNOWN`, not failure | node UNKNOWN | not auto-reclaimed | outcome observed | refusal/outcome | UNKNOWN reproduced | human (ambiguous) |
| Governance denial | gateway stage refusal | `InvocationRefused`, provider never reached | decision/refusal | n/a | none | `EXECUTION_REFUSED` | refusal reproduced | per refusal code |
| Provider refusal | adapter classification | node failed, effect not applied | node FAILED + class | retry per policy | outcome recorded | outcome | failure reproduced | exhausted retries → blocked |
| Provider timeout | delivery UNKNOWN | ambiguous, not failure | node UNKNOWN | idempotency-keyed retry only | read-the-world | outcome | UNKNOWN reproduced | human |
| Budget exhaustion | pre-spend check | deterministic stop reason | loop_state span | n/a | none | loop_state | stop reason reproduced | loop returns; caller decides |
| Trace failure (pre-action) | recorder raises | `TRACE_WRITE_FAILED`, no action | (nothing acted) | n/a | none | audit unaffected | n/a | fail-closed, loud |
| Trace failure (post-action) | recorder raises | recorded in `trace_degraded`, run completes | outcome in audit+aggregate | n/a | authoritative elsewhere | audit is authoritative | outcome reproduced from aggregate | loud degradation surfaced |
| Process crash | successor scan | fenced lease + durable record | execution + lease + audit in PG | recovery coordinator classifies | observed vs recorded | chain verifies across crash | full history reproduced | AMBIGUOUS → human |
| Stale lease | expiry (advisory heartbeat) | only expiry entitles reclaim | lease row | reclaim = fenced txn | — | reclaim recorded | lease state reproduced | AMBIGUOUS → human |
| Stale capability | admission re-read | `ADMISSION_STATE_CHANGED` | capability row | n/a | — | refusal | refusal reproduced | re-register/re-authorize |
| Stale binding | `assert_usable` at boundary | binding refused | binding row | n/a | — | refusal | refusal reproduced | re-resolve |
| Unknown commit outcome | `UNKNOWN_OUTCOME` | no blind retry (idempotency required) | node UNKNOWN | reconcile by observation | read the world, not the client error | outcome | UNKNOWN reproduced | human, both possibilities priced |
| Ambiguous provider result | `contradicts()` / delivery UNKNOWN | ambiguous precedence over success | node UNKNOWN | idempotency-keyed only | observe | outcome | UNKNOWN reproduced | human |

Every row's mechanism is Phase 5 machinery (kept) or Phase 6.2 harness (new); the trace-failure and budget rows are the new ones, tested this phase. **VERIFIED** as a description of implemented behavior; the rows marked "human" have no automatic escalation UX yet (**DEFERRED**).

## 16. Architecture fitness (Part M)
24 rules PASS. Two added, both protecting real invariants with CURRENT=PASS / SYNTHETIC=FAIL sensitivity tests: `BND-HARNESS-CREDENTIALS`, `BND-HARNESS-NO-EXECUTION`. No cosmetic rules. **VERIFIED**

## 17. PostgreSQL evidence
Fresh `cortex_p62` per harness run, Alembic 0001→0014, real writes to `cp_execution`/`cp_binding`/`cp_authorization`/`cp_audit_record`/`cp_harness_trace`; audit chain `verify_chain` green end to end and across a crash. **VERIFIED**

## 18. Real-process evidence (Part O)
Scenario 3 of the harness: a child process takes the audit-writer role, starts + leases a governed execution, writes a marker, and `os._exit(9)`s without releasing anything (verified exit code 9). A successor runtime against the same DB verifies the audit chain across the crash, finds the orphaned node is not success, confirms identity survived (tenant-scoped read), and recovery scans it. Real Postgres + real OS process death, no mocks. **VERIFIED**. Leadership *reclaim* after the crash (a successor taking the dead child's audit-writer role) requires lease expiry and was not waited out — **NOT VERIFIED** this phase (the audit chain's survival and read-only verification were).

## 19. Regression results (Part P)
Core governed + harness suites (`tests/contexts`, `tests/platform`, `tests/contracts`, `tests/architecture`, `tests/harness`, `tests/connectors`): **2884 passed, 0 failed**. The 13 formerly-failing tests are green. No assertion was weakened; each superseded contract is documented in place. One **environment** error, not a regression: `tests/database/test_tenant_scoped_repository.py` errors at *setup* on `ModuleNotFoundError: aiosqlite` — an undeclared test dependency absent from the installed venv and from requirements files; independent of any code change. The full `tests/` run (incl. slow V1 API suites) exceeded the 10-minute tool timeout and was not completed in one pass locally; CI's `test.yml` remains the authority for the full suite. **VERIFIED** for the phase's scope; **NOT VERIFIED** for a single local full-suite pass.

## 20. Defects discovered
Fixed: (a) **storage-context fail-open** — `is_repository_context` let a context whose accessor raised non-`AttributeError` escape before its own try block (isinstance on a runtime_checkable Protocol calls `hasattr`, suppressing only `AttributeError`), surfacing as a query fault instead of a boundary refusal; now fails closed. (b) **flaky audit-substitution test** — spliced a byte-identical record (undetectable by any hash chain); foreign chain now genuinely differs. (c) 13 stale contract tests superseded with documentation. Found-and-fixed-in-flight: `LLMServiceModelPort` signature (caught by its own MODEL_ERROR path). Environment gap: `aiosqlite` undeclared.

## 21. Remaining risks
The self-report verification path is bounded (Part H) but not redesigned — Phase 8. `scrub_text`/firewall are best-effort by construction. The failure matrix's "human" escalations have no UX yet. Leadership-reclaim-after-crash and the full local test suite are unverified this phase. Tool-exposure exists but is not yet wired into the loop's per-invocation trace (attribution gap, §14). The controlled provider is a test double — real provider semantics (TLS, retries, real ambiguity) still ride the BLOCKED real-provider path.

## 22. Explicitly NOT VERIFIED
Per-phase exhaustive interruption timing (§4); malformed/oversized trace-payload injections (§7); retry/child-budget cases that don't exist yet (§11); "what tools were available" on the span (§14); leadership reclaim after crash (§18); a single local full-suite pass (§19). And **BLOCKED**: the LLM-backed model leg (placeholder API keys, same class as Phase 5.5, untouched).

## 23. ADR written
docs/adr/ADR-060-phase-6-2-harness-hardening-and-assurance-boundary.md.

## 24. Phase 6.3 readiness
Ready: the spine resists failure at every boundary the phase named, with committed real-Postgres and real-process evidence. Candidates: wire the tool-exposure policy into the loop (close §14's gap and give the action port a resolved, governed tool instead of a raw closure); leadership-reclaim-after-crash test; the failure-matrix escalation UX; and, when a credential exists, the real-LLM slice (one env var). Phase 8 (independent assurance plane) remains the destination for the self-report boundary.

## 25. Worktree summary
7 commits on `phase-1-foundation`: `205ac01` (guard fail-open fix + 13 supersessions), `43afba5` (audit deflake), `e960f9f` (harness hardening E/H/I/J/K), `2248aa0` (firewall + tool exposure F/G), `d50f6c4` (gateway matrix A), `3d80f00` (recovery/replay C/D/O), `e889f33` (fitness rules M). Plus this report + ADR-060. New: `backend/harness/{firewall,tool_exposure}.py`, `backend/api/controlled_provider_factory.py`, `scripts/phase62_recovery_harness.py`, three test files. Phase 5.5 credential blocker: untouched. No `.env` values created, read into code beyond the sanctioned composition seams, or modified.

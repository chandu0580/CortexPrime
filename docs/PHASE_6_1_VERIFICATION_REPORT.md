# PHASE 6.1 — VERIFICATION REPORT

Date: 2026-08-11 · Branch `phase-1-foundation` · Commits `20f2f77` → `9521513` → `18e6d9b` → `3f071c7` (+ this report) · ADR-059

Labels used per claim: **VERIFIED** (evidence produced this phase, cited) · **NOT VERIFIED** (no evidence; not converted to "passed") · **DEFERRED** (deliberately out of Phase 6.1 scope) · **BLOCKED** (a precondition is absent and deliberately preserved).

---

## 1. Architecture review
Phase 6.0's laws were implemented in their smallest strong form: L1 by quarantine + fitness enforcement, L13 by deterministic gates and one fail-open defect fixed, L14 by the redacted append-only trace store, L15/L16 groundwork by the immutable `HarnessVersion` (no self-modification surface was built — its absence is the design). No new orchestrator, gateway, authorization, scheduler, audit, approval, memory, execution runtime, or leadership mechanism was introduced; every new component composes the Phase 5 machinery. One ratified pivot: the vertical-slice provider moved from Docker to Grafana when discovery showed the Docker named pipe cannot ride the transport fabric without either contract surgery or breaking the adapter socket law (ADR-059 §3).

## 2. Existing execution-path inventory
docs/PHASE_6_1_IMPLEMENTATION_MAP.md — 13 ungoverned chains (~60 unauthenticated mutating routes, 4 always-on loops, 5 startup one-shots), 22 already-quarantined surfaces, ~90 write-capable connector methods, 2 latent paths, and the chokepoint analysis that produced the ~23-insertion-point quarantine. **VERIFIED** (three parallel read-only investigations, file:line-cited).

## 3. One-Plane-of-Action result
**UNGOVERNED KNOWN SIDE-EFFECT PATHS = 0.** Every write-classified connector operation refuses by default at `BaseConnector._execute` + 3 bypass seams; every sandbox subprocess refuses at the spawn helper; the previously-latent `mission_skills`/`handlers` chains route through gated connector methods. Scope note, stated honestly: ~110 read-only connector methods remain ungoverned *outbound reads* with process-wide credentials — classified read-only by declared Phase 6.1 scope (the boundary module's own position), not governed. **VERIFIED** for writes (38 gate tests incl. per-connector classification-completeness tests that fail CI if any public async method is unclassified).

## 4. Ungoverned-path elimination evidence
- `tests/connectors/test_effect_gate.py` — 38 tests: fail-closed classification (unknown op/connector ⇒ WRITE ⇒ refused), gate-before-body (a refused write runs nothing, records nothing), terraform reads refuse too, flag restores operation. **VERIFIED**
- `tests/architecture/test_l1_quarantine.py` — 17 sensitivity tests: each new rule fails on a synthesized violation (new spawn site, aliased `Popen`, dynamic `import_module("docker")`, `__import__`, gate removed, gate not-first, gated module missing) and does not false-positive (`asyncio.run`, comments/docstrings). Runtime probes: `ungated_surfaces() == ()`; gate refuses with flag unset. **VERIFIED**
- Architecture gate: **PASS — 22 rules, 0 failed** across 1113 modules, the three new rules un-grandfathered at ERROR. **VERIFIED**

## 5. Harness implementation
`backend/harness/` — `version` (identity = digest over policy components; frozen; no setter/reload), `trace` (spans redacted at construction via `scrub_text`/`redact_mapping`; append-only recorders), `llm_boundary` (single chokepoint; strict `json.loads` + Pydantic; deterministic fence-unwrap only; normalized `TokenUsage`), `loop` (budgets pre-spend; typed stop reasons; deterministic completion port), `trace_sql` (`cp_harness_trace`, migration 0014, loud `TraceWriteFailed`). **VERIFIED** by 20 unit tests + the live slice.

## 6. Loop-engine evidence
Budgets stop **before** spending (third model call proven never to happen at `max_iterations=2`; token budget stops at the ceiling with exactly one call made); the model cannot declare completion (a proposal claiming "ALL DONE" runs to `MAX_ITERATIONS`, not `COMPLETED`); every run leaves a `loop_state` span (the recovery hook). **VERIFIED** (unit). Loop interruption (`INTERRUPTED` on cancellation) is implemented but has no dedicated test — **NOT VERIFIED**. Deep integration of loop checkpoints with `cp_execution` — **DEFERRED** (the governed executions the loop drives are themselves durable; the loop's own state rides the trace store).

## 7. LLM-boundary validation evidence
Non-JSON, schema-mismatch, and two-JSON-objects outputs each raise `InvalidModelOutput`, recorded on the trace, and **never execute** (`AllowActions.executed == []`). No regex extraction exists; the only preprocessing is a deterministic complete-fence unwrap. **VERIFIED** (unit + slice path). The V1 LLM stacks remain unvalidated and quarantined — their defects are documented (§19), not silently fixed. **DEFERRED** by design: V1 cognition re-homes in later phases.

## 8. Trace evidence
The slice persisted 4 spans (`model_proposal`, `governed_action`, `observation`, `loop_state`) to `cp_harness_trace` in real PostgreSQL, each carrying mission/iteration/step ids, correlation + trace ids shared with the audit events, model identity, gate decisions, token usage, timestamps, stop/failure reasons. `context_reconstructable` is **false** on every span — scrubbing is lossy and the report does not claim replayability the evidence cannot support. **VERIFIED**

## 9. Harness-version evidence
Every span carries `6.1.0+<digest12>`; changing any policy string changes the identity (unit-tested); the dataclass is frozen (mutation raises). **VERIFIED**

## 10. Governance-boundary evidence
The harness invokes **through** the existing gateway only: the action port's whole leg is authorize → durable start → resolve/bind (sealed, digest-carrying) → scheduler tick → dispatcher → 13-check gateway. The driver script contains no adapter, channel, connector, or httpx call. Model output cannot override a deny: gates are deterministic code paths that never consult model output (L13), and the slice's negative check proves a grant-less principal is refused by authorization. **VERIFIED**

## 11. Negative-path evidence
| Claim | Evidence | Label |
|---|---|---|
| Model cannot bypass deny | Grant-less principal refused (slice check 9); deterministic gates | **VERIFIED** |
| Invalid model output cannot execute | Unit: action port never called | **VERIFIED** |
| Budget exhaustion cannot execute another step | Unit: pre-spend checks; call counts pinned | **VERIFIED** |
| Unauthorized tool cannot execute | Effect gate refusals; fail-closed classification | **VERIFIED** |
| Direct connector attempt rejected | 38 gate tests; live watcher/report writes now refuse | **VERIFIED** |
| Refused execution creates correct audit behavior | Refusal auditing is Phase 5 machinery, untouched; the slice's clean run produced `execution_succeeded` records; a refused *gateway* invocation's audit record was not directly exercised this phase | **NOT VERIFIED** (this phase) |
| Credentials do not appear in trace | Token-absence assertion over all serialized spans; scrub on both directions unit-tested | **VERIFIED** (best-effort caveat §20) |

## 12. Failure-injection evidence
| # | Injection | What happened | Label |
|---|---|---|---|
| 1 | Malformed model output | `INVALID_MODEL_OUTPUT`, trace-recorded, nothing executed | **VERIFIED** |
| 2 | Schema mismatch | Same, with named field errors | **VERIFIED** |
| 3 | Tool timeout | Channel/authority-window machinery is Phase 5; not exercised this phase | **NOT VERIFIED** |
| 4 | Provider refusal | Live: Grafana 412 conflict → `external_system_failure`; 403 RBAC → failed node; both recorded on attempts with failure classes | **VERIFIED** (organic) |
| 5 | Governance denial | Live: grant-less refusal; plus dispatch conflicts (`UnknownWorker`, `NODE_LEASED`) surfaced and classified during bring-up | **VERIFIED** |
| 6 | Budget exhaustion | Unit: iterations/tool-calls/wall-clock/tokens | **VERIFIED** |
| 7 | Harness interruption | Implemented (state span + re-raise); untested | **NOT VERIFIED** |
| 8 | Process crash mid-loop | Phase 5 recovery machinery untouched; no new committed crash test | **NOT VERIFIED** (see §13) |
| 9 | Missing trace write | `SqlTraceRecorder` raises `TraceWriteFailed` loudly by design; failure not injected | **NOT VERIFIED** |
| 10 | Serialization failure | Organic: `LLMRequest` misuse surfaced as an explicit `MODEL_ERROR` stop with trace, then fixed | **VERIFIED** (organic) |
| 11 | Stale execution state | Organic: re-create of an existing uid → provider conflict → clean `ACTION_FAILED`, no retry storm (max_attempts=1, non-idempotent declared) | **VERIFIED** (organic) |
| 12 | Unexpected provider result | Organic: response-budget violation → `unknown_outcome` failure class recorded — ambiguity honored, not converted to failure | **VERIFIED** (organic) |

## 13. Crash/recovery evidence
**NOT VERIFIED this phase.** The Phase 5 recovery machinery (leases, AMBIGUOUS, recovery coordinator) is unmodified, and its Phase 5 evidence came from harnesses that were never committed (finding C3). Phase 6.1 added no committed crash test. The `loop_state` span provides the harness-side recovery hook (`SqlTraceRecorder.last_loop_state`), untested under a real kill.

## 14. Replay evidence
**NOT VERIFIED by new tests.** `application/replay.py` is structurally inert (no repository, no worker pool — unchanged this phase) and remains without a committed test. Claimed only as "unchanged", not as "proven".

## 15. Secret-safety evidence
Prompts scrubbed before leaving the process (unit: a bearer token in retrieved context never reaches the model port); spans scrubbed at construction (unit: `ghp_` token in model output absent from the span); the live Grafana token asserted absent from every serialized span of the slice run; the credential is minted by the broker at the last gateway stage and never enters model context. Caveat, stated: `scrub_text` is pattern-based and best-effort by its own docstring — the defense is that secrets do not enter text, the scrub is the last line. **VERIFIED** within that stated limit.

## 16. PostgreSQL evidence
Fresh `cortex_p61` database per run on the real `cortex-postgres` container; Alembic 0001→0014 applied cleanly; the slice wrote and read `cp_execution` (3 executions: create, observe, + retry reads), `cp_binding`, `cp_authorization`, `cp_audit_record` (2 `execution_succeeded`), `cp_harness_trace` (4 spans). Fail-closed startup (`build_durable_persistence` schema verification) exercised on every run. **VERIFIED**

## 17. Architecture-fitness results
**PASS: 22 rules, 0 failed, 6 skipped (the pre-existing NOT_ENFORCED invariants, still honestly reported as skipped), 306 warnings (pre-existing interface-purity), 1113 modules.** Three new ERROR rules active and sensitivity-tested. **VERIFIED**

## 18. Full regression results
`tests/architecture/` + `tests/connectors/` + `tests/harness/`: **186 passed, 0 failed.** The wider `tests/` suite (V1 product tests requiring live Postgres fixtures and services) was **not run in full** this phase — Phase 6.1 touched the V1 plane only at the quarantine points, whose behavior change (writes refuse) is the ratified intent; CI's `test.yml` remains the authority for the V1 suite. **VERIFIED** for the phase's scope; **NOT VERIFIED** for the full V1 suite locally.

## 19. Defects discovered
Fixed: computer-use governance check failed OPEN (`computer_agent.py` — L13); dashboards calling nonexistent `emergency_stop.is_active()` (2 sites); `LLMServiceModelPort` initially misused `LLMService.generate`'s signature (caught by the slice's own `MODEL_ERROR` stop). Documented, deliberately NOT fixed (quarantined V1 cognition, re-homed in later phases): `llm_gateway.complete()` kwarg mismatch at 3 call sites — LLM task decomposition has silently never run; `RouterResult.prompt_tokens` AttributeError on `mission_runtime`'s success path; `structured.py`'s greedy regex extraction; the approval center's LOW-tier auto-approve (superseded by the quarantine). Provider finding: Grafana's RBAC scope cache denies the creating service account reads of a new folder for ~45s (reproduced with curl alone).

## 20. Remaining risks
Read-only outbound connector calls remain ungoverned (declared scope). The CONTAINED isolation deviation (no separate worker process) stands until process separation exists. `scrub_text` is best-effort. The effect gate's classification table is fail-closed but socially maintained (CI test forces classification of new methods; misclassifying a write as read remains a review risk). `_load_extensions` uses `importlib` (fitness rule covers docker/kubernetes SDKs only; arbitrary factory modules are deployment-trusted by design). The scheduler tick context carries the tenant grant — a deployment that ticks with a broader context widens the re-authorization context (documented in the driver).

## 21. Explicitly NOT VERIFIED
The LLM-backed model leg (**BLOCKED** — both API keys are placeholders; same class as Phase 5.5, preserved); crash/recovery under kill; replay inertness by test; multi-process trace/audit concurrency; channel timeout machinery; loop interruption; trace-write failure injection; the full V1 test suite locally; Phase 5's uncommitted-harness claims (unchanged and unreproduced).

## 22. ADR written
docs/adr/ADR-059-phase-6-1-one-plane-of-action-and-harness-spine.md.

## 23. Phase 6.2 readiness
Ready: the L1 invariant is enforced and CI-blocking; the spine exists with evidence; the governed path has performed a real provider write. Next-phase candidates in priority order: (a) commit-worthy crash/recovery + replay tests over the in-memory fixture the recon identified (the gateway's 13 checks still have no direct test — the `TestProviderAdapter` fixture unlocks them); (b) the World Plane (Phase 7 per the ratified roadmap); (c) a real-LLM slice run the day a credential exists (one env var; zero code); (d) the local-IPC transport kind if the Docker adapter is still wanted.

## 24. Worktree summary
4 commits on `phase-1-foundation`: Phase 5 baseline (`20f2f77`, 178 files); quarantine (`9521513`: `effects.py`, 4 gate insertions, spawn guard, 3 fitness rules, 2 defect fixes, 55 tests); harness spine (`18e6d9b`: `backend/harness/` 5 modules, migration 0014, `cp_harness_trace` table, 20 tests); vertical slice (`3f071c7`: Grafana catalog/translator/channel, `build_grafana_connector`, connector-builder seam, `grafana_provider_factory`, driver script). Plus this report + ADR-059. Phase 5.5's GitHub credential blocker: **untouched**. No `.env` values were created, read into code paths beyond the sanctioned composition seams, or modified.

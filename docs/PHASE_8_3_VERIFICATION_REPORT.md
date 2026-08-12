# PHASE 8.3 — VERIFICATION REPORT

Date: 2026-08-12 · Branch `phase-1-foundation` · ADR-074 · No new migration (reuses 0019 + `cp_harness_trace`)

Labels: **VERIFIED** (evidence this phase) · **NOT VERIFIED** (no evidence) · **DEFERRED** · **BLOCKED**. Code existing is not evidence — distributed claims cite `tests/intelligence/test_model_boundary.py` (**16 passed**) and the real-Postgres/real-process harness `scripts/phase83_model_boundary_harness.py` (**14 checks, 0 fail, verdict VERIFIED** against a fresh `cortex_p83`). The real LLM is BLOCKED; every run is `provider="scripted"`.

## 1. Discovery — reuse, no second gateway/tracer/executor (Part A/K)
**VERIFIED** The engine's `ModelProposalPort` is now implemented over the existing `harness.GovernedModelBoundary`; the boundary's `SqlTraceRecorder`/`InMemoryTraceRecorder` is the only tracer and the boundary's `ModelPort` is the only provider seam. `GovernedModelProposalPort`/`ScriptedModelPort` add no gateway, tracer, or execution authority. Architecture gate **PASS: 32 passed, 0 failed, 6 skipped across 1162 modules** — `BND-INTELLIGENCE-CANNOT-EXECUTE`/`BND-MODEL-CANNOT-CREATE-FACT` intact; the engine imports no connector/provider/gateway/tracer.

## 2. The seam 8.2 deferred is closed (Part B)
**VERIFIED** ADR-073 left the model port scripted through a bare callable. It is now `harness.GovernedModelBoundary` (async, schema-validated, trace-before-return). The engine still depends only on the port — no engine signature changed. Unit `TestGovernedPort.test_full_loop_via_live_boundary_resolves` runs the full OODA loop through the live boundary to `RESOLVED`; harness Part N proves it against real Postgres.

## 3. Strict typed proposals — the model-output firewall (Part C/E/M)
**VERIFIED** `InvestigationProposalSchema` (and nested `HypothesisProposalSchema`/`TestProposalSchema`) use `extra="forbid"`. Parametrized unit `TestSchemaFirewall` proves rejection of every smuggled authority field — `success`, `verified`, `autonomy`, `status`, `provider`, `model`, `outcome`, `fact`, and a nested `extra` — plus the classic malicious `tool="shell"` + `arguments.command="terraform apply -auto-approve"` + `success`/`verified`/`autonomy` proposal. The valid minimal proposal parses. The model cannot serialize authority through this seam.

## 4. Platform-controlled identity (Part D)
**VERIFIED** `provider`/`model` come from the `ModelInvocation`/`HarnessSpan`, never the model JSON (which cannot carry them — extra fields fail). Unit `test_provider_identity_from_platform_not_model` asserts `res.provider == "scripted"` from the invocation; `test_smuggled_success_field_fails_closed` shows a model self-reporting `provider="openai"` + `autonomy="A4"` is rejected and autonomy stays `a1_investigate` (not promoted).

## 5. Durable trace of every cognitive step (Part G/N)
**VERIFIED** Every model call persists a pre-action span in `cp_harness_trace`. Harness: **durable traces == model calls** at check time (3 == 3), each carrying the harness version and context recipe (`context_digest`); the crash child adds the 4th trace (total durable_traces=4, main model_calls=3). The span records provider, model, schema identity, and proposal digest.

## 6. No secrets in the trace (Part G / secret firewall)
**VERIFIED** The harness scans every persisted trace record with the platform secret detector (`find_secrets`) — **none found**. No API key, bearer token, credential material, authorization header, or secret-bearing context is recorded. The scripted port holds no credentials.

## 7. Fail-closed pre-action trace — L14 (Part F)
**VERIFIED** The boundary persists the span before returning any proposal. Unit `test_trace_failure_fails_closed_blocked` injects a `FailingRecorder` (raises on `record`); the port raises `ModelTraceUnavailable` and the engine concludes **BLOCKED / FAILED** — the step never advances to a read. No trace ⇒ no cognition trusted.

## 8. Honest failure semantics (Part H)
**VERIFIED** `ModelProposalFailed` classifies three categories, each mapped by the engine, none ever success:
- `ModelSchemaRejected` (schema_violation) → `TEST_REJECTED` checkpoint, **no fabricated conclusion**, no autonomy promotion (unit `test_malformed_output_fails_closed_no_success`, `test_smuggled_success_field_fails_closed`).
- `ModelTraceUnavailable` (trace_unavailable) → **BLOCKED/FAILED** (unit `test_trace_failure_fails_closed_blocked`).
- `ModelProviderUnavailable` (provider_unavailable, any provider/timeout/auth error) → **BLOCKED/FAILED**.
Malformed output, a smuggled `success`, a dead provider, and a broken tracer all fail closed — none produces a RESOLVED.

## 9. Model cannot smuggle authority (Part M)
**VERIFIED** Structurally by the firewall (§3) and behaviorally: the harness confirms the platform sets the conclusion (COMPLETED via `_maybe_conclude`), governed reads == provider calls (3 == 3, no direct provider from the engine), and no model-supplied `success/verified/autonomy/Fact/Belief/Outcome/execution/URL/shell` survives.

## 10. Replay is inert (Part I)
**VERIFIED** Five reconstructions of the resolved investigation leave the model-call count, durable-trace count, and governed-read count **unchanged** (harness Part L). Cognition happens once, forward; replay only reads committed history — zero model calls, zero new spans, zero reads.

## 11. Real process interruption (Part O)
**VERIFIED** A child process runs one traced model step then `os._exit(9)` (rc 9). A successor with a fresh store reconstructs the investigation (status INVESTIGATING, **not fabricated**) and the pre-crash model trace **persists** (`_trace_count(successor) > traces_before_crash`) — attribution-grade evidence survives a hard crash, and no forward model response is invented.

## 12. Scripted provider honestly labeled; real LLM BLOCKED (Part J)
**VERIFIED / BLOCKED** Every model call is `provider="scripted"` via `ScriptedModelPort` (holds no credentials, contacts no external provider). **BLOCKED (honest):** the real-model leg. No credential was manufactured, inspected, or modified; no external provider was contacted; the Phase 5.5 blocker is untouched. The `LLMServiceModelPort` seam exists for when real credentials are provisioned.

## 13. Tenant isolation
**VERIFIED** Cross-tenant `reconstruct` fails closed with `InvestigationNotFound` (harness `[tenant]`). Traces and investigation state are tenant-scoped.

## 14. Regression
**VERIFIED** `pytest tests/intelligence tests/world tests/assurance tests/harness tests/architecture tests/contracts/world` → **552 passed** (1 collection warning: `TestRejected` is a domain exception, not a test class). Architecture gate PASS (32). Nothing in Phases 5–8.2 regressed.

## NOT built / DEFERRED (honest)
- **DEFERRED** The live-provider leg (real credentials) — BLOCKED, scripted port occupies the seam.
- **DEFERRED** Assurance-gated termination (independent verification of RESOLVED) — Phase 8.7 (unchanged from ADR-073).
- **DEFERRED** Exhaustive process-kill boundary matrix — the load-bearing crash-with-trace boundary is proven.
- **NOT claimed** Exactly-once. A crash may re-attempt a step; the durable ledger + optimistic concurrency prevent a fork (classified at-least-once, same-value dedup).

## Counts (harness, cortex_p83)
model_calls=3 · durable_traces=4 (3 main + 1 crash child) · governed_reads=3 · provider_calls=3 · investigation_events=27.

## Verdict
**VERIFIED** — the live governed model boundary is wired: strict typed proposals through the one reused `GovernedModelBoundary`, platform-controlled identity, a durable secret-free trace of every cognitive step, L14 fail-closed, honest failure classification, inert replay, and crash-surviving attribution — all against real Postgres with the real LLM BLOCKED and `provider="scripted"`.

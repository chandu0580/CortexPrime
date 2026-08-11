# ADR-061 — Phase 6.3: Final Harness Integration Gate

Status: Accepted · Date: 2026-08-11 · Commits `8682c72` `8c85fcc` `b7f78ef` `20b398f` (+ report)

## Context

Phase 6.1 built the harness spine; 6.2 hardened it. 6.3 is the final integration gate for Harness Architecture V2: prove the plane behaves as ONE controlled system under normal execution, refusal, interruption, crash, recovery, replay, and evidence inspection — and close the two items 6.2 left NOT VERIFIED (leadership reclaim after crash; the "tools available" attribution field). No new intelligence subsystem.

## Decisions

**1. Tool exposure is now wired into the loop (Parts E, I).** Discovery re-confirmed 6.2's own note: `ToolExposurePolicy` was built, exported, and unit-tested but on no live path — the loop's action leg was a raw closure. Now, under a `ToolExposurePolicy`, the loop's canonical proposal is `ToolProposal {tool, arguments}`; the loop resolves it against the frozen allowlist **before** governance (new `StopReason.TOOL_REFUSED`), and the model span records `tools_available`. Provider and operation come from the deployment registry — a model naming its own provider/operation/URL/shell/import is refused or ignored, structurally. Backward compatible: `tool_exposure` defaults `None` → the 6.1 raw-proposal mode is unchanged.

**2. Leadership reclaim after crash is verified with two real processes (Part B).** Using the existing `SqlLeadershipStore` (no new election system): process A takes SCHEDULER + AUDIT_WRITER and `os._exit(9)`s; process B does **not** steal either role while A's lease is still live, acquires both only after legitimate expiry, and the fencing token is **advanced** (A+1, never reset). The dead leader is fenced out of heartbeat; rows are never deleted; the audit chain verifies across the handover. This is exactly the WAIT-vs-STEAL predicate (`leadership.py:266-275`) and monotonic token, now exercised across real process death.

**3. Model outcome remains non-authoritative (Part H).** The completion port is deterministic and reads an `Observation`, never the proposal. A model output carrying `success`/`status`/`verification`/`rollback` claims — proven in both the live integration run and unit tests — never establishes completion; observation spans carry `BOUNDARY_UNVERIFIED`, never VERIFIED. The Phase 8 assurance plane is not built here; this only proves the existing boundary cannot be fooled by model language.

**4. Replay is inert across the state matrix (Part C).** Completed, refused (capability revoked mid-flight), and unknown/mid-flight executions each replay with 0 provider calls, 0 audit writes, 0 new outbox events, a non-drivable projection, and no fabricated success. UNKNOWN executions ARE representable and are faithfully reproduced as not-knowing (`replay.py` folds all events; non-terminal → `unresolved=True`), so replay is not refused.

**5. One justified fitness rule, no cosmetic gates (Part M).** `BND-HARNESS-NO-DYNAMIC-DISPATCH`: the harness calls no `eval`/`exec`/`compile`/`__import__`/`importlib.import_module`. Tool exposure's premise is that a model-named tool is a registry KEY, never a dynamic-dispatch target; this catches the exact regression where model output reaches dynamic execution. Static import and getattr-on-known-object are allowed. CURRENT=PASS / SYNTHETIC=FAIL. The other Part M candidates (BND-TRACE-LINEAGE, BND-CONTEXT-LINEAGE, BND-MODEL-OUTCOME-NONAUTHORITATIVE) were **deliberately not added**: their invariants are already enforced by the two 6.2 harness rules, frozen dataclasses, and the deterministic completion port, so a rule would be cosmetic — which Part M forbids.

**6. Redaction allowlist: LLM token counts are not secrets.** `token_usage`/`total_tokens`/`prompt_tokens`/`completion_tokens`/`tokens_spent`/`tokens` added to `NON_SENSITIVE_KEYS` — they match the "token" key-fragment but are integer usage counts; redacting them would blind cost/budget attribution. A reviewable, named addition, not a weakening (each is a specific claim that a named field is safe).

## Consequences

- The full plane runs as one system from a blank database through the scheduler with no manual `dispatcher.cycle()` and no injected result: 27 integration checks VERIFIED. Leadership reclaim: 13 checks. Every 6.2 NOT VERIFIED item that was in scope is closed.
- What 6.3 did not do: no verification redesign (still the Phase-8 boundary), no World Model, no learning, no self-evolution.
- Full per-claim evidence, the failure matrix, and the interruption matrix: docs/PHASE_6_3_VERIFICATION_REPORT.md.
- Phase 5.5's GitHub credential blocker: untouched. The LLM-backed model leg remains BLOCKED (placeholder keys); every scripted run is labeled `provider="scripted"`.

# ADR-074 — The Live Governed Model Boundary & Investigation Evidence Trace

Status: Accepted · Date: 2026-08-12 · Phase 8.3 · Follows ADR-073 (closes its deferred seam) and ADR-062–072

## Context

ADR-073 built the Investigation Engine but left the model port **scripted through a bare callable**, deferring "the live `GovernedModelBoundary` wiring… when real credentials exist (the engine already depends only on the port)." Phase 8.3 closes that seam: the engine's `ModelProposalPort` is now implemented over the existing `harness.GovernedModelBoundary`, so every cognitive step is schema-validated, trace-recorded-before-return, and stamped with a platform-controlled provider/model identity. No second model gateway, tracer, or execution authority is introduced; the real LLM stays BLOCKED and every run is honestly labeled `provider="scripted"`.

## Decisions

**1. One boundary, reused — no second gateway or tracer.** `GovernedModelProposalPort` (in `backend/intelligence/application/model_boundary.py`) is a thin `ModelProposalPort` over `harness.GovernedModelBoundary`. It builds a deterministic prompt from the assembled context, calls the async boundary from the sync loop, and maps the validated schema to the engine's `InvestigationProposal`. The boundary's own `SqlTraceRecorder`/`InMemoryTraceRecorder` is the only tracer; the boundary's `ModelPort` is the only provider seam. The engine still imports no connector, provider SDK, gateway, or tracer (enforced by `BND-INTELLIGENCE-CANNOT-EXECUTE`).

**2. The strict proposal schema is the model-output firewall.** `InvestigationProposalSchema` (`extra="forbid"`, and likewise its nested `HypothesisProposalSchema`/`TestProposalSchema`) is the ONLY shape the model may emit: an interpretation, candidate hypotheses, and at most one discriminating test that names a **tool key** plus reference-only subject/predicate. Any authoritative or smuggled field — `success`, `verified`, `autonomy`, `status`, `outcome`, `fact`, `belief`, `provider`, `model`, `url`, `command`, `arguments`, a nested `extra` — is an extra field and is rejected by construction. The model literally cannot serialize authority through this seam.

**3. Platform-controlled identity.** `provider`/`model` come from the `ModelInvocation`/`HarnessSpan` (platform configuration), never from the model's JSON — which cannot even carry them (they fail as extra fields). A model that self-reports `provider="openai"` is rejected before it is trusted; the recorded provider is the one the platform composed.

**4. Durable, attribution-grade trace of every cognitive step (L14, fail-closed).** The `GovernedModelBoundary` persists a pre-action trace span **before** returning any proposal. If the recorder fails (`TraceEvidenceMissing`), the port raises `ModelTraceUnavailable` and the engine concludes **BLOCKED** — the step never advances to a read. The span records the harness version, context recipe (`context_digest`), provider, model, schema identity, and proposal digest. It records **no** secrets: the phase83 harness scans every persisted trace record with the platform secret detector and finds none.

**5. Honest failure semantics — failures are never success.** `ModelProposalFailed` classifies three categories, each mapped by the engine: `ModelSchemaRejected` (schema_violation, from `InvalidModelOutput`) → the step is a `TEST_REJECTED` checkpoint with **no fabricated conclusion** and no autonomy promotion; `ModelTraceUnavailable` (trace_unavailable) and `ModelProviderUnavailable` (provider_unavailable, from any provider/timeout/auth error) → conclude **BLOCKED / FAILED**. Malformed model output, a smuggled `success` field, a dead provider, and a broken tracer all fail closed — none can produce a RESOLVED.

**6. Scripted provider, honestly labeled; real LLM BLOCKED.** `ScriptedModelPort` is a deterministic `ModelPort` (`provider="scripted"`) that holds no credentials and calls no external provider; the responder reads the assembled-context prompt and emits a schema-valid proposal. The real provider is a different `ModelPort` composed only when credentials exist. The Phase 5.5 credential blocker is untouched — no credential was manufactured, inspected, or modified, and no external provider was contacted.

**7. Replay is inert.** Reconstructing an investigation from its durable ledger makes **zero** model calls, **zero** new trace spans, and **zero** governed reads (proven in the harness: five reconstructions leave the model-call/trace/read counts unchanged). Cognition happens once, forward; replay only reads committed history.

## Explicit non-goals

No live LLM call, no direct provider access, no second gateway/tracer/executor, no numeric confidence, no RAG, no autonomy promotion by the model. Exactly-once not claimed (crash may re-attempt a step; the durable ledger + optimistic concurrency prevent a fork).

## NOT built / deferred (recorded honestly)

- **The real-model leg** remains BLOCKED (placeholder credentials). The `LLMServiceModelPort` seam exists; the scripted port occupies it deterministically. Wiring a live provider is gated on real credentials and stays out of scope.
- **Assurance-gated termination** (independent verification of a RESOLVED conclusion) is still Phase 8.7 (unchanged from ADR-073).
- **The exhaustive process-kill matrix** — the key boundary (crash after model calls, with traces persisted and state reconstructed) is proven; a full boundary sweep is deferred.

## Consequences

The Investigation Engine now reasons through the same governed, traced boundary the rest of the harness uses, with a durable per-call evidence trail suitable for attribution. Every model failure mode fails closed. The V1 intelligence stack remains quarantined. L1–L16, One Plane of Action, World immutability, independent Assurance, tenant isolation, the secret firewall, and the Phase 5.5 blocker are intact.

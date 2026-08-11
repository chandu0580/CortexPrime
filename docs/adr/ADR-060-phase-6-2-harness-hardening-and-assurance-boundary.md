# ADR-060 — Phase 6.2: Harness Hardening and the Assurance Boundary

Status: Accepted · Date: 2026-08-11 · Commits `205ac01` `43afba5` `e960f9f` `2248aa0` `d50f6c4` `3d80f00` `e889f33` (+ report)

## Context

Phase 6.1 built the harness spine and proved one governed action end to end,
but left evidence gaps its own report named: the gateway's 13 checks had no
direct tests, crash/recovery and replay were unproven by committed tests, and
trace-failure semantics were undecided. Phase 6.2's mandate was hardening, not
new intelligence: turn "the architecture works" into "the architecture resists
failure."

## Decisions

**1. Trace-failure semantics — derived, not chosen (Part E).** Constitution
L14 states a step without its evidence record is a failed step. Therefore the
**model-proposal span is fail-closed**: recorded before the proposal is
returned, and a persistence failure raises `TraceEvidenceMissing`, so no
proposal reaches a governed action. **Post-action spans are best-effort but
loud**: their authoritative outcome already lives in the fenced audit chain and
the durable execution aggregate (Phase 5), so a trace-store failure after the
fact is recorded in `trace_degraded` and never rolls back a side effect that
already happened. This split is the honest reading of L14 — mandatory evidence
before crossing the boundary, authoritative-outcome-elsewhere after it.

**2. Context contract (Part J).** Every model span now carries a deterministic
`context_id` (digest over mission/iteration/step/harness-version) and a
`schema_id` (schema name + JSON-schema digest). Both ride the span's JSONB
record — no migration. Reproducibility is not overclaimed: `context_reconstructable`
stays false, because scrubbing is lossy.

**3. Deterministic tool exposure (Part G).** `backend/harness/tool_exposure.py`:
a model names a tool; the harness resolves it against a frozen allowlist before
governance, or refuses. A model-named tool is a key into a registry — never a
`getattr`, an import, a URL, or a shell word. Provider and operation are the
deployment's values, never the model's. `narrowed()` cannot widen a sub-agent's
exposure past its parent's. This makes "the model cannot invent tools"
structural rather than a property of how an action port was written.

**4. Structured secret firewall (Part F).** `backend/harness/firewall.py`
detects a secret three independent ways — key-name, value-shape, credential-type
— plus base64 decode, walking dicts/lists/dataclasses/Pydantic/`__dict__` and
reporting each finding at its path. Defense-in-depth, backed by two fitness
rules (below); the primary control remains that credentials are minted at the
gateway and never enter the harness.

**5. Two justified fitness rules (Part M), no cosmetic gates.**
`BND-HARNESS-CREDENTIALS`: the harness imports no credential carrier (only the
redactor). `BND-HARNESS-NO-EXECUTION`: the harness imports no connector, gateway,
adapter, or transport — it proposes and records; the composed ActionPort
executes through the governed gateway. Each proven CURRENT=PASS / SYNTHETIC=FAIL.

**6. Controlled provider for real-process evidence (Part O).**
`backend/api/controlled_provider_factory.py` wires the ADR-042 TestProviderAdapter
through the same `CORTEX_CONNECTOR_FACTORIES` seam — every gate of the real
fabric, scripted answers, refuses production four ways over — so replay and
crash/recovery are deterministic and countable with no external contact. Real
external provider contact remains BLOCKED.

**7. One real fail-open defect fixed, thirteen stale contracts superseded.**
Running the never-run platform suite surfaced a genuine defect: a storage
context whose accessor property raised anything but `AttributeError` escaped
`is_repository_context` before its own try block (isinstance on a
`runtime_checkable` Protocol calls `hasattr`, which since Python 3.2 suppresses
only `AttributeError`), surfacing as a query-path fault instead of a boundary
refusal — now fails closed. Thirteen pre-existing test failures (verified
present at the Phase 5 baseline, never run because CI's job was vacuous) encoded
contracts Phase 5's own ADRs superseded; each updated with the supersession
documented in place, no assertion weakened.

## Consequences

- The gateway's 13 checks have 61 direct tests, every refusal proving
  `provider_calls == 0` and `credential_acquisitions == 0`, with positive
  ordering proofs. Crash/recovery and replay have 18 real-Postgres checks
  including a real `os._exit(9)`. The harness resists failure at every boundary
  the phase named.
- What Phase 6.2 deliberately did **not** do: no verification redesign (the
  self-report boundary is quarantined, not fixed — Part H bounds it, Phase 8
  owns the assurance plane); no World Model, ledger, learning, or self-evolution.
- Full per-claim evidence with VERIFIED / NOT VERIFIED / DEFERRED / BLOCKED
  labels and the authoritative failure matrix: docs/PHASE_6_2_VERIFICATION_REPORT.md.
- Phase 5.5's GitHub credential blocker: untouched.

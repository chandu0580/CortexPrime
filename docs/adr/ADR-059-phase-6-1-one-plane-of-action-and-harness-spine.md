# ADR-059 — Phase 6.1: One Plane of Action and the Harness Spine

Status: Accepted · Date: 2026-08-11 · Commits: `20f2f77` (Phase 5 baseline), `9521513` (quarantine), `18e6d9b` (harness spine), `3f071c7` (vertical slice)

## Context

Phase 6.0 (docs/CORTEXPRIME_INTELLIGENCE_HARNESS_ARCHITECTURE_V2.md) ratified
laws L1 (one plane of action), L13 (enforcement below the model trust
boundary), L14 (failures must be attributable), L15/L16 (harness changes
evaluated and human-promoted; the evaluator untouchable). Discovery found ~13
ungoverned side-effect chains (~60 unauthenticated mutating routes, 4 always-on
background loops, ~90 write-capable connector methods) beside a governed plane
that was off by default and had never performed a real side effect.

## Decisions

**1. The connector effect gate.** Every write-classified V1 connector
operation refuses with the existing `LegacyExecutionRefused` under the
existing `CORTEXPRIME_ENABLE_LEGACY_EXECUTION` flag — one mechanism, no second
governance system. Enforced as the first statement of `BaseConnector._execute`
and at the three bypass seams (`ArgoCDConnector._post`,
`GitHubConnector.graphql_request`, `TerraformConnector._run` — the last gating
*every* terraform verb, reads included, because every one is a subprocess).
Classification is fail-closed: an unlisted operation or connector is a write.
Sandbox subprocess spawns gate identically. Three un-grandfathered ERROR
fitness rules (`BND-PROCESS-SPAWN`, `BND-PROVIDER-SDK`, `BND-EFFECT-GATE`)
keep all of it true, each with sensitivity tests proving it fails when
violated.

**2. The harness spine** (`backend/harness/`). An immutable `HarnessVersion`
whose identity digests its policy components; trace spans redacted **at
construction** and persisted append-only to `cp_harness_trace` (migration
0014) — deliberately separate from the audit chain, joined by
`correlation_id`; a single model chokepoint with strict JSON + Pydantic
validation (no regex extraction, no getattr dispatch; invalid output is an
explicit harness failure); a loop with budgets checked before spending, typed
stop reasons, and a deterministic completion port — the model cannot declare
its own success. Observations are recorded `BOUNDARY_UNVERIFIED`: minting
VERIFIED belongs to the Phase 8 assurance plane (Part H boundary, stated).

**3. The slice pivoted from Docker to Grafana** (ratified mid-phase). The
adapter fabric's law — no adapter opens its own socket — collided with the
transport contract, which has no local-IPC kind (`TransportEndpoint` refuses
non-network targets by design; ADR-047 deferred exactly this). Reaching
Docker's named pipe properly means extending the Phase 4.2 contract; doing it
improperly means breaking a written law. Grafana (`cortex-grafana` in the
repo's own compose) rides the existing verified channel→broker→httpx fabric
with a catalog, a thin translator, and a channel builder — the
declaration-only provider addition the fabric was designed for. The catalog is
two operations: `folder.create_folder` (`REVERSIBLE_WRITE` — `DELETE
/api/folders/{uid}` is a complete inverse, deliberately **not** catalogued:
reversibility describes the action, not a grant) and `folder.get_folder`
(`READ`). A local-IPC transport kind remains future work; the Docker governed
adapter waits for it.

**4. Connector builders in the composition seam.**
`build_production_connectivity` now accepts callables invoked with its own
broker/policy/preflight, because `CORTEX_CONNECTor_FACTORIES` factories run
before the broker exists and a factory constructing its own broker would be a
second transport authority. Ready triples still work; the change is additive.

**5. The CONTAINED deviation, stated.** The Grafana worker declares
`IsolationTier.CONTAINED` (required for `REVERSIBLE_WRITE`). What the
in-process adapter genuinely provides: declared-catalog-only operations,
validated digested inputs, per-execution brokered credentials with bounded
lifetime. What it does not provide: a separate worker process. That gap is
this ADR's accepted deviation for the development deployment, to be revisited
when workers gain process separation. Declaring AMBIENT would refuse the
phase's one governed write; declaring SEALED would claim hardware isolation
that does not exist.

**6. Defects fixed under L13.** The computer-use governance check failed OPEN
on any exception (`except Exception: return True` authorized real
mouse-and-keyboard control) — now fail-closed and loud. Two dashboards called
a nonexistent `emergency_stop.is_active()` and silently reported "not
stopped" forever — fixed to the real property.

**7. Provider behavior discovered and absorbed at the right layer.** Grafana's
RBAC scope cache denies a service account reads of a folder it just created
for ~45s (reproduced with plain curl, no platform involved). The observation
leg retries the governed READ — each retry a fresh governed execution — rather
than teaching any layer to wave a 403 through.

## Consequences

- UNGOVERNED side-effect paths on the acting plane: **0 known**, enforced
  forward by CI-blocking rules. V1 write features return only through the
  governed path (the ratified product consequence).
- One real governed action ran end to end against real PostgreSQL and a real
  provider: model proposal → schema validation → authorization (digest-bound;
  grant-less principal refused) → durable execution → scheduler → dispatcher →
  13-check gateway → Grafana write → independent governed read-back →
  deterministic completion → fenced audit records → redacted trace spans
  carrying the harness version. Exit 0, 11/11 checks.
- The **LLM-backed** model leg is **BLOCKED — credential_unavailable** (both
  API keys in `.env` are placeholders), the same class of blocker as Phase
  5.5's GitHub token, preserved rather than worked around. The scripted model
  port names `provider="scripted"` on every span, so scripted evidence cannot
  masquerade as a model run.
- Full verification, per-claim labels, defects, and remaining risks:
  docs/PHASE_6_1_VERIFICATION_REPORT.md.

# ADR-070 — Final Intelligence Loop & the Durable Reasoning Trail

Status: Accepted · Date: 2026-08-12 · Phase 7.8 (Phase 7 final integration gate) · Follows ADR-062 through ADR-069

## Context

Phases 7.1–7.7 built each layer of the World + Intelligence + Assurance architecture. ADR-070 is the integration gate: it proves that **one complete epistemic lifecycle** runs end to end — Observation → Fact → Belief → Hypothesis → Prediction → governed action → Outcome → prediction evaluation → independent Assurance → Verification — while the model can never shortcut a transition, and it adds the one durable primitive the lifecycle still lacked: the reasoning trail.

## Decisions

**1. The lifecycle reuses the existing governed execution path — no new executor (Part D).** The Prediction → action transition goes through the Phase 6 One Plane of Action (harness proposal → tool exposure → governance → authorization → lease → gateway → execution), driven by the same `scheduler.tick`/gateway the earlier harnesses use. There is **no `prediction_executor`, no second gateway, no second scheduler, no second authorization system**. The integration scenario runs **exactly one governed execution and one provider action** (`provider_calls == 1`), verified against real Postgres.

**2. Outcome comes from the execution, never the model (Part F).** The `Outcome` is built from the real `execution_ref` and the **independently-queried world value** (via `WorldQuery`), not from any model claim. Proven: even when a `model_claimed_success` value is present, `outcome.observed` is the actual world state, and `Outcome` refuses an empty `execution_ref`.

**3. The durable reasoning trail — one minimal append-only ledger (Part J/K).** `cw_reasoning` (migration 0018) persists only the model-authored artifacts that **cannot be reconstructed** from the World ledgers: a grounded `Hypothesis`, a `Prediction`, and a `PredictionEvaluation` (the calibration payload — expected proposition, horizon, actual outcome, result, evidence refs). Beliefs stay derived projections; observations/facts/verifications live in their own ledgers. It is immutable, tenant-scoped, provenance-bearing (`refs` carries the graph edges), idempotent (unique `identity_digest`, at-least-once, **not exactly-once**), and **secret-free** — the field-aware firewall runs before any row is written. `record_hypothesis` takes the domain subject explicitly (the `Hypothesis` contract carries none), keeping the trail queryable by the same subject as the observations/facts.

**4. Calibration data captured, no learning engine (Part K).** The `PredictionEvaluation` record preserves everything a future measured-calibration phase needs, without training a model, optimizing a prompt, mutating a policy, or inventing a number. Calibration remains **DEFERRED** until enough outcome history accumulates; it will be measured from outcomes, never from model-stated confidence.

**5. No future leakage; crash leaves no fabricated success (Part L/M).** Bitemporal reconstruction over the reasoning trail (by `recorded_at`) and the World ledgers (as-known queries): a reconstruction at 10:04 sees no hypothesis (recorded 10:05); at 10:11 it sees the full chain. A real `os._exit(9)` before verification leaves the pre-crash hypothesis and prediction durable and **no fabricated verification** for the interrupted chain — the incomplete lifecycle stays unverified (UNKNOWN), never invented.

**6. Replay inert (Part N).** Replaying the governed execution mutates nothing (facts, verifications, reasoning counts unchanged) and does zero provider work.

**7. Firewalls intact (Part R/S/U).** World/Intelligence/Assurance import no execution infrastructure (existing `BND-WORLD-CANNOT-EXECUTE`, `BND-ASSURANCE-CANNOT-EXECUTE`; the reasoning ledger under `backend/world` is covered by them and by `BND-OBSERVATION-APPEND-ONLY`). The model cannot create Fact/Belief/Outcome/Verification (`BND-MODEL-CANNOT-CREATE-FACT`, the contracts). Self-verification is refused; UNKNOWN/STALE/CONFLICTED never become success. Dynamic tool names and direct provider/shell access remain refused by the Phase 6 gates (`BND-HARNESS-NO-DYNAMIC-DISPATCH`, `BND-EFFECT-GATE`, ToolExposurePolicy) — unchanged and re-cited, not re-implemented. **No new fitness rule was required** — the existing rules cover the new ledger; sensitivity is proven by the extended append-only tests.

## Explicit non-goals

No new executor/gateway/scheduler/governance, no model-created truth/outcome/verification, no calibration/learning engine, no numeric confidence, no embeddings/vector DB/RAG, no Kubernetes watch, no per-concept mutable table. Exactly-once not claimed.

## Kubernetes decision (Part V)

Still DEFERRED — the connector strips `resourceVersion`, has no `.watch()`, and there is no governed K8s read capability. Phase 7 does not depend on it; a future **Phase 7.9** would implement LIST→WATCH continuity and 410 recovery without fabricating continuity.

## Phase 8 boundary

Phase 7 is complete: the World Plane is a deterministic, bitemporal, provenanced, tenant-scoped truth substrate; beliefs are lineage-honest; assurance is independent; and the full lifecycle is proven. Phase 8 (per the Constitution's roadmap) is the Assurance/prediction plane's next step — measured calibration from accumulated prediction-vs-outcome history, dry-run harvesting, and independent executing verification — built on the reasoning trail this phase established, still with the model unable to manufacture truth, still one plane of action, still no exactly-once.

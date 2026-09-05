# ADR-093 — Phase 10: productizing the verified engine

**Status:** Accepted (discovery only; nothing implemented)
**Date:** 2026-09-05
**Extends:** ADR-071 (intelligence boundary), ADR-088–092 (Phase 9)
**Discovery:** `docs/PHASE_10_0_PRODUCT_DISCOVERY.md`
**Architecture:** `docs/PHASE_10_0_PRODUCT_ARCHITECTURE.md`

Labels: `[FACT]` verified from this repository or a live probe, `[SOURCE]`
web-verified, `[INFERENCE]`, `[PROPOSAL]`.

## Context

Phase 9 produced a verified DevOps execution vertical: World → Investigation →
Assurance → Approval → Authorization → CONTAINED worker → real Kubernetes write →
independent verification. Phase 10 must decide how that becomes a product.

## Finding 1 — The engine has no product surface at all `[FACT]`

- 138 frontend pages; **one** references any governed concept.
- 96 route modules, **185 registered routers**; searching the registry for
  `world`, `assurance`, `investigation` or `autonomy` returns **zero**.
- HTTP route modules for World, Assurance, Investigation, Autonomy, Calibration,
  Belief, Observation and Remediation: **0 each**.

`[INFERENCE]` The verified engine is reachable only from harness scripts. This is
the finding that orders the whole roadmap: there is nothing to put a UI on yet.

## Finding 2 — The V1 route surface is tenant-unaware `[FACT]`

**89 of 96 route modules contain no reference to `tenant`.** Three take a tenant
from a request body or query.

`[INFERENCE]` This is the largest product risk in Phase 10. The governed engine
enforces tenant everywhere and proves it (cross-tenant approvals refuse in 9.9C,
9.10 and 9.11), but a product built on the V1 routes would bypass that. It is a
stop condition, which is why the first phase builds new endpoints rather than
extending the old ones.

## Finding 3 — Every governance intervention already has a contract `[FACT]`

Approve, reject, revoke-before-dispatch, emergency stop, request-more-evidence
and audit inspection all exist as backend contracts and are proven refusing.
Acknowledge, cancel and override do not.

`[PROPOSAL]` **"Override" should not be built.** There is no contract for it, and
inventing one is exactly how a governance bypass gets added for UX convenience.

## Finding 4 — Explainability needs no new truth system `[FACT]`

All twelve product questions ("why do you think this", "what contradicts it",
"how fresh", "who approved", "how was success verified") map onto existing
artefacts: `WorldQuery`, `Investigation`, `CorroborationLevel`,
`AutonomyDecision`, `WorldVerification`, the audit chain.

## Decision 1 — The product API boundary is the only new layer, and it holds no authority

`[PROPOSAL]` It reads projections and submits into the existing chain. If it ever
needs to *decide* something, that is the signal it is becoming a second
governance authority.

## Decision 2 — First vertical: read-only AI Incident Investigator, then remediation

`[PROPOSAL]` Two phases, not one.

`[INFERENCE]` The read half (9.1–9.5) is verified with zero write risk; the write
half has exactly **one** commissioned capability, so a remediation-led product
would be a product with one button. `[SOURCE]` The market's own recommended
rollout — "suggest, then approve, then auto-remediate" — is the same sequence,
which is corroboration rather than the reason.

A knowledge/RAG copilot was rejected outright: it is the one candidate that pushes
*toward* the RAG-as-truth failure Phase 8 exists to prevent.

## Decision 3 — RAG proposes context; World establishes fact; Assurance establishes outcome

`[FACT]` 213 modules mention RAG, 56 embeddings, 41 Neo4j, 24 pgvector.

`[PROPOSAL]` RAG may answer runbooks, architecture, ownership and historical
narrative. It may never be authoritative about current infrastructure state,
current deployment state, whether an action succeeded, or any verdict. A
retrieved document may suggest a hypothesis and may never be cited as evidence.

## Decision 4 — Product roles map to permission and approval authority, never autonomy

`[FACT]` V1 RBAC is three roles over resource:action; it expresses *permission*
only. Approval authority is digest-bound per action (ADR-090); autonomy is
derived from measured calibration.

`[PROPOSAL]` No product role may raise an autonomy ceiling. `capability ≠
permission ≠ autonomy` stays true, and RBAC is deliberately late in the roadmap so
approval authority is not expressed in a model that has no digest binding.

## Decision 5 — Honest competitive position

`[SOURCE]` Approval gates, tiered autonomy, blast-radius statements, audit trails
and post-remediation confirmation are all **claimed by shipping products**
(Komodor, Shoreline, Rootly, incident.io, Azure SRE Agent, Resolve AI). Komodor
claims 97%+ accuracy and up to 80% MTTR reduction — vendor-stated, with no
independent methodology surfaced.

`[INFERENCE]` **CortexPrime is not differentiated by any of those.** Positioning
on them is positioning on parity.

`[PRODUCT BET]` The defensible claims, stated as bets — the search found no
evidence competitors lack these, only that it did not surface them:

1. Uncertainty as a first-class verdict (`INSUFFICIENT_EVIDENCE`; STALE ≠ FALSE,
   CONFLICTED ≠ FALSE, UNKNOWN ≠ FALSE). `[SOURCE]` The 2026 grounding literature
   (GSAR, CHARM) treats this as the open problem.
2. Lineage-aware corroboration — same-origin sources are CORRELATED, not
   INDEPENDENT `[FACT]`.
3. No invented confidence `[FACT]`.
4. Structural rather than configured refusal — `[FACT]` the platform refused its
   own first write for three consecutive phases on its own invariants.

`[INFERENCE]` And the weakness, stated plainly: competitors have products;
CortexPrime has an engine with no UI, one commissioned write capability and a
scripted model proposer. On integration breadth, time-to-value and proven scale it
is far behind.

## Decision 6 — Three invariants are most at risk from product pressure

`[INFERENCE]` A UI wants a confidence percentage — there isn't one. A UI wants a
green tick — `INSUFFICIENT_EVIDENCE` is not a failure and must not render as one.
A customer will ask for an autonomy toggle — autonomy is derived from calibration
and there is no toggle.

## Consequences

- Phase 10.1 is the governed product API boundary. Nothing user-facing can
  precede it, because the engine has no HTTP surface and the V1 surface is
  tenant-unaware.
- The V1 route surface is **deprecated, not extended**.
- Every Phase 7–9 invariant carries forward unweakened, including
  **never claim exactly-once**.
- Stop-condition audit: **PASS**. Four risks identified (tenant bypass, unsafe
  caching of World state, cross-tenant RAG retrieval, stale evidence rendered as
  current) and each assigned to the phase that must address it.

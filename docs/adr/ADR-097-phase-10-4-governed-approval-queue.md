# ADR-097 — Phase 10.4: the governed approval queue

**Status:** Accepted (implemented)
**Date:** 2026-09-06
**Extends:** ADR-096 (human approval and remediation), ADR-095 (workspace), ADR-094 (product API), ADR-090 (approval binds to the action)
**Map:** `docs/PHASE_10_4_IMPLEMENTATION_MAP.md`
**Verification:** `docs/PHASE_10_4_VERIFICATION_REPORT.md`
**Harness:** `scripts/phase104_approval_queue_harness.py` — 135/135

Labels: `[FACT]` verified from this repository or a live run, `[DECISION]`,
`[CONSEQUENCE]`.

## Context

Phase 10.3 made a remediation approvable, but only from inside the investigation
that raised it. That does not match how an on-call rota works: a responder
coming on shift has no way to discover what is waiting without already knowing
where to look.

## Decision 1 — The queue is a projection, and there is no queue state `[DECISION]`

`[FACT]` Discovery found that `cp_approval` already carries everything the queue
needs — tenant, requester, decider, both times, expiry, consumption, capability,
digest and payload — and that `GET /api/v1/approvals` already listed
cross-investigation and tenant-scoped. The genuinely missing parts were a rich
projection, a derived state, server-side filters and a route to put them on.

`[DECISION]` **No new table, no migration, no stored queue status.** Every state
is derived on read. `[CONSEQUENCE]` A queue read costs more than reading a
denormalised status column would, and that is the trade being made deliberately:
a second stored status is a second thing that can disagree with the approval
about whether an action is still live, and the first time they disagreed would
be a governance incident.

`[FACT]` The projection module contains no `insert`, `update`, `delete`,
`decide`, `request` or `grant` — asserted by the harness, so it cannot become an
authority by accident.

## Decision 2 — No new decision route `[DECISION]`

`[FACT]` The product's non-GET routes are **still exactly the three** Phase 10.3
enumerated. The queue submits to the same
`POST /api/v1/approvals/{id}/decision`, which is the same conditional update
against `outcome = 'pending'`. There remains exactly one place an approval is
decided.

## Decision 3 — Risk is extracted, not copied `[DECISION]`

`[FACT]` `AuthorizationSnapshot.implied_risk` already derives a `RiskLevel` from
the declared effect, and treats an **undeclared** effect as CRITICAL rather than
LOW.

`[DECISION]` That rule was **extracted** into `implied_risk_for` and the property
now delegates to it. One implementation, called by both. A copy in the product
layer would drift from the taxonomy it claims to reflect, and the drift would
show up as a queue that sorts by a risk authorization does not recognise.

## Decision 4 — Two things the queue refuses to compute `[DECISION]`

**Autonomy.** `AutonomyPolicy.evaluate` needs reliability, drift, world
freshness, emergency-stop and breaker state and a policy config `[FACT]`. A
queue supplying plausible values for those and calling it would be *deciding*
autonomy. It reports the platform-set ceiling and says, in the payload, that it
computes nothing.

**The ADR-038 action digest.** It covers `binding_digest`, which resolution
creates inside the execution the approval authorizes `[FACT]` — the reason
ADR-090 exists at all. For a pending approval it does not exist. It is returned
as `null` with the reason, never synthesised: a fabricated digest would look
like a binding nobody made.

## Decision 5 — Ordering is deterministic and stated `[DECISION]`

Actionable first, then risk descending, then **oldest first** — the approval
waiting longest is the one closest to expiring unanswered. Every term is a fact
already on the row.

`[DECISION]` No score, no model, no learned ranking (Part X). `[FACT]` Two reads
return the same order, and the response states its own ordering so a client does
not have to infer it. The frontend does not sort.

## Decision 6 — Existing optimistic concurrency, no lock `[DECISION]`

`[FACT]` Two genuinely simultaneous decisions on one approval produced status
codes `[200, 409]` in both the approve/approve and approve/reject cases, with a
single stored outcome and a single decider.

`[DECISION]` **No distributed lock was introduced.** The conditional UPDATE
already provides this, and a lock would be a second coordination authority
solving a problem that is already solved.

## Decision 7 — A decided approval keeps its decision; a stale grant does not `[DECISION]`

`[FACT]` A *granted* approval that passes its expiry projects as EXPIRED and is
not actionable — it authorizes nothing and the UI must not offer it. A
*rejected* approval that passes its expiry stays REJECTED, because relabelling
it would lose who refused it and why. An unrecognised outcome projects as
INVALID and is never actionable.

## Decision 8 — No bulk action, ever `[DECISION]`

`[FACT]` No approve-all, no select-all, no checkbox, no run-all — asserted by
component tests and by a source-scanning boundary test. Each approval authorizes
exactly one action, and the only path to a decision is a screen showing the
whole action. A bulk control would be a way to authorize actions nobody looked
at.

`[DECISION]` The action cannot be edited. `[FACT]` The decision screen has
exactly two inputs — a reason and a confirmation — and their ids are asserted. A
responder who wants something else rejects this and a new proposal is raised.

## Decision 9 — No new fitness rule `[DECISION]`

`[FACT]` `BND-PRODUCT-CANNOT-BYPASS-EXECUTION`, added in Phase 10.3, already
covers the queue: injecting a transport-broker import into `approval_queue.py`
turned the gate FAIL naming that module, and removing it returned PASS. A second
rule would be cosmetic, which Part V forbids.

## What this ADR does NOT decide

- No notifications (Part R) — the queue is sufficient for this phase.
- No "approval viewed" audit event: reads do not belong in the chain that
  establishes what was authorized.
- No pagination cursor, no queue-at-scale behaviour, no RBAC approver role.
- No exactly-once. No RAG. No SLA.

## Status of the invariants

`[FACT]` 135/135. 36 negative cases, **0 provider writes**, refusals attributed
across four layers. Architecture gate PASS (36 passed, 0 failed, 6 skipped, 1193
modules). Frontend 99/99. Tenant isolation proven with **both** tenants holding
real approvals, and again over the live browser path: 21 approvals from 21
investigations for one tenant, 1 for the other. No new table, no migration, no
new authority.

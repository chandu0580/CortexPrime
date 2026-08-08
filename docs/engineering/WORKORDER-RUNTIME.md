# WorkOrder Runtime

`backend/contexts/workorder/` — the executable form of the Engineering
Constitution's unit of work. See [ADR-019](../adr/ADR-019-work-order-runtime.md).

## Layout

```
domain/           pure — no I/O, no framework, no persistence
  identifiers.py    strongly-typed ULID identifiers
  states.py         the lifecycle, as two tables
  blast_radius.py   the scope value object
  assumption.py     beliefs and their resolutions
  rejection.py      the six typed rejection grounds
  work_order.py     the aggregate
  digest.py         canonical digest over the governed fields
  validation.py     V1–V10
  factory.py        construction

application/      commands, queries, and the service that runs them
infrastructure/   repository, record mapping, reference resolution
```

Imports point downward only: this context sees `contracts/` and `platform/`, and
nothing else. `DEP-LAYERS` enforces it.

## Lifecycle

```
Draft ──► Approved ──► Assigned ──► SpecTests ──► Implementation
             │  ▲                                       │
             ▼  │                                       ▼
          Blocked                                    Review ◄──┐
                                                        │      │
                                                        ▼      │
                                                  Verification ┘
                                                        │
                                                        ▼
                                                     Ready ──► Merged ──► Closed

  Rejected is reachable from Draft, SpecTests, Implementation, Review, Verification.
```

**SpecTests precedes Implementation.** Tests written after reading an
implementation test what the code does, not what it should do.

Forbidden transitions carry their reason:

```python
transition_reason(WorkOrderState.VERIFICATION, WorkOrderState.MERGED)
# 'no agent may merge; merge is the human gate'
```

## Using it

```python
from backend.contexts.workorder import (
    AssumptionSpec, BlastRadius, DraftWorkOrder, ApproveWorkOrder,
    InMemoryWorkOrderRepository, FilesystemReferenceResolver, WorkOrderService,
)
from backend.platform.context import ExecutionContext

service = WorkOrderService(
    repository=InMemoryWorkOrderRepository(),
    resolver=FilesystemReferenceResolver(known_constraints=...),
)
context = ExecutionContext.platform_internal(
    reason="engineering", component="architect", source="cli"
)

result = service.draft(context, DraftWorkOrder(
    intent="The storage boundary refuses operations without an ExecutionContext",
    acceptance_criteria=("A read with no context is refused",),
    blast_radius=BlastRadius.of(["backend/platform/storage/**"]),
    adr_references=("ADR-018",),
    constraints=("I6",),
    assumptions=(AssumptionSpec("Models carry a tenant column", "grep tenant_id"),),
))
```

Every assumption is paired with a rejection ground automatically. Declaring a
belief without declaring what to do when it turns out false is the gap V3 exists
to close.

Run validation before attempting approval — discovering ten findings one refusal
at a time is how a Draft takes six rounds to land:

```python
report = service.validate(context, work_id)
report.approvable          # False if any blocking finding
report.blocking            # structural and resolved rules
report.advisory            # heuristics — a human weighs these
```

## Behaviour worth knowing

**Approval binds a digest.** Every later transition re-verifies it. Change a
governed field afterwards and the next transition raises `DigestMismatch`.

**Priority is excluded from the digest.** Re-ordering the queue does not require
re-approving the work. `state` and assumption resolutions are excluded too — the
first changes by design, the second is written after approval by the receiver.

**Identity is `(work_id, version)`.** Only a blast-radius expansion increments
the version. Everything else is a new WorkOrder.

**Narrowing a blast radius is refused.** Already-authorised work must not become
retroactively out of scope.

**A rejection is a successful outcome.** It closes the WorkOrder having produced
proof the plan was wrong before code was written. `RejectionType.CONSTRAINT_CONFLICT`
resolves to the **Founder**; every other type to the Architect.

**Conflict detection is conservative.** Two radii conflict unless provably
disjoint. A false conflict costs serialised work; a false non-conflict costs two
agents editing the same file.

## Validation rules

| Rule | Checks | Decidability | Severity |
|---|---|---|---|
| V1 | intent states one outcome | heuristic | advisory |
| V2 | criteria are implementation-independent | heuristic | advisory |
| V3 | every assumption has a rejection ground | structural | blocking |
| V4 | evidence resolves and is not stale | resolved | blocking |
| V5 | ADRs resolve and are not superseded | resolved | blocking |
| V6 | blast radius matches real paths | resolved | blocking |
| V7 | no dependency cycle | resolved | blocking |
| V8 | no self-dependency | structural | (impossible to construct) |
| V9 | constraints are enforceable | resolved | blocking |
| V10 | done does not restate a universal condition | heuristic | advisory |

Heuristics are advisory on purpose. A heuristic that blocks a merge gets worked
around within a week, and the workaround outlives the rule.

## API

`/api/v1/engineering` — 11 endpoints, versioned from the first commit.

| Method | Path |
|---|---|
| POST | `/work-orders` |
| GET | `/work-orders` |
| GET | `/work-orders/{id}` |
| GET | `/work-orders/{id}/versions` |
| GET | `/work-orders/{id}/validation` |
| POST | `/work-orders/{id}/approve` |
| POST | `/work-orders/{id}/transition` |
| POST | `/work-orders/{id}/reject` |
| POST | `/work-orders/{id}/assumptions/{aid}/resolve` |
| POST | `/work-orders/{id}/blast-radius/expand` |
| POST | `/work-orders/{id}/priority` |
| POST | `/blast-radius/conflicts` |

Status codes: `409` for a state conflict (invalid transition, terminal state,
duplicate, digest mismatch), `422` for validation failure with the findings in
the body, `400` for a malformed value, `404` for an unknown WorkOrder.

## Current limitations

**Storage is in-memory.** Restarting loses everything. `STATE-NO-NEW-FILE-STORES`
forbids a JSON store, and a durable one belongs with the schema work. The
`WorkOrderRepository` Protocol is the seam.

**No WorkOrder citing evidence can be approved.** The Evidence context does not
exist, so V4 fails closed. Correct, and it means this runtime cannot yet govern a
real PR end to end.

**The execution context is manufactured per request.** It is not propagated from
the authenticated caller, so a user's identity does not yet reach a WorkOrder.

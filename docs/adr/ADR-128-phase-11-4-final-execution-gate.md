# ADR-128 — The asynchronous execution contract, multi-replica operation, and what running two replicas revealed

- **Status:** ACCEPTED (partial — the gate this phase was asked to close is **not** closed; see Consequences)
- **Date:** 2026-09-20
- **Phase:** 11.4 — Final product completion gate
- **Parents:** ADR-127 (the governed execution fabric, whose durable dispatch makes all of this possible), ADR-126 (GitHub), ADR-125 (Kubernetes), ADR-122 (signal fabric)

## Context

ADR-127 made dispatch a property of the run rather than of the process that
created it, and proved it with four real OS processes. What it did not do was
give a *caller* anything: there was no way to ask for governed work and leave,
and the deployment still ran one replica.

This phase adds the asynchronous contract, turns on multi-replica, and — mostly
— discovers what those two things expose.

## Decisions

### D-1 The asynchronous door is the same door

`_perform` gains `dispatch=False`. Everything a synchronous write does happens
before it returns — capability lookup, argument validation, authorization,
policy, the approval checked against the action digest, the sealed binding — and
what it drops is the caller standing there watching, which was never part of the
decision. `POST /approvals/{id}/execute` takes `wait: false` and answers with
`{execution_id, status}`; `GET /api/v1/executions/{id}` answers later.

A request governance **refuses** returns 409, never a receipt. "Accepted, ask
later" must not be the answer to "no".

This is a parameter rather than a second method because before ADR-127's durable
sweep existed, an execution nobody drove was an execution nobody would ever run.

### D-2 The public status vocabulary translates; it does not invent

`PUBLIC_NODE_STATE` maps the durable node states to names a caller can act on.
There is deliberately **no `VERIFIED` or `VERIFYING`**: verification is a
separate record with its own verdict, and reporting it as an execution state
would claim the execution knows something it does not. `UNKNOWN` maps to
`INSUFFICIENT_EVIDENCE`, never to `FAILED` — flattening ambiguity into failure
is how an ambiguous mutation gets attempted twice.

### D-3 More than one replica is safe, and the chart says why

`replicas` becomes a value; above 1 the strategy becomes `RollingUpdate`.
No new mechanism was added, because none was needed: `SCHEDULER`,
`AUDIT_WRITER`, `OUTBOX_PUBLISHER` and `WORLD_WATCH` already elect leaders
through the SQL leadership store, and the remediator — which does not — is
fenced by the idempotency store's primary key. The default stays 1 so an
operator opts in deliberately.

### D-4 A finished run is sealed

A run whose nodes have all succeeded or been skipped is completed. This is the
root cause of three separate findings (F-10, F-14, and ADR-127's F-9): a
governed read's node succeeds while its run stays `RUNNING` **forever**, and
`RUNNING` is the state discovery, recovery and the scheduler's target set all
key on. Conservative on purpose — a run with a failed or ambiguous node is not
finished being decided about.

### D-5 Cross-tenant stays 404, and the enforcement is authorization

The mandate asked for `DENIED` rather than `NOT FOUND`. **This ADR declines**,
and records why: ADR-094 chose 404 so an outsider cannot learn that a row
exists, and changing it would weaken a real anti-disclosure control to satisfy a
test's wording. The property the mandate actually wants — that the boundary is
authorization and not obscurity — is met: the storage guard narrows every read
by tenant *in SQL*, so another tenant's row is unreturnable even when its id is
known exactly. The enforcement is a deny; only the wording is discreet.

## Findings

| # | Finding | Severity | Status |
|---|---|---|---|
| F-10 | **Durable discovery would have starved new work.** `find_by_state` ordered oldest-first with `limit=100`, and the live store held **1784 runs in `RUNNING` of which 191 of the oldest 200 had nothing left to dispatch**. The sweep would have returned a window of finished work and never reached what a caller was waiting on — the asynchronous contract would have been dead on arrival. | High | **Fixed**: newest-first, and only runs with a genuinely ready node. Root cause addressed by D-4. |
| F-11 | **Audit writing stops permanently and silently.** `is_writer()` renews the lease on every append, so a quiet spell longer than the lease lets it lapse; another process may then take the role, the incumbent's next heartbeat returns `None` and it drops its handle — and `acquire()` was called only at startup. Refused appends are *contained*, not raised, so nothing reports it. Proven live: a second process seized the role from an idle deployment (fencing token 51 → 52). | High | **Fixed**: the pump reclaims the role when free. |
| F-12 | **The only execution-causing product route cannot run most commissioned capabilities.** `POST /approvals/{id}/execute` composes a definition set containing only `kubernetes.workload.rollout_restart` and `kubernetes.deployment.rollback`. The GitHub comment capability is commissioned, governed and reachable by the platform's own loops, but a product caller cannot execute it — the route answers `ContractViolation`. | Medium | **Open, recorded.** Not fixed here: widening a product route's capability surface is a product decision, not a gate's. |
| F-13 | **The F-11 fix made audit worse before it made it better.** Reclaiming without renewing made two replicas thrash the role — each reclaimed, the other's next append failed with `AuditWriterNotOwned`, and the chain tail went stale under both (`AuditStorageError: the audit chain tail did not match`). Caused by this phase; found within minutes of a real two-replica run. | High | **Fixed**: the pump heartbeats while it holds the role, acquires only when free — the pattern the outbox publisher already had, of which the first fix implemented half. |
| F-14 | **Startup recovery floods the dispatch set.** `recover()` seeded `_targets` from an unbounded scan: **2213 runs scanned, hundreds tracked**, so every 0.5 s tick re-walked them and the loop was too slow to return to a node it had just leased. Same root cause as F-10. | High | **Fixed**: bounded, with the remainder left to the durable sweep. |
| F-15 | **A refused invocation does not record why.** The gateway sets `refusal`, `reason` and `stage` on `InvocationRefusedEvent`, and **none of the three survives into the durable outbox payload**. The persisted record of a refusal contains the capability, the worker, the digests and `security_relevant: True` — everything except the reason. For an asynchronous caller this is the difference between "refused because the approval did not cover this action" and an execution that appears to hang forever in `EXECUTING`. | **High** | **Open.** Found by this gate and not yet fixed. |

## Consequences

- **The asynchronous contract works and is proven**: a caller in a separate
  process submitted, received a durable execution id, **exited**, and a
  different process read that execution's status afterwards. Multi-replica runs
  with one holder per singleton role.
- **The gate this phase was asked to close is not closed.** The asynchronous
  *write* has not landed: the invocation is refused after the node is leased,
  and F-15 means the reason is not recorded anywhere. Until F-15 is fixed the
  refusal cannot even be diagnosed from the durable record, which is why it is
  the next thing to do rather than the last.
- **Three of six findings were introduced or worsened by this phase's own
  changes** (F-13 outright). Every one was found by running two replicas against
  a real store, and none by deterministic tests.

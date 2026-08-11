# ADR-051 — Scheduler Lifecycle and Existing Audit Integration

**Status:** Accepted
**Date:** 2026-08-09
**Phase:** 5.8
**Relates to:** ADR-049 (the loop), ADR-050 (multi-process coordination)
**Does not complete:** Phase 5.5, still blocked on `credential_unavailable`.

---

## Why this phase exists

ADR-050 closed multi-process competition and crash recovery, and named what it
had not reached:

* `scheduler.start()` / `stop()` under real operation — 5.7 drove `tick()`
  directly, as the scheduler's own docstring intends for tests;
* the invocation audit sink, which was wired to nothing (`gateway._audit is None`).

Phase 5.8 closes exactly those two and adds nothing else.

## The lifecycle contract, as found

Read from the implementation rather than assumed:

| | Behaviour |
|---|---|
| `start()` | Runs startup recovery **before** marking itself `RUNNING`. Recovery failure ⇒ `FAILED`, and it does **not** begin dispatching. |
| `start()` again | **Refused** with `ContractViolation`. |
| `stop()` | Idempotent for terminal states. Stops scheduling, joins the current cycle, and releases leadership **last**. |
| `stop()` again | Accepted. |
| `stop()` never started | Safe. |
| No database | Fails closed; nothing dispatched, no provider call, no fabricated leadership. |

### One documentation defect, recorded rather than fixed

`start()`'s docstring says **"Idempotent."** The code raises `ContractViolation`
when already `RUNNING`. Those disagree.

The *behaviour* is the safer of the two — refusing a second start is how the
platform guarantees one tick loop, and the test confirms exactly one thread
named `cortexprime-execution-scheduler` exists after a double start. So this ADR
records the contract as **"repeated start is refused"** and flags the docstring
as wrong. It is not corrected here because Phase 5.8's mandate is verification,
and silently editing a contract sentence is how a phase changes behaviour while
claiming it only observed it.

**Action for whoever owns the scheduler:** the docstring should say "Refuses a
second start", not "Idempotent".

### Crash is not a graceful stop, and the difference is visible

Verified in real OS processes with `os._exit(9)`:

* died before electing ⇒ holds nothing;
* died while `RUNNING` holding a token ⇒ the claim **survives as held**, a
  successor is refused while the lease is live, and acquires only once it lapses.

After a *graceful* stop the role is released and a successor acquires
immediately, with an advanced fencing token, **without any database repair** —
no rows deleted, no leadership reset, no forced acquisition.

## Audit: wired, not invented

The critical question was whether the existing seam sufficed. It did:

* `SecureCapabilityInvocationGateway` already emits on invocation
  (`_audit_invocation`) and on refusal (`_audit_refusal`);
* the port's shape is `record_in_context(kind, context, **fields)`, which is
  exactly what `AuditRuntime` already provides;
* `AuditRuntime` writes into an append-only, hash-chained `AuditStore` that
  already exists.

So Phase 5.8 supplied `AuditRuntime()` at the composition root and nothing else.
**No `AuditService2`, no audit bounded context, no second event store, no new
policy.**

### Audit failure cannot change an outcome

`_safe_audit` contains every exception — *"Audit failure can never turn a denial
into an allow."* Verified behaviourally, not just by reading: with a sink that
raises on every call, a cross-tenant invocation still refused with
`tenant_mismatch`, and the sink's own `RuntimeError` never escaped the gate.

Audit is therefore **best-effort observation**, not a durable transactional
participant. It is deliberately *not* merged with execution state, domain events
or the outbox — those remain distinct concepts.

### What the audit contains, and what it must never contain

Records carry tenant, capability, provider operation, outcome and refusal code.

The security check needed sharpening. A naive substring search for
`"authorization"` fails — because the audit legitimately contains
`authorization_digest` and `authorization_effect`, a digest and a policy effect,
which are precisely the evidence an audit *should* hold. The real assertions are
narrower and all pass: no credential value, no `bearer `, no `ghp_`, no
`CredentialMaterial`, no `"authorization":` header key, and the only
`authorization*` fields are the digest and the effect.

**Replay emits zero audit records** — verified by count, alongside zero
credential, provider, transport and publication calls.

## Guarantees

**Guaranteed.** Recovery precedes dispatch. A failed startup does not dispatch.
Exactly one tick loop per scheduler. Graceful stop releases leadership; crash
does not. Stop never concludes attempts, cancels leases or fabricates results.
Audit records governed invocations and refusals without credential material, and
cannot alter an outcome.

**Not guaranteed.** Audit durability — the store used here is in-memory and
per-process; a durable audit store exists (`JsonlAuditStore`) but was not wired
or verified. Exactly-once anything.

## Non-goals

No rate limiter, tenant fairness, approver entitlement, MCP SSE, sandboxed
stdio, new retry or compensation policy, new credential provider or transport.
No GitHub contact; `GITHUB_TOKEN` was neither read nor modified.

## What remains unverified

* **Real provider execution** — Phase 5.5, `credential_unavailable`.
* **Durable audit storage** — only the in-memory store was exercised.
* **Audit chain verification after a crash** — recovery of a partially written
  chain was not tested.
* **Long-running lifecycle churn** — repeated start/stop cycles under sustained
  load; each case here was discrete.

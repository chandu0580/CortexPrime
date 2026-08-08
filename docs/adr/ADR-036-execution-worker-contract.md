# ADR-036 — Execution worker contract

**Status:** Accepted
**Date:** 2026-08-08
**Phase:** 3.3.1 — Execution Contract + Worker Runtime Foundation
**Extends:** ADR-029/031 (Execution), ADR-030 (WorkerKindResolver), ADR-035 (binding)

---

## 1. What a worker is handed

By the time a request reaches a worker, the capability exists (ADR-032), is
discovered and ingested (ADR-033), is authorized and admitted (ADR-034), and has
been resolved into a validated binding (ADR-035). A worker is handed the result
of all that and asked to perform it.

So `WorkerExecutionRequest` carries **no registry, no policy engine, no resolver,
and no discovery service**. A worker cannot look up whether it is allowed to run,
because there is nothing in its hand to look it up with. That is the only way to
be certain it never decides — verified: no such symbol appears in the module.

## 2. Reconciling the Phase 3.1 Protocol

`ExecutionWorker` already existed from ADR-029, and **it was wrong for this
phase**:

- `run` took a `RunContext` naming a node and a worker kind, with **no capability
  binding**. A worker receiving one could not tell what it had been authorized
  to do, and nothing downstream could check that what ran was what was approved.
- It returned a bare `ExecutionResult` with no classified failure, leaving the
  runtime to infer from an exception whether a production change had happened.

Nothing implemented or consumed it, so `run` was evolved rather than duplicated:
one worker Protocol, now taking a `WorkerExecutionRequest` and returning a
`WorkerExecutionResult`. Two competing worker contracts would have been worse
than one changed signature with no callers.

## 3. `BoundCapability` — the binding, as Execution may see it

`CapabilityBinding` lives in BC-8 and Execution may not import it (S2). The
composition root projects it into flat primitives.

The projection is **one-way**: there is no inverse, every field is required, and
the digests are opaque strings Execution cannot compute. A worker, an adapter, or
a caller cannot fabricate authority by constructing one, because what makes it
real is a validator on the other side of the boundary.

**Locally checkable** here: expiry, tenant, principal, execution, node,
operation. **Not checkable** here: lifecycle, trust, capability digest — those
arrive through the `BindingValidator` port, implemented at the composition root
over ADR-035's `validate_binding`.

## 4. The gate — seven refusals before anything runs

1. Local binding checks fail → **refuse**
2. No `BindingValidator` wired → **refuse** (`binding_unverifiable`)
3. Validator raises → **refuse** — unverifiable is unusable
4. Validator reports invalidations → **refuse** (`binding_invalid`)
5. Worker kind unresolvable → **refuse** — no default kind
6. Kind disagrees with the request → **refuse**
7. No adapter for the kind → **refuse** — **no default worker, no substitution**

All seven verified. There is no branch that proceeds because something was
unavailable.

## 5. No re-resolution, ever

An invalid binding does **not** trigger picking another provider. That would
silently change the target that was authorized and approved — the run would act
against a provider nobody signed off, with the original binding id in the audit
trail.

An invalid binding is a refusal. What happens next is a recovery decision
(ADR-031), made by a human or a policy with the facts in front of them. A
different provider requires a new authorization if the digest differs, a new
resolution, and a new binding.

## 6. Result semantics — facts, not conclusions

`WorkerExecutionResult` says what the worker *observed*. It does not say what the
run's state becomes, whether to retry, or whether the node failed. Execution
decides those from effect semantics, failure class, attempt history and retry
policy — all already owned by Phase 3.1.

Five outcomes: `SUCCESS · FAILURE · UNKNOWN_OUTCOME · CANCELLATION · TIMEOUT`.

**`TIMEOUT` is deliberately not a known outcome.** A deadline records when we
stopped waiting, never what the far side did. It maps to `NodeState.UNKNOWN`, so
the ambiguity rules from ADR-031 apply and a non-idempotent mutation is not
blindly retried.

## 7. Exceptions become classified failures at the boundary

No infrastructure exception leaks into the execution API. Timeouts, connection
failures, permission failures, validation errors and cancellations map onto
Phase 3.1's taxonomy.

**Anything unrecognised becomes `UNKNOWN_OUTCOME`, never `FAILURE`.** A
`RuntimeError` from an adapter mid-call could mean the request never left or that
it landed and the response was lost. Verified: an unclassifiable exception, and
an adapter returning the wrong type, both yield `UNKNOWN_OUTCOME` — never
`SUCCESS`.

## 8. Effect overreach is not a success

If a worker reports an effect stronger than the bound capability declared — a
capability registered as a reversible write reporting a destructive one — the
result is rewritten to `UNKNOWN_OUTCOME` with the contradiction as its reason.

Not a failure, because the change may well have landed; not a success, because
the operation exceeded what was authorized. Verified.

## 9. Ownership: lease, attempt, checkpoint

Execution owns lease acquisition, heartbeat, expiry and reclaim (ADR-031). A
worker **never acquires its own lease** and cannot extend its authority.
Heartbeat remains separate from expiry, so a stuck worker cannot hold a node by
breathing.

Every invocation belongs to an `ExecutionAttempt`; attempts are append-only.
`WorkerRuntime` holds **no repository** and never writes an `Execution` —
verified. It returns a result; the execution service records it. Worker reports
facts, Execution records facts.

## 10. Cancellation is honest about what it can promise

`CancellationSupport` is `NONE | BEST_EFFORT | GUARANTEED`. It exists because
"cancelled" is routinely claimed on the strength of a signal having been sent. A
worker that fired a stop and did not wait has not stopped anything it can vouch
for. `BEST_EFFORT` therefore leaves the outcome ambiguous rather than cancelled.

## 11. Tenancy, principal, credentials

`ExecutionContext` is mandatory throughout. The request refuses at construction
if its tenant or principal disagrees with the binding's — verified. A worker
receives identity facts and cannot redefine them.

`CredentialProvider` is a Protocol with **no implementation and no caller**. It
exists so that when credentials arrive they attach there rather than inside a
worker, and so `BoundCapability` is never where somebody puts a token. A binding
carries authority to *act*; it must never carry the secret proving who is acting.

## 12. Replay stays non-executable

Unchanged from ADR-031 and re-verified: the replayer holds no repository, no
pool, no queue, and now also no worker runtime and no adapter. A replayed
invocation reconstructs history and cannot re-send, retry, or rebind.

## 13. Observers cannot break execution

Reuses `ExecutionObserver` / `SafeObserver`. Observation failures are logged and
dropped; a telemetry backend having a bad afternoon must never fail a production
run or cause one to be retried. No OpenTelemetry dependency was added.

## 14. Composition root

`capability_execution_composition.py` is **the only module importing both
contexts** — verified across the whole `backend` tree. Execution does not import
Connectivity and Connectivity does not import Execution, verified in both
directions.

`WorkerKindResolver` (ADR-030) is **unchanged** and remains the single execution
attachment seam; the adapter presents the capability reference as the node
identity so an existing resolver works unmodified.

## 15. Deliberately not built

No worker of any kind. `StaticWorkerDirectory` starts empty, so **every
invocation currently refuses with `worker_unavailable`** — the correct behaviour
for a platform with no workers, rather than inventing a default.

No connector, no MCP transport, no Docker, no Kubernetes, no browser, no shell,
no subprocess — verified absent from the whole execution context. No scheduler,
queue, pool or autoscaler. No credential implementation. No fallback or worker
substitution. No new API endpoint: the Mission Control handoff (ADR-030) remains
the controlled entry point, and no route accepts a provider, worker kind or
capability digest as authority from a caller.

## 16. Known limitations

- **`InputValidator` is a seam with no implementation.** Absent one, payloads
  pass through unvalidated. Stated rather than assumed safe; wiring the
  platform's schema validation is follow-on work.
- **The lease check at invocation is advisory.** The authoritative check lives on
  the aggregate (ADR-031) and runs when the result is recorded, which is where it
  can actually refuse a write. The runtime does not duplicate it.
- **No event was added.** Phase 3.1's attempt and outcome events already carry
  these facts; a `worker_invocation_started` event would have duplicated
  `ExecutionAssigned`. Inspected and deliberately skipped.

## 17. Compliance

- **S2** — execution imports only `contracts/` and `platform/`; verified.
- **P2** — reversibility: ambiguity is preserved rather than resolved optimistically.
- **ADR-017 / BC-9** — explicit `ExecutionContext`; tenant and principal must
  agree with the binding.
- **ADR-018** — no new authoritative state of any kind.
- Reused: `EffectSemantics`, `SideEffectClass`, `FailureClass`/`FailureRecord`,
  `ExecutionResult`, `NodeState`, `PrincipalRef`, platform hashing,
  `ExecutionObserver`. No second taxonomy, hashing, or identity model.

## 18. Phase 3.3.2 boundary

3.3.2 implements adapters conforming to `ExecutionWorker` and registers them in
the directory. Nothing else needs to change: the gate, the classification, the
ownership split and the composition root are already in place, and a new adapter
becomes reachable by being registered — not by any code path being loosened.

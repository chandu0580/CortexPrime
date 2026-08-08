# ADR-031 — Durable Execution Core

**Status:** Accepted
**Date:** 2026-08-08
**Phase:** 3.1 — Durable Execution Core
**Supersedes:** nothing
**Extends:** ADR-029 (Execution bounded context), ADR-030 (Workflow → Execution handoff)
**Related:** ADR-016 (fitness functions), ADR-017 (request context), ADR-018 (storage boundary)

---

## Context

ADR-029 built an Execution context that could run a compiled workflow and refuse
the obviously unsafe moves. It was correct about orchestration and thin about
everything that makes a runtime trustworthy when things go wrong: failures were
strings, retry was a state change, ambiguity existed as one node state and
nowhere else, and there was no way to ask "what would you do about this?" before
it did something.

Phase 3.1 makes the substrate durable in design and honest about what it can and
cannot guarantee. It extends the existing context; no second execution
architecture was created.

## Decisions

### 1. Exactly-once is not claimed. Anywhere.

Nothing that crosses a network can honestly claim it. What is modelled instead is
the choice between two failure modes when the answer is unknowable:

- `AT_LEAST_ONCE` — may run again after ambiguity. Legal **only** where repeating
  is safe; the constructor refuses the combination otherwise.
- `AT_MOST_ONCE` — will not run again after ambiguity. Surfaces the ambiguity to
  a human and accepts that the work may never have happened.

### 2. UNKNOWN fails closed, in two independent places

`SideEffectClass` (published, ADR-005) says how *consequential* an action is. It
does not say whether repeating it is safe, and those are genuinely independent —
a reversible write can be violently non-idempotent.

`EffectSemantics` answers the second question and is **derived, never stored**:

| declaration | semantics | delivery |
|---|---|---|
| non-mutating | `READ_ONLY` | at-least-once |
| mutating + idempotency key | `IDEMPOTENT_WRITE` | at-least-once |
| mutating, no key | **`UNKNOWN`** | **at-most-once** |

`UNKNOWN` is treated as non-idempotent by every decision. The tempting default —
unknown means safe, so the retry can proceed — is exactly the assumption that
turns one production change into two. It is kept distinct from
`NON_IDEMPOTENT_WRITE` because an *undeclared* risk needs a different human
conversation than a declared one.

The published contract was **not forked** to add an UNKNOWN member. It encodes
P2/P9 and is used across contexts; deriving in the execution domain gets the
semantics without changing a published vocabulary.

### 3. Failure is a taxonomy, not a string

Thirteen classes chosen by *what the runtime should do next*, not by where the
error came from. Three properties drive every automatic decision: `is_ambiguous`,
`is_worth_retrying`, `is_terminal_for_the_node`.

`TIMEOUT` is deliberately ambiguous: a deadline records when we stopped waiting,
never what the far side did. `CANCELLATION` is a class of its own because "the
user cancelled the deploy" and "the deploy broke" are different facts that lead
to different conversations.

`UNKNOWN_OUTCOME` is not a failure. It is the absence of knowledge, and it exists
because the alternative — calling a lost response a failure and retrying — is how
a delete runs twice. A lapsed lease now classifies itself as `UNKNOWN_OUTCOME`
automatically.

### 4. No silent retry

Retry is a computed `RetryDecision` carrying verdict, reason, previous attempt,
next attempt, delay, failure class, and the budget the workflow allowed. The
service **refuses to retry without one** (`RetryRefused` → `409`), so a caller
cannot flip a node back to ready by any route.

The check order is the design: **ambiguity is evaluated before worthwhileness**,
so an operation that must not repeat is refused even when the failure looks
eminently retryable — precisely the case where a naive runtime does the damage.

Delay is a pure function of (attempt, policy); jitter comes from a caller-supplied
seed, not a random source, so replaying a history reproduces the schedule it
originally had.

**Ownership:** Workflow owns retry *legality* (how many attempts, what backoff,
whether a key exists). Execution owns retry *execution* (given what actually
happened, may this run now). Execution never raises the workflow's limit.

### 5. Idempotency keys are derived, never invented

Derived via the platform's canonical hashing from
`tenant + execution + workflow digest + node + operation key`.

The **workflow digest is included**: the same node in a revised workflow is not
the same logical operation, and reusing the old key would suppress work that
genuinely needs to happen.

The **attempt number is excluded**: including it would give every retry a fresh
key, making retries duplicate rather than collapse — the exact bug the mechanism
exists to prevent.

`IdempotencyRecord` stores a **digest of the response, never the response**:
external payloads of unbounded size do not belong in runtime state. `UNKNOWN`
status does not permit a fresh attempt; only `FAILED` does.

### 6. Recovery is a decision, never an action

`plan_recovery` is pure and returns one of six named actions with its reasoning.
Only `RESUME_FROM_CHECKPOINT` and `RETRY_ATTEMPT` are automatic.

Ambiguity outranks everything, and it is read from **two** sources: nodes left
`UNKNOWN` by a lapsed lease, *and* nodes marked `FAILED` whose recorded failure
class is ambiguous. Reading only node state would let recovery resume straight
past a delete that may well have happened — the same defect wearing a different
state name. This was found and fixed during implementation.

A run holding an ambiguous node cannot construct a `RESUME_FROM_CHECKPOINT`
decision at all; the invariant is in `__post_init__`.

### 7. Replay reconstructs; it never executes

`ExecutionReplayer` holds no repository, no worker pool, and no queue. It is
handed events and returns a `ReplayedExecution` projection. The guarantee is
structural, not a convention — there is nothing in the object for it to call.

The projection has no `assign`, `record_result`, or `start`. What comes back from
replay **cannot be driven**.

Replay reconstructs *orchestration* state only. Where history records `UNKNOWN`,
replay faithfully reproduces the not-knowing rather than resolving it. Causal
order is *checked* and gaps are reported, never silently repaired: a replay that
quietly reorders history no longer reconstructs what happened.

### 8. Heartbeat is separate from renewal

`heartbeat_at` is distinct from `expires_at` because a worker that took a long
lease and died a second later looks perfectly healthy by expiry alone.

`beating()` records liveness **without extending the claim**. A heartbeat that
silently renewed would let a stuck worker hold a node forever by doing nothing
but breathing.

Going quiet is *evidence* a worker is gone, not proof. Only expiry entitles
anyone else to the node — acting on evidence alone is how two workers end up
holding one lease. `silent_workers()` reports; it does not reclaim.

### 9. Compensation has a lifecycle, including the worst case

`REQUESTED → RUNNING → COMPLETED | FAILED | REQUIRES_INTERVENTION`.

`FAILED` matters most: a change was applied, the attempt to undo it did not work,
and the system is now further from where it started than when it began. A failed
compensation may **only** escalate — never silently re-run, because the change is
still applied and a second failing attempt buys nothing.

Phase 2's rule stands: compensation nodes are not projected as forward work.

### 10. The direct-start route now fails closed

`POST /api/v1/executions` accepts a caller-supplied workflow digest and node
list. Nothing in that module can check them — it may not import the Workflow
context, and that restriction is correct.

So it was the one path in the platform that could start a run over work nobody
approved. It is now **disabled by default**, gated on
`CORTEXPRIME_ALLOW_DIRECT_EXECUTION_START=1`, and returns `403` naming the
authoritative path (`/api/v1/mission-control/executions`, ADR-030).

Kept rather than deleted because it is a genuine internal surface for exercising
the runtime without a whole control plane. Disabled by default so keeping it
costs nothing in production.

### 11. Observation cannot influence execution

`ExecutionObserver` is a Protocol with named lifecycle moments, wrapped in
`SafeObserver` so exceptions are logged and dropped. A telemetry exporter having
a bad afternoon must never fail a production deployment or, worse, cause one to
be retried.

This is the opposite of the event stream, which is authoritative. Losing an
observation is survivable; losing an event is not.

### 12. The outbox is a contract, and its implementation is honestly in-memory

Events are recorded alongside the state change so "state committed, event lost"
cannot happen silently. Publication then fails, retries, or duplicates without
losing the fact.

**The current implementation is in-memory and not durable.** A restart loses
pending entries, exactly as the in-memory repository loses runs. This is stated
plainly because an outbox claiming durability it does not have is worse than
none: it invites reliance on a guarantee that is not there.

No new authoritative file store was introduced. When the repository becomes a
database, this contract is implemented against the same transaction and the
guarantee becomes real without any caller changing.

## Limitations — stated precisely

| Claim | Reality |
|---|---|
| Exactly-once | **Not claimed, not implemented, not implementable** |
| Durable persistence | **No.** Repository and outbox are in-memory |
| Durable idempotency records | **No.** Model exists; the store is Phase 3 DB work |
| Crash recovery | Deterministic *algorithm*; survives process restart only once persistence is durable |
| Compensation dispatch | Lifecycle modelled; performing the action needs a worker (3.3) |
| Distributed lease safety | Safe in-process; cross-process needs the durable store |
| Event history | Read from the outbox, which retains entries. Not an event store |

## Seams left for later phases

**3.2 Capability Fabric** — `WorkerKindResolver` (ADR-030) is untouched and
remains the only place worker kind is decided. No registry, discovery, or
routing was built.

**3.3 Workers/Connectors** — `ExecutionWorker` remains a Protocol. The context
still contains no `subprocess`, `docker`, `kubernetes`, or `playwright`
reference, and a test enforces it.

**3.4 Evidence Plane** — `ExecutionObserver` is the sole hook. No OpenTelemetry
dependency exists in the domain.

## Compliance

- **S2** — imports only `contracts/` and `platform/`; unchanged and test-enforced.
- **S4** — no state exited without recording why; ambiguity is representable.
- **P2** — reversibility precedes action: the retry gate is the enforcement.
- **BC-9 / ADR-017** — `ExecutionContext` threaded throughout; the outbox refuses
  to record an entry it cannot attribute to a tenant.
- **ADR-018** — no new file-based authoritative state.
- Reused: platform hashing, ULID identity, `DomainEvent`/`EventMetadata`,
  tenancy context. No second implementation of any of them.

Record schema version raised to **2** (lease heartbeat, attempt failure
classification, retry decision).

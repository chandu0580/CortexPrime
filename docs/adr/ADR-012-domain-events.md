# ADR-012 — Domain Event Foundation

- **Status:** Accepted
- **Date:** 2026-08-04
- **Phase:** 1 (PR-03)
- **Related:** ADR-010 (Contract Vocabulary), ADR-011 (Canonical Hashing)

## Context

The Constitution's nine bounded contexts communicate by **events** (facts that
happened) or **commands** (requests to a single owner), never by shared state.
Events are the primary mechanism, and nothing in the codebase defines what one
*is*.

A survey found **14 files** defining event classes and correlation ids generated
ad hoc as `uuid4().hex[:12]`. The existing `backend/events/` package is a
domain-specific cognition event system with a bus: pydantic models, naive
`datetime.utcnow()` timestamps, no correlation, no causation, no versioning. It
is a working transport for one domain, not a foundation for nine.

PR-03 defines the foundation. It deliberately contains no transport.

## Decision

Create `backend/platform/events` with base, metadata, envelope, registry,
serializer, validator, versioning, and exceptions.

### DomainEvent extends Contract

Rather than reimplementing serialization, versioning, and the envelope format,
`DomainEvent` subclasses `backend.contracts.Contract`. Constitution S11 forbids
duplicated implementations and the contract machinery already does this job.

An event's `EVENT_TYPE` **is** its `CONTRACT_NAME`; `__init_subclass__` sets both
from one declaration. Two identities that must agree will eventually disagree,
so there is only one.

### Correlation and causation are separate fields

Routinely conflated, with different jobs:

- `correlation_id` — constant across a causal chain. What you filter a log by.
- `causation_id` — the `event_id` of the single event that directly caused this
  one. Null only at a chain origin.

Correlation tells you *which* chain; causation tells you *where in it*. Only
causation reconstructs the exact path.

`DomainEvent.derive()` sets both correctly. Building a chain by hand invites a
missing link, and a chain with a missing link cannot be traced — so the
validator rejects an event whose causation matches but whose correlation does
not, which is exactly the mistake hand-construction produces.

### Tenant scope is mandatory on metadata

Constitution I6: every cross-context message carries tenant identity. `scope` is
required, not optional. An event with no tenant is a process-internal signal,
not a domain event, and does not belong in this foundation.

### Event ids are ULIDs

From ADR-011's `monotonic_ulid()`. Two consequences: events sort by id without
consulting a clock, and `validate_chain` can assert a caused event was created
after its cause using ids alone. Ordering that depends on timestamps is ordering
that breaks when a clock is corrected.

### Envelope is separate from event

The event is what happened. The envelope is how *this copy* is being carried —
enqueue time, delivery attempt, replay flag, content digest.

Redelivering must not alter the fact recorded, so delivery state lives outside
the event. An event is immutable history; an envelope is disposable transport.

**Replay is structurally enforced.** `replay=True` can only be produced by
`for_replay()`, and envelopes are frozen, so a replayed envelope cannot be
relabelled as a live delivery. Constitution S4 requires that replay never
re-execute side effects; a consumer checking `envelope.replay` cannot be fooled.

**Integrity uses ADR-011.** `content_digest` covers the whole event and is
computed inside `wrap()`, never accepted from a caller — a caller-supplied
digest could describe something other than the event it accompanies, which is
the binding this exists to prevent.

### Two digest functions, deliberately

- `event_digest` covers metadata, so two events with identical payloads but
  different ids differ. An envelope binds *this* event.
- `payload_digest` excludes metadata, so the same fact observed twice matches.
  Deduplication asks about content, not identity.

Equality follows the same split: `==` includes metadata (same event);
`same_content_as()` compares payload (same occurrence).

### Registry discovers rather than requires registration

Event subclasses already self-register in the contract registry at import. The
event registry derives its index from there. A registration you can forget will
be forgotten, and the failure surfaces only when something tries to decode.

### Versioning mirrors ADR-010

Additive-only. Older payloads decode as-is (a valid subset) or through
registered upcasters, one version step at a time. Newer payloads are refused —
silently dropping unknown fields would let a consumer act on a partial view of a
fact. Upcasters operate on payload dicts, never constructed events, because a v1
class may no longer exist while its serialized form always does.

## Alternatives Considered

**Extend the existing `backend/events/` base.** Rejected: `CognitionEvent` is
pydantic-based, mutable, uses naive `utcnow()` (deprecated in 3.12+ and
unorderable across processes), and carries cognition-specific fields. Retrofitting
it would mean changing a class 14 files depend on, in a PR that is supposed to
add a foundation rather than migrate one.

**A standalone `Event` base not derived from `Contract`.** Cleaner conceptual
separation. Rejected: it would duplicate envelope, versioning, encode/decode, and
registry — four mechanisms that must agree with the contract layer forever.

**Include a bus or dispatcher.** Explicitly out of scope. Transport choice is a
separate decision with separate operational consequences; defining the message
does not require choosing the pipe.

**Make `causation_id` a list.** Some systems allow multiple causes. Rejected: a
single direct cause makes the chain a path rather than a graph, and every
traversal simpler. Aggregation over several events is a legitimate case, but it
is modelled as an event whose *payload* references the inputs.

## Consequences

**Positive**

- One event definition for nine contexts, with causality tracing built in.
- Replay and integrity are structural, not conventional.
- Reuses ADR-010 serialization and ADR-011 hashing; no third implementation.
- 274 platform tests run in ~4 seconds with no infrastructure.

**Negative**

- Two event systems coexist: `backend/events/` (with a bus, in use) and
  `backend/platform/events/` (foundation, unused). This is the third
  "destination now, migration later" PR; the accumulating parallel surface is
  what PR-40's `legacy/` boundary exists to make visible and finite.
- `EventMetadata.create()` is the only clock read in the package. Convenient, but
  it means constructing metadata is not a pure function — tests needing
  determinism must pass `occurred_at` explicitly.

**Neutral**

- Nothing imports the package yet. No runtime risk on merge.

## Defect found and fixed in PR-01

`freeze_mapping` returned `types.MappingProxyType`, which is read-only but **not
hashable**. Any frozen contract carrying an opaque mapping — `ActionRef`,
`AuditEvent`, `ExecutionResult` — was therefore unhashable, contradicting PR-01's
own documented claim that contracts work as dict keys. PR-01's test passed
because it exercised only a tuple-bearing contract.

Fixed at the root: `freeze_mapping` now returns `FrozenDict`, an immutable
`Mapping` that hashes by canonicalized content (sorted keys, normalized nested
structures) with the hash cached. Three regression tests added to the contracts
suite.

Fixed in `contracts` rather than worked around in `events` because the defect is
in `contracts`, and a per-package workaround would have to be written three
times and would leave the original claim false.

## Compliance

Enforced by `tests/platform/test_dependency_isolation.py`:

- No event module imports outside the explicit stdlib allowlist.
- No event module imports `contexts/`, `legacy/`, `services/`, or `api/`.
- Importing the package in a clean interpreter loads no framework.
- Every module imports standalone in a fresh interpreter, proving no cycles.
- `APPROVED_THIRD_PARTY` remains empty.

The allowlist gained `dataclasses`, `datetime`, and `types` in this PR — all
standard library, all listed explicitly so the addition is reviewable.

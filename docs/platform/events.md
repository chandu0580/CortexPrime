# Domain Event Foundation

`backend.platform.events` — the shared infrastructure every bounded context uses
to define, serialize, validate, and trace domain events.

> **No transport lives here.** No bus, dispatcher, broker, queue, persistence,
> database, or network. This defines the thing those carry. Keeping them apart
> means an event's shape does not change when the transport does.

---

## Declaring an event

```python
from dataclasses import dataclass
from backend.platform.events import DomainEvent, EventMetadata

@dataclass(frozen=True)
class MissionConcluded(DomainEvent):
    EVENT_TYPE = "cortexprime.mission.concluded"

    outcome: str
    duration_ms: int
```

Past tense, always. A command may be refused; an event is a fact.

`EVENT_VERSION` defaults to 1. `EVENT_TYPE` doubles as the contract name — one
declaration sets both, so they cannot drift.

```python
event = MissionConcluded(
    metadata=EventMetadata.create(
        aggregate_id="msn_01J8XK", aggregate_type="mission", scope=scope,
    ),
    outcome="resolved",
    duration_ms=4200,
)
```

`metadata` is inherited and always first. `scope` is **mandatory** — Constitution
I6 requires every cross-context message to carry tenant identity.

---

## Correlation vs causation

Two identifiers, routinely conflated, with different jobs.

| | Scope | Answers |
|---|---|---|
| `correlation_id` | Constant across a whole causal chain | *Which* chain is this? |
| `causation_id` | The id of the one event that directly caused this | *Where* in the chain? |

Correlation is what you filter a log by. Causation is what reconstructs the exact
path. You need both.

**Always use `derive()` to build a chain:**

```python
ticket = event.derive(TicketFiled, ticket="OPS-1")
# inherits correlation_id, sets causation_id to event.event_id
```

Building a chain by hand invites a missing link, and a chain with a missing link
cannot be traced. `require_causal_link` rejects an event whose causation matches
but whose correlation does not — precisely the mistake hand-construction makes.

---

## Envelopes

The event says *what happened*. The envelope says *how this copy is being
carried*.

```python
from backend.platform.events import EventEnvelope

envelope = EventEnvelope.wrap(event)
envelope.require_integrity()      # raises if the digest no longer matches

retry  = envelope.next_attempt()  # attempt 2, same event, new envelope
replay = envelope.for_replay()    # replay=True, attempt resets to 1
```

**Replay is structurally enforced.** `replay=True` can only come from
`for_replay()`, and envelopes are frozen — a replayed envelope cannot be
relabelled as live. Constitution S4 requires replay never re-execute side
effects; a consumer checking `envelope.replay` cannot be fooled.

**Integrity.** `content_digest` is computed inside `wrap()`, never accepted from
a caller. A caller-supplied digest could describe a different event, which is the
binding this prevents. Same property Constitution I2 relies on for approvals,
applied to transport.

---

## Digests and equality

Two of each, because identity and content are different questions.

| Question | Use |
|---|---|
| Is this the same **event**? | `a == b`, `event_digest(e)` |
| Is this the same **occurrence**? | `a.same_content_as(b)`, `payload_digest(e)` |

An envelope binds *this* event, so it uses `event_digest`. Deduplication asks
about content, so it uses `payload_digest`.

---

## Serialization

```python
from backend.platform.events import serialize, deserialize, to_bytes

wire     = serialize(event)      # JSON-safe dict
restored = deserialize(wire)     # resolves the concrete class from the registry
raw      = to_bytes(event)       # canonical bytes, per ADR-011
```

Encoding reuses the contract envelope. Decoding adds what contracts cannot do
alone: resolving a type name to a class, and migrating older payloads forward.

---

## Versioning

Additive-only, mirroring ADR-010.

| Change | Breaking? |
|---|---|
| Add an optional field with a default | No |
| Add a new event type | No |
| Remove or rename a field | **Yes** |
| Make an optional field required | **Yes** |
| Narrow a field's type | **Yes** |
| Change a field's *meaning* | **Yes** — and easy to miss, since the shape doesn't change |

**Decoding.** Older payload → accepted as-is, or migrated by registered
upcasters. Newer payload → refused; silently dropping unknown fields would let a
consumer act on a partial view of a fact.

```python
from backend.platform.events import default_upcasters

default_upcasters.register(
    "cortexprime.mission.concluded", 1,
    lambda payload: {**payload, "duration_ms": 0},
)
```

Upcasters run one version step at a time (v1 → v2 → v3, never a bespoke jump)
and operate on payload dicts, never constructed events — a v1 class may no
longer exist, but its serialized form always does.

---

## Validation

```python
from backend.platform.events import validate_encoded, validate_chain

event_class = validate_encoded(wire)   # decodable? returns the class
validate_chain([first, second, third]) # one well-ordered causal chain?
```

`validate_chain` requires a shared correlation, an origin first, each event
caused by its predecessor, and strictly increasing event ids. Ids are ULIDs, so
increasing ids also mean non-decreasing time — **without trusting a clock**.

---

## Testing

```bash
pytest tests/platform/ --confcutdir=tests/platform    # ~4s, 274 tests
```

| File | Validates |
|---|---|
| `events/test_events.py` | Creation, metadata, causality, equality, immutability, threading |
| `events/test_serialization.py` | Round-trip, digests, versioning, registry, envelopes |

---

## Migration status

Nothing imports this yet.

`backend/events/` remains the in-use system: a cognition-specific event bus with
pydantic models and naive timestamps. It is not superseded by this PR — no
transport is defined here — and migration happens when contexts adopt the
foundation.

| PR | Consumes |
|---|---|
| **PR-04** | Envelope integrity, alongside the approval-binding fix |
| PR-06/07 | `EventMetadata`, `monotonic_ulid` sequencing for the audit chain |
| Later | Per-context event types, defined in the context that owns them |

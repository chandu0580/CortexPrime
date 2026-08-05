"""Domain event foundation.

The shared infrastructure every bounded context uses to define, serialize,
validate, and trace domain events. Contains no business events -- those belong
to the context that owns the thing they describe.

    from backend.platform.events import DomainEvent, EventMetadata, EventEnvelope

    @dataclass(frozen=True)
    class MissionConcluded(DomainEvent):
        EVENT_TYPE = "cortexprime.mission.concluded"
        outcome: str

    event = MissionConcluded(
        metadata=EventMetadata.create(
            aggregate_id="msn_01J8XK", aggregate_type="mission", scope=scope,
        ),
        outcome="resolved",
    )
    envelope = EventEnvelope.wrap(event)

What lives here
---------------
Event definitions, metadata, envelopes, serialization, validation, versioning,
and a type registry.

What does not
-------------
No bus, dispatcher, broker, queue, persistence, database, or network. Those are
transports; this is the thing they carry. Keeping the two apart means an event's
shape does not change when the transport does.

Design notes
------------
:class:`DomainEvent` extends ``backend.contracts.Contract`` rather than
reimplementing envelope, versioning, and serialization. An event's
``EVENT_TYPE`` *is* its ``CONTRACT_NAME`` -- one identity, so the two cannot
drift. Digests come from ``backend.platform.hashing``; there is exactly one
hashing implementation in CortexPrime and it is not in this package.

See ``docs/adr/ADR-012-domain-events.md``.
"""

from __future__ import annotations

from backend.platform.events.base import DomainEvent
from backend.platform.events.envelope import EventEnvelope
from backend.platform.events.exceptions import (
    EventError,
    EventIntegrityError,
    EventRegistrationError,
    EventSerializationError,
    EventValidationError,
    EventVersionError,
    UnknownEventTypeError,
)
from backend.platform.events.metadata import EventMetadata, new_correlation_id
from backend.platform.events.registry import EventRegistry, default_registry
from backend.platform.events.serializer import (
    deserialize,
    event_digest,
    payload_digest,
    serialize,
    to_bytes,
)
from backend.platform.events.validator import (
    is_decodable,
    require_causal_link,
    require_envelope_integrity,
    require_same_correlation,
    validate_chain,
    validate_encoded,
)
from backend.platform.events.versioning import (
    Upcaster,
    UpcasterRegistry,
    default_upcasters,
    is_version_decodable,
)

__all__ = [
    # base
    "DomainEvent",
    "EventMetadata",
    "new_correlation_id",
    "EventEnvelope",
    # registry
    "EventRegistry",
    "default_registry",
    # serialization
    "serialize",
    "deserialize",
    "to_bytes",
    "event_digest",
    "payload_digest",
    # validation
    "validate_encoded",
    "is_decodable",
    "require_causal_link",
    "require_same_correlation",
    "validate_chain",
    "require_envelope_integrity",
    # versioning
    "Upcaster",
    "UpcasterRegistry",
    "default_upcasters",
    "is_version_decodable",
    # errors
    "EventError",
    "EventValidationError",
    "EventRegistrationError",
    "UnknownEventTypeError",
    "EventVersionError",
    "EventSerializationError",
    "EventIntegrityError",
]

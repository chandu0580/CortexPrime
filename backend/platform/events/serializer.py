"""Event serialization and content digests.

Encoding delegates to the contract envelope (ADR-010); decoding adds the two
things contracts cannot do alone -- resolving a type name to a class, and
migrating an older payload forward.

Digests come from ``backend.platform.hashing`` (ADR-011). There is no hashing
code here, because there is exactly one hashing implementation in CortexPrime
and this is not it.

What a digest covers
--------------------
:func:`event_digest` hashes the whole event, metadata included, so two events
with identical payloads but different ids produce different digests. That is
what an envelope needs: it is binding *this* event, not an event like it.

:func:`payload_digest` hashes only the payload, which is what deduplication
needs -- "have I already seen this fact?" is a question about content, not
identity.
"""

from __future__ import annotations

from typing import Any, Mapping, Optional

from backend.contracts import ENVELOPE_CONTRACT_KEY, ENVELOPE_VERSION_KEY, HashAlgorithm
from backend.contracts.approval import PayloadDigest
from backend.platform.events.base import DomainEvent
from backend.platform.events.exceptions import (
    EventSerializationError,
    EventVersionError,
    UnknownEventTypeError,
)
from backend.platform.events.registry import EventRegistry, default_registry
from backend.platform.events.versioning import (
    UpcasterRegistry,
    default_upcasters,
    is_version_decodable,
)
from backend.platform.hashing import canonical_bytes, compute_digest

__all__ = [
    "serialize",
    "deserialize",
    "to_bytes",
    "event_digest",
    "payload_digest",
]


def serialize(event: DomainEvent) -> dict[str, Any]:
    """Encode ``event`` to a transport-neutral, JSON-safe dictionary."""
    if not isinstance(event, DomainEvent):
        raise EventSerializationError(
            f"expected a DomainEvent, received {type(event).__name__}"
        )
    return event.to_dict()


def to_bytes(event: DomainEvent) -> bytes:
    """Encode ``event`` to canonical bytes.

    Byte-identical for equal events regardless of field insertion order, which
    is what makes a digest over the result verifiable later.
    """
    return canonical_bytes(serialize(event))


def deserialize(
    data: Mapping[str, Any],
    *,
    registry: Optional[EventRegistry] = None,
    upcasters: Optional[UpcasterRegistry] = None,
) -> DomainEvent:
    """Reconstruct an event from :func:`serialize` output.

    Resolves the concrete class from the envelope, then migrates the payload
    forward if it predates the local schema.
    """
    if not isinstance(data, Mapping):
        raise EventSerializationError(
            f"expected a mapping, received {type(data).__name__}"
        )

    event_type = data.get(ENVELOPE_CONTRACT_KEY)
    if not isinstance(event_type, str):
        raise EventSerializationError(
            f"payload is missing {ENVELOPE_CONTRACT_KEY!r}; it was not produced by serialize()"
        )

    resolver = registry or default_registry
    event_class = resolver.resolve(event_type)  # raises UnknownEventTypeError

    declared = data.get(ENVELOPE_VERSION_KEY, event_class.EVENT_VERSION)
    if not isinstance(declared, int):
        raise EventSerializationError(f"envelope version must be an integer, got {declared!r}")

    local = event_class.EVENT_VERSION
    if not is_version_decodable(declared, local):
        raise EventVersionError(
            f"{event_type} payload is version {declared} but this build understands "
            f"at most version {local}"
        )

    payload = dict(data)
    if declared < local:
        migrator = upcasters or default_upcasters
        if migrator.has_step(event_type, declared):
            payload = migrator.upcast(event_type, payload, declared, local)
        # No upcaster registered: the payload is accepted as-is. Evolution is
        # additive-only, so an older payload is a valid subset of the current
        # shape and missing fields fall back to their declared defaults.
        payload[ENVELOPE_VERSION_KEY] = local

    return event_class.from_dict(payload)


def event_digest(
    event: DomainEvent, algorithm: HashAlgorithm = HashAlgorithm.SHA256
) -> PayloadDigest:
    """Digest over the whole event, metadata included.

    Two events describing the same occurrence but carrying different ids have
    different digests. Use this to bind an envelope to its event.
    """
    return compute_digest(serialize(event), algorithm)


def payload_digest(
    event: DomainEvent, algorithm: HashAlgorithm = HashAlgorithm.SHA256
) -> PayloadDigest:
    """Digest over the payload only, excluding metadata.

    Two events describing the same occurrence share a digest regardless of id,
    timestamp, or causal position. Use this to detect duplicates.
    """
    return compute_digest(
        {"event_type": event.event_type, "payload": event.payload()}, algorithm
    )

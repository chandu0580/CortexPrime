"""Structural validation for events and encoded payloads.

Most validation already happens at construction: contracts validate their own
invariants, and an event that will not construct cannot be published. This
module covers what construction cannot:

* **Encoded payloads** arriving from outside, before any class is chosen.
  ``validate_encoded`` answers "is this decodable?" without decoding, so a
  transport can reject malformed input without paying for construction.
* **Causal relationships** between two events, which no single event can check
  about itself.
* **Envelope integrity**, which compares a digest against its event.

Validation raises rather than returning a bool. A caller wanting a predicate
uses the ``is_*`` helpers; a caller wanting to proceed only if valid uses the
``require_*`` functions and lets the exception carry the reason.
"""

from __future__ import annotations

from typing import Any, Mapping, Optional, Sequence

from backend.contracts import ENVELOPE_CONTRACT_KEY, ENVELOPE_VERSION_KEY
from backend.platform.events.base import DomainEvent
from backend.platform.events.envelope import EventEnvelope
from backend.platform.events.exceptions import (
    EventValidationError,
    EventVersionError,
    UnknownEventTypeError,
)
from backend.platform.events.registry import EventRegistry, default_registry
from backend.platform.events.versioning import is_version_decodable

__all__ = [
    "validate_encoded",
    "is_decodable",
    "require_causal_link",
    "validate_chain",
    "require_same_correlation",
]


def validate_encoded(
    data: Mapping[str, Any], *, registry: Optional[EventRegistry] = None
) -> type[DomainEvent]:
    """Validate an encoded payload and return the class it decodes to.

    Checks the envelope only -- presence of the type key, a known type, and a
    decodable version. Field-level validation happens during construction,
    where the class's own rules live.
    """
    if not isinstance(data, Mapping):
        raise EventValidationError(f"expected a mapping, received {type(data).__name__}")

    event_type = data.get(ENVELOPE_CONTRACT_KEY)
    if not isinstance(event_type, str) or not event_type.strip():
        raise EventValidationError(
            f"payload is missing a valid {ENVELOPE_CONTRACT_KEY!r} key"
        )

    resolver = registry or default_registry
    try:
        event_class = resolver.resolve(event_type)
    except UnknownEventTypeError as exc:
        raise EventValidationError(str(exc)) from exc

    declared = data.get(ENVELOPE_VERSION_KEY, event_class.EVENT_VERSION)
    if not isinstance(declared, int):
        raise EventValidationError(f"envelope version must be an integer, got {declared!r}")
    try:
        decodable = is_version_decodable(declared, event_class.EVENT_VERSION)
    except EventVersionError as exc:
        raise EventValidationError(str(exc)) from exc
    if not decodable:
        raise EventValidationError(
            f"{event_type} payload is version {declared} but this build understands "
            f"at most version {event_class.EVENT_VERSION}"
        )

    if "metadata" not in data:
        raise EventValidationError(f"{event_type} payload is missing its metadata")

    return event_class


def is_decodable(
    data: Mapping[str, Any], *, registry: Optional[EventRegistry] = None
) -> bool:
    """Whether :func:`validate_encoded` would succeed."""
    try:
        validate_encoded(data, registry=registry)
    except EventValidationError:
        return False
    return True


def require_causal_link(effect: DomainEvent, cause: DomainEvent) -> None:
    """Assert that ``effect`` was directly caused by ``cause``.

    Verifies both halves: causation points at the cause, and correlation is
    shared. A matching causation with a different correlation means the chain
    was constructed by hand and got it wrong -- exactly what
    :meth:`DomainEvent.derive` exists to prevent.
    """
    if effect.causation_id is None:
        raise EventValidationError(
            f"{effect.event_type} has no causation_id; it claims to originate a chain"
        )
    if effect.causation_id != cause.event_id:
        raise EventValidationError(
            f"{effect.event_type} was caused by {effect.causation_id}, not {cause.event_id}"
        )
    if effect.correlation_id != cause.correlation_id:
        raise EventValidationError(
            f"{effect.event_type} shares a causation with {cause.event_type} but not a "
            "correlation; a caused event always inherits its cause's correlation_id"
        )


def require_same_correlation(events: Sequence[DomainEvent]) -> str:
    """Assert every event shares one correlation id, and return it."""
    if not events:
        raise EventValidationError("cannot determine a correlation id from no events")
    correlation = events[0].correlation_id
    for event in events[1:]:
        if event.correlation_id != correlation:
            raise EventValidationError(
                f"{event.event_type} has correlation {event.correlation_id!r}, "
                f"expected {correlation!r}"
            )
    return correlation


def validate_chain(events: Sequence[DomainEvent]) -> None:
    """Assert that ``events`` form one well-ordered causal chain.

    Requires a shared correlation, an origin as the first element, each
    subsequent event caused by its predecessor, and strictly increasing event
    ids. Ids are ULIDs, so increasing ids also mean non-decreasing time --
    without trusting a clock.
    """
    if not events:
        return

    require_same_correlation(events)

    if not events[0].metadata.is_chain_origin:
        raise EventValidationError(
            f"the first event in a chain must have no causation_id; "
            f"{events[0].event_type} claims to be caused by {events[0].causation_id}"
        )

    for previous, current in zip(events, events[1:]):
        require_causal_link(current, previous)
        if current.event_id <= previous.event_id:
            raise EventValidationError(
                f"{current.event_type} has an event_id that does not follow its cause; "
                "a caused event is always created after the event that caused it"
            )


def require_envelope_integrity(envelope: EventEnvelope) -> None:
    """Assert an envelope's digest still matches its event.

    Thin alias for :meth:`EventEnvelope.require_integrity`, present so that
    callers validating a batch have one import rather than two.
    """
    envelope.require_integrity()

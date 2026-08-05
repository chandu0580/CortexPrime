"""Event envelope: the unit a transport moves.

The event says *what happened*. The envelope says *how this copy of it is being
carried* -- when it was enqueued, which delivery attempt this is, whether it is
a replay, and a digest binding the envelope to its contents.

Keeping these apart matters. Redelivering an event must not alter the fact it
records, so delivery state lives outside the event. An event is immutable
history; an envelope is disposable transport.

Replay
------
Constitution S4: "Replay is read-only and never re-executes side effects -- this
is enforced structurally."

A replay envelope can only be produced by :meth:`EventEnvelope.for_replay`, and
``replay`` cannot be cleared afterwards because envelopes are frozen. A consumer
that checks ``envelope.replay`` before acting cannot be fooled by an envelope
that was replayed and then relabelled.

Integrity
---------
``content_digest`` is computed over the whole event at construction. Any change
to the event produces a different digest, so :meth:`verify_integrity` detects
substitution -- the same property Constitution I2 relies on for approvals,
applied to transport.

No transport lives here
-----------------------
No bus, no dispatcher, no queue, no broker. This module defines the shape of the
thing those would carry, and nothing else.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Mapping, Optional

from backend.contracts import Contract, ContractViolation, freeze_mapping
from backend.contracts.approval import PayloadDigest
from backend.platform.events.base import DomainEvent
from backend.platform.events.exceptions import EventIntegrityError, EventSerializationError
from backend.platform.events.registry import EventRegistry
from backend.platform.identity import is_ulid, monotonic_ulid

__all__ = ["EventEnvelope"]

_EVENT_KEY = "event"


@dataclass(frozen=True)
class EventEnvelope(Contract):
    """A single delivery of a single event."""

    CONTRACT_NAME = "cortexprime.events.envelope"

    envelope_id: str
    event: DomainEvent
    content_digest: PayloadDigest
    enqueued_at: datetime
    delivery_attempt: int = 1
    replay: bool = False
    headers: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not is_ulid(self.envelope_id):
            raise ContractViolation(
                f"envelope_id must be a ULID; got {self.envelope_id!r}"
            )
        if not isinstance(self.event, DomainEvent):
            raise ContractViolation("event must be a DomainEvent")
        if not isinstance(self.content_digest, PayloadDigest):
            raise ContractViolation("content_digest must be a PayloadDigest")
        if self.enqueued_at.tzinfo is None:
            raise ContractViolation("enqueued_at must be timezone-aware")
        if not isinstance(self.delivery_attempt, int) or self.delivery_attempt < 1:
            raise ContractViolation("delivery_attempt must be a positive integer")
        if not isinstance(self.replay, bool):
            raise ContractViolation("replay must be a bool")
        object.__setattr__(self, "headers", freeze_mapping(self.headers))

    # ------------------------------------------------------------------
    # Construction
    # ------------------------------------------------------------------

    @classmethod
    def wrap(
        cls,
        event: DomainEvent,
        *,
        headers: Optional[Mapping[str, Any]] = None,
        enqueued_at: Optional[datetime] = None,
    ) -> "EventEnvelope":
        """Wrap ``event`` for its first delivery.

        The digest is computed here rather than accepted from a caller. A
        caller-supplied digest could describe something other than the event it
        accompanies, which is precisely the binding this class exists to
        prevent.
        """
        from backend.platform.events.serializer import event_digest

        return cls(
            envelope_id=monotonic_ulid(),
            event=event,
            content_digest=event_digest(event),
            enqueued_at=enqueued_at or datetime.now(timezone.utc),
            delivery_attempt=1,
            replay=False,
            headers=headers or {},
        )

    def next_attempt(self) -> "EventEnvelope":
        """Return an envelope for the next delivery of the same event.

        A new envelope, not a mutation: the previous attempt remains a distinct,
        inspectable fact. Digest and replay flag carry over unchanged.
        """
        return EventEnvelope(
            envelope_id=monotonic_ulid(),
            event=self.event,
            content_digest=self.content_digest,
            enqueued_at=datetime.now(timezone.utc),
            delivery_attempt=self.delivery_attempt + 1,
            replay=self.replay,
            headers=self.headers,
        )

    def for_replay(self) -> "EventEnvelope":
        """Return a replay envelope for the same event.

        The only way to produce ``replay=True``. Delivery attempt resets to 1
        because a replay is a fresh delivery of an old fact, not a retry of a
        failed one.
        """
        return EventEnvelope(
            envelope_id=monotonic_ulid(),
            event=self.event,
            content_digest=self.content_digest,
            enqueued_at=datetime.now(timezone.utc),
            delivery_attempt=1,
            replay=True,
            headers=self.headers,
        )

    # ------------------------------------------------------------------
    # Integrity
    # ------------------------------------------------------------------

    def verify_integrity(self) -> bool:
        """Whether the digest still matches the event it accompanies."""
        from backend.platform.events.serializer import event_digest

        return event_digest(self.event, self.content_digest.algorithm).matches(
            self.content_digest
        )

    def require_integrity(self) -> None:
        """Raise :class:`EventIntegrityError` unless the digest matches.

        Use before acting on an envelope that crossed a trust boundary.
        """
        if not self.verify_integrity():
            raise EventIntegrityError(
                f"envelope {self.envelope_id} does not match its event "
                f"({self.event.event_type}); the payload changed after the digest was taken"
            )

    # ------------------------------------------------------------------
    # Serialization
    # ------------------------------------------------------------------

    @classmethod
    def from_dict(
        cls, data: Mapping[str, Any], *, registry: Optional[EventRegistry] = None
    ) -> "EventEnvelope":
        """Decode an envelope, resolving the concrete event type.

        Overridden because the inherited implementation would call
        ``DomainEvent.from_dict`` on the abstract base, which cannot know which
        subclass to construct. Type resolution needs the registry, so the
        envelope's fields are decoded explicitly here.
        """
        from backend.platform.events.serializer import deserialize

        if not isinstance(data, Mapping):
            raise EventSerializationError(
                f"expected a mapping, received {type(data).__name__}"
            )

        raw_event = data.get(_EVENT_KEY)
        if not isinstance(raw_event, Mapping):
            raise EventSerializationError("envelope payload is missing its event")

        for required in ("envelope_id", "content_digest", "enqueued_at"):
            if required not in data:
                raise EventSerializationError(
                    f"envelope payload is missing required field {required!r}"
                )

        raw_digest = data["content_digest"]
        if not isinstance(raw_digest, Mapping):
            raise EventSerializationError("content_digest must be an encoded PayloadDigest")

        raw_enqueued = data["enqueued_at"]
        if not isinstance(raw_enqueued, str):
            raise EventSerializationError("enqueued_at must be an ISO-8601 string")
        try:
            enqueued_at = datetime.fromisoformat(raw_enqueued)
        except ValueError as exc:
            raise EventSerializationError(
                f"enqueued_at is not a valid ISO-8601 timestamp: {raw_enqueued!r}"
            ) from exc
        if enqueued_at.tzinfo is None:
            raise EventSerializationError("enqueued_at must carry a timezone")

        return cls(
            envelope_id=data["envelope_id"],
            event=deserialize(raw_event, registry=registry),
            content_digest=PayloadDigest.from_dict(raw_digest),
            enqueued_at=enqueued_at.astimezone(timezone.utc),
            delivery_attempt=data.get("delivery_attempt", 1),
            replay=data.get("replay", False),
            headers=data.get("headers") or {},
        )

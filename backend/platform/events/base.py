"""The DomainEvent base class.

A domain event is an immutable statement that something happened. Past tense,
always: ``MissionConcluded``, not ``ConcludeMission``. A command may be refused;
an event is a fact, and facts are not negotiable.

Relationship to contracts
-------------------------
:class:`DomainEvent` extends ``backend.contracts.Contract`` rather than
reimplementing serialization, versioning, and the envelope format. Constitution
S11 forbids duplicated implementations, and the contract machinery already does
exactly this job. An event's ``CONTRACT_NAME`` *is* its ``event_type`` -- one
identity, not two that can drift.

Declaring an event
------------------
::

    @dataclass(frozen=True)
    class MissionConcluded(DomainEvent):
        EVENT_TYPE = "cortexprime.mission.concluded"

        outcome: str
        duration_ms: int

``EVENT_VERSION`` defaults to 1. Increment it only for a breaking payload
change; adding an optional field with a default is not breaking. See
``versioning.py``.

Immutability and threading
--------------------------
Events are frozen dataclasses with no mutable state, so they are safe to share
across threads without synchronization. Deriving a caused event returns a new
instance rather than mutating.
"""

from __future__ import annotations

import dataclasses
from typing import Any, ClassVar, Mapping, Optional, TypeVar

from backend.contracts import Contract, ContractViolation, PrincipalRef, TenantScope
from backend.platform.events.exceptions import EventRegistrationError
from backend.platform.events.metadata import EventMetadata

__all__ = ["DomainEvent"]

TEvent = TypeVar("TEvent", bound="DomainEvent")


@dataclasses.dataclass(frozen=True)
class DomainEvent(Contract):
    """Base class for every domain event in CortexPrime.

    Subclasses declare ``EVENT_TYPE`` and add payload fields. ``metadata`` is
    inherited and always first, so every event carries identity, causality, and
    tenant scope without restating them.
    """

    #: Stable identifier for this event type. Doubles as ``CONTRACT_NAME``.
    EVENT_TYPE: ClassVar[str]

    #: Payload schema version. Increment only for breaking changes.
    EVENT_VERSION: ClassVar[int] = 1

    metadata: EventMetadata

    def __init_subclass__(cls, **kwargs: Any) -> None:
        event_type = cls.__dict__.get("EVENT_TYPE")
        if event_type is not None:
            if not isinstance(event_type, str) or not event_type.strip():
                raise EventRegistrationError(
                    f"{cls.__name__}.EVENT_TYPE must be a non-empty string"
                )
            version = cls.__dict__.get("EVENT_VERSION", cls.EVENT_VERSION)
            if not isinstance(version, int) or version < 1:
                raise EventRegistrationError(
                    f"{cls.__name__}.EVENT_VERSION must be a positive integer"
                )
            # An event's contract identity IS its event identity. Setting both
            # from one declaration removes any way for them to diverge.
            cls.CONTRACT_NAME = event_type
            cls.CONTRACT_VERSION = version

        super().__init_subclass__(**kwargs)

    def __post_init__(self) -> None:
        if not isinstance(self.metadata, EventMetadata):
            raise ContractViolation("metadata must be an EventMetadata")
        if not hasattr(type(self), "EVENT_TYPE"):
            raise EventRegistrationError(
                f"{type(self).__name__} must declare EVENT_TYPE before it can be instantiated"
            )

    # ------------------------------------------------------------------
    # Identity
    # ------------------------------------------------------------------

    @property
    def event_type(self) -> str:
        return type(self).EVENT_TYPE

    @property
    def event_version(self) -> int:
        return type(self).EVENT_VERSION

    @property
    def event_id(self) -> str:
        return self.metadata.event_id

    @property
    def correlation_id(self) -> str:
        return self.metadata.correlation_id

    @property
    def causation_id(self) -> Optional[str]:
        return self.metadata.causation_id

    @property
    def aggregate_id(self) -> str:
        return self.metadata.aggregate_id

    @property
    def aggregate_type(self) -> str:
        return self.metadata.aggregate_type

    # ------------------------------------------------------------------
    # Payload
    # ------------------------------------------------------------------

    def payload(self) -> dict[str, Any]:
        """Return the event's own fields, excluding metadata and envelope keys.

        This is what "the same thing happened" means: two events with different
        identities but identical payloads describe the same occurrence.
        """
        full = self.to_dict()
        return {
            key: value
            for key, value in full.items()
            if key != "metadata" and not key.startswith("_")
        }

    # ------------------------------------------------------------------
    # Derivation
    # ------------------------------------------------------------------

    def derive(
        self: TEvent,
        event_class: type["DomainEvent"],
        *,
        aggregate_id: Optional[str] = None,
        aggregate_type: Optional[str] = None,
        scope: Optional[TenantScope] = None,
        sequence: Optional[int] = None,
        actor: Optional[PrincipalRef] = None,
        attributes: Optional[Mapping[str, Any]] = None,
        **payload: Any,
    ) -> "DomainEvent":
        """Create a new event caused by this one.

        The derived event inherits this event's ``correlation_id`` and records
        this event's id as its ``causation_id``. That is the whole point:
        building a causal chain by hand invites someone to forget a link, and a
        chain with a missing link cannot be traced.

        Aggregate and scope default to this event's, since a caused event
        usually concerns the same thing. Override when it does not.
        """
        metadata = EventMetadata.create(
            aggregate_id=aggregate_id or self.metadata.aggregate_id,
            aggregate_type=aggregate_type or self.metadata.aggregate_type,
            scope=scope or self.metadata.scope,
            correlation_id=self.metadata.correlation_id,
            causation_id=self.metadata.event_id,
            sequence=sequence,
            actor=actor,
            attributes=attributes,
        )
        return event_class(metadata=metadata, **payload)

    def with_metadata(self: TEvent, metadata: EventMetadata) -> TEvent:
        """Return a copy of this event carrying different metadata.

        The payload is unchanged. Used by upcasters and by replay, both of which
        need to restate an existing fact rather than assert a new one.
        """
        return dataclasses.replace(self, metadata=metadata)

    # ------------------------------------------------------------------
    # Comparison
    # ------------------------------------------------------------------

    def same_content_as(self, other: object) -> bool:
        """Whether two events describe the same occurrence.

        Distinct from ``==``. Equality includes metadata, so two events are
        equal only if they are *the same event*. Two events can describe an
        identical occurrence while being different events -- a retry, or the
        same fact observed twice. Deduplication needs this; ordinary comparison
        does not.
        """
        if not isinstance(other, DomainEvent):
            return False
        return self.event_type == other.event_type and self.payload() == other.payload()

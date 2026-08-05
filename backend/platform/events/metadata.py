"""Event metadata: who, when, where, and what caused this.

Every domain event carries exactly one :class:`EventMetadata`. It answers the
questions that are identical for every event, so no event type has to reinvent
them -- and so a consumer can trace causality without knowing anything about
the payload.

Correlation and causation
-------------------------
Two identifiers with distinct jobs, routinely conflated:

``correlation_id``
    Constant across an entire causal chain. Every event produced while handling
    one mission shares it. This is what you filter a log by.

``causation_id``
    The ``event_id`` of the single event that directly caused this one. Null
    only for the first event in a chain. Following these backwards reconstructs
    the exact path, which correlation alone cannot do -- correlation tells you
    *which* chain, causation tells you *where in it*.

Tenant scope is required
------------------------
Constitution I6: every cross-context message carries tenant identity.
``scope`` is therefore mandatory, not optional. An event with no tenant is not a
domain event -- it is a process-internal signal, and those do not belong in this
foundation.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Mapping, Optional

from backend.contracts import (
    Contract,
    ContractViolation,
    PrincipalRef,
    TenantScope,
    freeze_mapping,
)
from backend.platform.identity import is_ulid, monotonic_ulid

__all__ = ["EventMetadata", "new_correlation_id"]


def new_correlation_id() -> str:
    """Mint a correlation id for a new causal chain.

    Monotonic so that chains started in the same millisecond remain orderable,
    which matters when reconstructing "what ran first" during an incident.
    """
    return monotonic_ulid()


@dataclass(frozen=True)
class EventMetadata(Contract):
    """The invariant part of every domain event.

    ``aggregate_id`` and ``aggregate_type`` identify what the event is *about*
    -- the mission, execution, or approval whose state changed. Both are
    required: an event about nothing cannot be routed, replayed in order, or
    reconciled against the thing it describes.

    ``sequence`` is optional because not every aggregate maintains one. Where it
    is present it must be non-negative and is authoritative for ordering within
    that aggregate; timestamps are not, because clocks move.
    """

    CONTRACT_NAME = "cortexprime.events.metadata"

    event_id: str
    correlation_id: str
    aggregate_id: str
    aggregate_type: str
    occurred_at: datetime
    scope: TenantScope
    causation_id: Optional[str] = None
    sequence: Optional[int] = None
    actor: Optional[PrincipalRef] = None
    attributes: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        for label, value in (
            ("event_id", self.event_id),
            ("correlation_id", self.correlation_id),
            ("aggregate_id", self.aggregate_id),
            ("aggregate_type", self.aggregate_type),
        ):
            if not isinstance(value, str) or not value.strip():
                raise ContractViolation(f"{label} must be a non-blank string")

        if not is_ulid(self.event_id):
            raise ContractViolation(
                f"event_id must be a ULID so events sort by creation time; got {self.event_id!r}"
            )

        if self.occurred_at.tzinfo is None:
            raise ContractViolation(
                "occurred_at must be timezone-aware; a naive timestamp cannot be "
                "ordered against events from another process"
            )

        if self.causation_id is not None:
            if not isinstance(self.causation_id, str) or not self.causation_id.strip():
                raise ContractViolation("causation_id must be a non-blank string when present")
            if self.causation_id == self.event_id:
                raise ContractViolation(
                    "an event cannot be its own cause; that is a cycle in the causal graph"
                )

        if self.sequence is not None and (
            not isinstance(self.sequence, int) or self.sequence < 0
        ):
            raise ContractViolation("sequence must be a non-negative integer when present")

        object.__setattr__(self, "attributes", freeze_mapping(self.attributes))

    @classmethod
    def create(
        cls,
        *,
        aggregate_id: str,
        aggregate_type: str,
        scope: TenantScope,
        correlation_id: Optional[str] = None,
        causation_id: Optional[str] = None,
        sequence: Optional[int] = None,
        actor: Optional[PrincipalRef] = None,
        attributes: Optional[Mapping[str, Any]] = None,
        occurred_at: Optional[datetime] = None,
    ) -> "EventMetadata":
        """Build metadata for a new event, generating what is not supplied.

        ``event_id`` is always generated -- accepting one from a caller would
        let two distinct events share an identity. ``correlation_id`` defaults
        to a fresh chain; pass one to join an existing chain.

        This is the only place in the package that reads the clock, which keeps
        every other function pure and testable.
        """
        return cls(
            event_id=monotonic_ulid(),
            correlation_id=correlation_id or new_correlation_id(),
            aggregate_id=aggregate_id,
            aggregate_type=aggregate_type,
            occurred_at=occurred_at or datetime.now(timezone.utc),
            scope=scope,
            causation_id=causation_id,
            sequence=sequence,
            actor=actor,
            attributes=attributes or {},
        )

    @property
    def is_chain_origin(self) -> bool:
        """Whether this event began its causal chain."""
        return self.causation_id is None

    def caused_by(self, cause: "EventMetadata") -> bool:
        """Whether this event was directly caused by ``cause``."""
        return self.causation_id is not None and self.causation_id == cause.event_id

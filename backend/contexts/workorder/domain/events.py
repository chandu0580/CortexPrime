"""WorkOrder lifecycle events.

Built on the platform's :class:`~backend.platform.events.DomainEvent`, so every
one carries identity, causality, and tenant scope without restating them, and so
these events flow through the same registry, serializer, and validator as the
product's own.

The event log is **authoritative**; a WorkOrder's own ``state`` field is a
convenience projection. Where the two disagree, the log wins -- which is only
meaningful if every transition emits exactly one event. A transition with no
event did not happen.

``StateChanged`` is emitted alongside the specific event, not instead of it.
A consumer tracking the machine wants one uniform event; a consumer reacting to
approval wants the specific one. Making the general event a substitute for the
specific one forces every consumer to branch on a string field, which is how a
new state silently goes unhandled.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from backend.contracts.errors import ContractViolation
from backend.platform.events import DomainEvent

__all__ = [
    "WorkOrderDrafted",
    "WorkOrderApproved",
    "WorkOrderBlocked",
    "WorkOrderUnblocked",
    "WorkOrderAssigned",
    "WorkOrderStateChanged",
    "WorkOrderRejected",
    "WorkOrderMerged",
    "WorkOrderClosed",
    "WorkOrderSuperseded",
    "WorkOrderDigestValidated",
    "WorkOrderBlastRadiusExpanded",
    "WorkOrderAssumptionResolved",
    "WorkOrderReprioritised",
    "AGGREGATE_TYPE",
    "ALL_EVENT_TYPES",
]

AGGREGATE_TYPE = "work_order"


def _require_text(label: str, value: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise ContractViolation(f"{label} must be non-blank text")


@dataclass(frozen=True)
class WorkOrderDrafted(DomainEvent):
    """A WorkOrder was composed. Nothing is authorised yet."""

    EVENT_TYPE = "engineering.work_order.drafted"

    work_id: str = ""
    version: int = 1
    intent: str = ""
    created_by: str = ""

    def __post_init__(self) -> None:
        super().__post_init__()
        _require_text("work_id", self.work_id)
        _require_text("intent", self.intent)


@dataclass(frozen=True)
class WorkOrderApproved(DomainEvent):
    """The founder ratified the WorkOrder and the digest was bound.

    ``digest`` travels on the event because it is what the approval *is*. An
    approval event that named only the WorkOrder would leave a consumer unable to
    tell which content was approved.
    """

    EVENT_TYPE = "engineering.work_order.approved"

    work_id: str = ""
    version: int = 1
    digest: str = ""
    digest_algorithm: str = ""
    approved_by: str = ""

    def __post_init__(self) -> None:
        super().__post_init__()
        _require_text("work_id", self.work_id)
        _require_text("digest", self.digest)
        _require_text("approved_by", self.approved_by)


@dataclass(frozen=True)
class WorkOrderStateChanged(DomainEvent):
    """Any transition. Emitted alongside the specific event, never instead."""

    EVENT_TYPE = "engineering.work_order.state_changed"

    work_id: str = ""
    version: int = 1
    from_state: str = ""
    to_state: str = ""

    def __post_init__(self) -> None:
        super().__post_init__()
        _require_text("work_id", self.work_id)
        _require_text("from_state", self.from_state)
        _require_text("to_state", self.to_state)
        if self.from_state == self.to_state:
            raise ContractViolation(
                f"state change from {self.from_state!r} to itself is not a change"
            )


@dataclass(frozen=True)
class WorkOrderBlocked(DomainEvent):
    """Parked on an unmerged dependency."""

    EVENT_TYPE = "engineering.work_order.blocked"

    work_id: str = ""
    version: int = 1
    blocking_dependencies: tuple = ()

    def __post_init__(self) -> None:
        super().__post_init__()
        _require_text("work_id", self.work_id)
        if not self.blocking_dependencies:
            raise ContractViolation(
                "a blocked WorkOrder must name what blocks it; a block with no cause "
                "cannot be cleared by anything"
            )


@dataclass(frozen=True)
class WorkOrderUnblocked(DomainEvent):
    EVENT_TYPE = "engineering.work_order.unblocked"

    work_id: str = ""
    version: int = 1

    def __post_init__(self) -> None:
        super().__post_init__()
        _require_text("work_id", self.work_id)


@dataclass(frozen=True)
class WorkOrderAssigned(DomainEvent):
    """A blast-radius lock was acquired and work may begin."""

    EVENT_TYPE = "engineering.work_order.assigned"

    work_id: str = ""
    version: int = 1
    allowed_patterns: tuple = ()

    def __post_init__(self) -> None:
        super().__post_init__()
        _require_text("work_id", self.work_id)
        if not self.allowed_patterns:
            raise ContractViolation("an assigned WorkOrder must carry its allowed patterns")


@dataclass(frozen=True)
class WorkOrderRejected(DomainEvent):
    """Closed with a typed verdict. A successful outcome."""

    EVENT_TYPE = "engineering.work_order.rejected"

    work_id: str = ""
    version: int = 1
    rejection_type: str = ""
    detail: str = ""
    raised_by: str = ""

    def __post_init__(self) -> None:
        super().__post_init__()
        _require_text("work_id", self.work_id)
        _require_text("rejection_type", self.rejection_type)
        _require_text("detail", self.detail)


@dataclass(frozen=True)
class WorkOrderMerged(DomainEvent):
    """Landed on the trunk. Emitted only for a human-performed merge."""

    EVENT_TYPE = "engineering.work_order.merged"

    work_id: str = ""
    version: int = 1
    commit: str = ""
    merged_by: str = ""

    def __post_init__(self) -> None:
        super().__post_init__()
        _require_text("work_id", self.work_id)
        _require_text("commit", self.commit)
        _require_text("merged_by", self.merged_by)


@dataclass(frozen=True)
class WorkOrderClosed(DomainEvent):
    """Terminal success. The blast-radius lock is released here."""

    EVENT_TYPE = "engineering.work_order.closed"

    work_id: str = ""
    version: int = 1

    def __post_init__(self) -> None:
        super().__post_init__()
        _require_text("work_id", self.work_id)


@dataclass(frozen=True)
class WorkOrderSuperseded(DomainEvent):
    EVENT_TYPE = "engineering.work_order.superseded"

    work_id: str = ""
    version: int = 1
    superseded_by: str = ""

    def __post_init__(self) -> None:
        super().__post_init__()
        _require_text("work_id", self.work_id)
        _require_text("superseded_by", self.superseded_by)
        if self.work_id == self.superseded_by:
            raise ContractViolation("a WorkOrder cannot supersede itself")


@dataclass(frozen=True)
class WorkOrderDigestValidated(DomainEvent):
    """A digest check ran, and whether it held.

    Emitted on failure as well as success. A verification that only records its
    successes cannot answer the one question an investigation asks -- when did
    this last hold?
    """

    EVENT_TYPE = "engineering.work_order.digest_validated"

    work_id: str = ""
    version: int = 1
    expected: str = ""
    observed: str = ""
    valid: bool = False

    def __post_init__(self) -> None:
        super().__post_init__()
        _require_text("work_id", self.work_id)
        _require_text("expected", self.expected)
        _require_text("observed", self.observed)
        if not isinstance(self.valid, bool):
            raise ContractViolation("valid must be a bool")
        if self.valid != (self.expected == self.observed):
            raise ContractViolation(
                "valid contradicts the digests it reports; one of them is wrong"
            )


@dataclass(frozen=True)
class WorkOrderBlastRadiusExpanded(DomainEvent):
    """Scope widened and re-approved as a new version."""

    EVENT_TYPE = "engineering.work_order.blast_radius_expanded"

    work_id: str = ""
    from_version: int = 1
    to_version: int = 2
    added_patterns: tuple = ()
    new_digest: str = ""

    def __post_init__(self) -> None:
        super().__post_init__()
        _require_text("work_id", self.work_id)
        _require_text("new_digest", self.new_digest)
        if self.to_version <= self.from_version:
            raise ContractViolation("an expansion must increment the version")


@dataclass(frozen=True)
class WorkOrderAssumptionResolved(DomainEvent):
    """An assumption was checked. The most consequential event in the set.

    A ``contradicted`` resolution is the signal that the specification rested on
    a false premise -- the failure this whole model exists to catch before code
    is written.
    """

    EVENT_TYPE = "engineering.work_order.assumption_resolved"

    work_id: str = ""
    version: int = 1
    assumption_id: str = ""
    resolution: str = ""
    evidence: str = ""

    def __post_init__(self) -> None:
        super().__post_init__()
        _require_text("work_id", self.work_id)
        _require_text("assumption_id", self.assumption_id)
        _require_text("resolution", self.resolution)
        _require_text("evidence", self.evidence)


@dataclass(frozen=True)
class WorkOrderReprioritised(DomainEvent):
    """Scheduling order changed. Does not touch the digest."""

    EVENT_TYPE = "engineering.work_order.reprioritised"

    work_id: str = ""
    version: int = 1
    from_priority: str = ""
    to_priority: str = ""

    def __post_init__(self) -> None:
        super().__post_init__()
        _require_text("work_id", self.work_id)


ALL_EVENT_TYPES = (
    WorkOrderDrafted,
    WorkOrderApproved,
    WorkOrderBlocked,
    WorkOrderUnblocked,
    WorkOrderAssigned,
    WorkOrderStateChanged,
    WorkOrderRejected,
    WorkOrderMerged,
    WorkOrderClosed,
    WorkOrderSuperseded,
    WorkOrderDigestValidated,
    WorkOrderBlastRadiusExpanded,
    WorkOrderAssumptionResolved,
    WorkOrderReprioritised,
)

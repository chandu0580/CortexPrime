"""Engineering Runtime lifecycle events.

Six events, not eleven. The brief lists eleven; five of them already exist in the
WorkOrder context and are **not** redefined here:

===========================  ==================================================
Requested                    Already emitted, by the WorkOrder context
===========================  ==================================================
``WorkOrderCreated``         ``engineering.work_order.drafted``
``WorkOrderAssigned``        ``engineering.work_order.assigned``
``WorkOrderRejected``        ``engineering.work_order.rejected``
``WorkOrderMerged``          ``engineering.work_order.merged``
``WorkOrderSuperseded``      ``engineering.work_order.superseded``
===========================  ==================================================

Defining a second event for a fact that already has one is the mistake that
looks like completeness. Two event types meaning the same thing forces every
consumer to subscribe to both and handle the case where only one arrives; the
day they disagree, nobody can say which is authoritative. The runtime
**re-publishes** the WorkOrder context's events through its dispatcher rather
than restating them.

What is genuinely new is the six phase-boundary events below. They mark when the
runtime *asked a collaborator to do something* and when it *heard back* -- facts
no aggregate can know, because they concern the orchestration rather than the
artifact.

``ImplementationStarted`` and the ``StateChanged`` for the same transition are
different assertions: one says the machine moved, the other says work was handed
to an implementer. They coincide today and will not once dispatch is queued.
"""

from __future__ import annotations

from dataclasses import dataclass

from backend.contracts.errors import ContractViolation
from backend.platform.events import DomainEvent

__all__ = [
    "AGGREGATE_TYPE",
    "ImplementationStarted",
    "ImplementationCompleted",
    "ReviewRequested",
    "ReviewCompleted",
    "VerificationRequested",
    "VerificationCompleted",
    "RUNTIME_EVENT_TYPES",
    "WORK_ORDER_EVENT_ALIASES",
]

AGGREGATE_TYPE = "work_order"

#: The five events the brief names that already exist, and what emits them.
#: Kept as data so a consumer can resolve a requested name to the real one
#: rather than discovering the alias in a docstring.
WORK_ORDER_EVENT_ALIASES = {
    "WorkOrderCreated": "engineering.work_order.drafted",
    "WorkOrderAssigned": "engineering.work_order.assigned",
    "WorkOrderRejected": "engineering.work_order.rejected",
    "WorkOrderMerged": "engineering.work_order.merged",
    "WorkOrderSuperseded": "engineering.work_order.superseded",
}


def _require_text(label: str, value: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise ContractViolation(f"{label} must be non-blank text")


@dataclass(frozen=True)
class ImplementationStarted(DomainEvent):
    """Work was handed to an implementer, with a context bundle."""

    EVENT_TYPE = "engineering.runtime.implementation_started"

    work_id: str = ""
    version: int = 1
    round: int = 1
    context_bundle: str = ""

    def __post_init__(self) -> None:
        super().__post_init__()
        _require_text("work_id", self.work_id)
        if self.round < 1:
            raise ContractViolation("round starts at 1")


@dataclass(frozen=True)
class ImplementationCompleted(DomainEvent):
    """An implementer submitted a round for review."""

    EVENT_TYPE = "engineering.runtime.implementation_completed"

    work_id: str = ""
    version: int = 1
    round: int = 1
    claims: int = 0

    def __post_init__(self) -> None:
        super().__post_init__()
        _require_text("work_id", self.work_id)


@dataclass(frozen=True)
class ReviewRequested(DomainEvent):
    """Review was asked for, naming every lens.

    The lenses travel on the event because a missing lens is not a passing lens,
    and the only way to notice one never reported is to know it was asked.
    """

    EVENT_TYPE = "engineering.runtime.review_requested"

    work_id: str = ""
    version: int = 1
    round: int = 1
    lenses: tuple = ()

    def __post_init__(self) -> None:
        super().__post_init__()
        _require_text("work_id", self.work_id)
        if not self.lenses:
            raise ContractViolation(
                "a review request must name its lenses; a request for 'review' with no "
                "lens cannot be shown to have covered anything"
            )


@dataclass(frozen=True)
class ReviewCompleted(DomainEvent):
    """Every requested lens reported."""

    EVENT_TYPE = "engineering.runtime.review_completed"

    work_id: str = ""
    version: int = 1
    round: int = 1
    lenses_reported: tuple = ()
    blocking_findings: int = 0
    passed: bool = False

    def __post_init__(self) -> None:
        super().__post_init__()
        _require_text("work_id", self.work_id)
        if not isinstance(self.passed, bool):
            raise ContractViolation("passed must be a bool")
        if self.passed and self.blocking_findings:
            raise ContractViolation(
                "a review cannot pass with blocking findings outstanding"
            )


@dataclass(frozen=True)
class VerificationRequested(DomainEvent):
    EVENT_TYPE = "engineering.runtime.verification_requested"

    work_id: str = ""
    version: int = 1
    attempt: int = 1

    def __post_init__(self) -> None:
        super().__post_init__()
        _require_text("work_id", self.work_id)
        if self.attempt < 1:
            raise ContractViolation("attempt starts at 1")


@dataclass(frozen=True)
class VerificationCompleted(DomainEvent):
    """A verification attempt finished, whether or not it succeeded.

    Emitted on failure too. A record that only captures successes cannot answer
    the question an investigation asks -- when did this last hold?
    """

    EVENT_TYPE = "engineering.runtime.verification_completed"

    work_id: str = ""
    version: int = 1
    attempt: int = 1
    status: str = ""
    reproduced: int = 0
    contradicted: int = 0
    unreproducible: int = 0

    def __post_init__(self) -> None:
        super().__post_init__()
        _require_text("work_id", self.work_id)
        _require_text("status", self.status)


RUNTIME_EVENT_TYPES = (
    ImplementationStarted,
    ImplementationCompleted,
    ReviewRequested,
    ReviewCompleted,
    VerificationRequested,
    VerificationCompleted,
)

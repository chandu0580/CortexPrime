"""Commands and queries.

Each command is a frozen value naming one intent. Objects rather than long
parameter lists, because a command is the thing an orchestrator queues, logs,
retries, and eventually replays -- and none of that works on an argument list.

Commands validate their own *shape* and nothing else. Whether a transition is
legal, whether references resolve, whether a blast radius conflicts: all of that
needs the aggregate or the repository, and belongs in the service. A command
that could decide those things would be a second place for the rules to live.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Iterable, Optional, Sequence

from backend.contracts.errors import ContractViolation
from backend.contexts.workorder.domain.assumption import AssumptionResolution
from backend.contexts.workorder.domain.blast_radius import BlastRadius
from backend.contexts.workorder.domain.factory import AssumptionSpec
from backend.contexts.workorder.domain.rejection import RejectionType
from backend.contexts.workorder.domain.states import WorkOrderState
from backend.contexts.workorder.domain.work_order import Priority

__all__ = [
    "DraftWorkOrder",
    "ApproveWorkOrder",
    "TransitionWorkOrder",
    "RejectWorkOrder",
    "ResolveAssumption",
    "ExpandBlastRadius",
    "Reprioritise",
    "SupersedeWorkOrder",
    "GetWorkOrder",
    "ListWorkOrders",
    "CheckBlastRadiusConflicts",
]


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise ContractViolation(message)


# ----------------------------------------------------------------------
# Commands
# ----------------------------------------------------------------------


@dataclass(frozen=True)
class DraftWorkOrder:
    intent: str
    acceptance_criteria: tuple
    blast_radius: BlastRadius
    definition_of_done: tuple = ()
    adr_references: tuple = ()
    evidence: tuple = ()
    constraints: tuple = ()
    assumptions: tuple = ()
    extra_rejection_grounds: tuple = ()
    dependencies: tuple = ()
    priority: Priority = Priority.P1
    created_by: str = "architect"
    supersedes: Optional[str] = None

    def __post_init__(self) -> None:
        _require(bool(self.intent and self.intent.strip()), "intent is required")
        _require(bool(self.acceptance_criteria), "at least one acceptance criterion is required")
        _require(
            isinstance(self.blast_radius, BlastRadius), "blast_radius must be a BlastRadius"
        )
        for spec in self.assumptions:
            _require(
                isinstance(spec, AssumptionSpec),
                "assumptions must be AssumptionSpec values so each carries its "
                "rejection ground",
            )


@dataclass(frozen=True)
class ApproveWorkOrder:
    work_id: str
    approved_by: str

    def __post_init__(self) -> None:
        _require(bool(self.work_id), "work_id is required")
        _require(
            bool(self.approved_by and self.approved_by.strip()),
            "approved_by is required; approval is an act by a named person",
        )


@dataclass(frozen=True)
class TransitionWorkOrder:
    work_id: str
    to_state: WorkOrderState
    actor: str

    def __post_init__(self) -> None:
        _require(bool(self.work_id), "work_id is required")
        _require(isinstance(self.to_state, WorkOrderState), "to_state must be a WorkOrderState")
        _require(bool(self.actor and self.actor.strip()), "actor is required")


@dataclass(frozen=True)
class RejectWorkOrder:
    work_id: str
    rejection_type: RejectionType
    detail: str
    raised_by: str

    def __post_init__(self) -> None:
        _require(bool(self.work_id), "work_id is required")
        _require(
            isinstance(self.rejection_type, RejectionType),
            "rejection_type must be a RejectionType",
        )
        _require(
            bool(self.detail and self.detail.strip()),
            "a rejection must cite its evidence; a rejection without it is refusal to work",
        )
        _require(bool(self.raised_by and self.raised_by.strip()), "raised_by is required")


@dataclass(frozen=True)
class ResolveAssumption:
    work_id: str
    assumption_id: str
    resolution: AssumptionResolution
    evidence: str
    resolved_by: str

    def __post_init__(self) -> None:
        _require(bool(self.work_id), "work_id is required")
        _require(bool(self.assumption_id), "assumption_id is required")
        _require(
            isinstance(self.resolution, AssumptionResolution),
            "resolution must be an AssumptionResolution",
        )
        _require(
            bool(self.evidence and self.evidence.strip()),
            "every resolution must cite what was checked, including 'unverifiable'",
        )


@dataclass(frozen=True)
class ExpandBlastRadius:
    work_id: str
    radius: BlastRadius
    justification: str
    requested_by: str

    def __post_init__(self) -> None:
        _require(bool(self.work_id), "work_id is required")
        _require(isinstance(self.radius, BlastRadius), "radius must be a BlastRadius")
        _require(
            bool(self.justification and self.justification.strip()),
            "an expansion must say why the original radius was insufficient",
        )


@dataclass(frozen=True)
class Reprioritise:
    work_id: str
    priority: Priority
    actor: str

    def __post_init__(self) -> None:
        _require(bool(self.work_id), "work_id is required")
        _require(isinstance(self.priority, Priority), "priority must be a Priority")


@dataclass(frozen=True)
class SupersedeWorkOrder:
    work_id: str
    successor_id: str
    actor: str

    def __post_init__(self) -> None:
        _require(bool(self.work_id), "work_id is required")
        _require(bool(self.successor_id), "successor_id is required")
        _require(
            self.work_id != self.successor_id, "a WorkOrder cannot supersede itself"
        )


# ----------------------------------------------------------------------
# Queries
# ----------------------------------------------------------------------


@dataclass(frozen=True)
class GetWorkOrder:
    work_id: str
    version: Optional[int] = None


@dataclass(frozen=True)
class ListWorkOrders:
    state: Optional[WorkOrderState] = None
    active_only: bool = False


@dataclass(frozen=True)
class CheckBlastRadiusConflicts:
    radius: BlastRadius
    exclude_work_id: Optional[str] = None

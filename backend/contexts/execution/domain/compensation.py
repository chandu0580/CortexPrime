"""Compensation as a lifecycle, not a flag.

Phase 2 settled that compensation nodes are not ordinary forward work: they are
reachable only when something failed, so projecting them as normal dependencies
would leave every successful run permanently outstanding. That stays true here.

What Phase 3.1 adds is the ability to say where a compensation has *got to*.
``NodeState.COMPENSATED`` records that a change was walked back. It cannot record
that a walk-back was requested and is still running, or -- much more importantly
-- that it was attempted and **failed**.

A failed compensation is the worst state this runtime can be in: a change was
applied, the attempt to undo it did not work, and the system is now further from
where it started than when it began. It needs a name of its own so it can be
escalated rather than retried into the ground.

Dispatch of the compensating action itself needs a worker, so it stays deferred.
This module models the lifecycle; something later performs it.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from datetime import datetime, timezone
from enum import Enum
from typing import Optional

from backend.contracts.errors import ContractViolation
from backend.contexts.execution.domain.failure import FailureRecord

__all__ = ["CompensationState", "CompensationRecord", "COMPENSATION_TRANSITIONS"]


class CompensationState(str, Enum):
    """How far a walk-back has got."""

    REQUESTED = "requested"
    """Somebody decided the change should be undone. Nothing has run."""

    RUNNING = "running"
    """The compensating action is being performed."""

    COMPLETED = "completed"
    """The change was undone and that is known, not assumed."""

    FAILED = "failed"
    """The walk-back was attempted and did not work. The original change is
    still out there. This must escalate; it must not quietly retry forever."""

    REQUIRES_INTERVENTION = "requires_intervention"
    """Nothing automatic can safely undo this. A human owns it now."""

    @property
    def is_terminal(self) -> bool:
        return self in {
            CompensationState.COMPLETED,
            CompensationState.FAILED,
            CompensationState.REQUIRES_INTERVENTION,
        }

    @property
    def left_the_change_in_place(self) -> bool:
        """Whether the original change is believed to still be applied.

        The question an operator actually asks during an incident.
        """
        return self in {
            CompensationState.REQUESTED,
            CompensationState.RUNNING,
            CompensationState.FAILED,
            CompensationState.REQUIRES_INTERVENTION,
        }


COMPENSATION_TRANSITIONS = {
    CompensationState.REQUESTED: (
        CompensationState.RUNNING,
        CompensationState.REQUIRES_INTERVENTION,
    ),
    CompensationState.RUNNING: (
        CompensationState.COMPLETED,
        CompensationState.FAILED,
        CompensationState.REQUIRES_INTERVENTION,
    ),
    # A failed walk-back may be escalated, but never silently re-run: the change
    # is still applied and a second failing attempt buys nothing.
    CompensationState.FAILED: (CompensationState.REQUIRES_INTERVENTION,),
    CompensationState.COMPLETED: (),
    CompensationState.REQUIRES_INTERVENTION: (),
}


@dataclass(frozen=True)
class CompensationRecord:
    """One attempt to walk back one node's change."""

    node_id: str
    compensating_node: Optional[str]
    state: CompensationState
    reason: str
    requested_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    started_at: Optional[datetime] = None
    ended_at: Optional[datetime] = None
    failure: Optional[FailureRecord] = None

    def __post_init__(self) -> None:
        if not isinstance(self.state, CompensationState):
            raise ContractViolation("state must be a CompensationState")
        if not self.reason.strip():
            raise ContractViolation(
                "compensation must say why it was requested; an unexplained "
                "walk-back of a production change is not reviewable"
            )
        if self.state is CompensationState.FAILED and self.failure is None:
            raise ContractViolation(
                "a failed compensation must carry its failure; the change is "
                "still applied and whoever is paged needs to know what went wrong"
            )

    def _moved(self, target: CompensationState, **changes) -> "CompensationRecord":
        permitted = COMPENSATION_TRANSITIONS[self.state]
        if target not in permitted:
            raise ContractViolation(
                f"compensation of {self.node_id!r} cannot move "
                f"{self.state.value} -> {target.value}; permitted: "
                + (", ".join(s.value for s in permitted) or "nothing")
            )
        return replace(self, state=target, **changes)

    def started(self, *, now: Optional[datetime] = None) -> "CompensationRecord":
        return self._moved(
            CompensationState.RUNNING, started_at=now or datetime.now(timezone.utc)
        )

    def completed(self, *, now: Optional[datetime] = None) -> "CompensationRecord":
        return self._moved(
            CompensationState.COMPLETED, ended_at=now or datetime.now(timezone.utc)
        )

    def failed(
        self, failure: FailureRecord, *, now: Optional[datetime] = None
    ) -> "CompensationRecord":
        return self._moved(
            CompensationState.FAILED,
            failure=failure,
            ended_at=now or datetime.now(timezone.utc),
        )

    def escalated(self, reason: str, *, now: Optional[datetime] = None) -> "CompensationRecord":
        return self._moved(
            CompensationState.REQUIRES_INTERVENTION,
            reason=reason,
            ended_at=now or datetime.now(timezone.utc),
        )

    @classmethod
    def requested(
        cls,
        node_id: str,
        *,
        reason: str,
        compensating_node: Optional[str] = None,
        now: Optional[datetime] = None,
    ) -> "CompensationRecord":
        return cls(
            node_id=node_id,
            compensating_node=compensating_node,
            state=CompensationState.REQUESTED,
            reason=reason,
            requested_at=now or datetime.now(timezone.utc),
        )

    def to_dict(self) -> dict:
        return {
            "node_id": self.node_id,
            "compensating_node": self.compensating_node,
            "state": self.state.value,
            "reason": self.reason,
            "requested_at": self.requested_at.isoformat(),
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "ended_at": self.ended_at.isoformat() if self.ended_at else None,
            "failure": self.failure.to_dict() if self.failure else None,
        }

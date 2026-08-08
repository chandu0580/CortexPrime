"""Read-side of the Engineering Runtime.

Separate from the runtime service so a caller that only reads cannot accidentally
hold something able to transition. The runtime is passed in rather than
subclassed -- a query object inheriting transition methods would defeat the
separation it exists to create.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional

from backend.contexts.engineering.commands import (
    GetEventHistory,
    GetLifecycleCapability,
    GetRuntimeState,
    ReplayWorkOrder,
)
from backend.contexts.engineering.ports import WorkOrderPhase
from backend.contexts.engineering.state_executor import TransitionValidator

__all__ = ["RuntimeState", "EngineeringRuntimeQueries"]


@dataclass(frozen=True)
class RuntimeState:
    """Where a WorkOrder is and where it could go next."""

    work_id: str
    version: int
    phase: str
    digest: Optional[str]
    legal_next: tuple
    reachable_next: tuple
    blocked_next: tuple
    events_recorded: int
    round: int
    attempt: int


class EngineeringRuntimeQueries:
    def __init__(self, runtime: Any) -> None:
        self._runtime = runtime

    def state(self, context: Any, query: GetRuntimeState) -> RuntimeState:
        """Current phase, plus what the machine and the wiring each permit next.

        ``legal_next`` and ``reachable_next`` differ whenever a collaborator is
        unwired. Reporting only one would hide the distinction between "the
        Constitution forbids this" and "nothing is listening yet" -- different
        problems with different fixes.
        """
        snapshot = self._runtime.snapshot(context, query.work_id)
        lifecycle = self._runtime.lifecycle

        legal = tuple(
            sorted(
                phase.value
                for phase in WorkOrderPhase
                if TransitionValidator.is_legal(snapshot.phase, phase)
            )
        )
        reachable = tuple(sorted(p for p in legal if lifecycle.can_enter(WorkOrderPhase(p))))

        return RuntimeState(
            work_id=snapshot.work_id,
            version=snapshot.version,
            phase=snapshot.phase.value,
            digest=snapshot.digest,
            legal_next=legal,
            reachable_next=reachable,
            blocked_next=tuple(sorted(set(legal) - set(reachable))),
            events_recorded=len(self._runtime.log.for_work_order(snapshot.work_id)),
            round=self._runtime.round_number(snapshot.work_id),
            attempt=self._runtime.attempt_number(snapshot.work_id),
        )

    def history(self, query: GetEventHistory) -> tuple:
        if query.work_id:
            return self._runtime.log.for_work_order(query.work_id)
        return self._runtime.log.since(query.since)

    def capability(self, query: GetLifecycleCapability) -> dict:
        lifecycle = self._runtime.lifecycle
        return {
            "wired": list(lifecycle.collaborators.wired),
            "missing": list(lifecycle.collaborators.missing),
            "reachable_phases": list(lifecycle.reachable_phases()),
        }

    def replay(self, query: ReplayWorkOrder) -> tuple:
        return self._runtime.replay(query.work_id)

    def integrity(self) -> tuple:
        """Defects in the event log's ordering. Empty means intact."""
        return self._runtime.log.verify()

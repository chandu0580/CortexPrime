"""Replay: reconstruct what the state *was*, without doing anything again.

The guarantee
---------------
Replay never invokes a worker, never calls a connector, never touches an
external system, and never writes to the repository. It reads recorded history
and folds it into a projection. That is the entire contract, and it is enforced
structurally rather than by convention: this module is handed events and returns
a value. It holds no repository, no worker pool, and no queue, so there is
nothing here for it to call even if the code wanted to.

That matters more here than anywhere else in the codebase. The single most
dangerous thing a durable-execution runtime can do is treat "replay the history"
as "run the operations again" -- that is how an incident investigation deletes a
production database for a second time.

What replay is for
--------------------
Answering "what did the runtime believe, and when did it start believing it".
Debugging, audit, incident reconstruction, and later the deterministic input to
diagnosis. It reconstructs *orchestration* state only. It cannot tell you what
the external world did; only the recorded outcomes can, and where those say
UNKNOWN, replay faithfully reproduces the not-knowing rather than resolving it.

Why a projection and not the aggregate
----------------------------------------
Folding events into a live ``Execution`` would give the caller an object with
``assign`` and ``record_result`` on it -- methods that mutate a run. A
projection has no such methods. What you get back from replay cannot be driven.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Mapping, Optional, Sequence

from backend.contracts.errors import ContractViolation

__all__ = ["ReplayFrame", "ReplayedExecution", "ExecutionReplayer"]


# Event type -> the state the run was in once it had happened. Derived from the
# recorded facts; replay never guesses a state that no event supports.
_STATE_AFTER = {
    "execution.runtime.started": "running",
    "execution.runtime.paused": "paused",
    "execution.runtime.resumed": "running",
    "execution.runtime.completed": "completed",
    "execution.runtime.failed": "failed",
    "execution.runtime.cancelled": "cancelled",
    "execution.runtime.timed_out": "timed_out",
}

_TERMINAL = {"completed", "failed", "cancelled", "timed_out"}


@dataclass(frozen=True)
class ReplayFrame:
    """The run as it stood immediately after one recorded event."""

    sequence: int
    event_type: str
    occurred_at: Optional[datetime]
    state: str
    event_id: Optional[str] = None
    correlation_id: Optional[str] = None
    causation_id: Optional[str] = None
    detail: Mapping[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "sequence": self.sequence,
            "event_type": self.event_type,
            "occurred_at": self.occurred_at.isoformat() if self.occurred_at else None,
            "state": self.state,
            "event_id": self.event_id,
            "correlation_id": self.correlation_id,
            "causation_id": self.causation_id,
            "detail": dict(self.detail),
        }


@dataclass(frozen=True)
class ReplayedExecution:
    """The reconstruction. Deliberately inert -- nothing here can be driven."""

    execution_id: str
    workflow_id: Optional[str]
    workflow_digest: Optional[str]
    mission_id: Optional[str]
    final_state: str
    frames: tuple = ()
    checkpoints: tuple = ()
    retries: tuple = ()
    unresolved: bool = False
    causal_gaps: tuple = ()

    @property
    def event_count(self) -> int:
        return len(self.frames)

    @property
    def reached_a_terminal_state(self) -> bool:
        return self.final_state in _TERMINAL

    def state_at(self, sequence: int) -> str:
        """What the run's state was after the given event."""
        state = "pending"
        for frame in self.frames:
            if frame.sequence > sequence:
                break
            state = frame.state
        return state

    def to_dict(self) -> dict:
        return {
            "execution_id": self.execution_id,
            "workflow_id": self.workflow_id,
            "workflow_digest": self.workflow_digest,
            "mission_id": self.mission_id,
            "final_state": self.final_state,
            "event_count": self.event_count,
            "reached_terminal_state": self.reached_a_terminal_state,
            "unresolved": self.unresolved,
            "causal_gaps": list(self.causal_gaps),
            "checkpoints": list(self.checkpoints),
            "retries": [dict(r) for r in self.retries],
            "frames": [f.to_dict() for f in self.frames],
        }


class ExecutionReplayer:
    """Folds recorded execution events into a projection. Nothing else.

    Holds no repository, no worker pool, and no queue -- by construction, not by
    discipline. There is nothing here to call.
    """

    def replay(self, events: Sequence[Any]) -> ReplayedExecution:
        """Reconstruct the run from its history.

        Events are folded in the order given. Causal order is *checked* rather
        than imposed: where an event names a causation that has not been seen,
        that is reported as a gap instead of being silently reordered, because
        silently reordering history is how a replay comes to disagree with what
        actually happened.
        """
        if not events:
            raise ContractViolation(
                "replaying nothing produces nothing; an execution with no recorded "
                "history cannot be reconstructed, and returning an empty run would "
                "look like a run that did nothing rather than one nobody recorded"
            )

        state = "pending"
        frames: list = []
        checkpoints: list = []
        retries: list = []
        seen_ids: set = set()
        gaps: list = []
        execution_id = ""
        workflow_id = workflow_digest = mission_id = None

        for index, event in enumerate(events, start=1):
            event_type = getattr(type(event), "EVENT_TYPE", None) or getattr(
                event, "event_type", "unknown"
            )
            payload = event.to_dict() if hasattr(event, "to_dict") else {}

            execution_id = execution_id or payload.get("execution_id") or getattr(
                event, "aggregate_id", ""
            )
            workflow_id = workflow_id or payload.get("workflow_id")
            workflow_digest = workflow_digest or payload.get("workflow_digest")
            mission_id = mission_id or payload.get("mission_id")

            event_id = getattr(event, "event_id", None)
            causation_id = getattr(event, "causation_id", None)
            if causation_id and causation_id not in seen_ids:
                # Reported, never repaired. A replay that quietly reorders is a
                # replay that no longer reconstructs what happened.
                gaps.append(
                    {
                        "sequence": index,
                        "event_type": event_type,
                        "missing_causation": causation_id,
                    }
                )
            if event_id:
                seen_ids.add(event_id)

            state = _STATE_AFTER.get(event_type, state)

            if event_type == "execution.runtime.checkpoint_created":
                checkpoints.append(
                    {
                        "sequence": index,
                        "label": payload.get("label"),
                        "checkpoint_id": payload.get("checkpoint_id"),
                    }
                )
            elif event_type == "execution.runtime.retried":
                retries.append({"sequence": index, **payload})

            frames.append(
                ReplayFrame(
                    sequence=index,
                    event_type=event_type,
                    occurred_at=getattr(event, "occurred_at", None),
                    state=state,
                    event_id=event_id,
                    correlation_id=getattr(event, "correlation_id", None),
                    causation_id=causation_id,
                    detail=payload,
                )
            )

        return ReplayedExecution(
            execution_id=execution_id or "unknown",
            workflow_id=workflow_id,
            workflow_digest=workflow_digest,
            mission_id=mission_id,
            final_state=state,
            frames=tuple(frames),
            checkpoints=tuple(checkpoints),
            retries=tuple(retries),
            # A history that never reaches a terminal state is a run that was
            # interrupted. Saying so is the point: it is the flag that a
            # recovery decision is owed.
            unresolved=state not in _TERMINAL,
            causal_gaps=tuple(gaps),
        )

"""Failures raised by the Mission Runtime context.

Every one is a refusal. A mission never moves through a transition nobody
authorised, never completes without its execution having been verified, and
never loses the record of why it moved.

The refusals are shaped by what Mission Runtime *is*: an orchestrator that owns
lifecycle and performs no work. So every failure here is a failure to govern a
transition -- never a failure to execute, plan, or reason, because this context
does none of those.
"""

from __future__ import annotations

from typing import Sequence

from backend.contracts.errors import ContractViolation

__all__ = [
    "MissionError",
    "InvalidIdentifier",
    "IllegalStatusTransition",
    "IllegalExecutionTransition",
    "MissionTerminal",
    "MissionArchived",
    "VerificationNotReached",
    "PreconditionsUnmet",
    "NoPlanRecorded",
    "NoOpenExecution",
    "ExecutionAlreadyOpen",
    "UnknownCheckpoint",
    "TimelineOutOfOrder",
    "TransitionRefused",
    "DigestMismatch",
    "DigestNotComputed",
    "MissionNotFound",
    "DuplicateMission",
]


class MissionError(ContractViolation):
    """Base for every refusal raised by this context."""


class InvalidIdentifier(MissionError):
    def __init__(self, kind: str, value: object, reason: str) -> None:
        super().__init__(f"{kind} cannot be {value!r}: {reason}")
        self.kind = kind
        self.value = value
        self.reason = reason


class IllegalStatusTransition(MissionError):
    """A move the operational lifecycle does not permit.

    Carries the permitted set, because the useful question after a refusal is
    never "was that legal" but "what may I do instead".
    """

    def __init__(self, *, mission_id: str, source: str, target: str, permitted: Sequence[str]) -> None:
        allowed = ", ".join(sorted(permitted)) or "(nothing -- this state is terminal)"
        super().__init__(
            f"mission {mission_id} cannot move {source} -> {target}; "
            f"{source} may only move to: {allowed}"
        )
        self.mission_id = mission_id
        self.source = source
        self.target = target
        self.permitted = tuple(permitted)


class IllegalExecutionTransition(MissionError):
    """A move Constitution S4 does not permit.

    Raised by the published ``MissionTransition`` contract, re-raised here with
    the mission named. The legality table is not this context's to redefine.
    """

    def __init__(self, *, mission_id: str, source: str, target: str, detail: str = "") -> None:
        suffix = f" ({detail})" if detail else ""
        super().__init__(
            f"mission {mission_id}: Constitution S4 forbids the execution "
            f"transition {source} -> {target}{suffix}"
        )
        self.mission_id = mission_id
        self.source = source
        self.target = target


class MissionTerminal(MissionError):
    """The mission has reached an outcome and may not be driven further."""

    def __init__(self, *, mission_id: str, status: str, operation: str) -> None:
        super().__init__(
            f"mission {mission_id} is {status}; {operation} would reopen an outcome "
            "that has already been reported"
        )
        self.mission_id = mission_id
        self.status = status
        self.operation = operation


class MissionArchived(MissionError):
    """The mission is sealed.

    Stricter than terminal. An archived mission carries a digest over its whole
    timeline; changing it afterwards would make the digest a statement about a
    record that no longer exists.
    """

    def __init__(self, *, mission_id: str, operation: str) -> None:
        super().__init__(
            f"mission {mission_id} is archived; {operation} would change a record "
            "whose digest has already been published"
        )
        self.mission_id = mission_id
        self.operation = operation


class VerificationNotReached(MissionError):
    """A mission cannot complete on an execution that was never verified.

    Constitution S4: ``EXECUTING`` never reaches ``CONCLUDED`` directly. This is
    the operational half of the same rule -- a mission reported complete while
    its execution sits in ``EXECUTING`` would present unverified work as
    finished, which is the single failure this gate exists to prevent.
    """

    def __init__(self, *, mission_id: str, execution_state: str) -> None:
        super().__init__(
            f"mission {mission_id} cannot complete: its execution is "
            f"{execution_state!r}, not 'concluded'. Constitution S4 requires "
            "verification before an execution concludes, and a mission reported "
            "complete over unverified work is the failure that rule exists to stop"
        )
        self.mission_id = mission_id
        self.execution_state = execution_state


class PreconditionsUnmet(MissionError):
    """A mission may not be declared ready while a precondition is outstanding."""

    def __init__(self, *, mission_id: str, outstanding: Sequence[str]) -> None:
        listed = ", ".join(sorted(outstanding)[:5])
        more = f" (+{len(outstanding) - 5} more)" if len(outstanding) > 5 else ""
        super().__init__(
            f"mission {mission_id} has {len(outstanding)} unmet precondition(s): "
            f"{listed}{more}"
        )
        self.mission_id = mission_id
        self.outstanding = tuple(outstanding)


class NoPlanRecorded(MissionError):
    """A mission cannot be planned without a reference to the plan.

    Mission Runtime does not plan. What it requires is evidence that planning
    happened somewhere it can name -- without which "planned" is an assertion
    about nothing.
    """

    def __init__(self, mission_id: str) -> None:
        super().__init__(
            f"mission {mission_id} cannot be planned with no plan reference; "
            "Mission Runtime does not plan, so it records where the plan lives"
        )
        self.mission_id = mission_id


class NoOpenExecution(MissionError):
    def __init__(self, *, mission_id: str, operation: str) -> None:
        super().__init__(
            f"mission {mission_id} has no open execution; {operation} needs a run "
            "in flight"
        )
        self.mission_id = mission_id
        self.operation = operation


class ExecutionAlreadyOpen(MissionError):
    """Two concurrent runs of one mission would report two answers."""

    def __init__(self, *, mission_id: str, execution_id: str) -> None:
        super().__init__(
            f"mission {mission_id} already has execution {execution_id} open; a "
            "second concurrent run would produce two outcomes for one objective"
        )
        self.mission_id = mission_id
        self.execution_id = execution_id


class UnknownCheckpoint(MissionError):
    def __init__(self, *, mission_id: str, checkpoint_id: str) -> None:
        super().__init__(f"mission {mission_id} has no checkpoint {checkpoint_id}")
        self.mission_id = mission_id
        self.checkpoint_id = checkpoint_id


class TimelineOutOfOrder(MissionError):
    """The timeline is append-only and monotonic.

    Replay reconstructs a mission from this sequence. A gap or a repeat makes
    the reconstruction ambiguous, and an ambiguous audit trail is not one.
    """

    def __init__(self, *, expected: int, received: int) -> None:
        super().__init__(
            f"timeline entry {received} does not follow {expected - 1}; the timeline "
            "is append-only and replay depends on it being gapless"
        )
        self.expected = expected
        self.received = received


class TransitionRefused(MissionError):
    """Policy refused the transition, with every reason at once."""

    def __init__(self, *, mission_id: str, target: str, failures: Sequence) -> None:
        summary = "; ".join(f"{f.rule}: {f.detail}" for f in list(failures)[:3])
        more = f" (+{len(failures) - 3} more)" if len(failures) > 3 else ""
        super().__init__(
            f"mission {mission_id} cannot move to {target!r} -- {summary}{more}"
        )
        self.mission_id = mission_id
        self.target = target
        self.failures = tuple(failures)


class DigestMismatch(MissionError):
    def __init__(self, *, mission_id: str, recorded: str, recomputed: str) -> None:
        super().__init__(
            f"mission {mission_id}: archived with digest {recorded} but content now "
            f"hashes to {recomputed}; the record on file is not the one sealed"
        )
        self.mission_id = mission_id
        self.recorded = recorded
        self.recomputed = recomputed


class DigestNotComputed(MissionError):
    def __init__(self, mission_id: str) -> None:
        super().__init__(
            f"mission {mission_id} has no digest; digests are computed at archival"
        )
        self.mission_id = mission_id


class MissionNotFound(MissionError):
    def __init__(self, mission_id: str) -> None:
        super().__init__(f"no mission with id {mission_id}")
        self.mission_id = mission_id


class DuplicateMission(MissionError):
    def __init__(self, mission_id: str) -> None:
        super().__init__(f"mission {mission_id} already exists")
        self.mission_id = mission_id

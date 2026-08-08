"""The WorkOrder lifecycle manager.

Knows which collaborator a phase needs, and refuses a phase whose collaborator is
missing rather than proceeding unorchestrated.

That refusal is the point of this module. A phase that requires review and moves
on because nothing was listening is worse than a phase that stops: the first
produces an unreviewed merge that *looks* reviewed, and no later inspection can
tell the difference. So a transition into a phase whose port is unwired raises
:class:`CollaboratorUnavailable`.

Three of the four ports have no implementation yet. That is not a gap to be
papered over with a permissive default -- it is the honest state of the system,
and it means a WorkOrder cannot currently be driven past implementation. Wiring
an adapter is what changes that.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional, Sequence

from backend.contexts.engineering.errors import CollaboratorUnavailable
from backend.contexts.engineering.ports import (
    ContextPort,
    ReviewPort,
    VerificationPort,
    WorkOrderPhase,
    WorkOrderPort,
    WorkOrderSnapshot,
)

__all__ = ["Collaborators", "WorkOrderLifecycleManager", "PHASE_REQUIREMENTS"]


#: Which port a phase needs before it may be entered.
PHASE_REQUIREMENTS = {
    WorkOrderPhase.SPEC_TESTS: "context",
    WorkOrderPhase.IMPLEMENTATION: "context",
    WorkOrderPhase.REVIEW: "review",
    WorkOrderPhase.VERIFICATION: "verification",
}


@dataclass(frozen=True)
class Collaborators:
    """The adapters wired into this runtime.

    ``work_order`` is mandatory: a runtime with no WorkOrder port has nothing to
    orchestrate. The other three are optional because their contexts do not
    exist, and the lifecycle manager refuses the phases that need them.
    """

    work_order: WorkOrderPort
    review: Optional[ReviewPort] = None
    verification: Optional[VerificationPort] = None
    context_bundles: Optional[ContextPort] = None

    def __post_init__(self) -> None:
        if self.work_order is None:
            raise CollaboratorUnavailable(port="work_order", needed_for="the runtime itself")

    def get(self, name: str) -> Optional[Any]:
        return {
            "work_order": self.work_order,
            "review": self.review,
            "verification": self.verification,
            "context": self.context_bundles,
        }.get(name)

    @property
    def wired(self) -> tuple:
        return tuple(
            sorted(
                name
                for name in ("work_order", "review", "verification", "context")
                if self.get(name) is not None
            )
        )

    @property
    def missing(self) -> tuple:
        return tuple(
            sorted(
                name
                for name in ("work_order", "review", "verification", "context")
                if self.get(name) is None
            )
        )


class WorkOrderLifecycleManager:
    """Phase-boundary orchestration: what must exist, and what to ask for.

    Holds no state. Round and attempt numbers are derived from the event log
    rather than counted here -- a counter in memory disagrees with the log the
    moment the process restarts, and the log is authoritative.
    """

    def __init__(self, collaborators: Collaborators) -> None:
        self._collaborators = collaborators

    @property
    def collaborators(self) -> Collaborators:
        return self._collaborators

    def require_collaborator_for(self, phase: WorkOrderPhase) -> None:
        """Refuse a phase whose collaborator is unwired."""
        needed = PHASE_REQUIREMENTS.get(phase)
        if needed is None:
            return
        if self._collaborators.get(needed) is None:
            raise CollaboratorUnavailable(port=needed, needed_for=f"phase {phase.value!r}")

    def can_enter(self, phase: WorkOrderPhase) -> bool:
        needed = PHASE_REQUIREMENTS.get(phase)
        return needed is None or self._collaborators.get(needed) is not None

    def reachable_phases(self) -> tuple:
        return tuple(sorted((p.value for p in WorkOrderPhase if self.can_enter(p))))

    # ------------------------------------------------------------------
    # Phase entry
    # ------------------------------------------------------------------

    def on_entering_review(
        self, context: Any, snapshot: WorkOrderSnapshot, round_number: int
    ) -> Sequence[str]:
        """Ask the Review context for every required lens.

        Returns the lenses requested, so the event can name them. A missing lens
        is not a passing lens, and the only way to notice one never reported is
        to have recorded that it was asked.
        """
        self.require_collaborator_for(WorkOrderPhase.REVIEW)
        review = self._collaborators.review
        lenses = tuple(review.required_lenses())
        review.request(context, snapshot.work_id, round_number, lenses)
        return lenses

    def on_entering_verification(
        self, context: Any, snapshot: WorkOrderSnapshot, attempt: int
    ) -> str:
        self.require_collaborator_for(WorkOrderPhase.VERIFICATION)
        return self._collaborators.verification.request(context, snapshot.work_id, attempt)

    def on_entering_implementation(
        self, context: Any, snapshot: WorkOrderSnapshot
    ) -> Optional[str]:
        """Assemble the context bundle the implementer will work from."""
        self.require_collaborator_for(WorkOrderPhase.IMPLEMENTATION)
        bundles = self._collaborators.context_bundles
        if bundles is None:
            return None
        reference = bundles.assemble(context, snapshot.work_id, snapshot.version)
        return reference.manifest_digest

    # ------------------------------------------------------------------
    # Phase exit
    # ------------------------------------------------------------------

    def review_outcomes(self, context: Any, work_id: str, round_number: int) -> tuple:
        self.require_collaborator_for(WorkOrderPhase.REVIEW)
        return tuple(self._collaborators.review.outcomes(context, work_id, round_number))

    def verification_outcome(self, context: Any, work_id: str, attempt: int):
        self.require_collaborator_for(WorkOrderPhase.VERIFICATION)
        return self._collaborators.verification.outcome(context, work_id, attempt)

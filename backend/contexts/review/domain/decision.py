"""What a review concludes.

Three outcomes, because the lifecycle has three doors out of ``review``:
verification, back to implementation, or rejected (ADR-020's
``PHASE_TRANSITIONS``). Collapsing "request changes" into "reject" would tell the
runtime to abandon a WorkOrder whose premise is sound and whose implementation
merely needs another pass -- a materially different and much more expensive
answer.

The decision is not the verdict
--------------------------------
The runtime speaks in verdict strings, this context speaks in decisions, and the
composition root translates. That is deliberate: a context that knew the
orchestrator's vocabulary would be coupled to the orchestrator, which S2
forbids. The translation is one mapping in one adapter, and a drift test asserts
the runtime still accepts what the adapter emits.
"""

from __future__ import annotations

from enum import Enum

__all__ = ["ReviewDecision"]


class ReviewDecision(str, Enum):
    """The reviewer's conclusion about one lens on one round."""

    APPROVED = "approved"
    CHANGES_REQUESTED = "changes_requested"
    REJECTED = "rejected"

    @property
    def is_approval(self) -> bool:
        return self is ReviewDecision.APPROVED

    @property
    def permits_open_blockers(self) -> bool:
        """Whether this decision may be issued with blocking findings open.

        Only approval may not. The other two exist precisely to carry blockers
        outward -- refusing them for having blockers would leave a reviewer who
        found a real defect with no way to report it.
        """
        return not self.is_approval

    @property
    def requires_rationale(self) -> bool:
        """Anything other than approval must say why.

        An approval is explained by the findings it resolved and the files it
        examined. A refusal is not: the implementer's next round is built from
        the reason, and "changes requested" with no reason produces a round spent
        guessing.
        """
        return not self.is_approval

    @property
    def requires_a_finding(self) -> bool:
        """Requesting changes must name at least one thing to change.

        Rejection does not: a round can be rejected because the WorkOrder's
        premise turned out false, which is a statement about the WorkOrder rather
        than a defect in the diff.
        """
        return self is ReviewDecision.CHANGES_REQUESTED

    @property
    def sends_back_to_implementation(self) -> bool:
        return self is ReviewDecision.CHANGES_REQUESTED

    @property
    def ends_the_work_order(self) -> bool:
        return self is ReviewDecision.REJECTED

"""Review policy: whether a decision may be issued.

The aggregate enforces per-item invariants and holds the two refusals that must
never be bypassed. This decides whether the *decision* is a sound one to publish,
which is a different question -- a review where every finding is well-formed can
still be a judgement nobody should act on.

Kept out of the aggregate so the service can report every failure at once. A
decision refused one reason at a time takes five attempts to land, and the fifth
is made by someone who has stopped reading the refusals.

The rules, and the failure each prevents
-----------------------------------------
**R0 the review is in progress.** A decision from a review nobody took up has no
reviewer to attribute it to.

**R1 no open blocking finding.** The rule the runtime asserts on its own event.
Two independent checks for one fact, because the fact is whether work that was
blocked looks approved.

**R2 the change set was examined.** The rubber stamp. An approval covering nine
of ten files reports downstream exactly like one covering ten.

**R3 a refusal says why.** The next round is built from the reason.

**R4 requesting changes names a change.** "Changes requested" with nothing
outstanding sends the round back with no destination.

**R5 the decision names its reviewer.** An unattributed judgement has nobody
behind it, and nobody to ask.

**R6 the review is bound to an artifact digest.** Without it the review cannot
be shown to be about the implementation that was submitted.

**R7 accepted risks are visible.** Advisory: a hazard living in the tree by
decision is a fact the next reader needs, not a reason to refuse this decision.

**R8 an approval that found nothing says so out loud.** Advisory: clean reviews
are real, and a lens that never finds anything across many rounds is the signal
worth having.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Optional

from backend.contexts.review.domain.decision import ReviewDecision
from backend.contexts.review.domain.record import ReviewRecord, ReviewStatus

__all__ = ["Severity", "PolicyFinding", "PolicyReport", "ReviewPolicy", "default_policy"]


class Severity(str, Enum):
    BLOCKING = "blocking"
    ADVISORY = "advisory"

    @property
    def refuses(self) -> bool:
        return self is Severity.BLOCKING


@dataclass(frozen=True)
class PolicyFinding:
    rule: str
    severity: Severity
    detail: str
    subject: Optional[str] = None

    def __str__(self) -> str:  # pragma: no cover - diagnostic only
        return f"{self.rule}: {self.detail}"


@dataclass(frozen=True)
class PolicyReport:
    findings: tuple = ()

    @property
    def blocking(self) -> tuple:
        return tuple(f for f in self.findings if f.severity.refuses)

    @property
    def advisory(self) -> tuple:
        return tuple(f for f in self.findings if not f.severity.refuses)

    @property
    def may_decide(self) -> bool:
        return not self.blocking


class ReviewPolicy:
    """Decides whether a review may be concluded with a given decision."""

    def __init__(self, *, require_full_coverage: bool = True) -> None:
        self._require_full_coverage = require_full_coverage

    @property
    def requires_full_coverage(self) -> bool:
        return self._require_full_coverage

    def evaluate(self, record: ReviewRecord, decision: ReviewDecision) -> PolicyReport:
        """Every finding, not just the first."""
        findings: list = []

        # R0 -- the review is in progress.
        if record.status is not ReviewStatus.IN_PROGRESS:
            findings.append(
                PolicyFinding(
                    rule="R0-in-progress",
                    severity=Severity.BLOCKING,
                    detail=(
                        f"the review is {record.status.value}, not in progress; a "
                        "decision needs a reviewer who took it up"
                    ),
                    subject=str(record.review_id),
                )
            )

        if decision.is_approval:
            # R1 -- no open blocking finding.
            for finding in record.open_blockers:
                findings.append(
                    PolicyFinding(
                        rule="R1-no-open-blockers",
                        severity=Severity.BLOCKING,
                        detail=(
                            f"blocking finding is still open: {finding.summary[:60]!r} "
                            f"at {finding.anchor}. Fix it, withdraw it, or request "
                            "changes instead of approving"
                        ),
                        subject=str(finding.finding_id),
                    )
                )

            # R2 -- the change set was examined.
            if self._require_full_coverage:
                for path in record.unexamined_files:
                    findings.append(
                        PolicyFinding(
                            rule="R2-change-set-examined",
                            severity=Severity.BLOCKING,
                            detail=(
                                f"{path!r} is in the change set and was never examined; "
                                "an approval that skipped a file reports exactly like "
                                "one that did not"
                            ),
                            subject=path,
                        )
                    )

            # R8 -- a clean approval, stated rather than assumed.
            if not record.findings and not record.comments:
                findings.append(
                    PolicyFinding(
                        rule="R8-nothing-recorded",
                        severity=Severity.ADVISORY,
                        detail=(
                            "approved with no findings and no comments; a lens that "
                            "records nothing cannot be distinguished later from one "
                            "that read nothing"
                        ),
                        subject=record.lens.value,
                    )
                )

        # R3 -- a refusal says why.
        if decision.requires_rationale and not (
            record.decision_rationale and record.decision_rationale.strip()
        ):
            findings.append(
                PolicyFinding(
                    rule="R3-rationale-given",
                    severity=Severity.BLOCKING,
                    detail=(
                        f"a {decision.value!r} decision must say why; the implementer's "
                        "next round is built from the reason"
                    ),
                    subject=str(record.review_id),
                )
            )

        # R4 -- requesting changes names a change.
        if decision.requires_a_finding and not record.open_findings:
            findings.append(
                PolicyFinding(
                    rule="R4-changes-need-a-finding",
                    severity=Severity.BLOCKING,
                    detail=(
                        "changes were requested with no finding outstanding; the round "
                        "goes back with nothing to act on"
                    ),
                    subject=str(record.review_id),
                )
            )

        # R5 -- the decision names its reviewer.
        if not (record.reviewer and record.reviewer.strip()):
            findings.append(
                PolicyFinding(
                    rule="R5-reviewer-named",
                    severity=Severity.BLOCKING,
                    detail="the review names no reviewer; the judgement has nobody behind it",
                    subject=str(record.review_id),
                )
            )

        # R6 -- bound to an artifact.
        if not (record.implementation_digest and record.implementation_digest.strip()):
            findings.append(
                PolicyFinding(
                    rule="R6-bound-to-artifact",
                    severity=Severity.BLOCKING,
                    detail=(
                        "the review carries no implementation digest; it cannot be "
                        "shown to be about the artifact that was submitted"
                    ),
                    subject=record.implementation_id,
                )
            )

        # R7 -- accepted risks travel forward.
        for finding in record.accepted_risks:
            findings.append(
                PolicyFinding(
                    rule="R7-accepted-risk",
                    severity=Severity.ADVISORY,
                    detail=(
                        f"accepted as risk rather than fixed: {finding.summary[:60]!r} "
                        f"-- {finding.resolution_note or 'no justification recorded'}"
                    ),
                    subject=str(finding.finding_id),
                )
            )

        return PolicyReport(findings=tuple(findings))


def default_policy() -> ReviewPolicy:
    """The policy the Engineering Constitution defines."""
    return ReviewPolicy(require_full_coverage=True)

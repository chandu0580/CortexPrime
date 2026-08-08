"""Failures raised by the Review context.

Every one is a refusal. Review never approves past an unresolved blocking
finding, never records a finding it cannot point at, and never changes after a
decision is issued.

The refusals are shaped by what Review *is*: an independent read of an artifact
someone else produced. It has no power to edit that artifact, so every failure
here is a failure to say something well -- never a failure to change something.
"""

from __future__ import annotations

from typing import Sequence

from backend.contracts.errors import ContractViolation

__all__ = [
    "ReviewError",
    "InvalidIdentifier",
    "ReviewDecided",
    "ReviewNotStarted",
    "ReviewIsSuperseded",
    "FindingWithoutAnchor",
    "BlockingFindingWithoutRemedy",
    "UnknownFinding",
    "FindingAlreadyResolved",
    "BlockingFindingCannotBeWaived",
    "ApprovalWithOpenBlockers",
    "UnexaminedFiles",
    "DecisionRefused",
    "DigestMismatch",
    "DigestNotComputed",
    "ReviewNotFound",
    "DuplicateReview",
    "UnknownLens",
]


class ReviewError(ContractViolation):
    """Base for every refusal raised by this context."""


class InvalidIdentifier(ReviewError):
    def __init__(self, kind: str, value: object, reason: str) -> None:
        super().__init__(f"{kind} cannot be {value!r}: {reason}")
        self.kind = kind
        self.value = value
        self.reason = reason


class ReviewDecided(ReviewError):
    """The review is closed and may not change.

    A review that gained a finding after its decision would describe a judgement
    nobody made. The decision is the artifact; everything before it is working
    material, and the boundary between them is what makes the decision quotable.
    """

    def __init__(self, *, review_id: str, operation: str) -> None:
        super().__init__(
            f"review {review_id} is decided; {operation} would change a judgement "
            "that has already been reported"
        )
        self.review_id = review_id
        self.operation = operation


class ReviewNotStarted(ReviewError):
    """Findings belong to a review someone is actually conducting.

    A finding recorded against a review nobody started cannot say who looked, and
    an unattributed finding is an assertion with no one behind it.
    """

    def __init__(self, *, review_id: str, operation: str) -> None:
        super().__init__(
            f"review {review_id} has not started; {operation} needs a reviewer who "
            "has taken it up"
        )
        self.review_id = review_id
        self.operation = operation


class ReviewIsSuperseded(ReviewError):
    def __init__(self, *, review_id: str, successor: str) -> None:
        super().__init__(
            f"review {review_id} is superseded by {successor}; a later round replaced it"
        )
        self.review_id = review_id
        self.successor = successor


class FindingWithoutAnchor(ReviewError):
    """A finding that points at nothing cannot be acted on.

    The rule the implementer depends on. "The error handling is wrong" names no
    file, no line, and no evidence; the round it triggers is spent guessing at
    what the reviewer meant rather than fixing it.
    """

    def __init__(self, summary: str) -> None:
        super().__init__(
            f"finding {summary[:60]!r} names neither a location nor evidence; a "
            "finding that points at nothing cannot be acted on"
        )
        self.summary = summary


class BlockingFindingWithoutRemedy(ReviewError):
    """A blocking finding must say what would clear it.

    Blocking means work stops until it is addressed. Stopping work without
    saying what would restart it is the most expensive thing a reviewer can do.
    """

    def __init__(self, summary: str) -> None:
        super().__init__(
            f"blocking finding {summary[:60]!r} states no required change; blocking "
            "work without saying what would clear it stops the round on a guess"
        )
        self.summary = summary


class UnknownFinding(ReviewError):
    def __init__(self, *, review_id: str, finding_id: str) -> None:
        super().__init__(f"review {review_id} has no finding {finding_id}")
        self.review_id = review_id
        self.finding_id = finding_id


class FindingAlreadyResolved(ReviewError):
    def __init__(self, *, finding_id: str, resolution: str) -> None:
        super().__init__(
            f"finding {finding_id} is already resolved {resolution!r}; a second "
            "resolution would overwrite the first"
        )
        self.finding_id = finding_id
        self.resolution = resolution


class BlockingFindingCannotBeWaived(ReviewError):
    """A blocking finding is cleared by fixing it or withdrawing it -- not by
    accepting it.

    Accepting a risk is a legitimate act, and it is not the reviewer's to make
    alone on something they themselves called blocking. Waiving one silently
    converts "this must change" into "this may ship", which is the whole
    distinction the severity exists to draw. Escalate it instead: a blocker the
    reviewer no longer believes in is a withdrawal, and one nobody intends to fix
    is a rejection.
    """

    def __init__(self, *, finding_id: str, summary: str) -> None:
        super().__init__(
            f"finding {finding_id} is blocking and cannot be accepted as risk: "
            f"{summary[:60]!r}. Fix it, withdraw it, or reject the round -- waiving "
            "it turns 'must change' into 'may ship' without anyone deciding so"
        )
        self.finding_id = finding_id
        self.summary = summary


class ApprovalWithOpenBlockers(ReviewError):
    """Approval is refused while a blocking finding is outstanding.

    The runtime enforces the same rule on its own event (``ReviewCompleted``
    refuses to be constructed as passed with blocking findings). Two independent
    checks for one fact, because the fact is whether unreviewed work looks
    reviewed.
    """

    def __init__(self, *, review_id: str, open_findings: Sequence) -> None:
        names = "; ".join(f.summary[:40] for f in list(open_findings)[:3])
        more = f" (+{len(open_findings) - 3} more)" if len(open_findings) > 3 else ""
        super().__init__(
            f"review {review_id} cannot approve with {len(open_findings)} blocking "
            f"finding(s) open -- {names}{more}"
        )
        self.review_id = review_id
        self.open_findings = tuple(open_findings)


class UnexaminedFiles(ReviewError):
    """Approval is refused while a file in the change set was never looked at.

    This is the rubber stamp, and it is the failure Review most needs to be
    unable to commit. An approval that covered nine of ten files is reported
    downstream exactly like one that covered ten.
    """

    def __init__(self, *, review_id: str, unexamined: Sequence) -> None:
        listed = ", ".join(sorted(unexamined)[:5])
        more = f" (+{len(unexamined) - 5} more)" if len(unexamined) > 5 else ""
        super().__init__(
            f"review {review_id} cannot approve: {len(unexamined)} file(s) in the "
            f"change set were never examined -- {listed}{more}"
        )
        self.review_id = review_id
        self.unexamined = tuple(unexamined)


class DecisionRefused(ReviewError):
    """The review policy refused the decision, with every reason at once."""

    def __init__(self, *, review_id: str, decision: str, failures: Sequence) -> None:
        summary = "; ".join(f"{f.rule}: {f.detail}" for f in list(failures)[:3])
        more = f" (+{len(failures) - 3} more)" if len(failures) > 3 else ""
        super().__init__(
            f"review {review_id} cannot be decided {decision!r} -- {summary}{more}"
        )
        self.review_id = review_id
        self.decision = decision
        self.failures = tuple(failures)


class DigestMismatch(ReviewError):
    """The review no longer hashes to the digest bound at decision."""

    def __init__(self, *, review_id: str, recorded: str, recomputed: str) -> None:
        super().__init__(
            f"review {review_id}: decided with digest {recorded} but content now "
            f"hashes to {recomputed}; the judgement on record is not the one issued"
        )
        self.review_id = review_id
        self.recorded = recorded
        self.recomputed = recomputed


class DigestNotComputed(ReviewError):
    def __init__(self, review_id: str) -> None:
        super().__init__(
            f"review {review_id} has no digest; digests are computed at decision"
        )
        self.review_id = review_id


class ReviewNotFound(ReviewError):
    def __init__(self, review_id: str) -> None:
        super().__init__(f"no review with id {review_id}")
        self.review_id = review_id


class DuplicateReview(ReviewError):
    """One lens reviews one round once.

    Two open reviews for the same lens and round would let a second reviewer
    approve what the first blocked, and the runtime -- which reads one outcome
    per lens -- would report whichever it happened to see.
    """

    def __init__(self, *, work_id: str, round: int, lens: str) -> None:
        super().__init__(
            f"lens {lens!r} already has a review for round {round} of WorkOrder "
            f"{work_id}; a second would let one reviewer approve what another blocked"
        )
        self.work_id = work_id
        self.round = round
        self.lens = lens


class UnknownLens(ReviewError):
    def __init__(self, value: object, known: Sequence[str]) -> None:
        super().__init__(
            f"{value!r} is not a review lens; known lenses are {', '.join(sorted(known))}"
        )
        self.value = value
        self.known = tuple(known)

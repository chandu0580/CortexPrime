"""Failures raised by the ImplementationRecord context.

Every one is a refusal. The record never quietly accepts a file outside the blast
radius, never invents evidence for a claim that has none, and never mutates after
completion.

That last one carries the most weight. This record is what Review and
Verification consume; a record that could change after they read it would make
every finding they produced a statement about a document that no longer exists.
"""

from __future__ import annotations

from typing import Optional, Sequence

from backend.contracts.errors import ContractViolation

__all__ = [
    "ImplementationError",
    "InvalidIdentifier",
    "OutsideBlastRadius",
    "ClaimWithoutEvidence",
    "RecordCompleted",
    "RecordNotStarted",
    "RecordSuperseded",
    "DuplicateClaim",
    "UnknownClaim",
    "AssumptionAlreadyResolved",
    "UnknownAssumption",
    "IncompleteRecord",
    "DigestMismatch",
    "DigestNotComputed",
    "RecordNotFound",
    "DuplicateRecord",
]


class ImplementationError(ContractViolation):
    """Base for every refusal raised by this context."""


class InvalidIdentifier(ImplementationError):
    def __init__(self, kind: str, value: object, reason: str) -> None:
        super().__init__(f"{kind} cannot be {value!r}: {reason}")
        self.kind = kind
        self.value = value
        self.reason = reason


class OutsideBlastRadius(ImplementationError):
    """A changed file falls outside the scope the WorkOrder authorised.

    Carries the path and the reason separately, because the two failures need
    different responses: a path that is simply outside means the radius was
    predicted wrongly and should be expanded through re-approval; a path that is
    *forbidden* means the Architect ruled it out on purpose and expanding is the
    wrong answer.
    """

    def __init__(self, *, path: str, reason: str, allowed: Sequence[str] = ()) -> None:
        scope = f" (declared: {', '.join(sorted(allowed))})" if allowed else ""
        super().__init__(f"{path!r} {reason}{scope}")
        self.path = path
        self.reason = reason
        self.allowed = tuple(allowed)


class ClaimWithoutEvidence(ImplementationError):
    """A claim was recorded with nothing supporting it.

    The rule the Verification context depends on. A claim with no evidence
    reference gives a verifier nothing to attack -- it can only be taken on
    trust, which is the one thing verification exists not to do.
    """

    def __init__(self, statement: str) -> None:
        super().__init__(
            f"claim {statement[:60]!r} cites no evidence; a claim a verifier cannot "
            "attack can only be taken on trust"
        )
        self.statement = statement


class RecordCompleted(ImplementationError):
    """The record is closed and may not change.

    Review and Verification consume this artifact. A record that changed after
    they read it would make every finding they produced a statement about a
    document that no longer exists.
    """

    def __init__(self, *, record_id: str, operation: str) -> None:
        super().__init__(
            f"implementation {record_id} is complete; {operation} would change an "
            "artifact Review and Verification have already been given"
        )
        self.record_id = record_id
        self.operation = operation


class RecordNotStarted(ImplementationError):
    def __init__(self, record_id: str) -> None:
        super().__init__(
            f"implementation {record_id} has not started; work cannot be recorded "
            "against a round nobody has begun"
        )
        self.record_id = record_id


class RecordSuperseded(ImplementationError):
    def __init__(self, *, record_id: str, successor: str) -> None:
        super().__init__(
            f"implementation {record_id} is superseded by {successor}; a later round "
            "replaced it"
        )
        self.record_id = record_id
        self.successor = successor


class DuplicateClaim(ImplementationError):
    def __init__(self, statement: str) -> None:
        super().__init__(
            f"claim {statement[:60]!r} is already recorded; two identical claims would "
            "be verified twice and counted twice"
        )
        self.statement = statement


class UnknownClaim(ImplementationError):
    def __init__(self, *, record_id: str, claim_id: str) -> None:
        super().__init__(f"implementation {record_id} has no claim {claim_id}")
        self.record_id = record_id
        self.claim_id = claim_id


class AssumptionAlreadyResolved(ImplementationError):
    """A second answer to a settled question means one of them is wrong."""

    def __init__(self, *, assumption_id: str, resolution: str) -> None:
        super().__init__(
            f"assumption {assumption_id} is already resolved {resolution!r}; a second "
            "resolution would overwrite the first"
        )
        self.assumption_id = assumption_id
        self.resolution = resolution


class UnknownAssumption(ImplementationError):
    def __init__(self, *, record_id: str, assumption_id: str) -> None:
        super().__init__(
            f"implementation {record_id} was not asked to resolve assumption "
            f"{assumption_id}"
        )
        self.record_id = record_id
        self.assumption_id = assumption_id


class IncompleteRecord(ImplementationError):
    """A record cannot be completed while something required is missing."""

    def __init__(self, *, record_id: str, failures: Sequence) -> None:
        summary = "; ".join(f"{f.rule}: {f.detail}" for f in list(failures)[:3])
        more = f" (+{len(failures) - 3} more)" if len(failures) > 3 else ""
        super().__init__(f"implementation {record_id} cannot complete -- {summary}{more}")
        self.record_id = record_id
        self.failures = tuple(failures)


class DigestMismatch(ImplementationError):
    """The record no longer hashes to the digest computed at completion."""

    def __init__(self, *, record_id: str, recorded: str, recomputed: str) -> None:
        super().__init__(
            f"implementation {record_id}: completed with digest {recorded} but content "
            f"now hashes to {recomputed}; the artifact under review is not the one "
            "that was submitted"
        )
        self.record_id = record_id
        self.recorded = recorded
        self.recomputed = recomputed


class DigestNotComputed(ImplementationError):
    def __init__(self, record_id: str) -> None:
        super().__init__(
            f"implementation {record_id} has no digest; digests are computed at completion"
        )
        self.record_id = record_id


class RecordNotFound(ImplementationError):
    def __init__(self, record_id: str) -> None:
        super().__init__(f"no implementation record with id {record_id}")
        self.record_id = record_id


class DuplicateRecord(ImplementationError):
    def __init__(self, *, work_id: str, round: int) -> None:
        super().__init__(f"round {round} for WorkOrder {work_id} already exists")
        self.work_id = work_id
        self.round = round

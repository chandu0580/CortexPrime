"""Failures raised by the Intent context.

Every one is a refusal to accept an under-specified goal. That is the whole job:
Intent stands between a sentence somebody typed and a mandate an automated system
will act on, and the failures here are the ones that would otherwise be
discovered by a planner guessing, or by an executor doing something expensive
nobody asked for.

None of these are failures to plan or execute. This context does neither.
"""

from __future__ import annotations

from typing import Sequence

from backend.contracts.errors import ContractViolation

__all__ = [
    "IntentError",
    "InvalidIdentifier",
    "IllegalIntentTransition",
    "IntentApproved",
    "IntentIsSuperseded",
    "UnmeasurableCriterion",
    "UnboundedConstraint",
    "EmptyScope",
    "ContradictoryScope",
    "IncompleteIntent",
    "ValidationRefused",
    "UnknownConstraint",
    "UnknownCriterion",
    "DuplicateConstraint",
    "DigestMismatch",
    "DigestNotComputed",
    "IntentNotFound",
    "DuplicateIntent",
]


class IntentError(ContractViolation):
    """Base for every refusal raised by this context."""


class InvalidIdentifier(IntentError):
    def __init__(self, kind: str, value: object, reason: str) -> None:
        super().__init__(f"{kind} cannot be {value!r}: {reason}")
        self.kind = kind
        self.value = value
        self.reason = reason


class IllegalIntentTransition(IntentError):
    def __init__(
        self, *, intent_id: str, source: str, target: str, permitted: Sequence[str]
    ) -> None:
        allowed = ", ".join(sorted(permitted)) or "(nothing -- this state is terminal)"
        super().__init__(
            f"intent {intent_id} cannot move {source} -> {target}; {source} may only "
            f"move to: {allowed}"
        )
        self.intent_id = intent_id
        self.source = source
        self.target = target
        self.permitted = tuple(permitted)


class IntentApproved(IntentError):
    """The intent is approved and may not change.

    An approved intent is the canonical input to planning. One that changed
    afterwards would mean the plan was built from something nobody approved --
    and the approval would be evidence for a mandate that no longer exists.
    """

    def __init__(self, *, intent_id: str, operation: str) -> None:
        super().__init__(
            f"intent {intent_id} is approved; {operation} would change a mandate "
            "that planning has already been authorised to act on"
        )
        self.intent_id = intent_id
        self.operation = operation


class IntentIsSuperseded(IntentError):
    def __init__(self, *, intent_id: str, successor: str) -> None:
        super().__init__(
            f"intent {intent_id} is superseded by {successor}; a later intent "
            "replaced it"
        )
        self.intent_id = intent_id
        self.successor = successor


class UnmeasurableCriterion(IntentError):
    """A success criterion that nobody can check is a wish.

    The rule the whole context turns on. "The system should be faster" cannot be
    satisfied or refuted, so an executor cannot know when to stop and a verifier
    cannot know whether it worked. Refused at construction rather than flagged
    later, because a criterion this weak is consumed the moment it exists.
    """

    def __init__(self, statement: str) -> None:
        super().__init__(
            f"success criterion {statement[:60]!r} names no way to measure it; a "
            "criterion nobody can check is a wish, and nothing can be shown to "
            "have satisfied it"
        )
        self.statement = statement


class UnboundedConstraint(IntentError):
    """A quantitative constraint with no limit does not constrain anything."""

    def __init__(self, *, kind: str, statement: str) -> None:
        super().__init__(
            f"a {kind!r} constraint must carry its limit: {statement[:60]!r} states a "
            "concern but no boundary, so nothing can be shown to have exceeded it"
        )
        self.kind = kind
        self.statement = statement


class EmptyScope(IntentError):
    """A scope that includes nothing authorises nothing."""

    def __init__(self) -> None:
        super().__init__(
            "a scope must include at least one target; one that includes nothing "
            "authorises nothing, and a planner given it has no ground to stand on"
        )


class ContradictoryScope(IntentError):
    """A target both included and excluded is a contradiction nobody can resolve."""

    def __init__(self, overlapping: Sequence[str]) -> None:
        listed = ", ".join(sorted(overlapping)[:5])
        super().__init__(
            f"scope both includes and excludes {listed}; a planner cannot resolve "
            "the contradiction and would have to guess which the requester meant"
        )
        self.overlapping = tuple(overlapping)


class IncompleteIntent(IntentError):
    """The intent is missing something validation requires."""

    def __init__(self, *, intent_id: str, missing: Sequence[str]) -> None:
        listed = ", ".join(sorted(missing))
        super().__init__(f"intent {intent_id} is missing: {listed}")
        self.intent_id = intent_id
        self.missing = tuple(missing)


class ValidationRefused(IntentError):
    """Policy refused, with every reason at once."""

    def __init__(self, *, intent_id: str, target: str, failures: Sequence) -> None:
        summary = "; ".join(f"{f.rule}: {f.detail}" for f in list(failures)[:3])
        more = f" (+{len(failures) - 3} more)" if len(failures) > 3 else ""
        super().__init__(f"intent {intent_id} cannot be {target} -- {summary}{more}")
        self.intent_id = intent_id
        self.target = target
        self.failures = tuple(failures)


class UnknownConstraint(IntentError):
    def __init__(self, *, intent_id: str, constraint_id: str) -> None:
        super().__init__(f"intent {intent_id} has no constraint {constraint_id}")
        self.intent_id = intent_id
        self.constraint_id = constraint_id


class UnknownCriterion(IntentError):
    def __init__(self, *, intent_id: str, criterion_id: str) -> None:
        super().__init__(f"intent {intent_id} has no success criterion {criterion_id}")
        self.intent_id = intent_id
        self.criterion_id = criterion_id


class DuplicateConstraint(IntentError):
    def __init__(self, statement: str) -> None:
        super().__init__(
            f"constraint {statement[:60]!r} is already declared; two identical limits "
            "would be checked twice and counted twice"
        )
        self.statement = statement


class DigestMismatch(IntentError):
    def __init__(self, *, intent_id: str, recorded: str, recomputed: str) -> None:
        super().__init__(
            f"intent {intent_id}: approved with digest {recorded} but content now "
            f"hashes to {recomputed}; the mandate on record is not the one approved"
        )
        self.intent_id = intent_id
        self.recorded = recorded
        self.recomputed = recomputed


class DigestNotComputed(IntentError):
    def __init__(self, intent_id: str) -> None:
        super().__init__(
            f"intent {intent_id} has no digest; digests are computed at approval"
        )
        self.intent_id = intent_id


class IntentNotFound(IntentError):
    def __init__(self, intent_id: str) -> None:
        super().__init__(f"no intent with id {intent_id}")
        self.intent_id = intent_id


class DuplicateIntent(IntentError):
    def __init__(self, intent_id: str) -> None:
        super().__init__(f"intent {intent_id} already exists")
        self.intent_id = intent_id

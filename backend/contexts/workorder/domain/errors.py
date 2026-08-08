"""Failures raised by the WorkOrder domain.

All derive from :class:`~backend.contracts.errors.ContractViolation`, so a
caller already handling contract failures at its boundary handles these too
rather than needing a second except clause someone will forget to add.

Every one is a refusal. The domain never repairs a malformed WorkOrder, never
substitutes a default for a missing field, and never downgrades an invalid
transition to a no-op. Engineering Constitution EP-6: ambiguity resolves to
refusal.
"""

from __future__ import annotations

from typing import Optional

from backend.contracts.errors import ContractViolation

__all__ = [
    "WorkOrderError",
    "InvalidIdentifier",
    "InvalidTransition",
    "TerminalState",
    "ImmutableAfterApproval",
    "DigestMismatch",
    "DigestNotComputed",
    "BlastRadiusViolation",
    "ValidationFailed",
    "UnresolvedReference",
    "WorkOrderNotFound",
    "DuplicateWorkOrder",
]


class WorkOrderError(ContractViolation):
    """Base for every failure raised by this context."""


class InvalidIdentifier(WorkOrderError):
    """A strongly-typed identifier was given a value it cannot hold."""

    def __init__(self, kind: str, value: object, reason: str) -> None:
        super().__init__(f"{kind} cannot be {value!r}: {reason}")
        self.kind = kind
        self.value = value
        self.reason = reason


class InvalidTransition(WorkOrderError):
    """A state transition the machine does not permit.

    Carries both states and the stated reason, because the pair plus the reason
    is what tells a caller whether they hit an ordering bug or a genuinely
    forbidden shortcut.
    """

    def __init__(self, *, work_order_id: str, current: str, requested: str, reason: str) -> None:
        super().__init__(
            f"WorkOrder {work_order_id}: cannot move {current} -> {requested}. {reason}"
        )
        self.work_order_id = work_order_id
        self.current = current
        self.requested = requested
        self.reason = reason


class TerminalState(WorkOrderError):
    """An operation was attempted on a WorkOrder that has finished."""

    def __init__(self, *, work_order_id: str, state: str) -> None:
        super().__init__(
            f"WorkOrder {work_order_id} is {state}, which is terminal; "
            "answer it with a new WorkOrder that cites this one"
        )
        self.work_order_id = work_order_id
        self.state = state


class ImmutableAfterApproval(WorkOrderError):
    """A governed field was changed after approval.

    Approval binds to a digest over the governed fields. Changing one would mean
    implementing something other than what was approved -- the process analogue
    of the product's approved-payload-equals-executed-payload invariant.
    """

    def __init__(self, *, work_order_id: str, field: str) -> None:
        super().__init__(
            f"WorkOrder {work_order_id}: {field!r} is immutable after approval; "
            "a change to a governed field requires a new WorkOrder"
        )
        self.work_order_id = work_order_id
        self.field = field


class DigestMismatch(WorkOrderError):
    """The WorkOrder no longer hashes to the digest that was approved."""

    def __init__(self, *, work_order_id: str, approved: str, recomputed: str) -> None:
        super().__init__(
            f"WorkOrder {work_order_id}: approved digest {approved} but content now "
            f"hashes to {recomputed}; the approval does not cover this content"
        )
        self.work_order_id = work_order_id
        self.approved = approved
        self.recomputed = recomputed


class DigestNotComputed(WorkOrderError):
    """A digest was required but the WorkOrder has never been approved."""

    def __init__(self, work_order_id: str) -> None:
        super().__init__(
            f"WorkOrder {work_order_id} has no digest; digests are computed at approval"
        )
        self.work_order_id = work_order_id


class BlastRadiusViolation(WorkOrderError):
    """A path outside the declared radius, or inside its forbidden set."""

    def __init__(self, *, work_order_id: str, path: str, reason: str) -> None:
        super().__init__(f"WorkOrder {work_order_id}: {path!r} {reason}")
        self.work_order_id = work_order_id
        self.path = path
        self.reason = reason


class ValidationFailed(WorkOrderError):
    """One or more blocking validation findings.

    Carries the findings rather than only the first, because fixing them one
    round-trip at a time is how a Draft takes six approvals to land.
    """

    def __init__(self, findings: tuple) -> None:
        summary = "; ".join(f"{f.rule}: {f.detail}" for f in findings[:3])
        more = f" (+{len(findings) - 3} more)" if len(findings) > 3 else ""
        super().__init__(f"WorkOrder validation failed -- {summary}{more}")
        self.findings = findings


class UnresolvedReference(WorkOrderError):
    """A reference could not be resolved, so the claim resting on it is unproven.

    Raised rather than skipped. A reference nobody can resolve is indistinguishable
    from a fabricated one, and treating "unknown" as "fine" is how an unenforced
    constraint comes to look enforced.
    """

    def __init__(self, *, kind: str, reference: str, reason: Optional[str] = None) -> None:
        detail = f": {reason}" if reason else ""
        super().__init__(f"unresolved {kind} reference {reference!r}{detail}")
        self.kind = kind
        self.reference = reference
        self.reason = reason


class WorkOrderNotFound(WorkOrderError):
    def __init__(self, work_order_id: str) -> None:
        super().__init__(f"no WorkOrder with id {work_order_id}")
        self.work_order_id = work_order_id


class DuplicateWorkOrder(WorkOrderError):
    def __init__(self, *, work_order_id: str, version: int) -> None:
        super().__init__(f"WorkOrder {work_order_id} version {version} already exists")
        self.work_order_id = work_order_id
        self.version = version

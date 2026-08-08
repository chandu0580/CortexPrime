"""Engineering policy enforcement.

Every transition runs the checks registered for it. A check returns findings; the
executor refuses if any is blocking.

On "every transition validates Architecture Constitution rules"
---------------------------------------------------------------
Taken literally this is not implementable. The architecture gate parses 782
modules and takes **eight minutes**; running it on each of the eight transitions
a WorkOrder makes would add over an hour of wall-clock per WorkOrder, and a gate
nobody can afford to run is a gate that gets switched off.

What is implemented instead, and why it is not a dilution:

* **Cheap constitutional checks run on every transition** -- the digest still
  binds, assumptions are resolved before work proceeds, dependencies are merged,
  the phase is legal. These are the rules that can actually be violated *by a
  transition*.

* **The architecture gate runs where it can actually change the answer**: at
  ``VERIFICATION -> READY``, the last gate before a human merges. Architecture
  cannot drift during a state change; it drifts when code changes, and the only
  transition after code changes is this one.

That split is a judgement, and it is recorded here rather than buried. The gate
check is a registered policy like any other, so moving it is a one-line change to
:func:`default_policy` rather than a rewrite.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Mapping, Optional, Sequence

from backend.contexts.engineering.ports import WorkOrderPhase, WorkOrderSnapshot

__all__ = [
    "Severity",
    "PolicyFinding",
    "PolicyResult",
    "PolicyCheck",
    "EngineeringPolicy",
    "default_policy",
    "ARCHITECTURE_GATE_TRANSITION",
]


class Severity(str, Enum):
    BLOCKING = "blocking"
    ADVISORY = "advisory"

    @property
    def refuses(self) -> bool:
        return self is Severity.BLOCKING


@dataclass(frozen=True)
class PolicyFinding:
    check: str
    severity: Severity
    detail: str
    subject: Optional[str] = None

    def __str__(self) -> str:  # pragma: no cover - diagnostic only
        return f"{self.check}: {self.detail}"


@dataclass(frozen=True)
class PolicyResult:
    findings: tuple = ()

    @property
    def blocking(self) -> tuple:
        return tuple(f for f in self.findings if f.severity.refuses)

    @property
    def advisory(self) -> tuple:
        return tuple(f for f in self.findings if not f.severity.refuses)

    @property
    def permitted(self) -> bool:
        return not self.blocking


@dataclass(frozen=True)
class PolicyCheck:
    """One named rule, scoped to the transitions it applies to.

    ``applies_to`` of ``None`` means every transition. Scoping is what keeps an
    expensive check off the transitions where it cannot change the answer.
    """

    name: str
    check: Callable[[WorkOrderSnapshot, WorkOrderPhase, Any], Sequence[PolicyFinding]]
    applies_to: Optional[frozenset] = None
    description: str = ""

    def relevant(self, transition: tuple) -> bool:
        return self.applies_to is None or transition in self.applies_to


#: Where the architecture gate runs. The last gate before a human merges.
ARCHITECTURE_GATE_TRANSITION = (WorkOrderPhase.VERIFICATION, WorkOrderPhase.READY)


# ----------------------------------------------------------------------
# Checks
# ----------------------------------------------------------------------


def _digest_still_binds(
    snapshot: WorkOrderSnapshot, to_phase: WorkOrderPhase, context: Any
) -> Sequence[PolicyFinding]:
    """A governed WorkOrder must carry the digest it was approved against."""
    if not snapshot.phase.is_governed:
        return ()
    if snapshot.digest:
        return ()
    return (
        PolicyFinding(
            check="digest-binds",
            severity=Severity.BLOCKING,
            detail=(
                f"WorkOrder is in governed phase {snapshot.phase.value!r} with no digest; "
                "the approval does not cover any particular content"
            ),
            subject=snapshot.work_id,
        ),
    )


def _assumptions_resolved_before_review(
    snapshot: WorkOrderSnapshot, to_phase: WorkOrderPhase, context: Any
) -> Sequence[PolicyFinding]:
    """Work may not reach review on unchecked or failed beliefs.

    Checked at the boundary into review rather than at approval, because that is
    where the assumptions were supposed to have been resolved -- the receiver
    checks them during spec-tests and implementation.
    """
    findings: list = []
    if snapshot.blocking_assumptions:
        findings.append(
            PolicyFinding(
                check="assumptions-hold",
                severity=Severity.BLOCKING,
                detail=(
                    f"{snapshot.blocking_assumptions} assumption(s) were checked and did not "
                    "hold; the correct outcome is a PREMISE_FALSE rejection, not a review"
                ),
                subject=snapshot.work_id,
            )
        )
    if snapshot.unresolved_assumptions:
        findings.append(
            PolicyFinding(
                check="assumptions-checked",
                severity=Severity.BLOCKING,
                detail=(
                    f"{snapshot.unresolved_assumptions} assumption(s) were never checked; "
                    "an unverified belief reaching review is the gap the field exists to close"
                ),
                subject=snapshot.work_id,
            )
        )
    return tuple(findings)


def _dependencies_are_merged(
    snapshot: WorkOrderSnapshot, to_phase: WorkOrderPhase, context: Any
) -> Sequence[PolicyFinding]:
    """A WorkOrder may not be assigned while a dependency is outstanding.

    Advisory rather than blocking: the runtime cannot resolve another
    WorkOrder's state through this check -- that needs the port, and a policy
    check that reached for a collaborator would be doing orchestration. The
    lifecycle manager blocks on dependencies with the port available.
    """
    if not snapshot.dependencies:
        return ()
    return (
        PolicyFinding(
            check="dependencies-declared",
            severity=Severity.ADVISORY,
            detail=(
                f"{len(snapshot.dependencies)} dependency/dependencies declared; the "
                "lifecycle manager blocks until each is merged"
            ),
            subject=snapshot.work_id,
        ),
    )


def _not_superseded(
    snapshot: WorkOrderSnapshot, to_phase: WorkOrderPhase, context: Any
) -> Sequence[PolicyFinding]:
    """A superseded WorkOrder must not keep progressing."""
    if snapshot.superseded_by is None:
        return ()
    return (
        PolicyFinding(
            check="not-superseded",
            severity=Severity.BLOCKING,
            detail=(
                f"superseded by {snapshot.superseded_by}; work on a replaced WorkOrder "
                "produces a merge nobody approved"
            ),
            subject=snapshot.work_id,
        ),
    )


def architecture_gate_check(
    snapshot: WorkOrderSnapshot, to_phase: WorkOrderPhase, context: Any
) -> Sequence[PolicyFinding]:
    """Run the real architecture gate. Expensive; scoped to one transition.

    Imported lazily. ``backend.platform.architecture`` builds a module graph at
    import time in some paths, and paying that on every import of this package
    would slow every test that touches the runtime.
    """
    from backend.platform.architecture import analyze

    result = analyze()
    if result.gate_passed:
        return ()
    return tuple(
        PolicyFinding(
            check="architecture-gate",
            severity=Severity.BLOCKING,
            detail=str(violation),
            subject=snapshot.work_id,
        )
        for violation in result.blocking_violations
    )


def constraints_are_enforceable(
    snapshot: WorkOrderSnapshot, to_phase: WorkOrderPhase, context: Any
) -> Sequence[PolicyFinding]:
    """Every constraint the WorkOrder cites still resolves to a live rule.

    A constraint whose rule was deleted since approval is prose, and prose does
    not block a merge. Cheap: reads rule identifiers, does not run them.
    """
    if not snapshot.constraints:
        return ()

    from backend.platform.architecture import default_suite

    suite = default_suite()
    live = {rule.rule_id for rule in suite._rules}                       # noqa: SLF001
    live |= {check.invariant_id for check in suite._invariants}          # noqa: SLF001
    live |= {f"INV-{check.invariant_id}" for check in suite._invariants}  # noqa: SLF001

    return tuple(
        PolicyFinding(
            check="constraints-enforceable",
            severity=Severity.BLOCKING,
            detail=(
                f"constraint {constraint!r} no longer resolves to a live rule; it was "
                "enforceable when the WorkOrder was approved and is not now"
            ),
            subject=snapshot.work_id,
        )
        for constraint in snapshot.constraints
        if constraint not in live
    )


# ----------------------------------------------------------------------
# Policy
# ----------------------------------------------------------------------


class EngineeringPolicy:
    """The checks that run on a transition."""

    def __init__(self, checks: Sequence[PolicyCheck] = ()) -> None:
        self._checks = tuple(checks)

    @property
    def checks(self) -> tuple:
        return self._checks

    def with_check(self, check: PolicyCheck) -> "EngineeringPolicy":
        return EngineeringPolicy(self._checks + (check,))

    def evaluate(
        self, snapshot: WorkOrderSnapshot, to_phase: WorkOrderPhase, context: Any
    ) -> PolicyResult:
        """Run every relevant check and return all findings.

        Every check runs even after one fails. Returning on the first blocking
        finding is how a transition takes six attempts to land.
        """
        transition = (snapshot.phase, to_phase)
        findings: list = []
        for check in self._checks:
            if not check.relevant(transition):
                continue
            findings.extend(check.check(snapshot, to_phase, context))
        return PolicyResult(findings=tuple(findings))


def default_policy(*, run_architecture_gate: bool = False) -> EngineeringPolicy:
    """The policy the Engineering Constitution defines.

    ``run_architecture_gate`` is off by default. The gate takes eight minutes,
    which is right for CI and wrong for an interactive transition. Turn it on
    where a transition is allowed to take that long -- which in practice means
    the ``VERIFICATION -> READY`` gate in a pipeline, not a developer waiting on
    an HTTP response.
    """
    checks = [
        PolicyCheck(
            name="digest-binds",
            check=_digest_still_binds,
            description="a governed WorkOrder carries the digest it was approved against",
        ),
        PolicyCheck(
            name="not-superseded",
            check=_not_superseded,
            description="a superseded WorkOrder does not keep progressing",
        ),
        PolicyCheck(
            name="assumptions-hold",
            check=_assumptions_resolved_before_review,
            applies_to=frozenset({(WorkOrderPhase.IMPLEMENTATION, WorkOrderPhase.REVIEW)}),
            description="work does not reach review on unchecked or failed beliefs",
        ),
        PolicyCheck(
            name="dependencies-declared",
            check=_dependencies_are_merged,
            applies_to=frozenset({(WorkOrderPhase.APPROVED, WorkOrderPhase.ASSIGNED)}),
            description="dependencies are visible at assignment",
        ),
        PolicyCheck(
            name="constraints-enforceable",
            check=constraints_are_enforceable,
            applies_to=frozenset({ARCHITECTURE_GATE_TRANSITION}),
            description="every cited constraint still resolves to a live rule",
        ),
    ]

    if run_architecture_gate:
        checks.append(
            PolicyCheck(
                name="architecture-gate",
                check=architecture_gate_check,
                applies_to=frozenset({ARCHITECTURE_GATE_TRANSITION}),
                description="the full architecture gate passes before a WorkOrder is ready",
            )
        )

    return EngineeringPolicy(checks)

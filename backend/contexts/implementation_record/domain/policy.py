"""Completion policy: whether a record may be submitted to Review.

The aggregate enforces per-item invariants. This decides whether the whole is
submittable, which is a different question -- a record where every individual
claim is well-formed can still be an inadequate submission.

Kept out of the aggregate so the service can report every failure at once. A
completion that refuses one reason at a time takes six attempts to land, and the
sixth attempt is made by someone who has stopped reading the refusals.

The rules, and the failure each prevents
-----------------------------------------
**C1 something changed.** A record with no files claims work that left no trace.

**C2 nothing outside the radius.** The scope rule, checked again at completion
because a radius can be *narrowed* by re-approval after a file was recorded.

**C3 every assumption resolved.** An unchecked belief reaching Review is the gap
the WorkOrder's assumption field exists to close.

**C4 no contradicted assumption.** The correct response is a ``PREMISE_FALSE``
rejection, not an implementation that works around a false premise.

**C5 at least one claim.** A record with no claims gives Verification nothing to
verify, and a verification with nothing to verify reports complete having
established nothing -- the most dangerous outcome available.

**C6 tests were run and are green.** ``NOT_RUN`` is distinguished from
``FAILED``: the first says nothing about the work, the second says it is wrong.

**C7 builds are green.**

**C8 risks above LOW are mitigated.** Enforced by the value object too; repeated
here because a record assembled from storage bypasses no invariant but a future
loosening of one would go unnoticed with a single check.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Optional, Sequence

from backend.contexts.implementation_record.domain.outcomes import ExecutionStatus
from backend.contexts.implementation_record.domain.record import (
    ImplementationRecord,
    ImplementationStatus,
)

__all__ = ["Severity", "PolicyFinding", "PolicyReport", "CompletionPolicy", "default_policy"]


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
    def may_complete(self) -> bool:
        return not self.blocking


class CompletionPolicy:
    """Decides whether a record may be submitted."""

    def __init__(self, *, require_tests: bool = True) -> None:
        self._require_tests = require_tests

    def evaluate(self, record: ImplementationRecord) -> PolicyReport:
        """Every finding, not just the first."""
        findings: list = []

        if record.status is not ImplementationStatus.IN_PROGRESS:
            findings.append(
                PolicyFinding(
                    rule="C0-open",
                    severity=Severity.BLOCKING,
                    detail=f"the record is {record.status.value}, not in progress",
                    subject=str(record.implementation_id),
                )
            )

        # C1 -- something changed.
        if record.changes.is_empty:
            findings.append(
                PolicyFinding(
                    rule="C1-something-changed",
                    severity=Severity.BLOCKING,
                    detail=(
                        "no files were changed; a record claiming work that left no "
                        "trace cannot be reviewed"
                    ),
                )
            )

        # C2 -- nothing outside the radius.
        for path in record.paths_outside_radius:
            findings.append(
                PolicyFinding(
                    rule="C2-within-blast-radius",
                    severity=Severity.BLOCKING,
                    detail=(
                        f"{path!r} is outside the declared blast radius; expand the "
                        "radius through re-approval rather than submitting past it"
                    ),
                    subject=path,
                )
            )

        # A declared-but-untouched pattern weakens conflict detection for every
        # other WorkOrder, but it is not a reason to refuse this one.
        for pattern in record.untouched_radius_patterns:
            findings.append(
                PolicyFinding(
                    rule="C2-radius-not-fully-used",
                    severity=Severity.ADVISORY,
                    detail=(
                        f"{pattern!r} was declared but nothing under it changed; the "
                        "radius claimed more than the work needed"
                    ),
                    subject=pattern,
                )
            )

        # C3 -- every assumption resolved.
        for assumption_id in record.unresolved_assumptions:
            findings.append(
                PolicyFinding(
                    rule="C3-assumptions-resolved",
                    severity=Severity.BLOCKING,
                    detail=(
                        "the WorkOrder declared this assumption and it was never "
                        "checked; an unverified belief reaching Review is the gap the "
                        "field exists to close"
                    ),
                    subject=assumption_id,
                )
            )

        # C4 -- no contradicted assumption.
        for resolution in record.contradicted_assumptions:
            findings.append(
                PolicyFinding(
                    rule="C4-no-false-premise",
                    severity=Severity.BLOCKING,
                    detail=(
                        f"assumption was contradicted: {resolution.statement[:60]!r}; the "
                        "correct response is a PREMISE_FALSE rejection, not an "
                        "implementation that works around it"
                    ),
                    subject=resolution.assumption_id,
                )
            )

        for resolution in record.blocking_assumptions:
            if resolution.outcome.implies_rejection:
                continue
            findings.append(
                PolicyFinding(
                    rule="C4-no-unverifiable-premise",
                    severity=Severity.BLOCKING,
                    detail=(
                        "the assumption could not be verified either way; proceeding on "
                        "a belief nobody could check carries the same risk as one found "
                        "false, minus the knowledge that it was"
                    ),
                    subject=resolution.assumption_id,
                )
            )

        # C5 -- at least one claim.
        if not record.claims:
            findings.append(
                PolicyFinding(
                    rule="C5-at-least-one-claim",
                    severity=Severity.BLOCKING,
                    detail=(
                        "no claims were made; a verification with nothing to verify "
                        "reports complete having established nothing"
                    ),
                )
            )

        # C6 -- tests run and green.
        if self._require_tests:
            if not record.test_executions:
                findings.append(
                    PolicyFinding(
                        rule="C6-tests-run",
                        severity=Severity.BLOCKING,
                        detail="no test run was recorded",
                    )
                )
            for execution in record.failing_tests:
                blocking = execution.status is not ExecutionStatus.NOT_RUN
                findings.append(
                    PolicyFinding(
                        rule="C6-tests-green",
                        severity=Severity.BLOCKING,
                        detail=(
                            f"{execution.command!r} is {execution.status.value}"
                            + (
                                f" with {execution.failed} failed and {execution.errors} errored"
                                if blocking
                                else "; a suite that was never run says nothing about the work"
                            )
                        ),
                        subject=execution.command,
                    )
                )

        # C7 -- builds green.
        for result in record.failing_builds:
            findings.append(
                PolicyFinding(
                    rule="C7-builds-green",
                    severity=Severity.BLOCKING,
                    detail=f"{result.name!r} is {result.status.value}: {result.detail}",
                    subject=result.name,
                )
            )

        # C8 -- risks mitigated.
        for risk in record.unmitigated_risks:
            findings.append(
                PolicyFinding(
                    rule="C8-risks-mitigated",
                    severity=Severity.BLOCKING,
                    detail=(
                        f"a {risk.level.value} risk was declared with no mitigation: "
                        f"{risk.statement[:60]!r}"
                    ),
                    subject=str(risk.risk_id),
                )
            )

        # Advisory: a claim a verifier will have to attack rather than observe.
        for claim in record.claims:
            if claim.claim_type.needs_adversarial_verification:
                findings.append(
                    PolicyFinding(
                        rule="C9-absence-claim-declared",
                        severity=Severity.ADVISORY,
                        detail=(
                            "this is an absence claim; settling it requires constructing "
                            "the violation, not observing a green suite"
                        ),
                        subject=str(claim.claim_id),
                    )
                )

        return PolicyReport(findings=tuple(findings))


def default_policy() -> CompletionPolicy:
    """The policy the Engineering Constitution defines."""
    return CompletionPolicy(require_tests=True)

"""Plan policy: whether a plan is sound enough to hand to execution.

The aggregate enforces what is *structurally* true -- the graph is acyclic, every
task serves a goal, the risk is not understated. This decides what is
*advisable*, which is a different question: a plan every invariant permits can
still be one nobody should run.

Kept out of the aggregate so the service can report every failure at once. A plan
refused one reason at a time takes five attempts to land, and the fifth is made
by someone who has stopped reading the refusals.

The rules, and the failure each prevents
-----------------------------------------
**L0 the plan is open, and the move is legal.**

**L1 the seven elements are present.** Re-checked here so the report carries it
alongside everything else rather than raising first.

**L2 the graph is sound.** Re-checked for the same reason: the aggregate raises
on the first cycle, and a report naming every problem at once is what lets a plan
be fixed in one pass.

**L3 destructive work is checkpointed.** A plan that destroys something and takes
no checkpoint before it cannot be resumed after a failure -- only restarted, over
a world that has already changed.

**L4 a severe plan names a mitigation for every severe risk.**

**L5 a blast-radius outlier is visible.** Advisory: one task whose failure
strands most of the plan is a single point of failure worth knowing about before
committing, not after.

**L6 a sequential plan that could be parallel.** Advisory: the graph permits
concurrency the strategy does not use. Sometimes deliberate, always worth
stating.

**L7 accepted-irreversible tasks are listed.** Advisory: they are legal and
somebody accepted them, and the list is what a reviewer scans first.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Optional

from backend.contracts.execution import SideEffectClass
from backend.contexts.planner.domain.errors import CyclicDependency, DanglingDependency
from backend.contexts.planner.domain.graph import DependencyGraph
from backend.contexts.planner.domain.risk import implied_floor
from backend.contexts.planner.domain.status import (
    PlanStatus,
    is_legal_transition,
    permitted_from,
    refusal_reason,
)

__all__ = [
    "Severity",
    "PolicyFinding",
    "PolicyReport",
    "PlanPolicy",
    "default_policy",
    "BLAST_OUTLIER_RATIO",
]

#: A task whose failure would strand more than this share of the plan is called
#: out. A judgement, named so it can be argued with rather than hidden in a
#: conditional.
BLAST_OUTLIER_RATIO = 0.5


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
    def may_proceed(self) -> bool:
        return not self.blocking


class PlanPolicy:
    """Decides whether a plan is sound enough to validate or approve."""

    def __init__(self, *, require_destructive_checkpoint: bool = True) -> None:
        self._require_destructive_checkpoint = require_destructive_checkpoint

    @property
    def requires_destructive_checkpoint(self) -> bool:
        return self._require_destructive_checkpoint

    def evaluate(self, plan, to_status: PlanStatus) -> PolicyReport:
        """Every finding, not just the first."""
        findings: list = []

        # L0 -- open, and the move is legal.
        if not plan.status.is_open:
            findings.append(
                PolicyFinding(
                    rule="L0-plan-open",
                    severity=Severity.BLOCKING,
                    detail=(
                        f"the plan is {plan.status.value}; "
                        + (
                            refusal_reason(plan.status, to_status)
                            or "it may no longer be changed"
                        )
                    ),
                    subject=str(plan.plan_id),
                )
            )
            return PolicyReport(findings=tuple(findings))

        if not is_legal_transition(plan.status, to_status):
            findings.append(
                PolicyFinding(
                    rule="L0-legal-transition",
                    severity=Severity.BLOCKING,
                    detail=(
                        refusal_reason(plan.status, to_status)
                        or f"{plan.status.value} may only move to: "
                        f"{', '.join(permitted_from(plan.status))}"
                    ),
                    subject=to_status.value,
                )
            )

        if to_status not in (PlanStatus.VALIDATED, PlanStatus.APPROVED):
            return PolicyReport(findings=tuple(findings))

        # L1 -- the seven elements.
        for element in plan.missing_elements:
            findings.append(
                PolicyFinding(
                    rule="L1-required-elements",
                    severity=Severity.BLOCKING,
                    detail=(
                        f"no {element} recorded; a plan without one cannot be handed "
                        "to execution"
                    ),
                    subject=element,
                )
            )

        # L2 -- the graph, reported rather than raised.
        graph = None
        try:
            graph = DependencyGraph.of(plan.tasks)
        except CyclicDependency as exc:
            findings.append(
                PolicyFinding(
                    rule="L2-acyclic",
                    severity=Severity.BLOCKING,
                    detail=str(exc),
                    subject=" -> ".join(exc.cycle),
                )
            )
        except DanglingDependency as exc:
            findings.append(
                PolicyFinding(
                    rule="L2-dependencies-resolve",
                    severity=Severity.BLOCKING,
                    detail=str(exc),
                    subject=exc.task_id,
                )
            )

        for orphan in plan.orphan_tasks:
            findings.append(
                PolicyFinding(
                    rule="L2-task-serves-a-goal",
                    severity=Severity.BLOCKING,
                    detail=(
                        f"task {orphan!r} serves no goal; work that traces to nothing "
                        "asked for still spends the blast radius and the time"
                    ),
                    subject=orphan,
                )
            )

        for uncovered in plan.uncovered_criteria:
            findings.append(
                PolicyFinding(
                    rule="L2-criterion-covered",
                    severity=Severity.BLOCKING,
                    detail=(
                        f"success criterion {uncovered!r} is covered by no goal; the "
                        "plan could complete every task and still not achieve it"
                    ),
                    subject=uncovered,
                )
            )

        for idle in plan.idle_goals:
            findings.append(
                PolicyFinding(
                    rule="L2-goal-has-tasks",
                    severity=Severity.BLOCKING,
                    detail=f"goal {idle} has no tasks working towards it",
                    subject=idle,
                )
            )

        # L3 -- destructive work is checkpointed.
        if self._require_destructive_checkpoint:
            destructive = [
                t.task_id
                for t in plan.tasks
                if t.side_effect is SideEffectClass.DESTRUCTIVE
            ]
            if destructive and not plan.execution_strategy.checkpoint_after:
                findings.append(
                    PolicyFinding(
                        rule="L3-destructive-checkpointed",
                        severity=Severity.BLOCKING,
                        detail=(
                            f"{len(destructive)} destructive task(s) and no checkpoint "
                            "declared; a plan that destroys something and checkpoints "
                            "nothing cannot be resumed after a failure, only restarted "
                            "over a world that has already changed"
                        ),
                        subject=destructive[0],
                    )
                )

        # L4 -- severe risks are mitigated.
        if plan.risk_assessment is not None:
            for risk in plan.risk_assessment.unmitigated:
                findings.append(
                    PolicyFinding(
                        rule="L4-severe-risk-mitigated",
                        severity=Severity.BLOCKING,
                        detail=(
                            f"a {risk.level.value} risk has no mitigation: "
                            f"{risk.statement[:60]!r}"
                        ),
                        subject=str(risk.risk_id),
                    )
                )

            floor, driver = implied_floor(plan.tasks)
            if plan.risk_assessment.overall.rank < floor.rank:
                findings.append(
                    PolicyFinding(
                        rule="L4-risk-not-understated",
                        severity=Severity.BLOCKING,
                        detail=(
                            f"declared {plan.risk_assessment.overall.value!r} but the "
                            f"plan contains {driver}, implying at least {floor.value!r}"
                        ),
                        subject=floor.value,
                    )
                )

        # L5 -- a blast-radius outlier.
        if graph is not None and len(graph) > 2:
            for task_id in graph.task_ids:
                stranded = graph.blast_of(task_id)
                if stranded > len(graph) * BLAST_OUTLIER_RATIO:
                    findings.append(
                        PolicyFinding(
                            rule="L5-blast-radius-outlier",
                            severity=Severity.ADVISORY,
                            detail=(
                                f"a failure at {task_id!r} would strand {stranded} of "
                                f"{len(graph)} tasks; worth knowing before committing "
                                "rather than after"
                            ),
                            subject=task_id,
                        )
                    )

        # L6 -- unused concurrency.
        if (
            graph is not None
            and not plan.execution_strategy.is_concurrent
            and graph.widest_layer > 1
        ):
            findings.append(
                PolicyFinding(
                    rule="L6-unused-concurrency",
                    severity=Severity.ADVISORY,
                    detail=(
                        f"the graph permits {graph.widest_layer} tasks at once but the "
                        "strategy is sequential; sometimes deliberate, worth stating "
                        "either way"
                    ),
                    subject=str(graph.widest_layer),
                )
            )

        # L7 -- accepted irreversible work, listed.
        for task in plan.irreversible_tasks:
            findings.append(
                PolicyFinding(
                    rule="L7-accepted-irreversible",
                    severity=Severity.ADVISORY,
                    detail=(
                        f"task {task.task_id!r} cannot be undone and was accepted by "
                        f"{task.irreversible_accepted_by!r}"
                    ),
                    subject=task.task_id,
                )
            )

        return PolicyReport(findings=tuple(findings))


def default_policy() -> PlanPolicy:
    """The policy the Constitution defines."""
    return PlanPolicy(require_destructive_checkpoint=True)

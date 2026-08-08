"""The Plan aggregate: how an approved mandate would be achieved.

A plan is the answer to *how*, produced from a mission and an approved intent and
handed to execution. This context produces nothing else.

What the aggregate enforces that nothing smaller can
------------------------------------------------------
The value objects each enforce what is visible locally. Four rules need the whole
plan, and this is the only place all of it is visible:

* **The graph is acyclic and complete.** ``TaskRef`` says the whole-graph cycle
  check belongs to whoever holds the graph. That is here.
* **Every task serves a goal.** Work that traces to no goal is work nobody asked
  for, and it still spends the blast radius and the time.
* **Every criterion is covered by a goal.** Otherwise the plan can complete every
  task and still not achieve what was asked for -- the failure a plan exists to
  make impossible.
* **The declared risk is not below what the tasks imply.** Risk that can be
  argued down without changing anything else is a mood, not an assessment.

Bound to the mandate it was built from
---------------------------------------
A plan carries the intent's id *and its approval digest*. A plan is a statement
about *that* mandate; if the intent were revised, its digest changes and a plan
quoting the old one is visibly about something else. Same binding Review uses for
the implementation it reads.

What this aggregate refuses to be
----------------------------------
It has no execution state, no results, no task outcomes, no tool invocations.
Every field describes work that has not happened. ``PlanTask.as_task_ref``
projects onto the published vocabulary with every task ``PENDING``, because a
planner that could emit ``SUCCEEDED`` would be reporting execution it did not do.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from datetime import datetime, timezone
from typing import Any, Final, Optional

from backend.contracts._contract import Contract
from backend.contracts.approval import HashAlgorithm, PayloadDigest
from backend.contracts.errors import ContractViolation
from backend.contexts.planner.domain.errors import (
    DigestMismatch,
    DigestNotComputed,
    DuplicateTask,
    GoalWithoutTasks,
    IllegalPlanTransition,
    IncompletePlan,
    OrphanTask,
    PlanApproved,
    PlanIsSuperseded,
    RollbackNotDeclared,
    UncoveredCriterion,
    UnknownGoal,
    UnknownTask,
)
from backend.contexts.planner.domain.goals import PlanGoal, SuccessCriterionRef
from backend.contexts.planner.domain.graph import DependencyGraph
from backend.contexts.planner.domain.identifiers import GoalId, PlanId
from backend.contexts.planner.domain.risk import RiskAssessment, implied_floor
from backend.contexts.planner.domain.status import (
    PlanStatus,
    is_legal_transition,
    permitted_from,
)
from backend.contexts.planner.domain.strategy import (
    ExecutionStrategy,
    RollbackKind,
    RollbackStrategy,
)
from backend.contexts.planner.domain.tasks import PlanTask
from backend.platform.hashing import compute_digest, digests_match

__all__ = [
    "Plan",
    "ARTIFACT_KIND",
    "CANONICAL_FORM_VERSION",
    "GOVERNED_FIELDS",
    "REQUIRED_ELEMENTS",
]

ARTIFACT_KIND: Final[str] = "cortexprime.planner.plan"
CANONICAL_FORM_VERSION: Final[int] = 1

#: What the approval digest covers. Excludes status, timestamps and the digest
#: itself -- superseding an approved plan is legal and must not invalidate it.
GOVERNED_FIELDS: Final[tuple] = (
    "plan_id",
    "version",
    "mission_id",
    "intent_id",
    "intent_digest",
    "title",
    "goals",
    "tasks",
    "success_criteria",
    "execution_strategy",
    "rollback_strategy",
    "risk_assessment",
    "supersedes",
    "rejection_reason",
)

#: The seven the rules name. A refusal reports these names.
REQUIRED_ELEMENTS: Final[tuple] = (
    "goals",
    "tasks",
    "dependencies",
    "risk",
    "success criteria",
    "execution strategy",
    "rollback strategy",
)


@dataclass(frozen=True)
class Plan(Contract):
    """One version of how a mission's approved intent would be achieved."""

    CONTRACT_NAME = "cortexprime.planner.plan_aggregate"

    plan_id: PlanId
    mission_id: str
    intent_id: str
    intent_digest: str
    title: str

    version: int = 1
    goals: tuple = ()
    tasks: tuple = ()
    success_criteria: frozenset = field(default_factory=frozenset)
    execution_strategy: ExecutionStrategy = field(default_factory=ExecutionStrategy)
    rollback_strategy: RollbackStrategy = field(
        default_factory=RollbackStrategy.none_required
    )
    risk_assessment: Optional[RiskAssessment] = None

    status: PlanStatus = PlanStatus.DRAFT
    validated_at: Optional[datetime] = None
    approved_at: Optional[datetime] = None
    approved_by: Optional[str] = None
    rejection_reason: Optional[str] = None
    digest: Optional[str] = None
    supersedes: Optional[PlanId] = None
    superseded_by: Optional[PlanId] = None
    planned_by: str = "planner"
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    # ------------------------------------------------------------------
    # Invariants
    # ------------------------------------------------------------------

    def __post_init__(self) -> None:
        if not isinstance(self.plan_id, PlanId):
            raise ContractViolation("plan_id must be a PlanId")

        for label, value in (
            ("mission_id", self.mission_id),
            ("intent_id", self.intent_id),
            ("intent_digest", self.intent_digest),
            ("title", self.title),
        ):
            if not isinstance(value, str) or not value.strip():
                raise ContractViolation(
                    f"{label} must be non-blank text; a plan that cannot say which "
                    "mandate it was built from is not a plan for anything"
                )

        if not isinstance(self.version, int) or self.version < 1:
            raise ContractViolation("version must be a positive integer starting at 1")

        for label, items, expected in (
            ("goals", self.goals, PlanGoal),
            ("tasks", self.tasks, PlanTask),
        ):
            if not isinstance(items, tuple):
                raise ContractViolation(f"{label} must be a tuple")
            for item in items:
                if not isinstance(item, expected):
                    raise ContractViolation(
                        f"{label} contains {item!r}, which is not a {expected.__name__}"
                    )

        task_ids = [t.task_id for t in self.tasks]
        if len(set(task_ids)) != len(task_ids):
            duplicate = next(t for t in task_ids if task_ids.count(t) > 1)
            raise DuplicateTask(duplicate)

        goal_ids = [str(g.goal_id) for g in self.goals]
        if len(set(goal_ids)) != len(goal_ids):
            raise ContractViolation("goals contains duplicate ids")

        if not isinstance(self.success_criteria, (frozenset, set)):
            raise ContractViolation("success_criteria must be a set")
        object.__setattr__(
            self,
            "success_criteria",
            frozenset(
                c if isinstance(c, SuccessCriterionRef) else SuccessCriterionRef(c)
                for c in self.success_criteria
            ),
        )

        if not isinstance(self.execution_strategy, ExecutionStrategy):
            raise ContractViolation("execution_strategy must be an ExecutionStrategy")
        if not isinstance(self.rollback_strategy, RollbackStrategy):
            raise ContractViolation("rollback_strategy must be a RollbackStrategy")
        if self.risk_assessment is not None and not isinstance(
            self.risk_assessment, RiskAssessment
        ):
            raise ContractViolation("risk_assessment must be a RiskAssessment")

        # The graph is built here rather than stored, so it is checked on every
        # construction -- including one assembled from storage.
        if self.tasks:
            DependencyGraph.of(self.tasks)

        # Every task names goals the plan actually has.
        known_goals = {str(g.goal_id) for g in self.goals}
        for task in self.tasks:
            unknown = {g for g in task.goal_ids if g not in known_goals}
            if unknown:
                raise UnknownGoal(
                    plan_id=str(self.plan_id), goal_id=", ".join(sorted(unknown))
                )

        # Checkpoints name tasks the plan contains.
        known_tasks = set(task_ids)
        for checkpoint in self.execution_strategy.checkpoint_after:
            if checkpoint not in known_tasks:
                raise UnknownTask(plan_id=str(self.plan_id), task_id=checkpoint)

        if not isinstance(self.status, PlanStatus):
            raise ContractViolation("status must be a PlanStatus")

        # Validation and approval are statements about a complete, coherent plan.
        if self.status in (PlanStatus.VALIDATED, PlanStatus.APPROVED):
            missing = self._missing_elements()
            if missing:
                raise IncompletePlan(plan_id=str(self.plan_id), missing=missing)
            self._assert_coherent()

        if self.status is PlanStatus.VALIDATED and self.validated_at is None:
            raise ContractViolation("a validated plan must record when")

        if self.status is PlanStatus.APPROVED:
            if not self.digest:
                raise ContractViolation(
                    "an approved plan must carry the digest computed at approval; "
                    "without it the plan execution acts on cannot be shown to be the "
                    "one that was approved"
                )
            if self.approved_at is None:
                raise ContractViolation("an approved plan must record when")
            if not (self.approved_by and self.approved_by.strip()):
                raise ContractViolation(
                    "an approved plan must name who approved it; an unattributed "
                    "authorisation has nobody accountable for it"
                )

        if self.status is PlanStatus.REJECTED and not (
            self.rejection_reason and self.rejection_reason.strip()
        ):
            raise ContractViolation(
                "a rejected plan must say why; the next version is built from the "
                "reason, and an unexplained refusal produces the same plan again"
            )

        if self.status is PlanStatus.SUPERSEDED and self.superseded_by is None:
            raise ContractViolation("a superseded plan must name its successor")

        for label in ("supersedes", "superseded_by"):
            value = getattr(self, label)
            if value is not None and not isinstance(value, PlanId):
                raise ContractViolation(f"{label} must be a PlanId")

        if self.version > 1 and self.supersedes is None:
            raise ContractViolation(
                f"version {self.version} must name the version it supersedes; a "
                "version chain with a gap cannot be walked back"
            )

        for label in ("created_at", "validated_at", "approved_at"):
            value = getattr(self, label)
            if value is not None and value.tzinfo is None:
                raise ContractViolation(f"{label} must be timezone-aware")

    # ------------------------------------------------------------------
    # Whole-plan coherence
    # ------------------------------------------------------------------

    def _missing_elements(self) -> tuple:
        missing: list = []
        if not self.goals:
            missing.append("goals")
        if not self.tasks:
            missing.append("tasks")
        if not self.success_criteria:
            missing.append("success criteria")
        if self.risk_assessment is None:
            missing.append("risk")
        # Dependencies, execution strategy and rollback strategy always have a
        # value; whether they are *adequate* is coherence, checked below.
        return tuple(missing)

    def _assert_coherent(self) -> None:
        """The four checks only the whole plan can make."""
        orphans = [t.task_id for t in self.tasks if not t.goal_ids]
        if orphans:
            raise OrphanTask(orphans)

        worked_goals = {g for t in self.tasks for g in t.goal_ids}
        idle = [str(g.goal_id) for g in self.goals if str(g.goal_id) not in worked_goals]
        if idle:
            raise GoalWithoutTasks(idle)

        covered = {c for g in self.goals for c in g.criterion_ids}
        uncovered = [c.criterion_id for c in self.success_criteria if c.criterion_id not in covered]
        if uncovered:
            raise UncoveredCriterion(uncovered)

        # Constitution P2 at the plan level.
        mutating = [t.task_id for t in self.tasks if t.mutates]
        if mutating and self.rollback_strategy.kind is RollbackKind.NONE_REQUIRED:
            raise RollbackNotDeclared(
                mutating=mutating, strategy=self.rollback_strategy.kind.value
            )

        if self.risk_assessment is not None:
            self.risk_assessment.assert_covers(self.tasks)

    # ------------------------------------------------------------------
    # Queries
    # ------------------------------------------------------------------

    @property
    def graph(self) -> DependencyGraph:
        return DependencyGraph.of(self.tasks)

    @property
    def missing_elements(self) -> tuple:
        return self._missing_elements()

    @property
    def is_complete(self) -> bool:
        return not self._missing_elements()

    @property
    def is_open(self) -> bool:
        return self.status.is_open

    @property
    def is_executable(self) -> bool:
        return self.status.is_executable

    @property
    def mutating_tasks(self) -> tuple:
        return tuple(t for t in self.tasks if t.mutates)

    @property
    def irreversible_tasks(self) -> tuple:
        return tuple(t for t in self.tasks if t.is_accepted_irreversible)

    @property
    def orphan_tasks(self) -> tuple:
        return tuple(t.task_id for t in self.tasks if not t.goal_ids)

    @property
    def uncovered_criteria(self) -> tuple:
        covered = {c for g in self.goals for c in g.criterion_ids}
        return tuple(
            sorted(c.criterion_id for c in self.success_criteria if c.criterion_id not in covered)
        )

    @property
    def idle_goals(self) -> tuple:
        worked = {g for t in self.tasks for g in t.goal_ids}
        return tuple(sorted(str(g.goal_id) for g in self.goals if str(g.goal_id) not in worked))

    @property
    def implied_risk_floor(self) -> tuple:
        return implied_floor(self.tasks)

    def task(self, task_id: str) -> Optional[PlanTask]:
        for candidate in self.tasks:
            if candidate.task_id == task_id:
                return candidate
        return None

    def goal(self, goal_id: GoalId) -> Optional[PlanGoal]:
        for candidate in self.goals:
            if candidate.goal_id == goal_id:
                return candidate
        return None

    def tasks_for_goal(self, goal_id: str) -> tuple:
        return tuple(t for t in self.tasks if goal_id in t.goal_ids)

    def permitted_transitions(self) -> tuple:
        return permitted_from(self.status)

    def as_task_refs(self) -> tuple:
        """The plan projected onto the published task vocabulary."""
        return tuple(t.as_task_ref(self.mission_id) for t in self.tasks)

    # ------------------------------------------------------------------
    # Digest
    # ------------------------------------------------------------------

    def digest_payload(self) -> dict[str, Any]:
        return {
            "__artifact__": ARTIFACT_KIND,
            "__canonical_form__": CANONICAL_FORM_VERSION,
            "plan_id": str(self.plan_id),
            "version": self.version,
            "mission_id": self.mission_id,
            "intent_id": self.intent_id,
            "intent_digest": self.intent_digest,
            "title": self.title,
            "goals": sorted(
                (
                    {
                        "goal_id": str(g.goal_id),
                        "statement": g.statement,
                        "satisfies": list(g.criterion_ids),
                    }
                    for g in self.goals
                ),
                key=lambda item: item["goal_id"],
            ),
            "tasks": sorted(
                (
                    {
                        "task_id": t.task_id,
                        "purpose": t.purpose,
                        "goal_ids": sorted(t.goal_ids),
                        "depends_on": sorted(t.depends_on),
                        "side_effect": t.side_effect.value,
                        "reversal": (
                            {
                                "compensating_task": t.reversal.compensating_task,
                                "inverse_action": t.reversal.inverse_action,
                            }
                            if t.reversal
                            else None
                        ),
                        "irreversible_accepted_by": t.irreversible_accepted_by,
                        "execution_key": t.execution_key,
                    }
                    for t in self.tasks
                ),
                key=lambda item: item["task_id"],
            ),
            "success_criteria": sorted(c.criterion_id for c in self.success_criteria),
            "execution_strategy": {
                "mode": self.execution_strategy.mode.value,
                "on_failure": self.execution_strategy.on_failure.value,
                "max_parallelism": self.execution_strategy.max_parallelism,
                "checkpoint_after": sorted(self.execution_strategy.checkpoint_after),
            },
            "rollback_strategy": {
                "kind": self.rollback_strategy.kind.value,
                "description": self.rollback_strategy.description,
                "accepted_by": self.rollback_strategy.accepted_by,
                "snapshot_of": sorted(self.rollback_strategy.snapshot_of),
            },
            "risk_assessment": (
                {
                    "overall": self.risk_assessment.overall.value,
                    "assessed_by": self.risk_assessment.assessed_by,
                    "risks": sorted(
                        (
                            {
                                "risk_id": str(r.risk_id),
                                "statement": r.statement,
                                "level": r.level.value,
                                "likelihood": r.likelihood.value,
                                "mitigation": r.mitigation,
                            }
                            for r in self.risk_assessment.risks
                        ),
                        key=lambda item: item["risk_id"],
                    ),
                }
                if self.risk_assessment
                else None
            ),
            "supersedes": str(self.supersedes) if self.supersedes else None,
            "rejection_reason": self.rejection_reason,
        }

    def compute_digest(self, algorithm: HashAlgorithm = HashAlgorithm.SHA256) -> PayloadDigest:
        return compute_digest(self.digest_payload(), algorithm)

    def verify_digest(self) -> None:
        if not self.digest:
            raise DigestNotComputed(str(self.plan_id))
        recomputed = self.compute_digest()
        if not digests_match(
            recomputed, PayloadDigest(algorithm=recomputed.algorithm, value=self.digest)
        ):
            raise DigestMismatch(
                plan_id=str(self.plan_id),
                recorded=self.digest,
                recomputed=recomputed.value,
            )

    # ------------------------------------------------------------------
    # Guards
    # ------------------------------------------------------------------

    def _require_open(self, operation: str) -> None:
        if self.status is PlanStatus.SUPERSEDED:
            raise PlanIsSuperseded(
                plan_id=str(self.plan_id), successor=str(self.superseded_by)
            )
        if not self.status.is_open:
            raise PlanApproved(plan_id=str(self.plan_id), operation=operation)

    def _edited(self, **changes: Any) -> "Plan":
        """Apply a change, returning a validated plan to draft.

        The demotion happens in the same construction as the change, never a
        second one -- removing a task from a validated plan would otherwise build
        an intermediate that is validated and incoherent, which its own invariant
        refuses, correctly.
        """
        if self.status is PlanStatus.VALIDATED:
            return replace(self, status=PlanStatus.DRAFT, validated_at=None, **changes)
        return replace(self, **changes)

    # ------------------------------------------------------------------
    # Building the plan
    # ------------------------------------------------------------------

    def add_goal(self, goal: PlanGoal) -> "Plan":
        self._require_open("adding a goal")
        if not isinstance(goal, PlanGoal):
            raise ContractViolation("goal must be a PlanGoal")
        if any(g.goal_id == goal.goal_id for g in self.goals):
            raise ContractViolation(f"goal {goal.goal_id} is already in the plan")
        return self._edited(goals=self.goals + (goal,))

    def add_task(self, task: PlanTask) -> "Plan":
        """Add a task. The graph is re-checked, so a cycle is refused here."""
        self._require_open("adding a task")
        if not isinstance(task, PlanTask):
            raise ContractViolation("task must be a PlanTask")
        if self.task(task.task_id) is not None:
            raise DuplicateTask(task.task_id)
        return self._edited(tasks=self.tasks + (task,))

    def remove_task(self, task_id: str) -> "Plan":
        self._require_open("removing a task")
        if self.task(task_id) is None:
            raise UnknownTask(plan_id=str(self.plan_id), task_id=task_id)
        return self._edited(
            tasks=tuple(t for t in self.tasks if t.task_id != task_id)
        )

    def add_dependency(self, task_id: str, depends_on: str) -> "Plan":
        """Make one task wait for another.

        The cycle check runs on the resulting graph, so the refusal arrives while
        the person adding the edge still remembers why they wanted it.
        """
        self._require_open("adding a dependency")
        task = self.task(task_id)
        if task is None:
            raise UnknownTask(plan_id=str(self.plan_id), task_id=task_id)
        if self.task(depends_on) is None:
            raise UnknownTask(plan_id=str(self.plan_id), task_id=depends_on)
        if depends_on in task.depends_on:
            return self
        updated = replace(task, depends_on=task.depends_on + (depends_on,))
        return self._edited(
            tasks=tuple(updated if t.task_id == task_id else t for t in self.tasks)
        )

    def declare_criteria(self, criteria) -> "Plan":
        self._require_open("declaring success criteria")
        refs = frozenset(
            c if isinstance(c, SuccessCriterionRef) else SuccessCriterionRef(c)
            for c in criteria
        )
        if not refs:
            raise ContractViolation(
                "a plan must carry the criteria it is answerable for; one with none "
                "cannot be shown to serve what was asked for"
            )
        return self._edited(success_criteria=self.success_criteria | refs)

    def set_execution_strategy(self, strategy: ExecutionStrategy) -> "Plan":
        self._require_open("setting the execution strategy")
        if not isinstance(strategy, ExecutionStrategy):
            raise ContractViolation("strategy must be an ExecutionStrategy")
        return self._edited(execution_strategy=strategy)

    def set_rollback_strategy(self, strategy: RollbackStrategy) -> "Plan":
        self._require_open("setting the rollback strategy")
        if not isinstance(strategy, RollbackStrategy):
            raise ContractViolation("strategy must be a RollbackStrategy")
        return self._edited(rollback_strategy=strategy)

    def assess_risk(self, assessment: RiskAssessment) -> "Plan":
        """Record the risk assessment, refusing one below what the tasks imply."""
        self._require_open("assessing risk")
        if not isinstance(assessment, RiskAssessment):
            raise ContractViolation("assessment must be a RiskAssessment")
        assessment.assert_covers(self.tasks)
        return self._edited(risk_assessment=assessment)

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def _transition(self, to_status: PlanStatus, **changes: Any) -> "Plan":
        if not is_legal_transition(self.status, to_status):
            raise IllegalPlanTransition(
                plan_id=str(self.plan_id),
                source=self.status.value,
                target=to_status.value,
                permitted=permitted_from(self.status),
            )
        return replace(self, status=to_status, **changes)

    def validate(self) -> "Plan":
        """Mark the plan complete and coherent."""
        self._require_open("validating")
        missing = self._missing_elements()
        if missing:
            raise IncompletePlan(plan_id=str(self.plan_id), missing=missing)
        self._assert_coherent()
        return self._transition(
            PlanStatus.VALIDATED, validated_at=datetime.now(timezone.utc)
        )

    def approve(self, approved_by: str) -> "Plan":
        """Seal the plan and bind its digest."""
        self._require_open("approving")
        if not approved_by or not approved_by.strip():
            raise ContractViolation("an approval must name who gave it")
        if not is_legal_transition(self.status, PlanStatus.APPROVED):
            raise IllegalPlanTransition(
                plan_id=str(self.plan_id),
                source=self.status.value,
                target=PlanStatus.APPROVED.value,
                permitted=permitted_from(self.status),
            )
        # No governed field changes at approval, so the payload is already what
        # the sealed plan reports. A test asserts ``verify_digest`` passes.
        digest = compute_digest(self.digest_payload()).value
        return self._transition(
            PlanStatus.APPROVED,
            approved_at=datetime.now(timezone.utc),
            approved_by=approved_by.strip(),
            digest=digest,
        )

    def reject(self, reason: str) -> "Plan":
        self._require_open("rejecting")
        if not reason or not reason.strip():
            raise ContractViolation("rejecting a plan must say why")
        return self._transition(PlanStatus.REJECTED, rejection_reason=reason.strip())

    def supersede(self, successor: PlanId) -> "Plan":
        """Record that a later version replaces this one.

        Permitted on an approved plan: it does not change what the plan *said*,
        only whether it is current. The digest still verifies afterwards.
        """
        if not isinstance(successor, PlanId):
            raise ContractViolation("successor must be a PlanId")
        if successor == self.plan_id:
            raise ContractViolation("a plan cannot supersede itself")
        if self.superseded_by is not None:
            raise ContractViolation(
                f"plan {self.plan_id} is already superseded by {self.superseded_by}"
            )
        return self._transition(PlanStatus.SUPERSEDED, superseded_by=successor)

    def revise(self) -> "Plan":
        """Open the next version of this plan, carrying its content forward.

        The way to change an approved plan. The successor starts as a draft at
        ``version + 1`` and names what it supersedes; the caller supersedes the
        original with it, so both stay on record and "what changed between v2 and
        v3" is answerable.
        """
        return Plan(
            plan_id=PlanId.new(),
            mission_id=self.mission_id,
            intent_id=self.intent_id,
            intent_digest=self.intent_digest,
            title=self.title,
            version=self.version + 1,
            goals=self.goals,
            tasks=self.tasks,
            success_criteria=self.success_criteria,
            execution_strategy=self.execution_strategy,
            rollback_strategy=self.rollback_strategy,
            risk_assessment=self.risk_assessment,
            supersedes=self.plan_id,
            planned_by=self.planned_by,
        )

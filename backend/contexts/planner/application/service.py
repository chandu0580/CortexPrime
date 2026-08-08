"""The Planner application service.

Where the aggregate's invariants meet plan policy and the repository's facts.
Events are returned, never published -- this context owns no bus, the same
arrangement as every other context in this codebase.

Validation and approval are gated, not asserted
------------------------------------------------
Both run the policy first and refuse with **every** failure rather than the
first. A plan refused one reason at a time takes five attempts to land, and the
fifth is made by someone who has stopped reading the refusals. For a graph, this
matters more than elsewhere: a plan can have a cycle *and* an orphan task *and*
an understated risk, and finding them one round-trip at a time is how planning
becomes the slow part.

What this service deliberately cannot do
-----------------------------------------
It cannot execute, invoke a tool, schedule, or touch a mission. Every method
either records what the planner decided, checks whether the plan holds together,
or answers a question about it. If a method ever needs to *make something
happen*, it belongs in Execution.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional

from backend.contracts.execution import SideEffectClass
from backend.contexts.planner.application.commands import (
    AddDependency,
    AddGoal,
    AddTask,
    ApprovePlan,
    AssessRisk,
    DeclareCriteria,
    DraftPlan,
    GetGraph,
    GetPlan,
    ListPlans,
    RejectPlan,
    RemoveTask,
    RevisePlan,
    SetExecutionStrategy,
    SetRollbackStrategy,
    ValidatePlan,
)
from backend.contexts.planner.domain.errors import PlanNotFound, PlanRefused
from backend.contexts.planner.domain.events import (
    AGGREGATE_TYPE,
    DependencyAdded,
    PlanApproved,
    PlanCreated,
    PlanRejected,
    PlanValidated,
    PlanVersioned,
    RiskUpdated,
    TaskAdded,
)
from backend.contexts.planner.domain.factory import (
    assessment,
    criterion,
    draft_plan,
    goal,
    reversal,
    risk,
    task,
)
from backend.contexts.planner.domain.identifiers import PlanId
from backend.contexts.planner.domain.plan import Plan
from backend.contexts.planner.domain.policy import PlanPolicy, default_policy
from backend.contexts.planner.domain.risk import Likelihood, RiskLevel, implied_floor
from backend.contexts.planner.domain.status import PlanStatus
from backend.contexts.planner.domain.strategy import (
    ExecutionMode,
    ExecutionStrategy,
    FailureResponse,
    RollbackKind,
    RollbackStrategy,
)
from backend.platform.events import EventMetadata

__all__ = ["PlannerService", "CommandResult"]


@dataclass(frozen=True)
class CommandResult:
    plan: Plan
    events: tuple

    @property
    def event_types(self) -> tuple:
        return tuple(getattr(type(e), "EVENT_TYPE", "?") for e in self.events)


class PlannerService:
    def __init__(self, repository: Any, policy: Optional[PlanPolicy] = None) -> None:
        self._repository = repository
        self._policy = policy or default_policy()

    @property
    def policy(self) -> PlanPolicy:
        return self._policy

    # ------------------------------------------------------------------
    # Plumbing
    # ------------------------------------------------------------------

    @staticmethod
    def _metadata(context: Any, plan: Plan) -> EventMetadata:
        from backend.contracts.tenant import TenantRef, TenantScope

        scope = getattr(context, "scope", None)
        if scope is None:
            scope = TenantScope(tenant=TenantRef(tenant_id=context.tenant_id))
        return EventMetadata.create(
            aggregate_id=str(plan.plan_id),
            aggregate_type=AGGREGATE_TYPE,
            scope=scope,
        )

    def _load(self, context: Any, plan_id: str) -> Plan:
        found = self._repository.find(context, PlanId(plan_id))
        if found is None:
            raise PlanNotFound(plan_id)
        return found

    def _saved(self, context: Any, plan: Plan, events: tuple = ()) -> CommandResult:
        self._repository.replace(context, plan)
        return CommandResult(plan=plan, events=events)

    def _gated(self, plan: Plan, to_status: PlanStatus) -> None:
        report = self._policy.evaluate(plan, to_status)
        if not report.may_proceed:
            raise PlanRefused(
                plan_id=str(plan.plan_id),
                target=to_status.value,
                failures=report.blocking,
            )

    # ------------------------------------------------------------------
    # Drafting
    # ------------------------------------------------------------------

    def draft(self, context: Any, command: DraftPlan) -> CommandResult:
        """Open a plan bound to the mandate it will serve."""
        plan = draft_plan(
            mission_id=command.mission_id,
            intent_id=command.intent_id,
            intent_digest=command.intent_digest,
            title=command.title,
            planned_by=command.planned_by,
        )
        self._repository.save(context, plan)
        return CommandResult(
            plan=plan,
            events=(
                PlanCreated(
                    metadata=self._metadata(context, plan),
                    plan_id=str(plan.plan_id),
                    mission_id=plan.mission_id,
                    intent_id=plan.intent_id,
                    intent_digest=plan.intent_digest,
                    title=plan.title,
                    version=plan.version,
                ),
            ),
        )

    def add_goal(self, context: Any, command: AddGoal) -> CommandResult:
        plan = self._load(context, command.plan_id)
        added = plan.add_goal(
            goal(
                command.statement,
                tuple(criterion(c) for c in command.satisfies),
                rationale=command.rationale,
            )
        )
        return self._saved(context, added)

    def declare_criteria(self, context: Any, command: DeclareCriteria) -> CommandResult:
        plan = self._load(context, command.plan_id)
        declared = plan.declare_criteria(tuple(criterion(c) for c in command.criteria))
        return self._saved(context, declared)

    # ------------------------------------------------------------------
    # The graph
    # ------------------------------------------------------------------

    def add_task(self, context: Any, command: AddTask) -> CommandResult:
        """Add a unit of planned work. The graph is re-checked on every add."""
        plan = self._load(context, command.plan_id)
        reverses_with = None
        if command.compensating_task or command.inverse_action:
            reverses_with = reversal(
                compensating_task=command.compensating_task,
                inverse_action=command.inverse_action,
            )

        planned = task(
            command.task_id,
            command.purpose,
            goals=tuple(command.goals),
            depends_on=tuple(command.depends_on),
            side_effect=SideEffectClass(command.side_effect),
            reverses_with=reverses_with,
            irreversible_accepted_by=command.irreversible_accepted_by,
            execution_key=command.execution_key,
        )
        updated = plan.add_task(planned)
        self._repository.replace(context, updated)

        return CommandResult(
            plan=updated,
            events=(
                TaskAdded(
                    metadata=self._metadata(context, updated),
                    plan_id=str(updated.plan_id),
                    task_id=planned.task_id,
                    purpose=planned.purpose,
                    side_effect=planned.side_effect.value,
                    goal_count=len(planned.goal_ids),
                    reversible=planned.is_reversible or not planned.mutates,
                ),
            ),
        )

    def remove_task(self, context: Any, command: RemoveTask) -> CommandResult:
        plan = self._load(context, command.plan_id)
        return self._saved(context, plan.remove_task(command.task_id))

    def add_dependency(self, context: Any, command: AddDependency) -> CommandResult:
        """Make one task wait for another, refusing a cycle at the edge that makes it."""
        plan = self._load(context, command.plan_id)
        updated = plan.add_dependency(command.task_id, command.depends_on)
        self._repository.replace(context, updated)

        return CommandResult(
            plan=updated,
            events=(
                DependencyAdded(
                    metadata=self._metadata(context, updated),
                    plan_id=str(updated.plan_id),
                    task_id=command.task_id,
                    depends_on=command.depends_on,
                    graph_depth=updated.graph.depth,
                ),
            ),
        )

    # ------------------------------------------------------------------
    # Strategy and risk
    # ------------------------------------------------------------------

    def set_execution_strategy(
        self, context: Any, command: SetExecutionStrategy
    ) -> CommandResult:
        plan = self._load(context, command.plan_id)
        updated = plan.set_execution_strategy(
            ExecutionStrategy(
                mode=ExecutionMode(command.mode),
                on_failure=FailureResponse(command.on_failure),
                max_parallelism=command.max_parallelism,
                checkpoint_after=tuple(command.checkpoint_after),
                continue_justification=command.continue_justification,
            )
        )
        return self._saved(context, updated)

    def set_rollback_strategy(
        self, context: Any, command: SetRollbackStrategy
    ) -> CommandResult:
        plan = self._load(context, command.plan_id)
        updated = plan.set_rollback_strategy(
            RollbackStrategy(
                kind=RollbackKind(command.kind),
                description=command.description,
                accepted_by=command.accepted_by,
                snapshot_of=tuple(command.snapshot_of),
            )
        )
        return self._saved(context, updated)

    def assess_risk(self, context: Any, command: AssessRisk) -> CommandResult:
        """Record the assessment, refusing one below what the tasks imply."""
        plan = self._load(context, command.plan_id)
        declared = assessment(
            RiskLevel(command.overall),
            risks=tuple(
                risk(
                    entry["statement"],
                    RiskLevel(entry.get("level", "low")),
                    likelihood=Likelihood(entry.get("likelihood", "possible")),
                    mitigation=entry.get("mitigation"),
                    affected_tasks=tuple(entry.get("affected_tasks", ())),
                )
                for entry in command.risks
            ),
            assessed_by=command.assessed_by,
            note=command.note,
        )
        updated = plan.assess_risk(declared)
        self._repository.replace(context, updated)

        floor, _ = implied_floor(updated.tasks)
        return CommandResult(
            plan=updated,
            events=(
                RiskUpdated(
                    metadata=self._metadata(context, updated),
                    plan_id=str(updated.plan_id),
                    overall=declared.overall.value,
                    implied_floor=floor.value,
                    risk_count=len(declared.risks),
                    unmitigated=len(declared.unmitigated),
                    assessed_by=declared.assessed_by,
                ),
            ),
        )

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def validate(self, context: Any, command: ValidatePlan) -> CommandResult:
        plan = self._load(context, command.plan_id)
        self._gated(plan, PlanStatus.VALIDATED)
        validated = plan.validate()
        self._repository.replace(context, validated)

        graph = validated.graph
        advisories = self._policy.evaluate(validated, PlanStatus.VALIDATED).advisory
        return CommandResult(
            plan=validated,
            events=(
                PlanValidated(
                    metadata=self._metadata(context, validated),
                    plan_id=str(validated.plan_id),
                    version=validated.version,
                    goals=len(validated.goals),
                    tasks=len(validated.tasks),
                    graph_depth=graph.depth,
                    widest_layer=graph.widest_layer,
                    missing_elements=len(validated.missing_elements),
                    advisories=len(advisories),
                ),
            ),
        )

    def approve(self, context: Any, command: ApprovePlan) -> CommandResult:
        """Seal the plan. Execution may act on what this produces."""
        plan = self._load(context, command.plan_id)
        self._gated(plan, PlanStatus.APPROVED)
        approved = plan.approve(command.approved_by)
        self._repository.replace(context, approved)

        return CommandResult(
            plan=approved,
            events=(
                PlanApproved(
                    metadata=self._metadata(context, approved),
                    plan_id=str(approved.plan_id),
                    version=approved.version,
                    approved_by=approved.approved_by or "",
                    digest=approved.digest or "",
                    overall_risk=(
                        approved.risk_assessment.overall.value
                        if approved.risk_assessment
                        else "low"
                    ),
                    mutating_tasks=len(approved.mutating_tasks),
                    rollback_kind=approved.rollback_strategy.kind.value,
                ),
            ),
        )

    def reject(self, context: Any, command: RejectPlan) -> CommandResult:
        plan = self._load(context, command.plan_id)
        rejected_from = plan.status.value
        rejected = plan.reject(command.reason)
        self._repository.replace(context, rejected)

        return CommandResult(
            plan=rejected,
            events=(
                PlanRejected(
                    metadata=self._metadata(context, rejected),
                    plan_id=str(rejected.plan_id),
                    reason=command.reason,
                    rejected_by=command.rejected_by,
                    rejected_from=rejected_from,
                ),
            ),
        )

    def revise(self, context: Any, command: RevisePlan) -> CommandResult:
        """Open the next version and supersede this one. Both stay on record."""
        plan = self._load(context, command.plan_id)
        successor = plan.revise()
        self._repository.save(context, successor)

        superseded = plan.supersede(successor.plan_id)
        self._repository.replace(context, superseded)

        return CommandResult(
            plan=successor,
            events=(
                PlanVersioned(
                    metadata=self._metadata(context, successor),
                    plan_id=str(plan.plan_id),
                    successor_id=str(successor.plan_id),
                    from_version=plan.version,
                    to_version=successor.version,
                    reason=command.reason,
                ),
            ),
        )

    # ------------------------------------------------------------------
    # Queries
    # ------------------------------------------------------------------

    def get(self, context: Any, query: GetPlan) -> Plan:
        return self._load(context, query.plan_id)

    def graph(self, context: Any, query: GetGraph):
        return self._load(context, query.plan_id).graph

    def evaluate(self, context: Any, plan_id: str, to_status: str):
        """Run the policy without transitioning.

        What a planner checks before submitting. Discovering a cycle, an orphan
        task and an understated risk one round-trip at a time is how planning
        becomes the slow part.
        """
        return self._policy.evaluate(
            self._load(context, plan_id), PlanStatus(to_status)
        )

    def list(self, context: Any, query: ListPlans) -> tuple:
        found = self._repository.all(context)
        if query.mission_id:
            found = tuple(p for p in found if p.mission_id == query.mission_id)
        if query.intent_id:
            found = tuple(p for p in found if p.intent_id == query.intent_id)
        if query.status:
            wanted = PlanStatus(query.status)
            found = tuple(p for p in found if p.status is wanted)
        if query.executable_only:
            found = tuple(p for p in found if p.is_executable)
        return tuple(found)

    def executable_for(self, context: Any, mission_id: str) -> Optional[Plan]:
        """The approved plan for a mission, if there is one.

        What Workflow compiles from, and the only thing it reads from this
        context. Execution never sees a plan: it runs the compiled workflow, and
        the plan reaches it only as the ``plan_id``/``plan_digest`` the workflow
        carries.
        """
        candidates = [
            p
            for p in self._repository.all(context)
            if p.mission_id == mission_id and p.is_executable
        ]
        if not candidates:
            return None
        return max(candidates, key=lambda p: (p.version, str(p.plan_id)))

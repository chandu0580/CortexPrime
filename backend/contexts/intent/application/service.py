"""The Intent application service.

Where the aggregate's invariants meet intent policy and the repository's facts.
Events are returned, never published -- this context owns no bus, the same
arrangement as every other context in this codebase.

Validation and approval are gated, not asserted
------------------------------------------------
Both run the policy first and refuse with **every** failure rather than the
first. An intent refused one reason at a time takes five attempts to land, and
the fifth is made by someone who has stopped reading the refusals.

What this service deliberately cannot do
-----------------------------------------
It cannot plan, decompose, schedule, or execute. Every method either records what
the requester meant, checks whether the mandate holds together, or answers a
question about it. If a method ever needs to decide *how* the objective will be
achieved, it belongs in the Planner -- which does not exist and is not this PR.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional

from backend.contexts.intent.application.commands import (
    AcknowledgeRisk,
    AddConstraint,
    AddSuccessCriterion,
    ApproveIntent,
    CaptureIntent,
    GetIntent,
    ListIntents,
    RejectIntent,
    RemoveConstraint,
    RemoveSuccessCriterion,
    SetObjective,
    SetPriority,
    SetRiskAppetite,
    SetScope,
    SupersedeIntent,
    ValidateIntent,
)
from backend.contexts.intent.domain.constraints import (
    ConstraintEnforcement,
    ConstraintKind,
)
from backend.contexts.intent.domain.errors import IntentNotFound, ValidationRefused
from backend.contexts.intent.domain.events import (
    AGGREGATE_TYPE,
    IntentApproved,
    IntentCreated,
    IntentExpanded,
    IntentRejected,
    IntentSuperseded,
    IntentValidated,
)
from backend.contexts.intent.domain.factory import (
    capture_intent,
    constraint,
    criterion,
    objective,
    risk,
    scope,
)
from backend.contexts.intent.domain.identifiers import (
    ConstraintId,
    CriterionId,
    IntentId,
)
from backend.contexts.intent.domain.intent import Intent
from backend.contexts.intent.domain.metadata import IntentOrigin
from backend.contexts.intent.domain.objective import OutcomeKind
from backend.contexts.intent.domain.policy import IntentPolicy, default_policy
from backend.contexts.intent.domain.priority import (
    ImpactLevel,
    IntentPriority,
    RiskAppetite,
)
from backend.contexts.intent.domain.scope import Environment
from backend.contexts.intent.domain.status import IntentStatus
from backend.platform.events import EventMetadata

__all__ = ["IntentService", "CommandResult"]


@dataclass(frozen=True)
class CommandResult:
    intent: Intent
    events: tuple

    @property
    def event_types(self) -> tuple:
        return tuple(getattr(type(e), "EVENT_TYPE", "?") for e in self.events)


class IntentService:
    def __init__(self, repository: Any, policy: Optional[IntentPolicy] = None) -> None:
        self._repository = repository
        self._policy = policy or default_policy()

    @property
    def policy(self) -> IntentPolicy:
        return self._policy

    # ------------------------------------------------------------------
    # Plumbing
    # ------------------------------------------------------------------

    @staticmethod
    def _metadata(context: Any, intent: Intent) -> EventMetadata:
        from backend.contracts.tenant import TenantRef, TenantScope

        scope_value = getattr(context, "scope", None)
        if scope_value is None:
            scope_value = TenantScope(tenant=TenantRef(tenant_id=context.tenant_id))
        return EventMetadata.create(
            aggregate_id=str(intent.intent_id),
            aggregate_type=AGGREGATE_TYPE,
            scope=scope_value,
        )

    def _load(self, context: Any, intent_id: str) -> Intent:
        found = self._repository.find(context, IntentId(intent_id))
        if found is None:
            raise IntentNotFound(intent_id)
        return found

    def _expansion(
        self, context: Any, before: Intent, after: Intent, element: str, detail: str = ""
    ) -> CommandResult:
        """Persist an expansion and report whether it undid a validation."""
        self._repository.replace(context, after)
        return CommandResult(
            intent=after,
            events=(
                IntentExpanded(
                    metadata=self._metadata(context, after),
                    intent_id=str(after.intent_id),
                    element=element,
                    detail=detail,
                    expansion_count=after.expansion_count,
                    returned_to_draft=(
                        before.status is IntentStatus.VALIDATED
                        and after.status is IntentStatus.DRAFT
                    ),
                ),
            ),
        )

    def _gated(self, intent: Intent, to_status: IntentStatus) -> None:
        report = self._policy.evaluate(intent, to_status)
        if not report.may_proceed:
            raise ValidationRefused(
                intent_id=str(intent.intent_id),
                target=to_status.value,
                failures=report.blocking,
            )

    # ------------------------------------------------------------------
    # Capture
    # ------------------------------------------------------------------

    def capture(self, context: Any, command: CaptureIntent) -> CommandResult:
        """Record what somebody asked for, before it has any structure."""
        intent = capture_intent(
            stated_goal=command.stated_goal,
            requested_by=context.security_context,
            title=command.title,
            origin=IntentOrigin(command.origin),
            tags=tuple(command.tags),
            requested_for=command.requested_for,
            derived_from=command.derived_from,
        )
        self._repository.save(context, intent)
        return CommandResult(
            intent=intent,
            events=(
                IntentCreated(
                    metadata=self._metadata(context, intent),
                    intent_id=str(intent.intent_id),
                    title=intent.metadata.title,
                    stated_goal=intent.stated_goal,
                    origin=intent.metadata.origin.value,
                    requested_by=str(intent.raw.requested_by.principal.principal_id),
                ),
            ),
        )

    # ------------------------------------------------------------------
    # Expansion
    # ------------------------------------------------------------------

    def set_objective(self, context: Any, command: SetObjective) -> CommandResult:
        before = self._load(context, command.intent_id)
        after = before.set_objective(
            objective(
                command.outcome,
                OutcomeKind(command.kind),
                rationale=command.rationale,
                subject=command.subject,
            )
        )
        return self._expansion(context, before, after, "objective", command.outcome[:60])

    def set_scope(self, context: Any, command: SetScope) -> CommandResult:
        before = self._load(context, command.intent_id)
        after = before.set_scope(
            scope(
                tuple(command.included),
                excluded=tuple(command.excluded),
                environments=tuple(Environment(e) for e in command.environments),
                target_type=command.target_type,
                note=command.note,
            )
        )
        return self._expansion(
            context, before, after, "scope", f"{len(command.included)} target(s)"
        )

    def set_priority(self, context: Any, command: SetPriority) -> CommandResult:
        before = self._load(context, command.intent_id)
        after = before.set_priority(IntentPriority(command.priority))
        return self._expansion(context, before, after, "priority", command.priority)

    def set_risk_appetite(self, context: Any, command: SetRiskAppetite) -> CommandResult:
        before = self._load(context, command.intent_id)
        after = before.set_risk_appetite(RiskAppetite(command.appetite))
        return self._expansion(context, before, after, "risk_appetite", command.appetite)

    def add_constraint(self, context: Any, command: AddConstraint) -> CommandResult:
        before = self._load(context, command.intent_id)
        after = before.add_constraint(
            constraint(
                ConstraintKind(command.kind),
                command.statement,
                limit=command.limit,
                enforcement=ConstraintEnforcement(command.enforcement),
                rationale=command.rationale,
            )
        )
        return self._expansion(
            context, before, after, "constraint", f"{command.kind}: {command.statement[:40]}"
        )

    def remove_constraint(self, context: Any, command: RemoveConstraint) -> CommandResult:
        before = self._load(context, command.intent_id)
        after = before.remove_constraint(ConstraintId(command.constraint_id))
        return self._expansion(
            context, before, after, "constraint_removed", command.constraint_id
        )

    def add_success_criterion(
        self, context: Any, command: AddSuccessCriterion
    ) -> CommandResult:
        before = self._load(context, command.intent_id)
        after = before.add_success_criterion(
            criterion(
                command.statement,
                command.measure,
                threshold=command.threshold,
                baseline=command.baseline,
            )
        )
        return self._expansion(
            context, before, after, "success_criterion", command.statement[:60]
        )

    def remove_success_criterion(
        self, context: Any, command: RemoveSuccessCriterion
    ) -> CommandResult:
        before = self._load(context, command.intent_id)
        after = before.remove_success_criterion(CriterionId(command.criterion_id))
        return self._expansion(
            context, before, after, "success_criterion_removed", command.criterion_id
        )

    def acknowledge_risk(self, context: Any, command: AcknowledgeRisk) -> CommandResult:
        before = self._load(context, command.intent_id)
        after = before.acknowledge_risk(
            risk(
                command.statement,
                ImpactLevel(command.impact),
                accepted_by=command.accepted_by,
            )
        )
        return self._expansion(context, before, after, "risk", command.statement[:60])

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def validate(self, context: Any, command: ValidateIntent) -> CommandResult:
        """Check the mandate holds together, or refuse with every reason."""
        intent = self._load(context, command.intent_id)
        self._gated(intent, IntentStatus.VALIDATED)
        validated = intent.validate()
        self._repository.replace(context, validated)

        advisories = self._policy.evaluate(validated, IntentStatus.VALIDATED).advisory
        return CommandResult(
            intent=validated,
            events=(
                IntentValidated(
                    metadata=self._metadata(context, validated),
                    intent_id=str(validated.intent_id),
                    constraints=len(validated.constraints),
                    success_criteria=len(validated.success_criteria),
                    scope_breadth=validated.scope.breadth if validated.scope else 0,
                    missing_elements=len(validated.missing_elements),
                    advisories=len(advisories),
                ),
            ),
        )

    def approve(self, context: Any, command: ApproveIntent) -> CommandResult:
        """Seal the mandate. Planning may act on what this produces."""
        intent = self._load(context, command.intent_id)
        self._gated(intent, IntentStatus.APPROVED)
        approved = intent.approve(command.approved_by)
        self._repository.replace(context, approved)

        return CommandResult(
            intent=approved,
            events=(
                IntentApproved(
                    metadata=self._metadata(context, approved),
                    intent_id=str(approved.intent_id),
                    approved_by=approved.approved_by or "",
                    digest=approved.digest or "",
                    priority=approved.priority.value,
                    touches_production=approved.touches_production,
                    hard_constraints=len(approved.hard_constraints),
                ),
            ),
        )

    def reject(self, context: Any, command: RejectIntent) -> CommandResult:
        intent = self._load(context, command.intent_id)
        rejected_from = intent.status.value
        rejected = intent.reject(command.reason)
        self._repository.replace(context, rejected)

        return CommandResult(
            intent=rejected,
            events=(
                IntentRejected(
                    metadata=self._metadata(context, rejected),
                    intent_id=str(rejected.intent_id),
                    reason=command.reason,
                    rejected_by=command.rejected_by,
                    rejected_from=rejected_from,
                ),
            ),
        )

    def supersede(self, context: Any, command: SupersedeIntent) -> CommandResult:
        intent = self._load(context, command.intent_id)
        superseded = intent.supersede(IntentId(command.successor_id))
        self._repository.replace(context, superseded)

        return CommandResult(
            intent=superseded,
            events=(
                IntentSuperseded(
                    metadata=self._metadata(context, superseded),
                    intent_id=str(superseded.intent_id),
                    superseded_by=command.successor_id,
                    reason=command.reason,
                ),
            ),
        )

    # ------------------------------------------------------------------
    # Queries
    # ------------------------------------------------------------------

    def get(self, context: Any, query: GetIntent) -> Intent:
        return self._load(context, query.intent_id)

    def evaluate(self, context: Any, intent_id: str, to_status: str):
        """Run the policy without transitioning.

        What somebody checks before submitting for approval. Discovering four
        failures one refusal at a time is how an intent takes four attempts.
        """
        return self._policy.evaluate(
            self._load(context, intent_id), IntentStatus(to_status)
        )

    def list(self, context: Any, query: ListIntents) -> tuple:
        found = self._repository.all(context)
        if query.status:
            wanted = IntentStatus(query.status)
            found = tuple(i for i in found if i.status is wanted)
        if query.priority:
            wanted_priority = IntentPriority(query.priority)
            found = tuple(i for i in found if i.priority is wanted_priority)
        if query.origin:
            wanted_origin = IntentOrigin(query.origin)
            found = tuple(i for i in found if i.metadata.origin is wanted_origin)
        if query.planable_only:
            found = tuple(i for i in found if i.is_planable)
        return tuple(found)

    def planable(self, context: Any) -> tuple:
        """Every approved intent. What the Planner asks for.

        The only thing the Planner reads from this context. It does not import
        Intent to get it; the plan carries ``intent_id`` and ``intent_digest``,
        which is how a plan can be shown to serve the intent it claims to.
        """
        return tuple(i for i in self._repository.all(context) if i.is_planable)

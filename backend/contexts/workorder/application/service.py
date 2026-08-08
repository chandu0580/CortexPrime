"""The WorkOrder application service.

Where the aggregate's rules meet the repository's facts. Three things live here
because none of them can be decided by the aggregate alone:

**Validation that needs the world.** V4, V5, V7 and V9 need a resolver and the
dependency graph. The aggregate cannot reach either, so approval runs the full
validator here with both supplied.

**Blast-radius conflict detection.** Needs every other active WorkOrder.

**Event emission.** Every transition returns its events alongside the new
aggregate. They are returned rather than published: this context owns no bus,
and reaching for one would couple it to infrastructure it has no business
knowing about. The orchestrator publishes.

Every method takes an ``ExecutionContext`` and passes it down. Nothing here
derives tenancy, invents a context, or falls back to a default -- there is no
ambient context to fall back to, and inventing one would reintroduce the implicit
propagation ADR-017 removed.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable, Optional, Sequence

from backend.contracts.errors import ContractViolation
from backend.contracts.tenant import TenantRef, TenantScope
from backend.contexts.workorder.application.commands import (
    ApproveWorkOrder,
    CheckBlastRadiusConflicts,
    DraftWorkOrder,
    ExpandBlastRadius,
    GetWorkOrder,
    ListWorkOrders,
    RejectWorkOrder,
    Reprioritise,
    ResolveAssumption,
    SupersedeWorkOrder,
    TransitionWorkOrder,
)
from backend.contexts.workorder.domain.blast_radius import BlastRadius
from backend.contexts.workorder.domain.errors import ValidationFailed, WorkOrderNotFound
from backend.contexts.workorder.domain.events import (
    AGGREGATE_TYPE,
    WorkOrderApproved,
    WorkOrderAssigned,
    WorkOrderAssumptionResolved,
    WorkOrderBlastRadiusExpanded,
    WorkOrderClosed,
    WorkOrderDigestValidated,
    WorkOrderDrafted,
    WorkOrderMerged,
    WorkOrderRejected,
    WorkOrderReprioritised,
    WorkOrderStateChanged,
    WorkOrderSuperseded,
)
from backend.contexts.workorder.domain.factory import draft_work_order
from backend.contexts.workorder.domain.identifiers import AssumptionId, EvidenceRef, WorkOrderId
from backend.contexts.workorder.domain.states import WorkOrderState
from backend.contexts.workorder.domain.validation import ReferenceResolver, validate
from backend.contexts.workorder.domain.work_order import WorkOrder
from backend.platform.events import EventMetadata

__all__ = ["WorkOrderService", "CommandResult", "BlastRadiusConflict"]


@dataclass(frozen=True)
class CommandResult:
    """A new aggregate state plus the events describing how it got there.

    Events are returned, never published. This context owns no bus.
    """

    work_order: WorkOrder
    events: tuple


@dataclass(frozen=True)
class BlastRadiusConflict:
    """Another active WorkOrder contending for the same paths."""

    work_id: str
    state: str
    patterns: tuple


class WorkOrderService:
    """Commands and queries over the WorkOrder aggregate."""

    def __init__(
        self,
        repository: Any,
        resolver: ReferenceResolver,
        *,
        repository_paths: Optional[Sequence[str]] = None,
    ) -> None:
        self._repository = repository
        self._resolver = resolver
        self._repository_paths = tuple(repository_paths) if repository_paths is not None else None

    # ------------------------------------------------------------------
    # Event helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _metadata(context: Any, work_order: WorkOrder, **attributes: Any) -> EventMetadata:
        """Build event metadata from the execution context.

        The tenant scope comes from the context, never from the aggregate. An
        aggregate that supplied its own scope would let a stored record choose
        the tenant its events are attributed to.
        """
        scope = getattr(context, "scope", None)
        if scope is None:
            scope = TenantScope(tenant=TenantRef(tenant_id=context.tenant_id))
        return EventMetadata.create(
            aggregate_id=str(work_order.work_id),
            aggregate_type=AGGREGATE_TYPE,
            scope=scope,
            attributes=attributes or None,
        )

    def _state_change(
        self, context: Any, work_order: WorkOrder, previous: WorkOrderState
    ) -> WorkOrderStateChanged:
        return WorkOrderStateChanged(
            metadata=self._metadata(context, work_order),
            work_id=str(work_order.work_id),
            version=work_order.version,
            from_state=previous.value,
            to_state=work_order.state.value,
        )

    # ------------------------------------------------------------------
    # Commands
    # ------------------------------------------------------------------

    def draft(self, context: Any, command: DraftWorkOrder) -> CommandResult:
        work_order = draft_work_order(
            intent=command.intent,
            acceptance_criteria=command.acceptance_criteria,
            blast_radius=command.blast_radius,
            definition_of_done=command.definition_of_done,
            adr_references=command.adr_references,
            evidence=command.evidence,
            constraints=command.constraints,
            assumptions=command.assumptions,
            extra_rejection_grounds=command.extra_rejection_grounds,
            dependencies=command.dependencies,
            priority=command.priority,
            created_by=command.created_by,
            supersedes=command.supersedes,
        )
        self._repository.save(context, work_order)
        return CommandResult(
            work_order=work_order,
            events=(
                WorkOrderDrafted(
                    metadata=self._metadata(context, work_order),
                    work_id=str(work_order.work_id),
                    version=work_order.version,
                    intent=work_order.intent,
                    created_by=work_order.created_by,
                ),
            ),
        )

    def validate(self, context: Any, work_id: str):
        """Run every validation rule with the world supplied.

        Public because the Architect needs to see the report before attempting
        approval; discovering ten findings one refusal at a time is how a Draft
        takes six rounds to land.
        """
        work_order = self._repository.get(context, WorkOrderId(work_id))
        return validate(
            work_order,
            resolver=self._resolver,
            repository_paths=self._repository_paths,
            dependency_graph=self._repository.dependency_graph(context),
        )

    def approve(self, context: Any, command: ApproveWorkOrder) -> CommandResult:
        """Ratify a Draft, after it passes every rule.

        Validation runs *before* the transition. Approving first and validating
        after would mean a digest bound to content that was never checked.
        """
        work_order = self._repository.get(context, WorkOrderId(command.work_id))
        report = validate(
            work_order,
            resolver=self._resolver,
            repository_paths=self._repository_paths,
            dependency_graph=self._repository.dependency_graph(context),
        )
        if not report.approvable:
            raise ValidationFailed(report.blocking)

        previous = work_order.state
        approved = work_order.approve()
        self._repository.replace_version(context, approved)

        return CommandResult(
            work_order=approved,
            events=(
                WorkOrderApproved(
                    metadata=self._metadata(context, approved),
                    work_id=str(approved.work_id),
                    version=approved.version,
                    digest=approved.digest.value,
                    digest_algorithm=approved.digest.algorithm.value,
                    approved_by=command.approved_by,
                ),
                self._state_change(context, approved, previous),
            ),
        )

    def transition(self, context: Any, command: TransitionWorkOrder) -> CommandResult:
        """Move a WorkOrder along the machine, re-verifying the digest."""
        work_order = self._repository.get(context, WorkOrderId(command.work_id))
        previous = work_order.state

        events: list = []
        if previous.is_governed:
            observed = work_order.compute_digest()
            valid = work_order.digest is not None and observed.value == work_order.digest.value
            events.append(
                WorkOrderDigestValidated(
                    metadata=self._metadata(context, work_order),
                    work_id=str(work_order.work_id),
                    version=work_order.version,
                    expected=work_order.digest.value if work_order.digest else "",
                    observed=observed.value,
                    valid=valid,
                )
            )

        moved = work_order.transition(command.to_state)
        self._repository.replace_version(context, moved)
        events.append(self._state_change(context, moved, previous))

        if moved.state is WorkOrderState.ASSIGNED:
            events.append(
                WorkOrderAssigned(
                    metadata=self._metadata(context, moved),
                    work_id=str(moved.work_id),
                    version=moved.version,
                    allowed_patterns=tuple(sorted(str(p) for p in moved.blast_radius.allowed)),
                )
            )
        elif moved.state is WorkOrderState.MERGED:
            events.append(
                WorkOrderMerged(
                    metadata=self._metadata(context, moved),
                    work_id=str(moved.work_id),
                    version=moved.version,
                    commit="unrecorded",
                    merged_by=command.actor,
                )
            )
        elif moved.state is WorkOrderState.CLOSED:
            events.append(
                WorkOrderClosed(
                    metadata=self._metadata(context, moved),
                    work_id=str(moved.work_id),
                    version=moved.version,
                )
            )

        return CommandResult(work_order=moved, events=tuple(events))

    def reject(self, context: Any, command: RejectWorkOrder) -> CommandResult:
        work_order = self._repository.get(context, WorkOrderId(command.work_id))
        rejected = work_order.reject(command.rejection_type, command.detail)
        self._repository.replace_version(context, rejected)
        return CommandResult(
            work_order=rejected,
            events=(
                WorkOrderRejected(
                    metadata=self._metadata(context, rejected),
                    work_id=str(rejected.work_id),
                    version=rejected.version,
                    rejection_type=command.rejection_type.value,
                    detail=command.detail,
                    raised_by=command.raised_by,
                ),
                self._state_change(context, rejected, work_order.state),
            ),
        )

    def resolve_assumption(self, context: Any, command: ResolveAssumption) -> CommandResult:
        work_order = self._repository.get(context, WorkOrderId(command.work_id))
        resolved = work_order.resolve_assumption(
            AssumptionId(command.assumption_id),
            command.resolution,
            EvidenceRef(command.evidence),
        )
        self._repository.replace_version(context, resolved)
        return CommandResult(
            work_order=resolved,
            events=(
                WorkOrderAssumptionResolved(
                    metadata=self._metadata(context, resolved),
                    work_id=str(resolved.work_id),
                    version=resolved.version,
                    assumption_id=command.assumption_id,
                    resolution=command.resolution.value,
                    evidence=command.evidence,
                ),
            ),
        )

    def expand_blast_radius(self, context: Any, command: ExpandBlastRadius) -> CommandResult:
        """Widen scope and re-approve as a new version.

        Conflict detection re-runs: an expanded radius can collide with a
        WorkOrder it was compatible with a moment ago.
        """
        work_order = self._repository.get(context, WorkOrderId(command.work_id))

        conflicts = self.conflicts(
            context,
            CheckBlastRadiusConflicts(
                radius=command.radius, exclude_work_id=command.work_id
            ),
        )
        if conflicts:
            names = ", ".join(c.work_id for c in conflicts)
            raise ContractViolation(
                f"expanded blast radius conflicts with active WorkOrder(s): {names}"
            )

        expanded = work_order.expand_blast_radius(command.radius)
        self._repository.save(context, expanded)

        added = tuple(
            sorted(
                str(p)
                for p in (command.radius.allowed - work_order.blast_radius.allowed)
            )
        )
        return CommandResult(
            work_order=expanded,
            events=(
                WorkOrderBlastRadiusExpanded(
                    metadata=self._metadata(context, expanded),
                    work_id=str(expanded.work_id),
                    from_version=work_order.version,
                    to_version=expanded.version,
                    added_patterns=added,
                    new_digest=expanded.digest.value,
                ),
            ),
        )

    def reprioritise(self, context: Any, command: Reprioritise) -> CommandResult:
        work_order = self._repository.get(context, WorkOrderId(command.work_id))
        changed = work_order.reprioritise(command.priority)
        self._repository.replace_version(context, changed)
        return CommandResult(
            work_order=changed,
            events=(
                WorkOrderReprioritised(
                    metadata=self._metadata(context, changed),
                    work_id=str(changed.work_id),
                    version=changed.version,
                    from_priority=work_order.priority.value,
                    to_priority=changed.priority.value,
                ),
            ),
        )

    def supersede(self, context: Any, command: SupersedeWorkOrder) -> CommandResult:
        work_order = self._repository.get(context, WorkOrderId(command.work_id))
        superseded = work_order.supersede(WorkOrderId(command.successor_id))
        self._repository.replace_version(context, superseded)
        return CommandResult(
            work_order=superseded,
            events=(
                WorkOrderSuperseded(
                    metadata=self._metadata(context, superseded),
                    work_id=str(superseded.work_id),
                    version=superseded.version,
                    superseded_by=command.successor_id,
                ),
            ),
        )

    # ------------------------------------------------------------------
    # Queries
    # ------------------------------------------------------------------

    def get(self, context: Any, query: GetWorkOrder) -> WorkOrder:
        return self._repository.get(context, WorkOrderId(query.work_id), query.version)

    def versions(self, context: Any, work_id: str) -> tuple:
        return self._repository.versions(context, WorkOrderId(work_id))

    def list(self, context: Any, query: ListWorkOrders) -> tuple:
        if query.active_only:
            return self._repository.list_active(context)
        if query.state is not None:
            return self._repository.list_by_state(context, query.state)
        return self._repository.list_active(context)

    def conflicts(self, context: Any, query: CheckBlastRadiusConflicts) -> tuple:
        """Active WorkOrders whose radius could contend with ``query.radius``.

        Only WorkOrders holding a lock -- Assigned through Merged -- contend.
        Approved work has not acquired one, and terminal work has released it.
        """
        holding = {
            WorkOrderState.ASSIGNED,
            WorkOrderState.SPEC_TESTS,
            WorkOrderState.IMPLEMENTATION,
            WorkOrderState.REVIEW,
            WorkOrderState.VERIFICATION,
            WorkOrderState.READY,
            WorkOrderState.MERGED,
        }
        found: list = []
        for candidate in self._repository.list_active(context):
            if candidate.state not in holding:
                continue
            if query.exclude_work_id and str(candidate.work_id) == query.exclude_work_id:
                continue
            if candidate.blast_radius.conflicts_with(query.radius):
                found.append(
                    BlastRadiusConflict(
                        work_id=str(candidate.work_id),
                        state=candidate.state.value,
                        patterns=candidate.blast_radius.conflicting_patterns(query.radius),
                    )
                )
        return tuple(found)

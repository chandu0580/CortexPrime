"""Crash recovery: work out what was true, decide, and act only where it is safe.

The question this answers
--------------------------
A process died. Some executions were running, some nodes were leased, some
workers may have applied changes nobody recorded. On restart the platform has to
establish — from the durable record alone — which runs can continue, which need a
person, and which are holding a change that may or may not have landed.

Policy is Phase 3.1's; this is mechanism
------------------------------------------
``plan_recovery`` already decides (ADR-031) and it is pure. This coordinator
gathers the executions, asks it, records the answer, and hands automatic
decisions to the dispatcher. **It never invokes a worker**, which is what keeps
recovery replayable: the decision can be recomputed from the same record and will
be the same decision.

Restart-safe by construction
------------------------------
Running recovery twice must not create two attempts or two compensations. That
holds because this component performs nothing itself: it records a decision and
returns it. The actions it can trigger — retry, compensate — go through the
aggregate, whose lease and attempt invariants already refuse a duplicate. A
second recovery pass over an unchanged record produces an identical decision and
changes nothing.

Deterministic, in a stated order
----------------------------------
Executions are considered in ``recovery_priority`` order: unresolved mutations
first, then owed rollbacks, then expired leases, then deadlines, then stalls, with
the ULID execution id as a total tiebreak. Never dictionary order, never object
identity, never whichever the repository happened to return first.

Nothing here resumes past an unknown
--------------------------------------
``RecoveryDecision`` refuses to construct a ``RESUME_FROM_CHECKPOINT`` while
ambiguous nodes exist, so the dangerous case is unrepresentable rather than
merely discouraged.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Optional

from backend.contracts.errors import ContractViolation
from backend.contexts.execution.application.instrumentation import (
    NullObserver,
    SafeObserver,
)
from backend.contexts.execution.application.metrics import NullMetrics, SafeMetrics
from backend.contexts.execution.domain.dispatch import (
    compensation_order,
    recovery_priority,
)
from backend.contexts.execution.domain.invocation import Clock, SystemClock
from backend.contexts.execution.domain.lifecycle_events import (
    ExecutionPartiallyRecovered,
    ExecutionRecoveryPlanned,
)
from backend.contexts.execution.domain.recovery import (
    RecoveryAction,
    RecoveryDecision,
    RecoveryTrigger,
    plan_recovery,
)
from backend.contexts.execution.domain.state import ExecutionState, NodeState
from backend.platform.events import EventMetadata

__all__ = ["RecoveryPlan", "StartupReport", "RecoveryCoordinator"]

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class RecoveryPlan:
    """One execution's recovery decision, plus what it implies."""

    execution_id: str
    decision: RecoveryDecision
    expired_leases: tuple = ()
    compensation_targets: tuple = ()
    """Nodes to walk back, newest change first. Populated only for
    ``COMPENSATE`` — naming them for other actions would invite a caller to act
    on a rollback nobody decided."""

    events: tuple = ()

    @property
    def action(self) -> RecoveryAction:
        return self.decision.action

    @property
    def is_automatic(self) -> bool:
        return self.decision.is_automatic

    @property
    def needs_a_human(self) -> bool:
        return self.decision.action.needs_a_human

    def to_dict(self) -> dict:
        return {
            "execution_id": self.execution_id,
            "decision": self.decision.to_dict(),
            "expired_leases": list(self.expired_leases),
            "compensation_targets": list(self.compensation_targets),
            "automatic": self.is_automatic,
            "needs_a_human": self.needs_a_human,
            "events": [type(e).EVENT_TYPE for e in self.events],
        }


@dataclass(frozen=True)
class StartupReport:
    """What recovery found on restart. A record, and nothing that can be driven."""

    scanned: int = 0
    plans: tuple = ()
    resumable: tuple = ()
    blocked: tuple = ()
    awaiting_human: tuple = ()
    at: Optional[datetime] = None

    @property
    def safe_to_resume(self) -> tuple:
        return self.resumable

    def to_dict(self) -> dict:
        return {
            "scanned": self.scanned,
            "at": self.at.isoformat() if self.at else None,
            "resumable": list(self.resumable),
            "blocked": list(self.blocked),
            "awaiting_human": list(self.awaiting_human),
            "plans": [p.to_dict() for p in self.plans],
        }


class RecoveryCoordinator:
    """Gathers stopped runs, asks the recovery policy, records the answers.

    Invokes nothing. The dispatcher performs automatic decisions; a human
    performs the rest.
    """

    def __init__(
        self,
        *,
        executions: Any,
        outbox: Optional[Any] = None,
        observer: Optional[Any] = None,
        metrics: Optional[Any] = None,
        clock: Optional[Clock] = None,
    ) -> None:
        self._executions = executions
        self._outbox = outbox
        self._observer = SafeObserver(observer or NullObserver())
        self._metrics = SafeMetrics(metrics or NullMetrics())
        self._clock = clock or SystemClock()

    # ------------------------------------------------------------------
    # Startup
    # ------------------------------------------------------------------

    def recover(
        self,
        context: Any,
        *,
        trigger: RecoveryTrigger = RecoveryTrigger.PROCESS_RESTART,
        limit: int = 100,
    ) -> StartupReport:
        """Scan every unfinished run this tenant owns and decide about each.

        Read-then-decide. Nothing is invoked, nothing is retried, nothing is
        compensated. What comes back is a set of decisions somebody — the
        dispatcher for automatic ones, a person for the rest — acts on next.
        """
        now = self._clock.now()
        self._require_tenant(context)

        from backend.contexts.execution.application.commands import ListExecutions

        # The existing query, scoped by the repository's tenant guard. A run is a
        # recovery candidate when it is still open, or when it holds an outcome
        # nobody can state -- the second matters because such a run can be
        # *terminal* and still owe somebody an answer.
        candidates = [
            execution
            for execution in self._executions.list(context, ListExecutions())
            if execution.state
            in (ExecutionState.RUNNING, ExecutionState.PAUSED, ExecutionState.PENDING)
            or execution.ambiguous_nodes
        ]
        candidates.sort(key=lambda e: recovery_priority(e, now=now))

        plans: list = []
        for execution in candidates[:limit]:
            plans.append(self.plan(context, execution, trigger=trigger, now=now))

        return StartupReport(
            scanned=len(candidates),
            plans=tuple(plans),
            resumable=tuple(p.execution_id for p in plans if p.is_automatic),
            blocked=tuple(
                p.execution_id
                for p in plans
                if p.action is RecoveryAction.FAIL_EXECUTION
            ),
            awaiting_human=tuple(
                p.execution_id for p in plans if p.needs_a_human
            ),
            at=now,
        )

    # ------------------------------------------------------------------
    # One execution
    # ------------------------------------------------------------------

    def plan(
        self,
        context: Any,
        execution: Any,
        *,
        trigger: RecoveryTrigger = RecoveryTrigger.PROCESS_RESTART,
        now: Optional[datetime] = None,
    ) -> RecoveryPlan:
        """Decide about one run. Pure policy, recorded as a fact."""
        moment = now or self._clock.now()
        execution_id = str(execution.execution_id)

        expired = tuple(
            run.node_id
            for run in execution.runs
            if run.lease is not None
            and not run.lease.is_released
            and not run.lease.is_live_at(moment)
        )
        retryable = tuple(
            run.node_id
            for run in execution.runs
            if run.state.is_retryable and run.attempts_remaining > 0
        )

        decision = plan_recovery(execution, trigger, retryable_nodes=retryable)

        targets: tuple = ()
        if decision.action is RecoveryAction.COMPENSATE:
            # Newest change first. Undoing A before B would leave B referring to
            # something that no longer exists.
            targets = compensation_order(execution)

        event = ExecutionRecoveryPlanned(
            metadata=self._metadata(context, execution_id),
            execution_id=execution_id,
            action=decision.action.value,
            trigger=decision.trigger.value,
            reason=decision.reason,
            from_checkpoint=decision.from_checkpoint or "",
            subject_nodes=tuple(decision.subject_nodes),
            ambiguous_nodes=tuple(decision.ambiguous_nodes),
            automatic=decision.is_automatic,
        )
        self._publish(context, execution_id, [event])
        self._metrics.increment(
            "execution.recovery.planned",
            labels={
                "tenant": self._require_tenant(context),
                "action": decision.action.value,
            },
        )
        if expired:
            self._metrics.increment(
                "execution.lease.expired",
                value=len(expired),
                labels={"tenant": self._require_tenant(context)},
            )

        return RecoveryPlan(
            execution_id=execution_id,
            decision=decision,
            expired_leases=expired,
            compensation_targets=targets,
            events=(event,),
        )

    # ------------------------------------------------------------------
    # Partial recovery
    # ------------------------------------------------------------------

    def record_partial_recovery(
        self,
        context: Any,
        execution: Any,
        *,
        original_failure: str,
    ) -> Optional[ExecutionPartiallyRecovered]:
        """State that some changes were walked back and some were not.

        Emitted only when it is true: something was compensated *and* something
        was not. A run with nothing outstanding recovered completely and should
        say so through the ordinary completion path; one with nothing
        compensated has not partially recovered, it has simply failed.

        The original failure travels with it. A partial-recovery record that lost
        the reason recovery began is a record of half an incident.
        """
        compensated = tuple(
            run.node_id
            for run in execution.runs
            if run.state is NodeState.COMPENSATED
        )
        outstanding = tuple(
            run.node_id
            for run in execution.runs
            if run.state is NodeState.SUCCEEDED and run.spec.mutates
        )
        ambiguous = tuple(execution.ambiguous_nodes)

        if not compensated or not (outstanding or ambiguous):
            return None

        event = ExecutionPartiallyRecovered(
            metadata=self._metadata(context, str(execution.execution_id)),
            execution_id=str(execution.execution_id),
            compensated_nodes=compensated,
            outstanding_nodes=outstanding,
            ambiguous_nodes=ambiguous,
            original_failure=original_failure,
        )
        self._publish(context, str(execution.execution_id), [event])
        return event

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    @staticmethod
    def _require_tenant(context: Any) -> str:
        tenant = getattr(context, "tenant_id", None)
        if not tenant:
            raise ContractViolation(
                "recovery requires an ExecutionContext carrying a tenant; a "
                "recovery sweep with no tenant would read every tenant's runs"
            )
        return tenant

    @staticmethod
    def _metadata(context: Any, execution_id: str) -> EventMetadata:
        return EventMetadata.create(
            aggregate_id=execution_id,
            aggregate_type="execution",
            scope=context.scope,
            correlation_id=getattr(
                getattr(context, "correlation", None), "correlation_id", None
            ),
            actor=getattr(getattr(context, "identity", None), "principal", None),
        )

    def _publish(self, context: Any, execution_id: str, events: list) -> None:
        if self._outbox is None or not events:
            return
        try:
            self._outbox.record(context, execution_id, events)
        except Exception:  # noqa: BLE001 - publication is not a decision
            log.error("recording recovery events failed", exc_info=True)

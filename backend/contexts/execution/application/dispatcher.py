"""The dispatcher: moves ready nodes toward invocation. Orchestrates, never decides.

What it does
--------------
One cycle: find dispatchable nodes, acquire a lease, build an invocation request,
hand it to the gateway, record what came back, and ask recovery what happens next
when something went wrong.

What it is not allowed to do
------------------------------
Choose a capability. Choose a worker. Authorize. Bind. Rebind. Retry. Compensate
on its own initiative. Manufacture a tenant or a principal. Every one of those
belongs to something that already exists, and the dispatcher's whole value is
that it is the component with no authority of its own — it carries decisions
between the things entitled to make them.

**No loop.** ``cycle`` does one pass and returns. The loop lives in the scheduler,
which can be stopped; a loop in here could not be, and a dispatcher that cannot be
stopped is a dispatcher that keeps starting production work through a shutdown.

**No retry.** A failed node's next move is ``decide_retry`` (ADR-031), which reads
the failure class, the effect semantics and the attempt budget. ``attempts += 1``
is how an ambiguous mutation gets applied twice.

Ownership is the queue's, then the lease's
--------------------------------------------
Two dispatchers reaching for one node must produce exactly one owner. That is
established twice: the queue's ``claim`` is atomic under its lock and hands the
node to one caller, and ``NodeRun.leased_to`` refuses a second holder inside the
aggregate. The queue prevents the wasted work; the aggregate prevents the wrong
outcome. Neither alone is enough — the queue is a hint that can be lost, and the
aggregate check happens after work has already been prepared.

Late answers are classified, never applied
--------------------------------------------
A worker can return after its lease lapsed, after reassignment, and after the run
closed. Every such answer is recorded as history and refused as state. The
alternative is a dead worker reopening a completed run.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Mapping, Optional, Protocol, runtime_checkable

from backend.contracts.errors import ContractViolation
from backend.contexts.execution.application.instrumentation import (
    NullObserver,
    SafeObserver,
)
from backend.contexts.execution.application.invocation_gateway import (
    SecureCapabilityInvocationGateway,
)
from backend.contexts.execution.application.metrics import NullMetrics, SafeMetrics
from backend.contexts.execution.domain.bound_capability import BoundCapability
from backend.contexts.execution.domain.dispatch import (
    DispatchCandidate,
    DispatchRefusal,
    LateResultKind,
    classify_result_arrival,
    dispatchable_nodes,
)
from backend.contexts.execution.domain.effects import profile_for
from backend.contexts.execution.domain.invocation import (
    InvocationRefusal,
    Clock,
    InvocationRefused,
    InvocationRequest,
    SystemClock,
)
from backend.contexts.execution.domain.lifecycle_events import LateResultDiscarded
from backend.contexts.execution.domain.retry import (
    DEFAULT_RETRY_POLICY,
    RetryDecision,
    decide_retry,
)
from backend.contexts.execution.domain.worker_contract import WorkerExecutionResult
from backend.platform.events import EventMetadata

__all__ = [
    "BindingSource",
    "DispatchResult",
    "CycleReport",
    "ExecutionDispatcher",
]

log = logging.getLogger(__name__)


@runtime_checkable
class BindingSource(Protocol):
    """Supplies the capability binding for a node. Implemented at the composition root.

    The dispatcher never resolves or binds — it asks for the binding that
    Connectivity already made for this execution and node. Returning ``None``
    means no binding exists, and the node is refused rather than bound on the
    spot: binding at dispatch time would let the dispatcher choose a provider,
    which is the authority it exists not to have.
    """

    def binding_for(
        self, context: Any, execution_id: str, node_id: str
    ) -> Optional[BoundCapability]: ...


@runtime_checkable
class InvocationRequestFactory(Protocol):
    """Builds the ADR-038 request from a candidate and its binding.

    A seam because the request carries a worker selection, and selection belongs
    to the Phase 3.3.2 fabric reached through the gateway's runtime. The
    composition root wires the two together.
    """

    def build(
        self,
        context: Any,
        candidate: DispatchCandidate,
        binding: BoundCapability,
        *,
        attempt_id: str,
        deadline_at: Optional[datetime],
    ) -> Optional[InvocationRequest]: ...


@dataclass(frozen=True)
class DispatchResult:
    """What happened to one node on one cycle."""

    node_id: str
    dispatched: bool
    refusal: Optional[DispatchRefusal] = None
    invocation_refusal: Optional[str] = None
    outcome: Optional[str] = None
    outcome_known: bool = True
    retry: Optional[RetryDecision] = None
    late: Optional[LateResultKind] = None
    detail: Mapping[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "node_id": self.node_id,
            "dispatched": self.dispatched,
            "refusal": self.refusal.value if self.refusal else None,
            "invocation_refusal": self.invocation_refusal,
            "outcome": self.outcome,
            "outcome_known": self.outcome_known,
            "retry": self.retry.to_dict() if self.retry else None,
            "late": self.late.value if self.late else None,
            **dict(self.detail),
        }


@dataclass(frozen=True)
class CycleReport:
    """One dispatch pass over one execution. Inert — a record, not a handle."""

    execution_id: str
    tenant_id: str
    started_at: datetime
    finished_at: datetime
    considered: int = 0
    dispatched: int = 0
    results: tuple = ()
    refusals: Mapping[str, str] = field(default_factory=dict)
    events: tuple = ()

    @property
    def made_progress(self) -> bool:
        return self.dispatched > 0

    @property
    def unresolved(self) -> tuple:
        return tuple(r.node_id for r in self.results if not r.outcome_known)

    def to_dict(self) -> dict:
        return {
            "execution_id": self.execution_id,
            "tenant_id": self.tenant_id,
            "started_at": self.started_at.isoformat(),
            "finished_at": self.finished_at.isoformat(),
            "considered": self.considered,
            "dispatched": self.dispatched,
            "made_progress": self.made_progress,
            "unresolved": list(self.unresolved),
            "results": [r.to_dict() for r in self.results],
            "refusals": dict(self.refusals),
            "events": [type(e).EVENT_TYPE for e in self.events],
        }


class ExecutionDispatcher:
    """Moves an execution forward by one cycle. Holds no authority of its own."""

    def __init__(
        self,
        *,
        executions: Any,
        gateway: SecureCapabilityInvocationGateway,
        bindings: BindingSource,
        requests: InvocationRequestFactory,
        queue: Optional[Any] = None,
        outbox: Optional[Any] = None,
        observer: Optional[Any] = None,
        metrics: Optional[Any] = None,
        clock: Optional[Clock] = None,
        retry_policy: Any = DEFAULT_RETRY_POLICY,
    ) -> None:
        if not isinstance(gateway, SecureCapabilityInvocationGateway):
            raise ContractViolation(
                "the dispatcher invokes through the ADR-038 gateway; without it "
                "there is no authority chain and dispatch would reach a worker "
                "having checked nothing"
            )
        self._executions = executions
        self._gateway = gateway
        self._bindings = bindings
        self._requests = requests
        self._queue = queue
        self._outbox = outbox
        self._observer = SafeObserver(observer or NullObserver())
        self._metrics = SafeMetrics(metrics or NullMetrics())
        self._clock = clock or SystemClock()
        self._retry_policy = retry_policy

    # ------------------------------------------------------------------
    # One cycle
    # ------------------------------------------------------------------

    def cycle(
        self,
        context: Any,
        execution_id: str,
        *,
        deadline_at: Optional[datetime] = None,
        limit: int = 8,
    ) -> CycleReport:
        """One pass. Returns when it is done; never loops, never sleeps.

        ``limit`` bounds how many nodes one pass will dispatch, so a wide
        workflow cannot let a single execution monopolise a cycle. What was left
        is visible in the report rather than silently dropped.
        """
        started = self._clock.now()
        tenant_id = self._tenant_of(context)
        execution = self._load(context, execution_id)

        candidates, refusals = dispatchable_nodes(
            execution, tenant_id=tenant_id, now=started, deadline_at=deadline_at
        )
        self._metrics.increment(
            "execution.dispatch.cycles", labels={"tenant": tenant_id}
        )
        self._metrics.increment(
            "execution.dispatch.candidates",
            value=len(candidates),
            labels={"tenant": tenant_id},
        )
        self._metrics.increment(
            "execution.dispatch.refused",
            value=len(refusals),
            labels={"tenant": tenant_id},
        )

        results: list = []
        events: list = []
        dispatched = 0
        for candidate in candidates[:limit]:
            result, produced = self._dispatch_one(
                context, candidate, deadline_at=deadline_at
            )
            results.append(result)
            events.extend(produced)
            if result.dispatched:
                dispatched += 1

        if len(candidates) > limit:
            # Stated, not silent. A cycle that quietly dropped work would look
            # like a cycle that found none.
            log.debug(
                "dispatch cycle for %s capped at %d of %d candidates",
                execution_id,
                limit,
                len(candidates),
            )

        return CycleReport(
            execution_id=execution_id,
            tenant_id=tenant_id,
            started_at=started,
            finished_at=self._clock.now(),
            considered=len(candidates),
            dispatched=dispatched,
            results=tuple(results),
            refusals={n: r.value for n, r in refusals.items()},
            events=tuple(events),
        )

    # ------------------------------------------------------------------
    # One node
    # ------------------------------------------------------------------

    def _dispatch_one(
        self,
        context: Any,
        candidate: DispatchCandidate,
        *,
        deadline_at: Optional[datetime],
    ) -> tuple:
        """Claim, lease, invoke once, record. Every failure is a classified fact."""
        events: list = []
        tenant = {"tenant": candidate.tenant_id}

        # 1. Exclusive claim. One dispatcher wins; the rest see the node taken.
        if self._queue is not None and not self._claim(context, candidate):
            self._metrics.increment("execution.lease.conflict", labels=tenant)
            return (
                DispatchResult(
                    node_id=candidate.node_id,
                    dispatched=False,
                    refusal=DispatchRefusal.NODE_LEASED,
                    detail={"conflict": "queue_claim"},
                ),
                events,
            )

        binding = self._bindings.binding_for(
            context, candidate.execution_id, candidate.node_id
        )
        if binding is None:
            self._release(context, candidate)
            return (
                DispatchResult(
                    node_id=candidate.node_id,
                    dispatched=False,
                    invocation_refusal="binding_missing",
                    detail={"reason": "no capability binding exists for this node"},
                ),
                events,
            )

        # Phase 11.3 (ADR-123 F-9): a context the gateway will certainly refuse
        # must not lease. The gateway's tenancy stage refuses EVERY invocation a
        # platform-internal context makes -- but only after the lease below is
        # taken, and the quiet reclaim then rightly declines to take back a
        # lease that has not lapsed. Measured on the live cluster: the runtime's
        # own loop (platform context) leased a tenant's governed read out from
        # under the tenant's reader, the gateway refused it, and the node stayed
        # LEASED for the whole lease term while the reader waited on it. Refusing
        # here takes no lease, records the same refusal, and leaves the node for
        # the context that can invoke it.
        if getattr(context, "is_platform_internal", False):
            self._release(context, candidate)
            self._metrics.increment("execution.invocation.refused", labels=tenant)
            return (
                DispatchResult(
                    node_id=candidate.node_id,
                    dispatched=False,
                    invocation_refusal=InvocationRefusal.TENANT_UNKNOWN.value,
                    detail={
                        "reason": "a platform-internal context cannot invoke a "
                                  "tenant capability; nothing was leased",
                        "retryable": False,
                        "security_relevant": False,
                    },
                ),
                events,
            )

        # 2. The lease. Execution owns it; the aggregate refuses a second holder.
        try:
            self._assign(context, candidate)
        except Exception as exc:  # noqa: BLE001 - a lost race is a fact, not a crash
            self._release(context, candidate)
            self._metrics.increment("execution.lease.conflict", labels=tenant)
            return (
                DispatchResult(
                    node_id=candidate.node_id,
                    dispatched=False,
                    refusal=DispatchRefusal.NODE_LEASED,
                    detail={"conflict": type(exc).__name__},
                ),
                events,
            )
        self._metrics.increment("execution.lease.acquired", labels=tenant)

        attempt_id = self._current_attempt_id(context, candidate)
        request = self._requests.build(
            context,
            candidate,
            binding,
            attempt_id=attempt_id,
            deadline_at=deadline_at,
            lease_holder=self._lease_holder(candidate),
        )
        if request is None:
            self._release(context, candidate)
            return (
                DispatchResult(
                    node_id=candidate.node_id,
                    dispatched=False,
                    invocation_refusal="invocation_request_unavailable",
                    detail={"reason": "no worker selection could be established"},
                ),
                events,
            )

        # 3. The gateway. Every authority is re-checked there, not here.
        try:
            outcome = self._gateway.invoke(context, request, binding)
        except InvocationRefused as refused:
            self._release(context, candidate)
            self._metrics.increment("execution.invocation.refused", labels=tenant)
            # Refused before anything ran, so the node goes back rather than
            # being recorded as a failed attempt against a worker that never saw it.
            self._reclaim_quietly(context, candidate)
            return (
                DispatchResult(
                    node_id=candidate.node_id,
                    dispatched=False,
                    invocation_refusal=refused.reason_code,
                    detail={
                        "retryable": refused.retryable,
                        "security_relevant": refused.refusal.is_security_relevant,
                        # The gateway's own sentence, which says WHICH stage
                        # refused and why ("namespace 'x' is outside this
                        # tenant's connection"). Without it a caller sees only
                        # a code and cannot act (Phase 11.2 F-4; the same
                        # lesson as 11.1-K F-8 for connector health). It is the
                        # message the gateway already considered safe to show a
                        # caller: no credential, no URL, no traceback.
                        "invocation_reason": str(getattr(refused, "safe_message", "") or "")[:400],
                    },
                ),
                events,
            )

        self._metrics.increment("execution.invocation.admitted", labels=tenant)
        result = outcome.result

        # 4. Is this still the answer to the question being asked?
        arrival = self._classify(context, candidate, request, result)
        if not arrival.may_be_applied:
            discarded = self._late_event(context, candidate, request, result, arrival)
            events.append(discarded)
            self._publish(context, candidate.execution_id, [discarded])
            self._metrics.increment(
                "execution.result.duplicate"
                if arrival is LateResultKind.DUPLICATE
                else "execution.result.late",
                labels=tenant,
            )
            return (
                DispatchResult(
                    node_id=candidate.node_id,
                    dispatched=True,
                    outcome=result.outcome.value,
                    outcome_known=result.outcome_is_known,
                    late=arrival,
                    detail={"applied": False},
                ),
                events,
            )

        self._record_outcome_metrics(result, tenant)

        # 5. What happens next -- decided by policy, executed by nobody here.
        retry = self._plan_retry(context, candidate, result)
        return (
            DispatchResult(
                node_id=candidate.node_id,
                dispatched=True,
                outcome=result.outcome.value,
                outcome_known=result.outcome_is_known,
                retry=retry,
                late=LateResultKind.CURRENT,
                detail={"recorded": outcome.recorded},
            ),
            events,
        )

    # ------------------------------------------------------------------
    # Retry -- planned, never performed here
    # ------------------------------------------------------------------

    def _plan_retry(
        self, context: Any, candidate: DispatchCandidate, result: WorkerExecutionResult
    ) -> Optional[RetryDecision]:
        """Ask the Phase 3.1 policy. The dispatcher does not act on the answer.

        Deliberately: a dispatcher that both decided and performed a retry would
        be free to reinterpret its own decision, and the check that stops an
        ambiguous mutation repeating lives in the decision, not in the action.
        """
        if result.succeeded:
            return None
        execution = self._load(context, candidate.execution_id)
        run = execution.run_for(candidate.node_id)
        if run is None:
            return None
        decision = decide_retry(
            node_id=candidate.node_id,
            attempts_spent=run.attempt_count,
            attempts_allowed=run.spec.max_attempts,
            # The whole spec, not just its side effect: the effect profile is
            # derived from the side effect *and* the idempotency key, and an
            # idempotency key is the only evidence this platform accepts that a
            # repeat is safe. Passing the class alone would silently classify
            # every keyed write as unkeyed and refuse retries that are fine.
            effect=profile_for(run.spec),
            failure=result.failure,
            policy=self._retry_policy,
        )
        self._metrics.increment(
            "execution.retry.decided" if decision.may_run_again else "execution.retry.refused",
            labels={"tenant": candidate.tenant_id},
        )
        return decision

    # ------------------------------------------------------------------
    # Collaborators
    # ------------------------------------------------------------------

    def _classify(
        self,
        context: Any,
        candidate: DispatchCandidate,
        request: InvocationRequest,
        result: WorkerExecutionResult,
    ) -> LateResultKind:
        execution = self._load(context, candidate.execution_id)
        return classify_result_arrival(
            execution,
            node_id=candidate.node_id,
            attempt_id=str(request.attempt_id),
            worker_id=request.worker_id,
            now=self._clock.now(),
        )

    def _claim(self, context: Any, candidate: DispatchCandidate) -> bool:
        try:
            claimed = self._queue.claim(
                context, worker_id=f"dispatcher:{candidate.execution_id}", limit=1
            )
        except TypeError:
            # An older queue signature. Treated as unclaimable rather than
            # assumed free -- the aggregate's lease check still decides.
            return True
        except Exception:  # noqa: BLE001
            log.debug("queue claim failed", exc_info=True)
            return True
        if not claimed:
            return True
        return any(item.node_id == candidate.node_id for item in claimed)

    def _release(self, context: Any, candidate: DispatchCandidate) -> None:
        if self._queue is None:
            return
        try:
            self._queue.release(context, candidate.execution_id, candidate.node_id)
        except Exception:  # noqa: BLE001
            log.debug("queue release failed", exc_info=True)

    @staticmethod
    def _lease_holder(candidate: DispatchCandidate) -> str:
        """Who holds this node's lease. **One definition, two readers.**

        The dispatcher is the lease holder: ADR-036 §9 gives lease ownership to
        Execution and forbids a worker from holding one. This identity is written
        into the aggregate by ``_assign`` and handed to the gateway on the
        request, and both must be the same string -- so it is computed here and
        nowhere else. Two spellings of the dispatcher's own name would refuse
        every invocation and look like a lease bug.
        """
        return f"dispatcher:{candidate.execution_id}"

    def _assign(self, context: Any, candidate: DispatchCandidate) -> Any:
        from backend.contexts.execution.application.commands import AssignNode

        return self._executions.assign(
            context,
            AssignNode(
                execution_id=candidate.execution_id,
                node_id=candidate.node_id,
                worker_id=self._lease_holder(candidate),
            ),
        )

    def _reclaim_quietly(self, context: Any, candidate: DispatchCandidate) -> None:
        """Return a node whose invocation was refused before anything ran.

        Uses the ordinary reclaim path, which records ``UNKNOWN`` rather than
        failure. That is deliberate even though nothing ran: reclaim is the
        aggregate's one way back from ``LEASED``, and asserting "nothing
        happened" through a different path would be a second opinion about a
        state the aggregate already models.
        """
        from backend.contexts.execution.application.commands import ReclaimNode

        try:
            self._executions.reclaim(
                context,
                ReclaimNode(
                    execution_id=candidate.execution_id, node_id=candidate.node_id
                ),
            )
        except Exception:  # noqa: BLE001
            log.debug("reclaim after refused invocation failed", exc_info=True)

    def _current_attempt_id(self, context: Any, candidate: DispatchCandidate) -> str:
        execution = self._load(context, candidate.execution_id)
        run = execution.run_for(candidate.node_id)
        attempt = run.current_attempt if run else None
        if attempt is None:
            raise ContractViolation(
                f"node {candidate.node_id!r} was leased but has no open attempt; "
                "there is nothing for a result to be recorded against"
            )
        return str(attempt.attempt_id)

    def _load(self, context: Any, execution_id: str) -> Any:
        from backend.contexts.execution.application.commands import GetExecution

        return self._executions.get(context, GetExecution(execution_id=execution_id))

    @staticmethod
    def _tenant_of(context: Any) -> str:
        tenant = getattr(context, "tenant_id", None)
        if not tenant:
            raise ContractViolation(
                "dispatch requires an ExecutionContext carrying a tenant; there is "
                "no ambient tenant and no default"
            )
        return tenant

    def _record_outcome_metrics(self, result: WorkerExecutionResult, tenant: dict) -> None:
        if result.succeeded:
            self._metrics.increment("execution.outcome.success", labels=tenant)
        elif result.outcome_is_known:
            self._metrics.increment("execution.outcome.failure", labels=tenant)
        else:
            self._metrics.increment("execution.outcome.unknown", labels=tenant)
        self._metrics.observe(
            "execution.worker.latency", result.duration_seconds, labels=tenant
        )

    def _late_event(
        self,
        context: Any,
        candidate: DispatchCandidate,
        request: InvocationRequest,
        result: WorkerExecutionResult,
        arrival: LateResultKind,
    ) -> LateResultDiscarded:
        return LateResultDiscarded(
            metadata=EventMetadata.create(
                aggregate_id=candidate.execution_id,
                aggregate_type="execution",
                scope=context.scope,
                correlation_id=request.correlation_id,
                causation_id=request.causation_id,
            ),
            execution_id=candidate.execution_id,
            node_id=candidate.node_id,
            attempt_id=str(request.attempt_id),
            worker_id=request.worker_id,
            kind=arrival.value,
            reported_outcome=result.outcome.value,
            # A mutating node whose answer arrived late may have applied the
            # change. Saying so is the point of keeping the record.
            may_have_mutated=candidate.mutates and not result.outcome_is_known,
            operationally_serious=arrival.is_operationally_serious,
        )

    def _publish(self, context: Any, execution_id: str, events: list) -> None:
        if self._outbox is None or not events:
            return
        try:
            self._outbox.record(context, execution_id, events)
        except Exception:  # noqa: BLE001 - publication is not a decision
            log.error("recording dispatch events failed", exc_info=True)

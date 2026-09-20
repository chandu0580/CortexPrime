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

Ownership is the lease's, and the queue is only a hint
--------------------------------------------------------
Two dispatchers reaching for one node must produce exactly one owner, and the
thing that establishes it is the **revision-checked lease**: ``assign`` writes
through ``compare_and_swap``, so the compare and the swap are one statement and
the loser is refused rather than overwritten (ADR-127 D-1).

This used to claim ownership was established twice, by the queue and then by the
aggregate. It was not. The queue claim was called with a signature no
implementation of the port accepts, so every call raised ``TypeError`` into a
handler that returned "proceed" — a claim reported as obtained and never made,
on every dispatch (ADR-127 F-2). Nothing enqueues either, so the queue is empty
in any case. It is kept as what it honestly is: a hint about *where* work is,
which saves wasted preparation when present and is safe to lose, because the
lease is what decides.

The aggregate's own "refuses a second holder" check is still there and still
useful, but note what it is: a check against the copy *this* caller loaded. On
its own it does not fence two processes — which is why the write is
revision-checked, and why the revision must be read in the same statement as the
aggregate (ADR-127 F-7).

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


def _context_from_binding(context: Any, binding: BoundCapability) -> Optional[Any]:
    """The tenant context this node's sealed binding was written for.

    **Read this as: carrying a decision, not making one** (ADR-127 D-2, ratified
    2026-09-20). ``cp_binding`` is written at resolve time, *after* identity,
    tenancy and authorization have already been decided, and it is
    content-addressed — so the tenant and principal in it are the ones the work
    was authorized for, not ones this process chose.

    Nothing here grants anything. The gateway re-runs every stage against
    durable records, and because both the request and this context derive from
    the same binding, a dispatcher cannot name a tenant, a principal or a
    capability other than the one already admitted. What it *can* now do is
    dispatch work some other process started, which is the whole point.

    Returns ``None`` — and the caller refuses — when the binding does not name
    both a tenant and a principal. A half-identified dispatch is not dispatched.
    """
    tenant_id = getattr(binding, "tenant_id", None)
    principal_id = getattr(binding, "principal_id", None)
    if not tenant_id or not principal_id:
        return None
    try:
        from backend.contracts.identity import PrincipalKind, PrincipalRef
        from backend.platform.context import ExecutionContext, IdentityContext

        return ExecutionContext.for_tenant(
            tenant_id=str(tenant_id),
            identity=IdentityContext(
                principal=PrincipalRef(
                    principal_id=str(principal_id), kind=PrincipalKind.PLATFORM
                ),
                capabilities=("capability:invoke",),
            ),
            # Named so an auditor reading the trail can tell a resumed dispatch
            # from a caller standing at the other end of a socket.
            source="execution.dispatcher",
            correlation=getattr(context, "correlation", None),
        )
    except Exception:  # noqa: BLE001 - an unbuildable context is a refusal
        log.error(
            "could not rebuild a dispatch context for %s/%s",
            getattr(binding, "execution_id", "?"),
            getattr(binding, "node_id", "?"),
            exc_info=True,
        )
        return None


def _worker_kind_of(candidate: DispatchCandidate) -> Optional[Any]:
    """The candidate's worker kind as the queue's enum, or ``None``.

    The candidate carries the kind as text because it came out of the stored
    aggregate. ``None`` for an unrecognised kind rather than a guess: claiming
    for the wrong kind would take work this dispatcher cannot run.
    """
    from backend.contexts.execution.domain.worker import WorkerKind

    try:
        return WorkerKind(str(candidate.worker_kind))
    except (ValueError, TypeError):
        return None


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
        claim_seconds: int = 60,
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
        if not isinstance(claim_seconds, int) or claim_seconds < 1:
            raise ContractViolation("a queue claim must last at least a second")
        self._claim_seconds = claim_seconds

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
            # Phase 11.3 (ADR-127 D-2, ratified): before refusing, try to become
            # a context that *can* invoke -- rebuilt from this node's own sealed
            # binding, which was written at resolve time carrying the tenant and
            # principal the request was authorized for.
            #
            # This does not relax F-9's rule. F-9's rule is "never lease under a
            # context the gateway will certainly refuse", and it is kept exactly:
            # the reconstructed context matches the binding by construction, so
            # it is the one context the gateway will not refuse on tenancy. The
            # refusal below still stands for every case where no such context can
            # be built.
            #
            # It confers nothing. The binding is a record of a decision already
            # made -- identity, tenancy and authorization were all decided before
            # it was written -- and every gateway stage re-runs against durable
            # records, both sides deriving from this same binding. A dispatcher
            # carrying a decision cannot widen it.
            rebuilt = _context_from_binding(context, binding)
            if rebuilt is not None:
                context = rebuilt
                self._metrics.increment("execution.dispatch.rebound", labels=tenant)
            else:
                self._release(context, candidate)
                self._metrics.increment("execution.invocation.refused", labels=tenant)
                return (
                    DispatchResult(
                        node_id=candidate.node_id,
                        dispatched=False,
                        invocation_refusal=InvocationRefusal.TENANT_UNKNOWN.value,
                        detail={
                            "reason": "a platform-internal context cannot invoke a "
                            "tenant capability, and this node's binding did not "
                            "name a tenant and principal to dispatch as",
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
        """Take this node from the queue, if the queue knows about it.

        **This layer was dead.** It called ``claim(context, worker_id=…,
        limit=1)``, which no implementation of the port accepts -- the port is
        ``(context, worker_id, kinds, seconds)``. Every call raised ``TypeError``
        into an ``except TypeError: return True``, so the claim reported success
        it had never obtained, on every dispatch, silently. Nothing enqueues
        either, so even the correct call would have found an empty queue. The
        module docstring's "ownership is the queue's, then the lease's" described
        a layer that did not run (Phase 11.3 F-2).

        The signature is now the port's, and the ``TypeError`` branch is gone
        rather than kept as a safety net: with the right call it can only mask a
        future signature regression, which is the defect it just caused.

        An *absent* item still means proceed. The queue is a hint about where
        work is, not the authority on who owns it -- the docstring is right that
        it "can be lost" -- and the revision-checked lease (D-1) is what actually
        refuses a second holder. What must never happen again is reporting a
        claim that was never made.
        """
        kind = _worker_kind_of(candidate)
        try:
            claimed = self._queue.claim(
                context,
                f"dispatcher:{candidate.execution_id}",
                (kind,) if kind is not None else (),
                self._claim_seconds,
            )
        except Exception:  # noqa: BLE001 - a queue outage is not a decision
            # Loud, not debug: this is the line whose silence hid F-2.
            log.error("queue claim failed for %s/%s", candidate.execution_id,
                      candidate.node_id, exc_info=True)
            self._metrics.increment(
                "execution.queue.unavailable", labels={"tenant": candidate.tenant_id}
            )
            return True
        if not claimed:
            return True
        items = claimed if isinstance(claimed, (list, tuple)) else (claimed,)
        return any(item.node_id == candidate.node_id for item in items)

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

        holder = self._lease_holder(candidate)
        self._ensure_capacity(holder, candidate)
        return self._executions.assign(
            context,
            AssignNode(
                execution_id=candidate.execution_id,
                node_id=candidate.node_id,
                worker_id=holder,
            ),
        )

    def _ensure_capacity(self, holder: str, candidate: DispatchCandidate) -> None:
        """Make sure *this* process's pool knows the holder it is about to use.

        The lease holder is ``dispatcher:<execution id>`` and the pool that
        answers "how much can it take?" is process-local. Until now only the
        process that *started* the execution registered that entry, so a second
        dispatcher failed at ``UnknownWorker`` before it ever reached the lease
        — which is the capacity half of ADR-127 F-4.

        Registering it here is not a grant. The pool answers capacity, never
        authority: whether this worker may be *selected* is the durable
        directory's answer, and whether the invocation is permitted at all is
        re-decided by the gateway against the stored binding, authorization and
        approval. What this removes is an accident of which process happened to
        create the run.
        """
        kind = _worker_kind_of(candidate)
        if kind is None:
            return  # an unknown kind registers nothing; selection refuses it
        pool = getattr(self._executions, "pool", None)
        if pool is None:
            return
        try:
            pool.get(holder)
            return
        except Exception:  # noqa: BLE001 - absent is the ordinary case
            pass
        from backend.contexts.execution.application.commands import RegisterWorker

        try:
            self._executions.register_worker(
                RegisterWorker(
                    worker_id=holder,
                    kinds=(kind.value,),
                    lease_seconds=self._claim_seconds,
                )
            )
        except Exception:  # noqa: BLE001 - a lost registration race is harmless
            log.debug("lease-holder registration failed", exc_info=True)

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

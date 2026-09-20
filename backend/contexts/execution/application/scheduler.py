"""The scheduler: an explicitly controlled lifecycle around the dispatcher.

Why the loop lives here and nowhere else
------------------------------------------
The domain has no loop and the dispatcher has no loop. Both do one bounded thing
and return, which is what makes them testable without a clock and stoppable
without a flag. The loop is the one part that genuinely has to keep going, so it
is isolated here behind ``start`` / ``stop`` / ``recover`` — three methods, all
explicit, none of them a daemon that starts itself on import.

This is a mechanism, and a replaceable one
--------------------------------------------
`ExecutionScheduler` is deliberately thin. Nothing in the execution *authority*
depends on how cycles are triggered — a thread, a cron, a queue consumer, a
Kubernetes job, or a test calling ``tick()`` once are all equivalent to
everything below it. Replacing this with real distributed infrastructure changes
no domain code, and that property is the point of the phase rather than the
thread implementation in it.

Distributed in Phase 5.2, and only where a singleton is genuinely needed
--------------------------------------------------------------------------
The loop is still a background thread in one process — that part is unchanged
and still replaceable. What Phase 5.2 added is two ports:

``leadership``  a durable, fenced role. Several instances may run this
                scheduler; exactly one of them coordinates. Every other instance
                ticks, finds it is not the leader, and does nothing.
``readiness``   whether durable state is usable. Without it the scheduler will
                not dispatch **authoritative work**, because a dispatch it
                cannot durably record is a side effect nothing will remember.

Both are optional and both fail closed when present. Absent, the scheduler
behaves exactly as it did in Phase 3.3.4 — a single process, coordinating
because nobody told it not to — which is the correct behaviour for a deployment
that has not adopted durability.

**It is still not a distributed *executor*.** Leadership coordinates; the durable
queue is what actually scales horizontally, and several dispatchers claiming from
it is the supported shape. Electing a leader for ordinary dispatch would take a
system that scales and give it a bottleneck and a failover gap.

Shutdown never invents an outcome
-----------------------------------
``stop`` stops *dispatch*. It does not cancel leases, does not mark running work
finished, and does not conclude anything. Work that was in flight stays in
flight, its lease lapses on its own schedule, and recovery decides what happened
— which is the only honest answer, because a process shutting down knows nothing
about what a worker did.
"""

from __future__ import annotations

import logging
import threading
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Optional, Protocol, Sequence, runtime_checkable

from backend.contracts.errors import ContractViolation
from backend.contexts.execution.application.dispatcher import ExecutionDispatcher
from backend.contexts.execution.application.metrics import NullMetrics, SafeMetrics
from backend.contexts.execution.application.recovery_coordinator import (
    RecoveryCoordinator,
    StartupReport,
)
from backend.contexts.execution.domain.invocation import Clock, SystemClock
from backend.contexts.execution.domain.recovery import RecoveryAction, RecoveryTrigger

__all__ = [
    "SchedulerState",
    "TickReport",
    "ExecutionScheduler",
    "LeadershipPort",
    "ReadinessPort",
]

log = logging.getLogger(__name__)


@runtime_checkable
class LeadershipPort(Protocol):
    """Durable, fenced leadership for the scheduler role.

    Implemented at the composition root over ``SqlLeadershipStore``. Three
    methods and no more: this context does not need to know what a fencing token
    is, only that it either holds the role or does not.

    **Absence is not a bypass** — it is the single-instance deployment, which
    coordinates because nobody else is running. Presence fails closed: a
    leadership port that raises is treated as not holding the role.
    """

    def acquire(self) -> Optional[Any]: ...

    def heartbeat(self, handle: Any) -> Optional[Any]: ...

    def release(self, handle: Any) -> bool: ...


@runtime_checkable
class ReadinessPort(Protocol):
    """Whether durable state is usable right now.

    Read every tick rather than once at startup: a database that went away after
    the process started is exactly the case this exists for, and a scheduler that
    checked once would keep dispatching work it cannot record.
    """

    def is_ready(self) -> bool: ...


class SchedulerState(str, Enum):
    """Where the scheduler is. Five states, no implicit ones."""

    STOPPED = "stopped"
    RECOVERING = "recovering"
    """Startup recovery is running. Dispatch has not begun, deliberately: starting
    work before establishing what the last process left behind is how a run gets
    a second attempt at something that already happened."""

    RUNNING = "running"
    DRAINING = "draining"
    """Stopping. No new dispatch; the current cycle is allowed to finish rather
    than being abandoned halfway through recording a result."""

    FAILED = "failed"
    """The loop stopped because something it cannot recover from happened —
    durable state became unusable, or startup recovery raised.

    Distinct from ``STOPPED`` because 'we stopped it' and 'it broke' need
    different responses, and a scheduler that reported a fault as an orderly
    stop would be restarted by an operator who thought nothing was wrong."""

    #: The Phase 5.2 vocabulary, as aliases rather than new states. ``STARTING``
    #: and ``QUIESCING`` are what the coordination directive calls the two this
    #: platform already had; adding a second pair of states with the same meaning
    #: would be two things to keep in step for no gain.
    STARTING = "recovering"
    QUIESCING = "draining"

    @property
    def accepts_dispatch(self) -> bool:
        return self is SchedulerState.RUNNING

    @property
    def is_terminal(self) -> bool:
        return self in {SchedulerState.STOPPED, SchedulerState.FAILED}


@dataclass(frozen=True)
class TickReport:
    """One scheduler pass across the executions it was given."""

    at: datetime
    cycles: tuple = ()
    dispatched: int = 0
    skipped: bool = False
    reason: str = ""

    def to_dict(self) -> dict:
        return {
            "at": self.at.isoformat(),
            "dispatched": self.dispatched,
            "skipped": self.skipped,
            "reason": self.reason,
            "cycles": [c.to_dict() for c in self.cycles],
        }


class ExecutionScheduler:
    """Drives dispatch cycles with an explicit, stoppable lifecycle."""

    def __init__(
        self,
        *,
        dispatcher: ExecutionDispatcher,
        recovery: RecoveryCoordinator,
        context_factory: Callable[[], Any],
        interval_seconds: float = 1.0,
        metrics: Optional[Any] = None,
        clock: Optional[Clock] = None,
        leadership: Optional[LeadershipPort] = None,
        readiness: Optional[ReadinessPort] = None,
        discovery: Optional[Callable[[Any], Sequence[str]]] = None,
        discovery_limit: int = 100,
        discovery_interval_seconds: float = 5.0,
    ) -> None:
        if interval_seconds <= 0:
            raise ContractViolation(
                "a scheduler interval must be positive; zero would spin a core and "
                "starve the work it is trying to dispatch"
            )
        self._dispatcher = dispatcher
        self._recovery = recovery
        self._context_factory = context_factory
        self._interval = interval_seconds
        self._metrics = SafeMetrics(metrics or NullMetrics())
        self._clock = clock or SystemClock()
        self._leadership = leadership
        self._readiness = readiness
        self._discovery = discovery
        self._discovery_limit = discovery_limit
        self._discovery_interval = max(0.0, float(discovery_interval_seconds))
        self._discovered_at: Optional[float] = None

        self._state = SchedulerState.STOPPED
        self._lock = threading.RLock()
        self._stopping = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._targets: list = []
        self._handle: Optional[Any] = None
        self._failure: Optional[str] = None

    # ------------------------------------------------------------------
    # State
    # ------------------------------------------------------------------

    @property
    def state(self) -> SchedulerState:
        with self._lock:
            return self._state

    @property
    def is_running(self) -> bool:
        return self.state is SchedulerState.RUNNING

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def recover(self, context: Optional[Any] = None) -> StartupReport:
        """Establish what the last process left behind. Invokes nothing.

        Runs before dispatch, always. What it returns is a set of decisions:
        automatic ones the scheduler may act on, and everything else — unresolved
        outcomes, owed rollbacks — that waits for a person. Startup does not
        execute arbitrary work on the strength of having restarted.
        """
        with self._lock:
            self._state = SchedulerState.RECOVERING
        ctx = context or self._context_factory()
        try:
            report = self._recovery.recover(ctx, trigger=RecoveryTrigger.PROCESS_RESTART)
        finally:
            with self._lock:
                if self._state is SchedulerState.RECOVERING:
                    self._state = SchedulerState.STOPPED

        log.info(
            "startup recovery: %d scanned, %d resumable, %d awaiting a human, %d blocked",
            report.scanned,
            len(report.resumable),
            len(report.awaiting_human),
            len(report.blocked),
        )
        # Only the automatic decisions become dispatch targets. Everything else
        # stays out of the loop until somebody decides.
        with self._lock:
            self._targets = [
                plan.execution_id
                for plan in report.plans
                if plan.is_automatic
                and plan.action
                in (RecoveryAction.RESUME_FROM_CHECKPOINT, RecoveryAction.RETRY_ATTEMPT)
            ]
        return report

    def start(self, context: Optional[Any] = None) -> StartupReport:
        """Recover, then begin dispatching. Idempotent.

        Recovery first and unconditionally. A scheduler that dispatched before
        recovering would start new work beside an outcome nobody had established.
        """
        with self._lock:
            if self._state is SchedulerState.RUNNING:
                raise ContractViolation("the scheduler is already running")
            self._failure = None

        try:
            report = self.recover(context)
        except Exception as exc:  # noqa: BLE001
            # Startup recovery failed. The scheduler does **not** begin
            # dispatching anyway: it would be starting new work beside outcomes
            # nobody established, which is the one thing recovery exists to
            # prevent. FAILED rather than STOPPED, so an operator can tell this
            # from an orderly shutdown.
            with self._lock:
                self._state = SchedulerState.FAILED
                self._failure = f"startup recovery failed ({type(exc).__name__})"
            log.error("scheduler startup recovery failed", exc_info=True)
            raise

        self._stopping.clear()
        with self._lock:
            self._state = SchedulerState.RUNNING
            self._thread = threading.Thread(
                target=self._run, name="cortexprime-execution-scheduler", daemon=True
            )
            self._thread.start()
        return report

    def stop(self, *, timeout_seconds: float = 30.0) -> None:
        """Stop dispatching. Preserves everything in flight.

        Does **not** cancel leases, conclude attempts, or mark running work
        finished. A process shutting down knows nothing about what a worker did,
        so it says nothing about it — the lease lapses on its own schedule and
        recovery decides. Marking active work successful on shutdown is the one
        thing this must never do.
        """
        with self._lock:
            if self._state.is_terminal:
                # Idempotent, including after a failure: stopping something that
                # already stopped is a no-op, not an error.
                self._release_leadership()
                return
            self._state = SchedulerState.DRAINING
        self._stopping.set()

        thread = self._thread
        if thread is not None and thread.is_alive():
            # Waits for the current cycle rather than abandoning it mid-record.
            thread.join(timeout=timeout_seconds)
            if thread.is_alive():
                log.warning(
                    "scheduler did not finish its cycle within %ss; leases remain "
                    "held and recovery will decide about them",
                    timeout_seconds,
                )
        # Order matters, and it is the order of §30: stop scheduling, stop
        # claiming, leave active leases alone, then give the role back. Releasing
        # leadership *last* means a successor cannot start coordinating while
        # this one is still finishing a cycle.
        self._release_leadership()
        with self._lock:
            self._state = SchedulerState.STOPPED
            self._thread = None

    def _release_leadership(self) -> None:
        """Give the role back so a successor need not wait out the expiry.

        Best effort and never raising: a shutdown that failed because it could
        not reach the database would leave the process alive holding a role it
        is no longer using, which is worse than a role that lapses on its own.
        """
        with self._lock:
            handle, self._handle = self._handle, None
        if handle is None or self._leadership is None:
            return
        try:
            self._leadership.release(handle)
        except Exception:  # noqa: BLE001
            log.warning(
                "releasing scheduler leadership failed; it will lapse on expiry",
                exc_info=False,
            )

    # ------------------------------------------------------------------
    # Work
    # ------------------------------------------------------------------

    def tick(self, context: Optional[Any] = None) -> TickReport:
        """One pass over the current targets. The unit a test or a cron drives.

        Public and synchronous on purpose: everything the background thread does
        is this, so a deployment that would rather trigger cycles from outside
        needs no different code path.
        """
        now = self._clock.now()
        if not self.state.accepts_dispatch and context is None:
            return TickReport(at=now, skipped=True, reason=self.state.value)

        # 1. Durable state, before anything else. A dispatch this process cannot
        #    record is a side effect nothing will remember, which is worse than
        #    not dispatching at all.
        if not self._durable_state_ready():
            self._metrics.increment("scheduler.skipped", labels={"reason": "not_ready"})
            return TickReport(at=now, skipped=True, reason="durability_unavailable")

        # 2. Leadership. Several instances may run this scheduler; exactly one
        #    coordinates. A follower ticks, finds it is not the leader, and does
        #    nothing -- which is the whole point of it being cheap.
        if not self._hold_leadership():
            self._metrics.increment("scheduler.skipped", labels={"reason": "not_leader"})
            return TickReport(at=now, skipped=True, reason="not_leader")

        ctx = context or self._context_factory()
        with self._lock:
            targets = list(self._targets)
        targets = self._with_discovered(ctx, targets, caller_driven=context is not None)

        cycles: list = []
        dispatched = 0
        for execution_id in targets:
            if self._stopping.is_set():
                # Stop between executions, never mid-execution.
                break
            try:
                report = self._dispatcher.cycle(ctx, execution_id)
            except Exception:  # noqa: BLE001 - one bad run never stops the sweep
                log.error("dispatch cycle for %s failed", execution_id, exc_info=True)
                continue
            cycles.append(report)
            dispatched += report.dispatched

        return TickReport(at=now, cycles=tuple(cycles), dispatched=dispatched)

    def _with_discovered(
        self, context: Any, targets: list, *, caller_driven: bool = False
    ) -> list:
        """The tracked set, plus whatever the durable store says is dispatchable.

        **This is the fix for F-3** (ADR-127; the signal-fabric report's F-1).
        ``_targets`` is process-local, so a run started anywhere else was
        dispatched by nobody, forever. Asking the store each tick makes dispatch
        a property of the run rather than of the process that created it.

        The tracked set is kept rather than replaced: a caller driving its own
        execution through ``tick`` still gets it dispatched on the tick it asked
        for, without waiting to be rediscovered.

        Discovery grants nothing -- it is a bounded, tenant-narrowed read, and
        every candidate is still authorized in full downstream. A discovery
        failure degrades to the tracked set rather than stopping dispatch:
        losing the query should cost the executions nobody is holding, not the
        ones somebody is waiting on.
        """
        if self._discovery is None:
            return targets

        # **Discovery is a background sweep, not something to do on every tick.**
        # Two guards, both learned the same way -- by breaking a real run.
        #
        # 1. A caller-driven tick does the caller's work, not the store's. A
        #    governed read drives ``tick`` in a tight loop waiting for its own
        #    node; sweeping there makes every caller pay for every orphan.
        # 2. Even the background loop sweeps on an interval rather than at its
        #    tick rate.
        #
        # Measured: governed reads never finalise their aggregate, so a live
        # database held 1382 runs in RUNNING. Discovering per tick meant one
        # governed read cycled up to 100 unrelated runs on each of up to 450
        # ticks -- tens of thousands of dispatch cycles for a single read, and
        # the run wedged (ADR-127 F-9).
        if caller_driven:
            return targets
        now = self._clock.now().timestamp()
        if (
            self._discovered_at is not None
            and (now - self._discovered_at) < self._discovery_interval
        ):
            return targets
        self._discovered_at = now
        try:
            discovered = self._discovery(context) or ()
        except Exception:  # noqa: BLE001 - a failed query is not a decision
            log.error("durable dispatch discovery failed", exc_info=True)
            self._metrics.increment("scheduler.discovery.failed")
            return targets
        known = set(targets)
        for execution_id in discovered:
            if execution_id not in known:
                known.add(execution_id)
                targets.append(execution_id)
        return targets

    def track(self, execution_id: str) -> None:
        """Add an execution to the dispatch set."""
        if not isinstance(execution_id, str) or not execution_id.strip():
            raise ContractViolation("execution_id must be non-blank text")
        with self._lock:
            if execution_id not in self._targets:
                self._targets.append(execution_id)

    def untrack(self, execution_id: str) -> None:
        with self._lock:
            if execution_id in self._targets:
                self._targets.remove(execution_id)

    @property
    def targets(self) -> tuple:
        with self._lock:
            return tuple(self._targets)

    # ------------------------------------------------------------------
    # Coordination
    # ------------------------------------------------------------------

    def _durable_state_ready(self) -> bool:
        """Whether durable state is usable. Fails closed on any doubt.

        No port wired means the deployment has not adopted durability, and the
        scheduler behaves as it did before — that is a deliberate difference from
        a port that says *no*, which stops dispatch.
        """
        if self._readiness is None:
            return True
        try:
            return bool(self._readiness.is_ready())
        except Exception:  # noqa: BLE001 - unverifiable durability is unusable
            log.warning("durability readiness check failed", exc_info=False)
            return False

    def _hold_leadership(self) -> bool:
        """Acquire or renew the scheduler role. ``True`` only while holding it.

        Renewal is fenced by the store, so an instance whose role was taken while
        it was stalled gets ``None`` back and stops coordinating. What it does
        **not** do is touch running work: active leases govern that, and a
        scheduler that killed workers on losing an election would turn a
        coordination hiccup into a production incident.
        """
        if self._leadership is None:
            return True
        try:
            with self._lock:
                handle = self._handle
            if handle is None:
                handle = self._leadership.acquire()
            else:
                handle = self._leadership.heartbeat(handle)
                if handle is None:
                    self._metrics.increment("leader.lost", labels={"role": "scheduler"})
                    log.warning(
                        "scheduler lost leadership; it stops scheduling and leaves "
                        "in-flight work to its own execution leases"
                    )
                    # Try to take it back on this same tick. A brief loss during
                    # a slow cycle should not cost a whole interval.
                    handle = self._leadership.acquire()
            with self._lock:
                self._handle = handle
            return handle is not None
        except Exception:  # noqa: BLE001 - unverifiable leadership is no leadership
            log.warning("leadership check failed", exc_info=False)
            with self._lock:
                self._handle = None
            return False

    @property
    def leadership_handle(self) -> Optional[Any]:
        """The current handle, for a caller that must carry the fence into a write."""
        with self._lock:
            return self._handle

    @property
    def failure(self) -> Optional[str]:
        with self._lock:
            return self._failure

    def status(self) -> dict:
        """What an operator needs, without contacting anything."""
        with self._lock:
            handle = self._handle
            return {
                "state": self._state.value,
                "targets": len(self._targets),
                "leader": handle is not None,
                "fencing_token": getattr(handle, "fencing_token", None),
                "instance_id": getattr(handle, "instance_id", None),
                "failure": self._failure,
                "coordinated": self._leadership is not None,
                "durability_gated": self._readiness is not None,
            }

    # ------------------------------------------------------------------
    # The loop -- the only one in the phase
    # ------------------------------------------------------------------

    def _run(self) -> None:
        """The background loop. Exits on the stop event, never on an exception.

        ``wait`` rather than ``sleep`` so a shutdown is observed immediately
        instead of after the interval elapses — a scheduler that sleeps through
        its own shutdown holds the process open for no reason.
        """
        while not self._stopping.is_set():
            try:
                self.tick()
            except Exception:  # noqa: BLE001 - a failed tick must not kill the loop
                log.error("scheduler tick failed", exc_info=True)
            self._stopping.wait(self._interval)

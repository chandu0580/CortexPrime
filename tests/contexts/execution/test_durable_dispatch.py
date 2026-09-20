"""Phase 11.3 (ADR-127 F-1, F-2): the two layers that were supposed to stop a
second dispatcher, and did not.

F-1 -- the node lease was not fenced. ``ExecutionService.assign`` wrote through
``replace``, the unguarded write, after checking "is this node free?" against
the copy *this* caller had loaded. Two callers that both loaded an unleased node
both wrote, and the second silently erased the first's lease while both believed
they owned the node. Reproduced against real PostgreSQL before the fix: two
winners. It never bit only because exactly one process dispatched -- which means
the limitation ADR-126 called F-3 was the thing holding the hole shut.

F-2 -- the queue claim was dead. It was called with a signature no
implementation of the port accepts, so every call raised ``TypeError`` into an
``except TypeError: return True``: a claim reported as obtained on every
dispatch, and never made.
"""
from __future__ import annotations

import pytest

from backend.contexts.execution import (
    ExecutionService,
    InMemoryExecutionRepository,
    RegisterWorker,
    StartExecution,
)
from backend.contexts.execution.application.commands import AssignNode
from backend.contexts.execution.application.dispatcher import ExecutionDispatcher
from backend.contexts.execution.domain.dispatch import DispatchCandidate
from backend.contexts.execution.domain.worker import WorkerKind
from backend.contexts.execution.infrastructure.repository import (
    ConcurrentExecutionUpdate,
)
from backend.contracts.identity import PrincipalKind, PrincipalRef
from backend.platform.context import ExecutionContext, IdentityContext
from tests.contexts.execution.test_invocation_gateway_matrix import Fixture



def _id(execution_id):
    from backend.contexts.execution.domain.identifiers import ExecutionId

    return ExecutionId(execution_id)


class _StaleOnce:
    """A repository that hands back the snapshot a caller read earlier.

    Models the only thing that matters about a second process: it decided from
    a copy that was current when it loaded and is not current when it writes.
    Writes go to the real store, so the revision check meets the real revision.
    """

    def __init__(self, real, snapshot):
        self._real = real
        self._snapshot = snapshot

    def find(self, context, execution_id, **kwargs):
        return self._snapshot

    def revision_of(self, context, execution_id, **kwargs):
        # The revision the stale reader would have seen alongside its snapshot.
        return 1

    def find_with_revision(self, context, execution_id, **kwargs):
        # Both as of the moment this caller read: a copy that still says the
        # node is free, and the revision that copy was current at.
        return (self._snapshot, 1)

    def __getattr__(self, name):
        return getattr(self._real, name)


def _started(service, context):
    started = service.start(
        context,
        StartExecution(
            workflow_id="observe-read",
            workflow_digest="observe-read-digest",
            mission_id="world-observation",
            nodes=(
                {
                    "node_id": "node-1",
                    "worker_kind": "connector",
                    "side_effect": "read",
                    "max_attempts": 1,
                    "input": {},
                },
            ),
        ),
    )
    return str(started.execution.execution_id)


# ---------------------------------------------------------------- F-1


def test_two_dispatchers_racing_one_node_produce_exactly_one_holder():
    """The defect, as a test: both callers load the node free, both assign."""
    fx = Fixture()
    repository = InMemoryExecutionRepository()
    # Two services over one store is what two processes are: each has loaded
    # its own copy of the aggregate and neither can see the other's decision.
    left = ExecutionService(repository=repository)
    right = ExecutionService(repository=repository)
    execution_id = _started(left, fx.context)
    for service in (left, right):
        for worker_id in ("worker-left", "worker-right"):
            service.register_worker(
                RegisterWorker(
                    worker_id=worker_id, kinds=("connector",), lease_seconds=300
                )
            )

    # What two processes actually have: ``right`` read the aggregate before
    # ``left`` wrote, so its copy still says the node is free. Serving that
    # stale copy is the whole race -- without it the second caller re-reads
    # after the first write and the aggregate refuses it for a different
    # reason, which would prove nothing about the write.
    stale = repository.find(fx.context, _id(execution_id))

    left.assign(
        fx.context,
        AssignNode(execution_id=execution_id, node_id="node-1", worker_id="worker-left"),
    )

    right._repository = _StaleOnce(repository, stale)
    with pytest.raises(ConcurrentExecutionUpdate):
        right.assign(
            fx.context,
            AssignNode(
                execution_id=execution_id, node_id="node-1", worker_id="worker-right"
            ),
        )

    holder = left._load(fx.context, execution_id).run_for("node-1").lease.worker_id
    assert holder == "worker-left", "the first holder must not be overwritten"


# ---------------------------------------------------------------- F-2


class RecordingQueue:
    """Records exactly how it was called, and hands back what it was told to."""

    def __init__(self, give=()):
        self.calls = []
        self._give = give

    def claim(self, context, worker_id, kinds, seconds, **kwargs):
        self.calls.append(
            {"worker_id": worker_id, "kinds": tuple(kinds), "seconds": seconds}
        )
        return self._give

    def release(self, context, execution_id, node_id):
        pass


class Item:
    def __init__(self, node_id):
        self.node_id = node_id


def _candidate(node_id="node-1"):
    return DispatchCandidate(
        execution_id="exec-1",
        node_id=node_id,
        tenant_id="tenant-a",
        attempt_number=1,
        worker_kind="connector",
        mutates=False,
    )


def _dispatcher(queue):
    fx = Fixture()
    return ExecutionDispatcher(
        executions=ExecutionService(repository=InMemoryExecutionRepository()),
        gateway=fx.gateway,
        bindings=object(),
        requests=object(),
        queue=queue,
    )


def test_the_queue_is_claimed_with_the_ports_own_signature():
    """The regression that defines F-2: it must not raise, and it must ask for
    the kind of work this node actually is."""
    queue = RecordingQueue(give=(Item("node-1"),))
    assert _dispatcher(queue)._claim(None, _candidate()) is True
    assert queue.calls == [
        {
            "worker_id": "dispatcher:exec-1",
            "kinds": (WorkerKind.CONNECTOR,),
            "seconds": 60,
        }
    ]


def test_a_node_the_queue_gave_to_someone_else_is_refused():
    queue = RecordingQueue(give=(Item("a-different-node"),))
    assert _dispatcher(queue)._claim(None, _candidate()) is False


def test_an_empty_queue_does_not_block_dispatch():
    """The queue is a hint about where work is, not the authority on who owns
    it. Nothing enqueues today, so refusing here would stop every dispatch."""
    assert _dispatcher(RecordingQueue(give=()))._claim(None, _candidate()) is True


def test_a_broken_queue_is_reported_rather_than_silently_believed():
    """A queue outage still proceeds -- the lease decides -- but it must not
    pass silently, which is exactly how F-2 survived."""

    class Broken:
        def claim(self, *a, **k):
            raise RuntimeError("queue is down")

    class Metrics:
        def __init__(self):
            self.counted = []

        def increment(self, name, *, value=1, labels=None):
            self.counted.append(name)

        def observe(self, *a, **k):
            pass

    metrics = Metrics()
    fx = Fixture()
    dispatcher = ExecutionDispatcher(
        executions=ExecutionService(repository=InMemoryExecutionRepository()),
        gateway=fx.gateway,
        bindings=object(),
        requests=object(),
        queue=Broken(),
        metrics=metrics,
    )
    assert dispatcher._claim(None, _candidate()) is True
    assert "execution.queue.unavailable" in metrics.counted


def test_an_unrecognised_worker_kind_claims_nothing_rather_than_guessing():
    queue = RecordingQueue(give=())
    candidate = DispatchCandidate(
        execution_id="exec-1",
        node_id="node-1",
        tenant_id="tenant-a",
        attempt_number=1,
        worker_kind="a-kind-that-does-not-exist",
        mutates=False,
    )
    _dispatcher(queue)._claim(None, candidate)
    assert queue.calls[0]["kinds"] == ()


# ---------------------------------------------------------------- F-7


def test_the_revision_is_read_with_the_aggregate_not_after_it():
    """ADR-127 F-7. The revision check is only worth anything if the revision
    belongs to the copy the caller decided from.

    ``find`` then ``revision_of`` lets a writer land between the two. The caller
    is then holding an aggregate that still says the node is free and a revision
    that already includes somebody else's lease -- so the compare-and-swap
    *matches*, and the winner's lease is overwritten by a decision made without
    seeing it. This passed every deterministic test; four real processes racing
    twelve nodes double-leased all twelve.

    Pinning the shape rather than the timing: ``assign`` must obtain both from
    one call, so no statement can be interleaved between them.
    """
    fx = Fixture()
    repository = InMemoryExecutionRepository()
    service = ExecutionService(repository=repository)
    execution_id = _started(service, fx.context)
    service.register_worker(
        RegisterWorker(worker_id="w", kinds=("connector",), lease_seconds=300)
    )

    calls = []

    class Watched:
        def __init__(self, real):
            self._real = real

        def find(self, context, execution_id, **kwargs):
            calls.append("find")
            return self._real.find(context, execution_id, **kwargs)

        def revision_of(self, context, execution_id, **kwargs):
            calls.append("revision_of")
            return self._real.revision_of(context, execution_id, **kwargs)

        def find_with_revision(self, context, execution_id, **kwargs):
            calls.append("find_with_revision")
            return self._real.find_with_revision(context, execution_id, **kwargs)

        def __getattr__(self, name):
            return getattr(self._real, name)

    service._repository = Watched(repository)
    service.assign(
        fx.context,
        AssignNode(execution_id=execution_id, node_id="node-1", worker_id="w"),
    )

    assert "find_with_revision" in calls
    assert "revision_of" not in calls, (
        "reading the revision separately is the race this finding is about"
    )


def test_find_with_revision_returns_the_revision_of_that_very_copy():
    fx = Fixture()
    repository = InMemoryExecutionRepository()
    service = ExecutionService(repository=repository)
    execution_id = _started(service, fx.context)

    execution, revision = repository.find_with_revision(fx.context, _id(execution_id))
    assert execution is not None and revision == 1

    service.register_worker(
        RegisterWorker(worker_id="w", kinds=("connector",), lease_seconds=300)
    )
    service.assign(
        fx.context,
        AssignNode(execution_id=execution_id, node_id="node-1", worker_id="w"),
    )
    _, after = repository.find_with_revision(fx.context, _id(execution_id))
    assert after == revision + 1


def test_another_tenants_run_reads_as_absent_not_as_a_revision():
    fx = Fixture()
    repository = InMemoryExecutionRepository()
    service = ExecutionService(repository=repository)
    execution_id = _started(service, fx.context)

    other = ExecutionContext.for_tenant(
        tenant_id="some-other-tenant",
        identity=IdentityContext(
            principal=PrincipalRef(principal_id="p", kind=PrincipalKind.PLATFORM),
            capabilities=("capability:invoke",),
        ),
        source="pytest",
    )
    assert repository.find_with_revision(other, _id(execution_id)) == (None, None)


# ---------------------------------------------------------------- F-8


def test_a_holder_and_a_reclaimer_can_never_both_be_entitled_to_write():
    """ADR-127 F-8, recorded as **refuted**.

    The hypothesis was a lost update: fencing the claim leaves one holder but
    not one writer, so a holder that loaded while its lease was live might
    record success while a reclaimer that loaded after the lapse records
    UNKNOWN -- both having passed a real check against their own copy -- and
    whichever wrote last would win. A reclaim landing after a success would
    erase it, the node would read UNKNOWN, and recovery would be entitled to run
    the action again.

    It is not reachable, and this test is why. The aggregate does not evaluate
    the lease against the copy a caller loaded; it evaluates it against the
    clock **at the moment of the write**. So the two are mutually exclusive at
    every instant: while the lease is live the reclaimer is refused, and the
    moment it lapses the holder is refused -- with ``LeaseExpired``, which says
    exactly the right thing ("whether the work happened is not knowable from
    here") rather than silently accepting a stale success.

    The revision check on these transitions is kept as defence in depth, not as
    a fix: it costs one column in a predicate and removes a class of lost update
    from a path that now has more than one process on it.
    """
    import time

    from backend.contexts.execution.application.commands import (
        GetExecution,
        ReclaimNode,
        RecordSuccess,
    )
    from backend.contexts.execution.domain.errors import LeaseExpired

    fx = Fixture()
    repository = InMemoryExecutionRepository()
    service = ExecutionService(repository=repository)
    execution_id = _started(service, fx.context)
    service.register_worker(
        RegisterWorker(worker_id="holder", kinds=("connector",), lease_seconds=1)
    )
    service.assign(
        fx.context,
        AssignNode(execution_id=execution_id, node_id="node-1", worker_id="holder"),
    )

    # While the lease is live, the reclaimer is refused.
    with pytest.raises(Exception) as too_early:
        service.reclaim(
            fx.context, ReclaimNode(execution_id=execution_id, node_id="node-1")
        )
    assert "not expired" in str(too_early.value)

    live_copy, _ = repository.find_with_revision(fx.context, _id(execution_id))
    time.sleep(1.4)

    # Once it lapses, the holder is refused -- even holding the copy it read
    # while the lease was still live.
    holder = ExecutionService(repository=_StaleOnce(repository, live_copy))
    holder.register_worker(
        RegisterWorker(worker_id="holder", kinds=("connector",), lease_seconds=1)
    )
    with pytest.raises(LeaseExpired):
        holder.record_success(
            fx.context,
            RecordSuccess(
                execution_id=execution_id,
                node_id="node-1",
                worker_id="holder",
                execution_key="k",
                detail={},
            ),
        )

    # And the reclaim now stands, recording the honest answer.
    service.reclaim(
        fx.context, ReclaimNode(execution_id=execution_id, node_id="node-1")
    )
    final = service.get(
        fx.context, GetExecution(execution_id=execution_id)
    ).run_for("node-1")
    assert final.state.value == "unknown"


# ---------------------------------------------------------------- F-9


class _Discovery:
    def __init__(self, ids):
        self.ids = ids
        self.calls = 0

    def __call__(self, context):
        self.calls += 1
        return self.ids


class _Spy:
    def __init__(self):
        self.cycled = []

    def cycle(self, context, execution_id):
        self.cycled.append(execution_id)
        return type("R", (), {"dispatched": 0, "cycles": (), "results": ()})()


class _NoRecovery:
    def recover(self, *a, **k):
        return type("S", (), {"resumable": ()})()


def _scheduler(discovery, **kwargs):
    from backend.contexts.execution.application.scheduler import (
        ExecutionScheduler,
        SchedulerState,
    )

    fx = Fixture()
    scheduler = ExecutionScheduler(
        dispatcher=_Spy(), recovery=_NoRecovery(),
        context_factory=lambda: fx.context, discovery=discovery, **kwargs)
    # A stopped scheduler skips every context-less tick, which is right and is
    # not what these tests are about: they are about what a *running* background
    # loop does.
    scheduler._state = SchedulerState.RUNNING
    return scheduler


def test_a_caller_driven_tick_does_not_sweep_the_store():
    """ADR-127 F-9. Discovery is a background sweep, not a per-tick operation.

    A governed read drives ``tick`` in a tight loop waiting for its own node.
    Sweeping there makes every caller pay for every orphan in the database --
    and governed reads never finalise their aggregate, so orphans accumulate.
    Measured on a live database holding 1382 runs in RUNNING: one governed read
    cycled up to 100 unrelated runs on each of up to 450 ticks, and wedged.
    """
    discovery = _Discovery(["someone-elses-run"])
    scheduler = _scheduler(discovery)
    fx = Fixture()
    for _ in range(50):
        scheduler.tick(fx.context)  # a caller ticking for its own work
    assert discovery.calls == 0, "a caller's tick swept the store"


def test_the_background_loop_sweeps_but_only_on_its_interval():
    discovery = _Discovery(["orphan-1"])
    scheduler = _scheduler(discovery, discovery_interval_seconds=3600)
    for _ in range(20):
        scheduler.tick()  # no caller context: this is the background loop
    assert discovery.calls == 1, "the sweep must be rate-limited, not per tick"
    assert "orphan-1" in scheduler._dispatcher.cycled


def test_an_orphan_is_still_found_by_the_sweep():
    discovery = _Discovery(["orphan-1"])
    scheduler = _scheduler(discovery, discovery_interval_seconds=0)
    scheduler.tick()
    assert scheduler.targets == (), "the tracked set stays empty"
    assert scheduler._dispatcher.cycled == ["orphan-1"]

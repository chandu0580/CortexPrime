"""Phase 11.3 (ADR-123): ONE governed read in flight per process.

Every reader thread drives the shared scheduler with its own tenant context;
two threads ticking at once performed each other's executions and blocked on
each other's rows (the 11.2 F-6 stall, reproduced with the signal loop and the
investigator in one process). ``read`` therefore serialises through a
process-wide re-entrant lock, and ``_drive`` still ticks -- the runtime's own
loop dispatches only platform work, so a tenant read must tick for itself."""
from __future__ import annotations

import threading
import time
from types import SimpleNamespace

from backend.api.capability_execution_composition import GovernedCapabilityReader
from backend.contracts.identity import PrincipalKind, PrincipalRef


class _Scheduler:
    def __init__(self):
        self.ticks = 0
        self.tracked = []
        self.untracked = []

    def track(self, execution_id):
        self.tracked.append(execution_id)

    def untrack(self, execution_id):
        self.untracked.append(execution_id)

    def tick(self, context):
        self.ticks += 1


class _Executions:
    def __init__(self, terminal_after: int):
        self.calls = 0
        self._after = terminal_after

    def stream_state(self, context, execution_id):
        self.calls += 1
        state = "succeeded" if self.calls >= self._after else "running"
        return {"nodes": [{"node_id": "n", "state": state}]}


def _reader():
    runtime = SimpleNamespace(scheduler=_Scheduler(), executions=_Executions(terminal_after=3))
    reader = GovernedCapabilityReader(
        runtime=runtime, capability_definitions={"kubernetes.pod.get": object()},
        principal=PrincipalRef(principal_id="t", kind=PrincipalKind.PLATFORM),
        max_ticks=10, tick_seconds=0.0)
    return runtime, reader


def test_the_reader_ticks_the_scheduler_with_its_own_context_and_untracks_when_done():
    runtime, reader = _reader()
    assert reader._drive(object(), "exec-1", "n") == "succeeded"
    assert runtime.scheduler.tracked == ["exec-1"] and runtime.scheduler.ticks == 3
    # the 11.2 F-6 stall: a read left tracked forever makes every later tick
    # re-load it; a finished read must leave the dispatch set
    assert runtime.scheduler.untracked == ["exec-1"]


def test_a_read_that_exhausts_its_budget_still_leaves_the_dispatch_set():
    runtime = SimpleNamespace(scheduler=_Scheduler(), executions=_Executions(terminal_after=999))
    reader = GovernedCapabilityReader(
        runtime=runtime, capability_definitions={"kubernetes.pod.get": object()},
        principal=PrincipalRef(principal_id="t", kind=PrincipalKind.PLATFORM), max_ticks=3, tick_seconds=0.0)
    assert reader._drive(object(), "exec-9", "n") is None
    assert runtime.scheduler.untracked == ["exec-9"]


def test_a_back_to_back_reader_cannot_starve_a_single_read():
    lock = GovernedCapabilityReader.READ_LOCK
    turns: list = []
    stop = threading.Event()

    def hog():
        while not stop.is_set():
            with lock:
                turns.append("hog")
                time.sleep(0.01)

    def single():
        with lock:
            turns.append("single")
    h = threading.Thread(target=hog)
    h.start()
    time.sleep(0.03)
    s = threading.Thread(target=single)
    s.start()
    s.join(timeout=2.0)
    stop.set()
    h.join(timeout=2.0)
    assert "single" in turns
    # the single read got its turn within a few hog cycles, not after the hog stopped
    assert turns.index("single") <= turns.index("hog") + 6


def test_reads_are_serialised_process_wide():
    assert hasattr(GovernedCapabilityReader.READ_LOCK, "acquire")
    _, reader = _reader()
    order: list = []

    def _perform(context, **kwargs):
        order.append(("enter", kwargs["operation"]))
        time.sleep(0.05)
        order.append(("exit", kwargs["operation"]))
        return SimpleNamespace(succeeded=True)

    reader._perform = _perform  # the governed chain is not under test here
    definition = SimpleNamespace(contract=SimpleNamespace(side_effect_class=SimpleNamespace(mutates=False, value="read")))
    reader._definitions = {"a": definition, "b": definition}
    threads = [threading.Thread(target=reader.read, args=(object(),), kwargs={"operation": op, "payload": {}})
               for op in ("a", "b")]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    # never interleaved: enter/exit pairs are contiguous
    assert order[0][0] == "enter" and order[1] == ("exit", order[0][1])
    assert order[2][0] == "enter" and order[3] == ("exit", order[2][1])


def test_the_lock_is_reentrant_for_a_reader_composed_inside_a_read():
    with GovernedCapabilityReader.READ_LOCK:
        with GovernedCapabilityReader.READ_LOCK:
            assert True


def test_a_gateway_refusal_at_dispatch_reaches_the_caller_for_its_own_node_only():
    """Phase 11.4 run 8: a write refused by the gateway at dispatch (approval
    digest, binding ...) is reclaimed as UNKNOWN with no attempt reason, so the
    caller was told ``None``. The gateway's code is taken from this process's
    dispatch report -- and only for this execution's node, never another's."""
    def result(node, code):
        return SimpleNamespace(node_id=node, invocation_refusal=code)

    class _Refusing(_Scheduler):
        def tick(self, context):
            super().tick(context)
            return SimpleNamespace(cycles=(
                SimpleNamespace(execution_id="other", results=(result("n", "someone_elses_refusal"),)),
                SimpleNamespace(execution_id="exec-7", results=(result("m", "another_node"),
                                                                result("n", "approval_digest_mismatch"))),
            ))

    runtime = SimpleNamespace(scheduler=_Refusing(), executions=_Executions(terminal_after=1))
    reader = GovernedCapabilityReader(
        runtime=runtime, capability_definitions={"kubernetes.pod.get": object()},
        principal=PrincipalRef(principal_id="t", kind=PrincipalKind.PLATFORM), max_ticks=3, tick_seconds=0.0)
    refusals: list = []
    reader._drive(object(), "exec-7", "n", refusals=refusals)
    assert refusals == ["approval_digest_mismatch"]

"""The append-only log and its dispatcher.

The outbox is what makes "state changed" and "events emitted" unable to disagree,
so most of these tests are about what happens when delivery goes wrong.
"""

from __future__ import annotations

import threading

import pytest

from backend.contracts.errors import ContractViolation
from backend.contexts.engineering import (
    EngineeringEventDispatcher,
    EngineeringEventLog,
    ImplementationStarted,
    LoggedEvent,
    ReviewRequested,
)
from backend.contracts.tenant import TenantRef, TenantScope
from backend.platform.events import EventMetadata


def _metadata(work_id: str = "w1") -> EventMetadata:
    return EventMetadata.create(
        aggregate_id=work_id,
        aggregate_type="work_order",
        scope=TenantScope(tenant=TenantRef(tenant_id="platform")),
    )


def _event(work_id: str = "w1", round_number: int = 1) -> ImplementationStarted:
    return ImplementationStarted(
        metadata=_metadata(work_id), work_id=work_id, version=1, round=round_number
    )


# ----------------------------------------------------------------------
# Append
# ----------------------------------------------------------------------


def test_append_assigns_gapless_sequence_numbers():
    log = EngineeringEventLog()
    log.append("w1", (_event(), _event()))
    log.append("w2", (_event("w2"),))
    assert [e.sequence for e in log.since(0)] == [0, 1, 2]


def test_append_is_all_or_nothing():
    """A transition's events belong together.

    A partial append would let a consumer observe the second half of a transition
    without the first.
    """
    log = EngineeringEventLog()

    class NotAnEvent:
        pass

    with pytest.raises(ContractViolation):
        log.append("w1", (_event(), NotAnEvent()))
    assert len(log) == 0


def test_append_refuses_a_blank_work_id():
    with pytest.raises(ContractViolation):
        EngineeringEventLog().append("", (_event(),))


def test_for_work_order_filters():
    log = EngineeringEventLog()
    log.append("w1", (_event("w1"),))
    log.append("w2", (_event("w2"),))
    log.append("w1", (_event("w1"),))
    assert len(log.for_work_order("w1")) == 2
    assert len(log.for_work_order("w2")) == 1


def test_since_returns_the_tail():
    log = EngineeringEventLog()
    for _ in range(5):
        log.append("w1", (_event(),))
    assert [e.sequence for e in log.since(3)] == [3, 4]


# ----------------------------------------------------------------------
# Integrity
# ----------------------------------------------------------------------


def test_an_intact_log_reports_no_defects():
    log = EngineeringEventLog()
    for _ in range(10):
        log.append("w1", (_event(),))
    assert log.verify() == ()


def test_a_removed_entry_is_detected():
    """Deletion leaves an intact-looking chain unless sequence numbers are checked.

    The record someone would most want gone is a rejection, which is exactly why
    the sequence and not just the ordering has to be verified.
    """
    log = EngineeringEventLog()
    for _ in range(5):
        log.append("w1", (_event(),))

    del log._entries[2]  # noqa: SLF001 - simulating tampering is the test

    defects = log.verify()
    assert defects and "gap or a duplicate" in defects[0]


# ----------------------------------------------------------------------
# Dispatch
# ----------------------------------------------------------------------


def test_drain_delivers_to_every_subscriber():
    log = EngineeringEventLog()
    dispatcher = EngineeringEventDispatcher(log)
    seen_a, seen_b = [], []
    dispatcher.subscribe("a", seen_a.append)
    dispatcher.subscribe("b", seen_b.append)

    log.append("w1", (_event(), _event()))
    assert dispatcher.drain() == ()
    assert len(seen_a) == 2 and len(seen_b) == 2


def test_drain_advances_the_cursor():
    log = EngineeringEventLog()
    dispatcher = EngineeringEventDispatcher(log)
    seen = []
    dispatcher.subscribe("s", seen.append)

    log.append("w1", (_event(),))
    dispatcher.drain()
    dispatcher.drain()  # nothing new
    assert len(seen) == 1
    assert dispatcher.cursor == 1


def test_a_subscriber_may_narrow_to_event_types():
    log = EngineeringEventLog()
    dispatcher = EngineeringEventDispatcher(log)
    seen = []
    dispatcher.subscribe("narrow", seen.append, event_types=[ReviewRequested.EVENT_TYPE])

    log.append("w1", (_event(),))
    dispatcher.drain()
    assert seen == []


def test_duplicate_subscriber_names_are_refused():
    """A delivery failure must be able to say which subscriber raised."""
    dispatcher = EngineeringEventDispatcher(EngineeringEventLog())
    dispatcher.subscribe("s", lambda e: None)
    with pytest.raises(ContractViolation):
        dispatcher.subscribe("s", lambda e: None)


def test_an_unnamed_subscriber_is_refused():
    dispatcher = EngineeringEventDispatcher(EngineeringEventLog())
    with pytest.raises(ContractViolation):
        dispatcher.subscribe("", lambda e: None)


# ----------------------------------------------------------------------
# Delivery failure
# ----------------------------------------------------------------------


def test_a_raising_subscriber_does_not_stop_the_others():
    log = EngineeringEventLog()
    dispatcher = EngineeringEventDispatcher(log)
    delivered = []

    def broken(entry):
        raise RuntimeError("handler exploded")

    dispatcher.subscribe("broken", broken)
    dispatcher.subscribe("healthy", delivered.append)

    log.append("w1", (_event(),))
    failures = dispatcher.drain()

    assert len(failures) == 1
    assert failures[0].subscriber == "broken"
    assert len(delivered) == 1, "a healthy subscriber was starved by a broken one"


def test_a_delivery_failure_does_not_lose_the_event():
    """The whole point of the outbox: the event is already durable."""
    log = EngineeringEventLog()
    dispatcher = EngineeringEventDispatcher(log)
    dispatcher.subscribe("broken", lambda e: (_ for _ in ()).throw(RuntimeError("nope")))

    log.append("w1", (_event(),))
    dispatcher.drain()

    assert len(log) == 1
    assert log.for_work_order("w1")


def test_the_cursor_advances_past_a_failure():
    """Holding it back would turn one bad handler into a redelivery storm."""
    log = EngineeringEventLog()
    dispatcher = EngineeringEventDispatcher(log)
    calls = []

    def broken(entry):
        calls.append(entry.sequence)
        raise RuntimeError("nope")

    dispatcher.subscribe("broken", broken)

    log.append("w1", (_event(),))
    dispatcher.drain()
    log.append("w1", (_event(),))
    dispatcher.drain()

    assert calls == [0, 1], "an event was redelivered after its failure"


# ----------------------------------------------------------------------
# Replay
# ----------------------------------------------------------------------


def test_replay_redelivers_without_touching_the_live_cursor():
    log = EngineeringEventLog()
    dispatcher = EngineeringEventDispatcher(log)
    live = []
    dispatcher.subscribe("live", live.append)

    log.append("w1", (_event(), _event(), _event()))
    dispatcher.drain()
    assert dispatcher.cursor == 3

    rebuilt = []
    delivered = dispatcher.replay(into=rebuilt.append)

    assert delivered == 3
    assert dispatcher.cursor == 3, "replay moved the live cursor"
    assert [e.sequence for e in rebuilt] == [e.sequence for e in live]


def test_a_projection_rebuilt_by_replay_equals_the_live_one():
    """If these disagree, the live path mutated something it never recorded."""
    log = EngineeringEventLog()
    dispatcher = EngineeringEventDispatcher(log)

    live_projection: dict = {}

    def project(target, entry):
        target[entry.work_id] = target.get(entry.work_id, 0) + 1

    dispatcher.subscribe("live", lambda e: project(live_projection, e))

    for work_id in ("w1", "w2", "w1", "w3", "w1"):
        log.append(work_id, (_event(work_id),))
    dispatcher.drain()

    replayed: dict = {}
    dispatcher.replay(into=lambda e: project(replayed, e))

    assert replayed == live_projection


# ----------------------------------------------------------------------
# Concurrency
# ----------------------------------------------------------------------


def test_concurrent_appends_lose_nothing():
    """A list appended from several threads without a lock drops entries silently."""
    log = EngineeringEventLog()
    threads = []
    per_thread = 40

    def writer(index: int) -> None:
        for _ in range(per_thread):
            log.append(f"w{index}", (_event(f"w{index}"),))

    for index in range(8):
        thread = threading.Thread(target=writer, args=(index,))
        threads.append(thread)
        thread.start()
    for thread in threads:
        thread.join()

    assert len(log) == 8 * per_thread
    assert log.verify() == (), "concurrent appends produced a gap or duplicate"


def test_sequence_numbers_are_unique_under_concurrency():
    log = EngineeringEventLog()

    def writer() -> None:
        for _ in range(50):
            log.append("w1", (_event(),))

    threads = [threading.Thread(target=writer) for _ in range(6)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    sequences = [e.sequence for e in log.since(0)]
    assert len(sequences) == len(set(sequences))
    assert sequences == sorted(sequences)

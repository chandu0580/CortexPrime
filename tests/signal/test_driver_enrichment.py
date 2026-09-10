"""Phase 11.2 (ADR-122): the watch driver's enrichment hook and stall relist.

The driver's 9.3 behaviour is unchanged without an enricher; with one, each
mutation observation carries the pod state read through the governed
``pod.get``; a failing enrichment yields an honest "unavailable" marker, never
an invented state; ``relist`` abandons a position with a checkpoint that names
the stall.
"""
from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace

from backend.api.kubernetes_watch_driver import (
    ORIGIN_LIST_AFTER_STALL,
    KubernetesWatchDriver,
)
from backend.contracts.tenant import TenantRef

NOW = datetime(2026, 9, 10, 12, 0, tzinfo=timezone.utc)


class Outcome(SimpleNamespace):
    def __init__(self, **kw):
        base = dict(succeeded=True, evidence={}, execution_id="exec", failure_reason=None,
                    expired=False, duration_seconds=0.01, operation="op")
        base.update(kw)
        super().__init__(**base)


class Reader:
    def __init__(self, list_rv="500", events=()):
        self.list_rv = list_rv
        self.events = list(events)
        self.calls: list = []

    def read(self, context, *, operation, payload):
        self.calls.append((operation, dict(payload)))
        if operation == "list":
            return Outcome(evidence={"resourceVersion": self.list_rv, "podCount": 1})
        return Outcome(evidence={"events": self.events, "lastResourceVersion": "600",
                                 "eventCount": len(self.events)})


class Observer:
    def __init__(self):
        self.legs: list = []

    def observe(self, *, tenant, outcome, legs, trace_ref=None, now=None):
        self.legs.extend(legs)
        return tuple((SimpleNamespace(record_id=f"obs-{i}", predicate=leg.predicate, value=leg.value), True)
                     for i, leg in enumerate(legs))


class Observations:
    def __init__(self, position=None):
        self.position = position

    def latest_for_subject(self, *, tenant_id, subject_ref, predicate):
        return self.position


class Leadership:
    def acquire(self, *, role, lease_seconds, scope):
        return SimpleNamespace(role=role)

    def heartbeat(self, handle, *, lease_seconds):
        return handle

    def release(self, handle):
        return True


def _driver(reader, observer, *, enricher=None, position=None):
    return KubernetesWatchDriver(
        reader=reader, observer=observer, observations=Observations(position),
        leadership=Leadership(), tenant=TenantRef(tenant_id="t"), namespace="prod",
        list_operation="list", watch_operation="watch", window_seconds=5, lease_seconds=12,
        clock=lambda: NOW, enricher=enricher)


EVENT = {"type": "MODIFIED", "kind": "Pod", "namespace": "prod", "name": "api-7d9f8b6c5-aaaaa",
         "uid": "u1", "resourceVersion": "550"}
POSITION = SimpleNamespace(value={"resourceVersion": "500", "origin": "list"}, record_id="chk")


class TestEnrichment:
    def test_without_an_enricher_the_leg_is_the_9_3_leg(self):
        observer = Observer()
        _driver(Reader(events=[EVENT]), observer, position=POSITION).cycle(object())
        leg = observer.legs[0]
        assert leg.value == {"eventType": "MODIFIED", "resourceVersion": "550", "kind": "Pod",
                             "namespace": "prod", "name": "api-7d9f8b6c5-aaaaa", "uid": "u1",
                             "observedVia": "watch"}

    def test_with_an_enricher_the_state_rides_on_the_same_observation(self):
        observer = Observer()
        asked: list = []

        def enrich(name):
            asked.append(name)
            return {"phase": "Running", "waitingReason": "CrashLoopBackOff", "restartCount": 6,
                    "cluster": "k3d", "workload": "api", "name": "MUST-NOT-OVERRIDE", "nothing": None}
        _driver(Reader(events=[EVENT]), observer, enricher=enrich, position=POSITION).cycle(object())
        value = observer.legs[0].value
        assert asked == ["api-7d9f8b6c5-aaaaa"]
        assert value["waitingReason"] == "CrashLoopBackOff" and value["restartCount"] == 6
        assert value["name"] == "api-7d9f8b6c5-aaaaa"  # the watch's identity wins
        assert "nothing" not in value

    def test_a_deleted_pod_is_not_enriched(self):
        observer = Observer()
        asked: list = []
        deleted = dict(EVENT, type="DELETED")
        _driver(Reader(events=[deleted]), observer, enricher=lambda n: asked.append(n) or {},
                position=POSITION).cycle(object())
        assert asked == [] and observer.legs[0].value["eventType"] == "DELETED"

    def test_a_failing_enrichment_is_recorded_as_unavailable_never_invented(self):
        observer = Observer()

        def boom(name):
            raise RuntimeError("404")
        _driver(Reader(events=[EVENT]), observer, enricher=boom, position=POSITION).cycle(object())
        value = observer.legs[0].value
        assert value["enrichment"] == "unavailable:RuntimeError"
        assert "phase" not in value and "waitingReason" not in value


class TestRelist:
    def test_relist_abandons_the_position_with_a_stall_checkpoint(self):
        observer = Observer()
        reader = Reader(list_rv="900")
        driver = _driver(reader, observer, position=POSITION)
        report = driver.relist(object(), reason="5 consecutive failures at position 500")
        assert report.outcome == "relisted_after_stall" and report.advanced_to == "900"
        checkpoint = observer.legs[-1]
        assert checkpoint.predicate == "watch_position"
        assert checkpoint.value["origin"] == ORIGIN_LIST_AFTER_STALL
        assert checkpoint.value["resourceVersion"] == "900"
        assert "5 consecutive failures" in checkpoint.value["stallReason"]
        assert reader.calls[0][0] == "list"

    def test_relist_refuses_as_a_follower(self):
        class Vacant(Leadership):
            def acquire(self, **kw):
                return None
        driver = KubernetesWatchDriver(
            reader=Reader(), observer=Observer(), observations=Observations(POSITION),
            leadership=Vacant(), tenant=TenantRef(tenant_id="t"), namespace="prod",
            list_operation="list", watch_operation="watch", window_seconds=5, lease_seconds=12)
        assert driver.relist(object(), reason="x").outcome == "follower"

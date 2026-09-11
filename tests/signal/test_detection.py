"""Phase 11.3 (ADR-123): detection is deterministic, sustained, tenant-safe,
and never turns a single flap into an incident."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from backend.contracts.evidence import SourceStatus
from backend.contracts.tenant import TenantRef
from backend.contracts.world import ObservationSourceKind
from backend.signal.correlation import project_candidates
from backend.signal.detection import (
    CONDITION_ALERT_FIRING, CONDITION_CRASHLOOP, CONDITION_RESTARTING, DetectionPolicy, detect,
    detection_identity,
)
from backend.world.application import ObservationIngestion, ReadObservation

NOW = datetime(2026, 9, 10, 12, 0, tzinfo=timezone.utc)
POD = "kubernetes:pod:prod/api-7d9f8b6c5-abcde"


class MemoryRepository:
    def __init__(self):
        self.rows: dict = {}

    def record(self, observation, *, identity_digest):
        if identity_digest in self.rows:
            return False
        self.rows[identity_digest] = observation
        return True


def _ingest(repo, tenant, subject, value, at, *, predicate="state", source_kind=ObservationSourceKind.CONNECTOR,
            source_ref="connector:kubernetes"):
    obs, _ = ObservationIngestion(repository=repo).ingest(
        tenant=TenantRef(tenant_id=tenant),
        read=ReadObservation(source_kind=source_kind, source_ref=source_ref, subject_ref=subject,
                             predicate=predicate, value=value, status=SourceStatus.RETURNED_DATA,
                             observed_at=at, retrieved_at=at, produced_by="t"),
        recorded_at=at)
    return obs


def _pod_history(repo, tenant="tenant-a", n=3, reason="CrashLoopBackOff", restarts=4, spacing=40):
    out = []
    for i in range(n):
        at = NOW - timedelta(seconds=spacing * (n - i))
        out.append(_ingest(repo, tenant, POD, {"eventType": "MODIFIED", "name": "api-7d9f8b6c5-abcde",
                                               "namespace": "prod", "waitingReason": reason,
                                               "restartCount": restarts + i, "phase": "Running"}, at))
    return out


class TestPodDetection:
    def test_a_sustained_backoff_becomes_one_detection_with_its_evidence(self):
        repo = MemoryRepository()
        history = _pod_history(repo)
        candidates = project_candidates([history[-1]], tenant_id="tenant-a")
        events = detect(candidates=candidates, observations=history, tenant_id="tenant-a", now=NOW)
        assert len(events) == 1
        event = events[0]
        assert event.condition == CONDITION_CRASHLOOP and event.subject_ref == POD
        assert set(event.evidence) == {o.record_id for o in history}
        assert event.window_start == history[0].instant.observed_at
        assert "CrashLoopBackOff" in event.reason and event.to_dict()["authority"] == "none"

    def test_a_single_flap_without_restarts_is_not_a_detection(self):
        repo = MemoryRepository()
        history = _pod_history(repo, n=1, restarts=0)
        candidates = project_candidates([history[-1]], tenant_id="tenant-a")
        assert detect(candidates=candidates, observations=history, tenant_id="tenant-a", now=NOW,
                      policy=DetectionPolicy(crashloop_min_duration_seconds=600)) == ()

    def test_restarts_without_backoff_are_a_lower_severity_condition(self):
        repo = MemoryRepository()
        history = _pod_history(repo, n=2, reason=None, restarts=5)
        candidates = project_candidates([history[-1]], tenant_id="tenant-a")
        events = detect(candidates=candidates, observations=history, tenant_id="tenant-a", now=NOW)
        assert [e.condition for e in events] == [CONDITION_RESTARTING]
        assert events[0].severity == "medium"

    def test_identity_is_deterministic_and_the_same_condition_is_the_same_detection(self):
        repo = MemoryRepository()
        history = _pod_history(repo)
        candidates = project_candidates([history[-1]], tenant_id="tenant-a")
        first = detect(candidates=candidates, observations=history, tenant_id="tenant-a", now=NOW)
        second = detect(candidates=candidates, observations=history, tenant_id="tenant-a",
                        now=NOW + timedelta(minutes=5))
        assert first[0].detection_id == second[0].detection_id
        assert first[0].detection_id == detection_identity(
            tenant_id="tenant-a", condition=CONDITION_CRASHLOOP, subject_ref=POD,
            window_start=first[0].window_start)

    def test_another_tenants_observations_never_feed_a_detection(self):
        repo = MemoryRepository()
        theirs = _pod_history(repo, tenant="tenant-b")
        mine = _pod_history(repo, tenant="tenant-a", n=1, restarts=0)
        candidates = project_candidates([mine[-1]], tenant_id="tenant-a")
        events = detect(candidates=candidates, observations=theirs + mine, tenant_id="tenant-a", now=NOW,
                        policy=DetectionPolicy(crashloop_min_duration_seconds=600))
        assert events == ()

    def test_old_observations_are_outside_the_lookback(self):
        repo = MemoryRepository()
        history = _pod_history(repo, spacing=1200)  # 20, 40, 60 minutes ago
        candidates = project_candidates([history[-1]], tenant_id="tenant-a")
        events = detect(candidates=candidates, observations=history, tenant_id="tenant-a", now=NOW,
                        policy=DetectionPolicy(lookback_seconds=1500))
        assert len(events) == 1 and len(events[0].evidence) == 1  # only the 20-minute-old one


class TestAlertDetection:
    def test_a_firing_alert_older_than_the_minimum_is_detected_with_its_labels(self):
        repo = MemoryRepository()
        subject = "alertmanager:alert:abc123"
        started = (NOW - timedelta(minutes=2)).isoformat()
        obs = _ingest(repo, "tenant-a", subject,
                      {"status": "firing", "startsAt": started, "endsAt": None,
                       "labels": {"alertname": "VictimServiceDown", "severity": "critical",
                                  "namespace": "prod", "pod": "api-7d9f8b6c5-abcde"}},
                      NOW - timedelta(seconds=10), predicate="alert",
                      source_kind=ObservationSourceKind.PROBE, source_ref="webhook:alertmanager")
        candidates = project_candidates([obs], tenant_id="tenant-a")
        events = detect(candidates=candidates, observations=[obs], tenant_id="tenant-a", now=NOW)
        assert len(events) == 1 and events[0].condition == CONDITION_ALERT_FIRING
        assert events[0].severity == "critical" and events[0].correlation["alertname"] == "VictimServiceDown"

    def test_a_just_fired_alert_waits(self):
        repo = MemoryRepository()
        subject = "alertmanager:alert:abc123"
        obs = _ingest(repo, "tenant-a", subject,
                      {"status": "firing", "startsAt": (NOW - timedelta(seconds=5)).isoformat(),
                       "labels": {"alertname": "X"}}, NOW, predicate="alert",
                      source_kind=ObservationSourceKind.PROBE, source_ref="webhook:alertmanager")
        candidates = project_candidates([obs], tenant_id="tenant-a")
        assert detect(candidates=candidates, observations=[obs], tenant_id="tenant-a", now=NOW) == ()

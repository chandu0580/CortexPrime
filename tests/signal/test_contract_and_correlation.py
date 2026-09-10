"""Phase 11.2 (ADR-122): the canonical signal contract and the candidate projection.

Pure: no database, no cluster. Observations are built through the World
Plane's own ingestion against an in-memory repository so identity and dedupe
are the real ones.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from backend.contracts.evidence import SourceStatus
from backend.contracts.tenant import TenantRef
from backend.contracts.world import ObservationSourceKind
from backend.signal.alertmanager import (
    AlertmanagerPayload,
    normalise_alertmanager,
    parse_alertmanager_time,
)
from backend.signal.contract import (
    DeliverySemantics,
    SignalSource,
    canonical_signal,
)
from backend.signal.correlation import (
    candidate_id_for,
    project_candidates,
    workload_of,
)
from backend.world.application import ObservationIngestion, ReadObservation

NOW = datetime(2026, 9, 10, 12, 0, tzinfo=timezone.utc)
A = TenantRef(tenant_id="tenant-a")
B = TenantRef(tenant_id="tenant-b")


class MemoryRepository:
    def __init__(self) -> None:
        self.rows: dict = {}

    def record(self, observation, *, identity_digest: str) -> bool:
        if identity_digest in self.rows:
            return False
        self.rows[identity_digest] = observation
        return True


def _pod_read(name: str, *, value: dict, observed_at=NOW) -> ReadObservation:
    return ReadObservation(
        source_kind=ObservationSourceKind.CONNECTOR, source_ref="connector:kubernetes",
        subject_ref=f"kubernetes:pod:prod/{name}", predicate="state",
        value={"eventType": "MODIFIED", "kind": "Pod", "namespace": "prod", "name": name,
               "uid": "u-" + name, "resourceVersion": "100", "observedVia": "watch",
               "cluster": "k3d-p99b", **value},
        status=SourceStatus.RETURNED_DATA, observed_at=observed_at, retrieved_at=observed_at,
        produced_by="signal:kubernetes-worker/1", execution_ref="exec-1", trace_ref="trace-1")


def _ingest(repo, tenant, read, recorded_at=NOW):
    return ObservationIngestion(repository=repo).ingest(tenant=tenant, read=read, recorded_at=recorded_at)


class TestCanonicalSignal:
    def test_kubernetes_observation_is_viewed_with_native_identity_and_provenance(self):
        obs, newly = _ingest(MemoryRepository(), A, _pod_read(
            "api-7d9f8b6c5-abcde", value={"phase": "Running", "waitingReason": "CrashLoopBackOff",
                                          "restartCount": 7, "workload": "api"}))
        assert newly
        sig = canonical_signal(obs)
        assert sig.source is SignalSource.KUBERNETES
        assert sig.delivery is DeliverySemantics.AT_LEAST_ONCE
        assert sig.global_id == obs.record_id and sig.tenant_id == "tenant-a"
        assert sig.native_identity == {"cluster": "k3d-p99b", "namespace": "prod", "kind": "Pod",
                                       "name": "api-7d9f8b6c5-abcde", "uid": "u-api-7d9f8b6c5-abcde",
                                       "resourceVersion": "100", "eventType": "MODIFIED"}
        assert sig.correlation["waitingReason"] == "CrashLoopBackOff"
        assert sig.correlation["workload"] == "api"
        d = sig.to_dict()
        assert d["provenance"] == {"produced_by": "signal:kubernetes-worker/1",
                                   "execution_ref": "exec-1", "trace_ref": "trace-1"}
        assert d["trust"] == "untrusted_external"

    def test_identity_is_tenant_scoped_and_deduplicates_redelivery(self):
        repo = MemoryRepository()
        read = _pod_read("api-1", value={"phase": "Running"})
        _, first = _ingest(repo, A, read)
        _, again = _ingest(repo, A, read)
        _, other_tenant = _ingest(repo, B, read)
        assert (first, again, other_tenant) == (True, False, True)

    def test_alertmanager_observation_is_viewed_with_fingerprint_identity(self):
        payload = AlertmanagerPayload.model_validate({
            "version": "4", "groupKey": '{}:{alertname="BackendDown"}', "status": "firing",
            "receiver": "cortexprime", "alerts": [{
                "status": "firing", "labels": {"alertname": "BackendDown", "severity": "critical",
                                               "job": "cortex-backend"},
                "annotations": {"summary": "down"}, "startsAt": "2026-09-10T11:59:00.123456789Z",
                "endsAt": "0001-01-01T00:00:00Z", "generatorURL": "http://prom/graph",
                "fingerprint": "ABCDEF0123456789"}]})
        alerts = normalise_alertmanager(payload, received_at=NOW)
        assert len(alerts) == 1
        obs, _ = _ingest(MemoryRepository(), A, alerts[0].to_read(retrieved_at=NOW, produced_by="signal:alertmanager-ingress/1"))
        sig = canonical_signal(obs)
        assert sig.source is SignalSource.ALERTMANAGER
        assert sig.delivery is DeliverySemantics.EFFECTIVELY_ONCE_PER_STATE
        assert sig.native_identity["fingerprint"] == "abcdef0123456789"
        assert sig.native_identity["status"] == "firing"
        assert sig.correlation["alertname"] == "BackendDown" and sig.correlation["severity"] == "critical"
        assert sig.observed_at == datetime(2026, 9, 10, 11, 59, 0, 123456, tzinfo=timezone.utc)


class TestAlertmanagerNormalisation:
    def test_repeated_notification_deduplicates_and_resolution_is_new(self):
        repo = MemoryRepository()
        base = {"version": "4", "groupKey": "g", "status": "firing", "receiver": "r",
                "alerts": [{"status": "firing", "labels": {"alertname": "X"}, "annotations": {},
                            "startsAt": "2026-09-10T11:00:00Z", "endsAt": "0001-01-01T00:00:00Z",
                            "generatorURL": "", "fingerprint": "0011"}]}
        first = normalise_alertmanager(AlertmanagerPayload.model_validate(base), received_at=NOW)[0]
        again = normalise_alertmanager(AlertmanagerPayload.model_validate(base), received_at=NOW + timedelta(hours=4))[0]
        resolved_body = dict(base, status="resolved")
        resolved_body["alerts"] = [dict(base["alerts"][0], status="resolved", endsAt="2026-09-10T12:30:00Z")]
        resolved = normalise_alertmanager(AlertmanagerPayload.model_validate(resolved_body), received_at=NOW + timedelta(hours=5))[0]
        r1 = _ingest(repo, A, first.to_read(retrieved_at=NOW, produced_by="p"))[1]
        r2 = _ingest(repo, A, again.to_read(retrieved_at=NOW + timedelta(hours=4), produced_by="p"), NOW + timedelta(hours=4))[1]
        r3 = _ingest(repo, A, resolved.to_read(retrieved_at=NOW + timedelta(hours=5), produced_by="p"), NOW + timedelta(hours=5))[1]
        assert (r1, r2, r3) == (True, False, True)

    def test_future_starts_at_is_clamped_to_receipt_and_the_skew_recorded(self):
        body = {"version": "4", "alerts": [{"status": "firing", "labels": {}, "annotations": {},
                                            "startsAt": "2026-09-10T12:05:00Z", "fingerprint": "ab"}]}
        alert = normalise_alertmanager(AlertmanagerPayload.model_validate(body), received_at=NOW)[0]
        assert alert.observed_at == NOW and alert.value["startsAtSkewSeconds"] == 300.0
        obs, newly = _ingest(MemoryRepository(), A, alert.to_read(retrieved_at=NOW, produced_by="p"))
        assert newly and obs.instant.observed_at == NOW

    def test_labels_are_bounded_and_the_zero_time_is_none(self):
        assert parse_alertmanager_time("0001-01-01T00:00:00Z") is None
        assert parse_alertmanager_time("garbage") is None
        body = {"version": "4", "alerts": [{"status": "firing", "labels": {f"l{i}": "x" * 5000 for i in range(80)},
                                            "annotations": {}, "startsAt": "not-a-time",
                                            "fingerprint": "ff"}]}
        alert = normalise_alertmanager(AlertmanagerPayload.model_validate(body), received_at=NOW)[0]
        assert alert.value["labels"]["_truncated"] is True
        assert len(alert.value["labels"]) == 65
        assert all(len(v) <= 2048 for v in alert.value["labels"].values() if isinstance(v, str))
        assert alert.observed_at == NOW and alert.value["startsAtUnparsed"] == "not-a-time"

    @pytest.mark.parametrize("bad", [
        {"version": "4", "alerts": []},
        {"version": "4", "alerts": [{"status": "weird", "startsAt": "x", "fingerprint": "aa"}]},
        {"version": "4", "alerts": [{"status": "firing", "startsAt": "x", "fingerprint": "not hex!"}]},
        {"version": "4", "alerts": [{"status": "firing", "startsAt": "x"}]},
    ])
    def test_schema_refuses_malformed_payloads(self, bad):
        with pytest.raises(Exception):
            AlertmanagerPayload.model_validate(bad)


class TestCandidateProjection:
    def test_backoff_pods_of_one_workload_fold_into_one_candidate(self):
        repo = MemoryRepository()
        obs = [
            _ingest(repo, A, _pod_read("api-7d9f8b6c5-aaaaa", value={"phase": "Running", "waitingReason": "CrashLoopBackOff", "restartCount": 5}))[0],
            _ingest(repo, A, _pod_read("api-7d9f8b6c5-bbbbb", value={"phase": "Running", "waitingReason": "CrashLoopBackOff", "restartCount": 2}))[0],
            _ingest(repo, A, _pod_read("web-5c4d3b2a1-ccccc", value={"phase": "Running", "restartCount": 0}))[0],
        ]
        candidates = project_candidates(obs, tenant_id="tenant-a")
        assert len(candidates) == 1
        c = candidates[0]
        assert c.kind == "kubernetes.pod.backoff"
        assert c.correlation["workload"] == "api" and c.correlation["namespace"] == "prod"
        assert sorted(c.correlation["pods"]) == ["api-7d9f8b6c5-aaaaa", "api-7d9f8b6c5-bbbbb"]
        assert len(c.evidence) == 2 and c.handoff["incident_ref"] == c.candidate_id
        assert c.to_dict()["authority"] == "none"

    def test_projection_is_deterministic(self):
        repo = MemoryRepository()
        obs = [_ingest(repo, A, _pod_read("api-7d9f8b6c5-aaaaa", value={"waitingReason": "ImagePullBackOff"}))[0]]
        assert project_candidates(obs, tenant_id="tenant-a") == project_candidates(list(reversed(obs)), tenant_id="tenant-a")
        assert candidate_id_for("t", "k", "x") == candidate_id_for("t", "k", "x")
        assert candidate_id_for("t", "k", "x") != candidate_id_for("t2", "k", "x")

    def test_other_tenants_evidence_never_enters_a_candidate(self):
        repo = MemoryRepository()
        mine = _ingest(repo, A, _pod_read("api-7d9f8b6c5-aaaaa", value={"waitingReason": "CrashLoopBackOff"}))[0]
        theirs = _ingest(repo, B, _pod_read("api-7d9f8b6c5-aaaaa", value={"waitingReason": "CrashLoopBackOff"}))[0]
        candidates = project_candidates([mine, theirs], tenant_id="tenant-a")
        assert len(candidates) == 1 and candidates[0].evidence == (mine.record_id,)
        assert project_candidates([theirs], tenant_id="tenant-a") == ()

    def test_deleted_pods_healthy_pods_and_resolved_alerts_are_not_candidates(self):
        repo = MemoryRepository()
        deleted = _ingest(repo, A, _pod_read("api-7d9f8b6c5-aaaaa", value={"eventType": "DELETED", "waitingReason": "CrashLoopBackOff"}))[0]
        healthy = _ingest(repo, A, _pod_read("api-7d9f8b6c5-bbbbb", value={"phase": "Running", "restartCount": 1}))[0]
        payload = AlertmanagerPayload.model_validate({"version": "4", "alerts": [{
            "status": "resolved", "labels": {"alertname": "X"}, "annotations": {},
            "startsAt": "2026-09-10T11:00:00Z", "endsAt": "2026-09-10T11:30:00Z", "fingerprint": "aa"}]})
        resolved = _ingest(repo, A, normalise_alertmanager(payload, received_at=NOW)[0].to_read(retrieved_at=NOW, produced_by="p"))[0]
        assert project_candidates([deleted, healthy, resolved], tenant_id="tenant-a") == ()

    def test_firing_alert_is_a_candidate_with_correlation(self):
        repo = MemoryRepository()
        payload = AlertmanagerPayload.model_validate({"version": "4", "alerts": [{
            "status": "firing", "labels": {"alertname": "BackendDown", "severity": "critical", "namespace": "prod", "pod": "api-1"},
            "annotations": {}, "startsAt": "2026-09-10T11:00:00Z", "fingerprint": "aa"}]})
        obs = _ingest(repo, A, normalise_alertmanager(payload, received_at=NOW)[0].to_read(retrieved_at=NOW, produced_by="p"))[0]
        (c,) = project_candidates([obs], tenant_id="tenant-a")
        assert c.kind == "alertmanager.alert.firing"
        assert c.correlation["alertname"] == "BackendDown" and c.correlation["namespace"] == "prod"
        assert c.correlation["fingerprint"] == "aa"

    def test_workload_inference_is_conservative(self):
        assert workload_of("api-7d9f8b6c5-abcde") == "api"
        assert workload_of("payments-api-88bdf4f45-mxwcr") == "payments-api"
        assert workload_of("single") is None
        assert workload_of("") is None

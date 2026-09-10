"""Phase 11.2 (ADR-122): the supervised worker loop, against a fake driver.

Every outcome the driver can report is exercised: progress, follower,
failures with backoff, a stall that ends in an explicit relist, expiry
exhaustion, fencing, a raised exception, and shutdown that releases the role.
"""
from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace

from backend.contracts.evidence import SourceStatus
from backend.contracts.tenant import TenantRef
from backend.contracts.world import ObservationSourceKind
from backend.signal.worker import (
    LoggingHandoff,
    RecordingObserver,
    SignalWorker,
    SignalWorkerConfig,
)
from backend.world.application import ObservationIngestion, ReadObservation

NOW = datetime(2026, 9, 10, 12, 0, tzinfo=timezone.utc)
TENANT = TenantRef(tenant_id="tenant-a")
CFG = SignalWorkerConfig(tenant_id="tenant-a", namespace="prod", cluster_ref="k3d",
                         backoff_min_seconds=1.0, backoff_max_seconds=8.0, max_stall_failures=3,
                         follower_sleep_seconds=2.5)


class MemoryRepository:
    def __init__(self) -> None:
        self.rows: dict = {}

    def record(self, observation, *, identity_digest: str) -> bool:
        if identity_digest in self.rows:
            return False
        self.rows[identity_digest] = observation
        return True

    def latest_by_subject_prefix(self, *, tenant_id, subject_prefix, predicate, limit=500):
        latest: dict = {}
        for obs in self.rows.values():
            if obs.tenant.tenant_id == tenant_id and obs.subject_ref.startswith(subject_prefix) and obs.predicate == predicate:
                latest[obs.subject_ref] = obs
        return tuple(latest.values())


class Report(SimpleNamespace):
    def __init__(self, outcome, **kw):
        defaults = dict(outcome=outcome, started_from=None, advanced_to=None, events_seen=0,
                        observations_recorded=0, observations_deduped=0, bookmarks=0,
                        recovered_from_expiry=False, execution_id=None, detail=None,
                        provider_calls=0, durations={})
        defaults.update(kw)
        super().__init__(**defaults)


class FakeDriver:
    """Scripted outcomes; records what the worker asked of it."""

    def __init__(self, script, *, observer=None, repo=None):
        self.script = list(script)
        self.observer = observer
        self.repo = repo
        self.relists: list = []
        self.released = 0
        self.leadership_handle = object()

    def cycle(self, context):
        item = self.script.pop(0) if self.script else Report("idle")
        if callable(item):
            return item()
        if item.outcome == "observed" and self.observer is not None:
            read = ReadObservation(
                source_kind=ObservationSourceKind.CONNECTOR, source_ref="connector:kubernetes",
                subject_ref=f"kubernetes:pod:prod/api-7d9f8b6c5-{len(self.repo.rows):05d}", predicate="state",
                value={"eventType": "MODIFIED", "name": f"api-7d9f8b6c5-{len(self.repo.rows):05d}",
                       "namespace": "prod", "waitingReason": "CrashLoopBackOff", "restartCount": 4},
                status=SourceStatus.RETURNED_DATA, observed_at=NOW, retrieved_at=NOW, produced_by="t")
            self.observer.observe(tenant=TENANT, read=read)
        return item

    def relist(self, context, *, reason):
        self.relists.append(reason)
        return Report("relisted_after_stall", advanced_to="900", observations_recorded=1)

    def release_leadership(self):
        self.released += 1
        return True


class Ingesting:
    """A stand-in for the governed observer: ingests straight into the repository."""

    def __init__(self, repo):
        self._ingestion = ObservationIngestion(repository=repo)

    def observe(self, *, tenant, read):
        return (self._ingestion.ingest(tenant=tenant, read=read, recorded_at=NOW),)


class Derivation:
    def __init__(self):
        self.calls = 0

    def derive(self, *, tenant, observation, recorded_at):
        self.calls += 1
        return SimpleNamespace(outcome=SimpleNamespace(value="derived"))


def _worker(script, *, repo=None, derivation=None, handoff=None, sleeps=None):
    repo = repo if repo is not None else MemoryRepository()
    observer = RecordingObserver(Ingesting(repo))
    driver = FakeDriver(script, observer=observer, repo=repo)
    worker = SignalWorker(config=CFG, driver=driver, tenant=TENANT, tenant_context=object(),
                          observer=observer, observations=repo, derivation=derivation,
                          handoff=handoff, clock=lambda: NOW,
                          sleep=(sleeps.append if sleeps is not None else (lambda s: None)))
    return worker, driver, repo


class TestProgress:
    def test_observed_cycle_derives_facts_projects_candidates_and_hands_off(self):
        derivation = Derivation()
        handoff = LoggingHandoff()
        worker, driver, repo = _worker([Report("observed", events_seen=1, observations_recorded=1)],
                                       derivation=derivation, handoff=handoff)
        step = worker.step()
        assert step.outcome == "observed" and step.leader is True
        assert derivation.calls == 1 and step.facts == {"derived": 1}
        assert step.candidates == 1 and worker.last_candidates[0].kind == "kubernetes.pod.backoff"
        assert handoff.offers[-1]["count"] == 1
        assert step.backoff_seconds == 0

    def test_follower_sleeps_and_derives_nothing(self):
        derivation = Derivation()
        worker, driver, _ = _worker([Report("follower")], derivation=derivation)
        driver.leadership_handle = None
        step = worker.step()
        assert step.outcome == "follower" and step.leader is False
        assert step.backoff_seconds == 2.5 and derivation.calls == 0

    def test_run_stops_at_max_cycles_and_releases_the_role(self):
        sleeps: list = []
        worker, driver, _ = _worker([Report("idle"), Report("idle")], sleeps=sleeps)
        worker.config = SignalWorkerConfig(**{**CFG.__dict__, "max_cycles": 2})
        assert worker.run() == 0
        assert worker.cycles == 2 and driver.released == 1


class TestFailures:
    def test_failures_back_off_exponentially_and_reset_on_progress(self):
        worker, driver, _ = _worker([Report("watch_failed", started_from="1"),
                                     Report("watch_failed", started_from="1"),
                                     Report("observed")])
        s1, s2, s3 = worker.step(), worker.step(), worker.step()
        assert (s1.backoff_seconds, s2.backoff_seconds, s3.backoff_seconds) == (1.0, 2.0, 0.0)
        assert driver.relists == []

    def test_a_stall_at_one_position_ends_in_an_explicit_relist(self):
        worker, driver, _ = _worker([Report("watch_failed", started_from="42")] * 3)
        worker.step(); worker.step()
        step = worker.step()
        assert step.outcome == "relisted_after_stall" and step.relisted is True
        assert driver.relists and "3 consecutive failures at position 42" in driver.relists[0]

    def test_the_status_written_for_a_failed_cycle_carries_its_backoff(self, tmp_path):
        # Harness 7.1: the status file was written before the backoff was
        # decided, so a failed cycle read as backoff 0 (a sleep the loop DID
        # take but did not report).
        worker, driver, _ = _worker([Report("watch_failed", started_from="7")])
        worker.config = SignalWorkerConfig(**{**CFG.__dict__, "status_file": str(tmp_path / "s.json")})
        step = worker.step()
        import json
        written = json.loads((tmp_path / "s.json").read_text(encoding="utf-8"))
        assert step.backoff_seconds == 1.0
        assert written["last"]["outcome"] == "watch_failed" and written["last"]["backoff_seconds"] == 1.0

    def test_failures_at_different_positions_do_not_count_as_a_stall(self):
        worker, driver, _ = _worker([Report("watch_failed", started_from="1"),
                                     Report("watch_failed", started_from="2"),
                                     Report("watch_failed", started_from="3")])
        for _ in range(3):
            worker.step()
        assert driver.relists == []

    def test_expiry_exhaustion_relists(self):
        worker, driver, _ = _worker([Report("expiry_recovery_exhausted", detail="410 x4")])
        step = worker.step()
        assert step.relisted is True and driver.relists == ["expiry: 410 x4"]

    def test_fenced_keeps_events_and_retries_soon(self):
        worker, driver, _ = _worker([Report("fenced", events_seen=2, observations_recorded=2, detail="role taken")])
        step = worker.step()
        assert step.outcome == "fenced" and step.backoff_seconds == 1.0

    def test_a_raising_cycle_is_a_failure_never_a_success(self):
        def boom():
            raise RuntimeError("api gone")
        worker, driver, _ = _worker([boom, boom, boom])
        steps = [worker.step() for _ in range(3)]
        assert [s.outcome for s in steps] == ["cycle_exception"] * 3
        assert [s.backoff_seconds for s in steps] == [1.0, 2.0, 4.0]
        assert driver.relists == []  # no position to abandon

    def test_stop_ends_the_loop_and_releases(self):
        worker, driver, _ = _worker([Report("idle")] * 100)
        calls = {"n": 0}

        def _sleep(seconds):
            calls["n"] += 1
            worker.stop()
        worker._sleep = _sleep
        worker.config = SignalWorkerConfig(**{**CFG.__dict__, "idle_sleep_seconds": 0.1})
        assert worker.run() == 0
        assert driver.released == 1 and worker.cycles == 1


class TestRoles:
    def test_without_the_roles_the_instance_is_a_hot_standby_follower(self):
        held = {"v": False}
        released = []
        worker, driver, _ = _worker([Report("observed", events_seen=1, observations_recorded=1)] * 2)
        worker._roles = lambda: held["v"]
        worker._release_roles = lambda: released.append(True)
        first = worker.step()
        assert first.outcome == "follower" and first.leader is False
        assert first.backoff_seconds == 2.5 and "hot standby" in first.detail
        held["v"] = True
        second = worker.step()
        assert second.outcome == "observed"
        worker.config = SignalWorkerConfig(**{**CFG.__dict__, "max_cycles": 1})
        worker.run()
        assert released == [True] and driver.released == 1

    def test_a_raising_role_check_is_no_admission(self):
        def boom():
            raise RuntimeError("store down")
        worker, driver, _ = _worker([Report("observed")])
        worker._roles = boom
        assert worker.step().outcome == "follower"


class TestConfig:
    def test_from_env_refuses_without_tenant_and_namespace(self, monkeypatch):
        monkeypatch.delenv("CORTEX_SIGNAL_TENANT_ID", raising=False)
        monkeypatch.delenv("CORTEX_SIGNAL_NAMESPACE", raising=False)
        import pytest
        with pytest.raises(SystemExit):
            SignalWorkerConfig.from_env()

    def test_from_env_reads_the_declared_variables(self, monkeypatch):
        monkeypatch.setenv("CORTEX_SIGNAL_TENANT_ID", "t")
        monkeypatch.setenv("CORTEX_SIGNAL_NAMESPACE", "ns")
        monkeypatch.setenv("CORTEX_KUBERNETES_URL", "https://127.0.0.1:6443")
        monkeypatch.setenv("CORTEX_SIGNAL_WINDOW_SECONDS", "5")
        monkeypatch.setenv("CORTEX_SIGNAL_LEASE_SECONDS", "12")
        cfg = SignalWorkerConfig.from_env()
        assert (cfg.tenant_id, cfg.namespace, cfg.cluster_ref, cfg.window_seconds, cfg.lease_seconds) == \
            ("t", "ns", "127.0.0.1:6443", 5, 12)

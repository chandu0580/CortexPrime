from __future__ import annotations

import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from backend.services.enterprise_docker_health_monitor import (
    DockerHealthHistoryStore,
    _gap_signature,
    _overall_severity,
    assess_container_health,
    check_all_containers,
    is_critical_container,
)


class TestIsCriticalContainer:
    def test_matches_known_data_plane_containers(self):
        assert is_critical_container("cortex-postgres") is True
        assert is_critical_container("cortex-redis") is True
        assert is_critical_container("cortex-rabbitmq") is True
        assert is_critical_container("cortex-neo4j") is True

    def test_does_not_match_unrelated_container(self):
        assert is_critical_container("my-test-container") is False


class TestAssessContainerHealth:
    def test_first_observation_no_prev_raises_no_crash_loop(self):
        curr = {"restart_count": 5, "started_at": "t1", "oom_killed": False, "exit_code": 0, "status": "running", "host_config": {}}
        gaps = assess_container_health(None, curr)
        assert gaps == []

    def test_restart_count_delta_over_threshold_is_crash_loop(self):
        prev = {"restart_count": 0, "started_at": "t1", "oom_killed": False, "exit_code": 0, "status": "running", "host_config": {}}
        curr = {"restart_count": 4, "started_at": "t2", "oom_killed": False, "exit_code": 0, "status": "running", "host_config": {}}
        gaps = assess_container_health(prev, curr)
        gap_names = [g["gap"] for g in gaps]
        assert "crash_loop" in gap_names

    def test_restart_count_delta_under_threshold_no_crash_loop(self):
        prev = {"restart_count": 0, "started_at": "t1", "oom_killed": False, "exit_code": 0, "status": "running", "host_config": {}}
        curr = {"restart_count": 1, "started_at": "t2", "oom_killed": False, "exit_code": 0, "status": "running", "host_config": {}}
        gaps = assess_container_health(prev, curr)
        assert gaps == []

    def test_new_oom_kill_flagged(self):
        prev = {"restart_count": 0, "started_at": "t1", "oom_killed": False, "exit_code": 0, "status": "running", "host_config": {}}
        curr = {"restart_count": 1, "started_at": "t2", "oom_killed": True, "exit_code": 137, "status": "exited", "host_config": {"restart_policy": "unless-stopped"}}
        gaps = assess_container_health(prev, curr)
        gap_names = [g["gap"] for g in gaps]
        assert "oom_killed" in gap_names

    def test_stale_oom_flag_same_incarnation_not_reflagged(self):
        prev = {"restart_count": 1, "started_at": "t2", "oom_killed": True, "exit_code": 137, "status": "running", "host_config": {}}
        curr = {"restart_count": 1, "started_at": "t2", "oom_killed": True, "exit_code": 137, "status": "running", "host_config": {}}
        gaps = assess_container_health(prev, curr)
        assert gaps == []

    def test_dead_with_no_restart_policy_flagged(self):
        curr = {"restart_count": 0, "started_at": "t1", "oom_killed": False, "exit_code": 1, "status": "exited", "host_config": {"restart_policy": ""}}
        gaps = assess_container_health(None, curr)
        gap_names = [g["gap"] for g in gaps]
        assert "not_running_no_recovery" in gap_names

    def test_dead_with_restart_policy_not_flagged_as_no_recovery(self):
        curr = {"restart_count": 0, "started_at": "t1", "oom_killed": False, "exit_code": 1, "status": "exited", "host_config": {"restart_policy": "unless-stopped"}}
        gaps = assess_container_health(None, curr)
        gap_names = [g["gap"] for g in gaps]
        assert "not_running_no_recovery" not in gap_names

    def test_healthy_running_container_has_no_gaps(self):
        prev = {"restart_count": 0, "started_at": "t1", "oom_killed": False, "exit_code": 0, "status": "running", "host_config": {}}
        curr = {"restart_count": 0, "started_at": "t1", "oom_killed": False, "exit_code": 0, "status": "running", "host_config": {}}
        assert assess_container_health(prev, curr) == []


class TestOverallSeverity:
    def test_no_gaps_is_low(self):
        assert _overall_severity([]) == "low"

    def test_picks_highest_severity(self):
        gaps = [{"gap": "a", "severity": "high"}, {"gap": "b", "severity": "critical"}]
        assert _overall_severity(gaps) == "critical"


class TestGapSignature:
    def test_order_independent(self):
        a = [{"gap": "x", "severity": "low"}, {"gap": "y", "severity": "low"}]
        b = [{"gap": "y", "severity": "low"}, {"gap": "x", "severity": "low"}]
        assert _gap_signature(a) == _gap_signature(b)


class TestDockerHealthHistoryStore:
    @pytest.fixture
    def store(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            yield DockerHealthHistoryStore(file_path=Path(tmpdir) / "dh_history.json")

    def test_record_and_list_recent(self, store):
        store.record("c1", "abc123", {"restart_count": 1}, [{"gap": "crash_loop", "severity": "critical"}], "critical")
        recent = store.list_recent()
        assert len(recent) == 1
        assert recent[0]["container"] == "c1"

    def test_record_replaces_prior_entry_for_same_container(self, store):
        store.record("c1", "abc123", {"restart_count": 1}, [{"gap": "crash_loop", "severity": "critical"}], "critical")
        store.record("c1", "abc123", {"restart_count": 1}, [], "low", fix_applied=True)
        recent = store.list_recent()
        assert len(recent) == 1
        assert recent[0]["severity"] == "low"
        assert recent[0]["fix_applied"] is True

    def test_last_signature_scoped_per_container(self, store):
        store.record("c1", "abc123", {"restart_count": 1}, [{"gap": "crash_loop", "severity": "critical"}], "critical")
        assert store.last_signature("c1") == "crash_loop"
        assert store.last_signature("c2") is None

    def test_last_snapshot_returned(self, store):
        store.record("c1", "abc123", {"restart_count": 3, "started_at": "t1"}, [], "low")
        snap = store.last_snapshot("c1")
        assert snap == {"restart_count": 3, "started_at": "t1"}
        assert store.last_snapshot("c2") is None


@pytest.mark.asyncio
class TestCheckAllContainers:
    @pytest.fixture
    def store(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            yield DockerHealthHistoryStore(file_path=Path(tmpdir) / "dh_history.json")

    async def test_docker_not_registered_returns_empty(self, store):
        with patch("backend.connectors.registry.connector_registry.get", return_value=None):
            results = await check_all_containers(history_store=store)
        assert results == []

    async def test_crash_loop_files_ticket(self, store):
        store.record("c1", "abc123", {"restart_count": 0, "started_at": "t1", "oom_killed": False, "exit_code": 0, "status": "running", "host_config": {}}, [], "low")
        fake_docker = MagicMock()
        fake_docker.list_containers = AsyncMock(return_value=[{
            "name": "c1", "container_id": "abc123", "restart_count": 5, "started_at": "t2",
            "oom_killed": False, "exit_code": 0, "status": "running", "host_config": {},
        }])

        with patch("backend.connectors.registry.connector_registry.get", return_value=fake_docker), \
             patch("backend.services.enterprise_alert_correlator.correlate_and_report", new=AsyncMock(return_value={"key": "OPS-1"})) as mock_correlate:
            results = await check_all_containers(history_store=store)

        assert len(results) == 1
        assert results[0]["ticket_key"] == "OPS-1"
        assert results[0]["severity"] == "critical"
        mock_correlate.assert_awaited_once()
        assert mock_correlate.call_args.kwargs["service"] == "c1"

    async def test_healthy_container_records_no_ticket(self, store):
        fake_docker = MagicMock()
        fake_docker.list_containers = AsyncMock(return_value=[{
            "name": "c1", "container_id": "abc123", "restart_count": 0, "started_at": "t1",
            "oom_killed": False, "exit_code": 0, "status": "running", "host_config": {},
        }])

        with patch("backend.connectors.registry.connector_registry.get", return_value=fake_docker), \
             patch("backend.services.enterprise_alert_correlator.correlate_and_report", new=AsyncMock()) as mock_correlate:
            results = await check_all_containers(history_store=store)

        assert results[0]["ticket_key"] is None
        assert results[0]["severity"] == "low"
        mock_correlate.assert_not_awaited()

    async def test_already_seen_gap_signature_not_reticketed(self, store):
        store.record("c1", "abc123", {"restart_count": 5, "started_at": "t2", "oom_killed": False, "exit_code": 0, "status": "running", "host_config": {}}, [{"gap": "crash_loop", "severity": "critical"}], "critical", ticket_key="OPS-1")
        fake_docker = MagicMock()
        fake_docker.list_containers = AsyncMock(return_value=[{
            "name": "c1", "container_id": "abc123", "restart_count": 9, "started_at": "t2",
            "oom_killed": False, "exit_code": 0, "status": "running", "host_config": {},
        }])

        with patch("backend.connectors.registry.connector_registry.get", return_value=fake_docker), \
             patch("backend.services.enterprise_alert_correlator.correlate_and_report", new=AsyncMock()) as mock_correlate:
            results = await check_all_containers(history_store=store)

        assert results[0]["ticket_key"] is None
        mock_correlate.assert_not_awaited()

    async def test_check_exception_for_one_container_does_not_break_others(self, store):
        fake_docker = MagicMock()
        fake_docker.list_containers = AsyncMock(return_value=[
            {"name": "bad", "container_id": "bad1", "restart_count": "not-a-number", "started_at": "t1", "oom_killed": False, "exit_code": 0, "status": "running", "host_config": {}},
            {"name": "good", "container_id": "good1", "restart_count": 0, "started_at": "t1", "oom_killed": False, "exit_code": 0, "status": "running", "host_config": {}},
        ])
        store.record("bad", "bad1", {"restart_count": 0, "started_at": "t0", "oom_killed": False, "exit_code": 0, "status": "running", "host_config": {}}, [], "low")

        with patch("backend.connectors.registry.connector_registry.get", return_value=fake_docker), \
             patch("backend.services.enterprise_alert_correlator.correlate_and_report", new=AsyncMock(return_value={"key": "OPS-1"})):
            results = await check_all_containers(history_store=store)

        assert len(results) == 1
        assert results[0]["container"] == "good"

    async def test_list_containers_raises_returns_empty(self, store):
        fake_docker = MagicMock()
        fake_docker.list_containers = AsyncMock(side_effect=RuntimeError("daemon unreachable"))

        with patch("backend.connectors.registry.connector_registry.get", return_value=fake_docker):
            results = await check_all_containers(history_store=store)

        assert results == []

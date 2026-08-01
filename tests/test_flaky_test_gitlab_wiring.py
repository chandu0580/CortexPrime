"""
Tests for the flaky-test detector wired into the GitLab webhook flow
(backend.services.enterprise_gitlab_integration._process_pipeline_event).

Verifies GitLab-specific glue: extracting repo/pipeline info from a
"Pipeline Hook" payload, status normalization ("failed" -> "failure"),
and the trigger_retry/fetch_evidence callbacks — the actual detection
logic itself is tested in test_flaky_test_detector.py.
"""
from __future__ import annotations

import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from backend.services.enterprise_flaky_test_detector import FlakyTestHistoryStore, PendingRetryStore
from backend.services.enterprise_gitlab_integration import _process_pipeline_event

pytestmark = pytest.mark.asyncio


@pytest.fixture(autouse=True)
def _isolate_flaky_test_stores():
    with tempfile.TemporaryDirectory() as tmpdir:
        pending = PendingRetryStore(file_path=Path(tmpdir) / "pending.json")
        history = FlakyTestHistoryStore(file_path=Path(tmpdir) / "history.json")
        with patch("backend.services.enterprise_flaky_test_detector.pending_retry_store", pending), \
             patch("backend.services.enterprise_flaky_test_detector.flaky_test_history_store", history):
            yield pending, history


def _payload(status="failed", **overrides):
    base = {
        "object_kind": "pipeline",
        "object_attributes": {"id": 777, "status": status},
        "project": {"id": 85021889, "path_with_namespace": "group/project"},
    }
    base.update(overrides)
    return base


class TestProcessPipelineEventGating:
    async def test_returns_none_without_project_path(self):
        payload = _payload()
        payload["project"] = {"id": 1}
        assert await _process_pipeline_event(payload) is None

    async def test_returns_none_without_project_id(self):
        payload = _payload()
        payload["project"] = {"path_with_namespace": "group/project"}
        assert await _process_pipeline_event(payload) is None

    async def test_returns_none_without_pipeline_id(self):
        payload = _payload()
        payload["object_attributes"] = {"status": "failed"}
        assert await _process_pipeline_event(payload) is None

    async def test_ignores_non_terminal_status(self):
        with patch("backend.connectors.registry.connector_registry.get") as mock_get:
            result = await _process_pipeline_event(_payload(status="running"))
        assert result is None
        mock_get.assert_not_called()


class TestProcessPipelineEventFreshFailure:
    async def test_triggers_retry_pipeline_and_records_pending(self, _isolate_flaky_test_stores):
        pending, _ = _isolate_flaky_test_stores
        fake_gl = MagicMock()
        fake_gl.retry_pipeline = AsyncMock(return_value={})
        with patch("backend.connectors.registry.connector_registry.get", return_value=fake_gl):
            result = await _process_pipeline_event(_payload(status="failed"))

        assert result is None
        fake_gl.retry_pipeline.assert_awaited_once_with(85021889, 777)
        assert pending.get("gl:group/project:777") is not None

    async def test_success_status_does_not_trigger_retry(self):
        fake_gl = MagicMock()
        fake_gl.retry_pipeline = AsyncMock()
        with patch("backend.connectors.registry.connector_registry.get", return_value=fake_gl):
            await _process_pipeline_event(_payload(status="success"))
        fake_gl.retry_pipeline.assert_not_awaited()

    async def test_missing_connector_does_not_record_pending(self, _isolate_flaky_test_stores):
        pending, _ = _isolate_flaky_test_stores
        with patch("backend.connectors.registry.connector_registry.get", return_value=None):
            await _process_pipeline_event(_payload(status="failed"))
        assert pending.get("gl:group/project:777") is None


class TestProcessPipelineEventRetryCompletion:
    async def test_retry_succeeds_records_flaky_occurrence(self, _isolate_flaky_test_stores):
        pending, history = _isolate_flaky_test_stores
        pending.add("gl:group/project:777", "group/project", "pipeline", {})

        fake_gl = MagicMock()
        fake_gl.list_jobs = AsyncMock(return_value=[{"name": "test", "status": "success"}])
        with patch("backend.connectors.registry.connector_registry.get", return_value=fake_gl):
            result = await _process_pipeline_event(_payload(status="success"))

        assert result is None  # below ticket threshold
        assert pending.get("gl:group/project:777") is None
        assert len(history.list_recent()) == 1
        assert history.list_recent()[0]["workflow_name"] == "pipeline"

    async def test_retry_fails_again_records_no_occurrence(self, _isolate_flaky_test_stores):
        pending, history = _isolate_flaky_test_stores
        pending.add("gl:group/project:777", "group/project", "pipeline", {})

        with patch("backend.connectors.registry.connector_registry.get", return_value=MagicMock()):
            result = await _process_pipeline_event(_payload(status="failed"))

        assert result is None
        assert pending.get("gl:group/project:777") is None
        assert history.list_recent() == []

    async def test_evidence_normalizes_job_status_to_conclusion_vocabulary(self, _isolate_flaky_test_stores):
        pending, history = _isolate_flaky_test_stores
        pending.add("gl:group/project:777", "group/project", "pipeline", {})

        fake_gl = MagicMock()
        fake_gl.list_jobs = AsyncMock(return_value=[
            {"name": "unit-tests", "status": "failed"},
            {"name": "unit-tests", "status": "success"},
            {"name": "lint", "status": "skipped"},  # should be filtered out
        ])
        with patch("backend.connectors.registry.connector_registry.get", return_value=fake_gl):
            await _process_pipeline_event(_payload(status="success"))

        evidence = history.list_recent()[0]["evidence"]
        assert "unit-tests" in evidence
        assert "lint" not in evidence

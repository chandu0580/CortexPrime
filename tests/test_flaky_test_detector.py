"""
Tests for enterprise_flaky_test_detector's persistence classes, threshold
logic, evidence formatting, and the core provider-agnostic state machine.
"""
from __future__ import annotations

import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from backend.services.enterprise_flaky_test_detector import (
    DEFAULT_FLAKY_THRESHOLD_COUNT,
    DEFAULT_FLAKY_THRESHOLD_WINDOW_DAYS,
    FlakyTestHistoryStore,
    PendingRetryStore,
    crosses_flaky_threshold,
    handle_ci_completion,
    summarize_evidence,
)


@pytest.fixture
def pending_store():
    with tempfile.TemporaryDirectory() as tmpdir:
        yield PendingRetryStore(file_path=Path(tmpdir) / "pending.json")


@pytest.fixture
def history_store():
    with tempfile.TemporaryDirectory() as tmpdir:
        yield FlakyTestHistoryStore(file_path=Path(tmpdir) / "history.json")


class TestPendingRetryStore:
    def test_starts_empty(self, pending_store):
        assert pending_store.list_pending() == []

    def test_add_then_get(self, pending_store):
        pending_store.add("run:1", "org/repo", "CI", {"run_id": 1})
        record = pending_store.get("run:1")
        assert record["service"] == "org/repo"
        assert record["workflow_name"] == "CI"

    def test_get_returns_none_for_unknown_key(self, pending_store):
        assert pending_store.get("nope") is None

    def test_remove(self, pending_store):
        pending_store.add("run:1", "org/repo", "CI", {})
        pending_store.remove("run:1")
        assert pending_store.get("run:1") is None

    def test_add_replaces_existing_entry_for_same_key(self, pending_store):
        pending_store.add("run:1", "org/repo", "CI", {"attempt": 1})
        pending_store.add("run:1", "org/repo", "CI", {"attempt": 2})
        assert len(pending_store.list_pending()) == 1
        assert pending_store.get("run:1")["ctx"]["attempt"] == 2

    def test_persists_across_instances(self, pending_store):
        pending_store.add("run:1", "org/repo", "CI", {})
        reloaded = PendingRetryStore(file_path=pending_store._file_path)
        assert reloaded.get("run:1") is not None

    def test_clear(self, pending_store):
        pending_store.add("run:1", "org/repo", "CI", {})
        pending_store.clear()
        assert pending_store.list_pending() == []


class TestFlakyTestHistoryStore:
    def test_starts_empty(self, history_store):
        assert history_store.list_recent() == []

    def test_record_then_list(self, history_store):
        history_store.record("org/repo", "CI", "run:1", "job X failed then passed")
        recent = history_store.list_recent()
        assert len(recent) == 1
        assert recent[0]["service"] == "org/repo"
        assert recent[0]["workflow_name"] == "CI"
        assert "history_id" in recent[0]

    def test_most_recent_first(self, history_store):
        history_store.record("org/repo", "CI", "run:1", "evidence 1")
        history_store.record("org/repo", "CI", "run:2", "evidence 2")
        recent = history_store.list_recent()
        assert recent[0]["run_key"] == "run:2"
        assert recent[1]["run_key"] == "run:1"

    def test_history_id_unique_per_occurrence(self, history_store):
        history_store.record("org/repo", "CI", "run:1", "evidence")
        history_store.record("org/repo", "CI", "run:1", "evidence again")
        recent = history_store.list_recent()
        assert recent[0]["history_id"] != recent[1]["history_id"]

    def test_count_since_filters_by_service_and_workflow(self, history_store):
        history_store.record("org/repo", "CI", "run:1", "evidence")
        history_store.record("org/repo", "other-workflow", "run:2", "evidence")
        history_store.record("other/repo", "CI", "run:3", "evidence")
        since = datetime.now(timezone.utc) - timedelta(days=1)
        assert history_store.count_since("org/repo", "CI", since) == 1

    def test_count_since_excludes_old_occurrences(self, history_store):
        history_store.record("org/repo", "CI", "run:1", "evidence")
        far_future = datetime.now(timezone.utc) + timedelta(days=1)
        assert history_store.count_since("org/repo", "CI", far_future) == 0

    def test_persists_across_instances(self, history_store):
        history_store.record("org/repo", "CI", "run:1", "evidence")
        reloaded = FlakyTestHistoryStore(file_path=history_store._file_path)
        assert len(reloaded.list_recent()) == 1

    def test_clear(self, history_store):
        history_store.record("org/repo", "CI", "run:1", "evidence")
        history_store.clear()
        assert history_store.list_recent() == []

    def test_update_ticket_key_links_ticket_to_the_right_occurrence(self, history_store):
        first = history_store.record("org/repo", "CI", "run:1", "evidence 1")
        second = history_store.record("org/repo", "CI", "run:2", "evidence 2")
        history_store.update_ticket_key(second["history_id"], "OPS-99")
        recent = history_store.list_recent()
        by_id = {h["history_id"]: h for h in recent}
        assert by_id[second["history_id"]]["ticket_key"] == "OPS-99"
        assert by_id[first["history_id"]]["ticket_key"] is None

    def test_update_ticket_key_persists_across_instances(self, history_store):
        recorded = history_store.record("org/repo", "CI", "run:1", "evidence")
        history_store.update_ticket_key(recorded["history_id"], "OPS-100")
        reloaded = FlakyTestHistoryStore(file_path=history_store._file_path)
        assert reloaded.list_recent()[0]["ticket_key"] == "OPS-100"

    def test_update_ticket_key_is_a_noop_for_unknown_history_id(self, history_store):
        history_store.record("org/repo", "CI", "run:1", "evidence")
        history_store.update_ticket_key("does-not-exist", "OPS-101")
        assert history_store.list_recent()[0]["ticket_key"] is None


class TestCrossesFlakyThreshold:
    def test_false_when_no_occurrences(self, history_store):
        assert crosses_flaky_threshold("org/repo", "CI", history_store=history_store) is False

    def test_false_when_below_default_threshold(self, history_store):
        for i in range(DEFAULT_FLAKY_THRESHOLD_COUNT - 1):
            history_store.record("org/repo", "CI", f"run:{i}", "evidence")
        assert crosses_flaky_threshold("org/repo", "CI", history_store=history_store) is False

    def test_true_when_at_default_threshold(self, history_store):
        for i in range(DEFAULT_FLAKY_THRESHOLD_COUNT):
            history_store.record("org/repo", "CI", f"run:{i}", "evidence")
        assert crosses_flaky_threshold("org/repo", "CI", history_store=history_store) is True

    def test_respects_custom_threshold_count(self, history_store):
        history_store.record("org/repo", "CI", "run:1", "evidence")
        assert crosses_flaky_threshold("org/repo", "CI", threshold_count=1, history_store=history_store) is True

    def test_does_not_count_other_workflows(self, history_store):
        for i in range(DEFAULT_FLAKY_THRESHOLD_COUNT):
            history_store.record("org/repo", "other-workflow", f"run:{i}", "evidence")
        assert crosses_flaky_threshold("org/repo", "CI", history_store=history_store) is False


class TestSummarizeEvidence:
    def test_includes_job_name_and_conclusion(self):
        summary = summarize_evidence([
            {"attempt": 1, "job_name": "backend-tests", "conclusion": "failure", "failed_steps": []},
        ])
        assert "backend-tests" in summary
        assert "failure" in summary

    def test_includes_failed_steps(self):
        summary = summarize_evidence([
            {"attempt": 1, "job_name": "backend-tests", "conclusion": "failure", "failed_steps": ["Run pytest"]},
        ])
        assert "Run pytest" in summary

    def test_handles_empty_evidence(self):
        summary = summarize_evidence([])
        assert "no job/step evidence" in summary

    def test_includes_multiple_attempts(self):
        summary = summarize_evidence([
            {"attempt": 1, "job_name": "backend-tests", "conclusion": "failure", "failed_steps": ["Run pytest"]},
            {"attempt": 2, "job_name": "backend-tests", "conclusion": "success", "failed_steps": []},
        ])
        assert "Attempt 1" in summary
        assert "Attempt 2" in summary


@pytest.mark.asyncio
class TestHandleCiCompletion:
    async def test_fresh_success_does_nothing(self, pending_store, history_store):
        trigger_retry = AsyncMock(return_value=True)
        fetch_evidence = AsyncMock(return_value=[])
        result = await handle_ci_completion(
            "org/repo", "CI", "run:1", "success", {},
            trigger_retry, fetch_evidence,
            pending_store=pending_store, history_store=history_store,
        )
        assert result is None
        trigger_retry.assert_not_awaited()
        assert pending_store.list_pending() == []
        assert history_store.list_recent() == []

    async def test_fresh_failure_triggers_retry_and_records_pending(self, pending_store, history_store):
        trigger_retry = AsyncMock(return_value=True)
        fetch_evidence = AsyncMock(return_value=[])
        result = await handle_ci_completion(
            "org/repo", "CI", "run:1", "failure", {"run_id": 1},
            trigger_retry, fetch_evidence,
            pending_store=pending_store, history_store=history_store,
        )
        assert result is None
        trigger_retry.assert_awaited_once()
        assert pending_store.get("run:1") is not None

    async def test_fresh_failure_with_retry_trigger_returning_false_does_not_record_pending(self, pending_store, history_store):
        trigger_retry = AsyncMock(return_value=False)
        fetch_evidence = AsyncMock(return_value=[])
        await handle_ci_completion(
            "org/repo", "CI", "run:1", "failure", {},
            trigger_retry, fetch_evidence,
            pending_store=pending_store, history_store=history_store,
        )
        assert pending_store.get("run:1") is None

    async def test_fresh_failure_with_retry_trigger_raising_does_not_propagate(self, pending_store, history_store):
        trigger_retry = AsyncMock(side_effect=RuntimeError("API down"))
        fetch_evidence = AsyncMock(return_value=[])
        result = await handle_ci_completion(
            "org/repo", "CI", "run:1", "failure", {},
            trigger_retry, fetch_evidence,
            pending_store=pending_store, history_store=history_store,
        )
        assert result is None
        assert pending_store.get("run:1") is None

    async def test_retry_completion_success_records_history_and_clears_pending(self, pending_store, history_store):
        pending_store.add("run:1", "org/repo", "CI", {})
        fetch_evidence = AsyncMock(return_value=[{"attempt": 2, "job_name": "CI", "conclusion": "success"}])
        trigger_retry = AsyncMock()

        result = await handle_ci_completion(
            "org/repo", "CI", "run:1", "success", {},
            trigger_retry, fetch_evidence,
            pending_store=pending_store, history_store=history_store,
        )

        assert result is None  # below threshold, no ticket
        assert pending_store.get("run:1") is None
        assert len(history_store.list_recent()) == 1

    async def test_retry_completion_success_still_records_history_when_evidence_fetch_raises(self, pending_store, history_store):
        pending_store.add("run:1", "org/repo", "CI", {})
        fetch_evidence = AsyncMock(side_effect=RuntimeError("connector unavailable"))

        result = await handle_ci_completion(
            "org/repo", "CI", "run:1", "success", {},
            AsyncMock(), fetch_evidence,
            pending_store=pending_store, history_store=history_store,
        )

        assert result is None
        assert pending_store.get("run:1") is None
        assert len(history_store.list_recent()) == 1

    async def test_retry_completion_failure_clears_pending_without_recording_history(self, pending_store, history_store):
        pending_store.add("run:1", "org/repo", "CI", {})
        fetch_evidence = AsyncMock(return_value=[])
        trigger_retry = AsyncMock()

        result = await handle_ci_completion(
            "org/repo", "CI", "run:1", "failure", {},
            trigger_retry, fetch_evidence,
            pending_store=pending_store, history_store=history_store,
        )

        assert result is None
        assert pending_store.get("run:1") is None
        assert history_store.list_recent() == []
        fetch_evidence.assert_not_awaited()

    async def test_retry_completion_crossing_threshold_files_ticket(self, pending_store, history_store):
        # Already at threshold - 1 occurrences; this completion should push it over.
        for i in range(DEFAULT_FLAKY_THRESHOLD_COUNT - 1):
            history_store.record("org/repo", "CI", f"run:{i}", "evidence")
        pending_store.add("run:new", "org/repo", "CI", {})
        fetch_evidence = AsyncMock(return_value=[{"attempt": 2, "job_name": "CI", "conclusion": "success"}])

        with patch(
            "backend.services.enterprise_flaky_test_incident_reporter.report_flaky_incident",
            new=AsyncMock(return_value={"key": "OPS-1"}),
        ) as mock_report:
            result = await handle_ci_completion(
                "org/repo", "CI", "run:new", "success", {},
                AsyncMock(), fetch_evidence,
                pending_store=pending_store, history_store=history_store,
            )

        assert result == {"key": "OPS-1"}
        mock_report.assert_awaited_once()

        # The occurrence that triggered the ticket must be linked to it,
        # not just left with ticket_key=None despite a real ticket existing.
        triggering_occurrence = next(h for h in history_store.list_recent() if h["run_key"] == "run:new")
        assert triggering_occurrence["ticket_key"] == "OPS-1"

    async def test_retry_completion_crossing_threshold_does_not_link_ticket_when_filing_fails(self, pending_store, history_store):
        for i in range(DEFAULT_FLAKY_THRESHOLD_COUNT - 1):
            history_store.record("org/repo", "CI", f"run:{i}", "evidence")
        pending_store.add("run:new", "org/repo", "CI", {})

        with patch(
            "backend.services.enterprise_flaky_test_incident_reporter.report_flaky_incident",
            new=AsyncMock(return_value=None),
        ):
            await handle_ci_completion(
                "org/repo", "CI", "run:new", "success", {},
                AsyncMock(), AsyncMock(return_value=[]),
                pending_store=pending_store, history_store=history_store,
            )

        triggering_occurrence = next(h for h in history_store.list_recent() if h["run_key"] == "run:new")
        assert triggering_occurrence["ticket_key"] is None

    async def test_ignores_unrecognized_conclusion_values(self, pending_store, history_store):
        trigger_retry = AsyncMock()
        result = await handle_ci_completion(
            "org/repo", "CI", "run:1", "cancelled", {},
            trigger_retry, AsyncMock(),
            pending_store=pending_store, history_store=history_store,
        )
        assert result is None
        trigger_retry.assert_not_awaited()

    async def test_unrelated_run_key_success_is_ignored(self, pending_store, history_store):
        # A success for a run_key we never triggered a retry for (e.g. a
        # normal passing run) must not be mistaken for a retry completion.
        result = await handle_ci_completion(
            "org/repo", "CI", "run:never-seen", "success", {},
            AsyncMock(), AsyncMock(),
            pending_store=pending_store, history_store=history_store,
        )
        assert result is None
        assert history_store.list_recent() == []

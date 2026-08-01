"""
Tests for the flaky-test detector wired into the GitHub webhook flow
(backend.services.enterprise_github_integration._check_flaky_test).

Verifies GitHub-specific glue: extracting service/workflow_name/run_id
from ctx, building the run_key, and the trigger_retry/fetch_evidence
callbacks that call the real connector methods — the actual detection
logic itself is tested in test_flaky_test_detector.py.

_check_flaky_test returns an asyncio.Task (not the final result) — it's
scheduled as a background task rather than awaited inline, since GitHub's
webhook delivery times out at 10 seconds and the retry-completion path
(LLM reasoning + Jira ticket filing) can exceed that on its own. Tests
that need the final outcome explicitly await the returned task, exactly
like test_deploy_regression_webhook_wiring.py already does for the same
reason.
"""
from __future__ import annotations

import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from backend.services.enterprise_flaky_test_detector import FlakyTestHistoryStore, PendingRetryStore
from backend.services.enterprise_github_integration import _check_flaky_test

pytestmark = pytest.mark.asyncio


@pytest.fixture(autouse=True)
def _isolate_flaky_test_stores():
    with tempfile.TemporaryDirectory() as tmpdir:
        pending = PendingRetryStore(file_path=Path(tmpdir) / "pending.json")
        history = FlakyTestHistoryStore(file_path=Path(tmpdir) / "history.json")
        with patch("backend.services.enterprise_flaky_test_detector.pending_retry_store", pending), \
             patch("backend.services.enterprise_flaky_test_detector.flaky_test_history_store", history):
            yield pending, history


def _ctx(status="completed", conclusion="failure", **overrides):
    base = {
        "repo_full_name": "org/checkout-service",
        "workflow_name": "CI",
        "workflow_run_id": 555,
        "workflow_status": status,
        "workflow_conclusion": conclusion,
    }
    base.update(overrides)
    return base


async def _run(ctx):
    """Call _check_flaky_test and, if it scheduled a background task,
    await it so the test can deterministically check side effects."""
    task = await _check_flaky_test(ctx)
    if task is not None:
        return await task
    return None


class TestCheckFlakyTestGating:
    async def test_ignores_non_completed_status(self):
        result = await _check_flaky_test(_ctx(status="in_progress"))
        assert result is None

    async def test_returns_none_without_repo_full_name(self):
        ctx = _ctx()
        del ctx["repo_full_name"]
        assert await _check_flaky_test(ctx) is None

    async def test_returns_none_without_workflow_name(self):
        ctx = _ctx()
        ctx["workflow_name"] = ""
        assert await _check_flaky_test(ctx) is None

    async def test_returns_none_without_run_id(self):
        ctx = _ctx()
        ctx["workflow_run_id"] = None
        assert await _check_flaky_test(ctx) is None


class TestCheckFlakyTestFreshFailure:
    async def test_triggers_rerun_failed_jobs_and_records_pending(self, _isolate_flaky_test_stores):
        pending, _ = _isolate_flaky_test_stores
        fake_gh = MagicMock()
        fake_gh.rerun_failed_jobs = AsyncMock(return_value=True)
        with patch("backend.services.enterprise_github_integration._get_gh", new=AsyncMock(return_value=fake_gh)):
            result = await _run(_ctx(conclusion="failure"))

        assert result is None
        fake_gh.rerun_failed_jobs.assert_awaited_once_with("org", "checkout-service", 555)
        assert pending.get("gh:org/checkout-service:555") is not None

    async def test_success_conclusion_does_not_trigger_retry(self):
        fake_gh = MagicMock()
        fake_gh.rerun_failed_jobs = AsyncMock(return_value=True)
        with patch("backend.services.enterprise_github_integration._get_gh", new=AsyncMock(return_value=fake_gh)):
            await _run(_ctx(conclusion="success"))
        fake_gh.rerun_failed_jobs.assert_not_awaited()


class TestCheckFlakyTestReturnsBackgroundTask:
    """The whole point of the fix: the caller (the webhook route) must
    never block on the slow retry-completion path."""

    async def test_returns_a_task_not_the_final_result(self, _isolate_flaky_test_stores):
        pending, _ = _isolate_flaky_test_stores
        fake_gh = MagicMock()
        fake_gh.rerun_failed_jobs = AsyncMock(return_value=True)
        with patch("backend.services.enterprise_github_integration._get_gh", new=AsyncMock(return_value=fake_gh)):
            import asyncio
            task = await _check_flaky_test(_ctx(conclusion="failure"))
        assert isinstance(task, asyncio.Task)
        await task


class TestCheckFlakyTestRetryCompletion:
    async def test_retry_passes_records_flaky_occurrence(self, _isolate_flaky_test_stores):
        pending, history = _isolate_flaky_test_stores
        pending.add("gh:org/checkout-service:555", "org/checkout-service", "CI", _ctx())

        fake_gh = MagicMock()
        fake_gh.list_jobs_for_run = AsyncMock(return_value=[
            {"name": "backend-tests", "conclusion": "success", "run_attempt": 2, "steps": []},
        ])
        with patch("backend.services.enterprise_github_integration._get_gh", new=AsyncMock(return_value=fake_gh)):
            result = await _run(_ctx(conclusion="success"))

        assert result is None  # below ticket threshold
        assert pending.get("gh:org/checkout-service:555") is None
        assert len(history.list_recent()) == 1
        assert history.list_recent()[0]["service"] == "org/checkout-service"

    async def test_retry_fails_again_records_no_occurrence(self, _isolate_flaky_test_stores):
        pending, history = _isolate_flaky_test_stores
        pending.add("gh:org/checkout-service:555", "org/checkout-service", "CI", _ctx())

        with patch("backend.services.enterprise_github_integration._get_gh", new=AsyncMock()):
            result = await _run(_ctx(conclusion="failure"))

        assert result is None
        assert pending.get("gh:org/checkout-service:555") is None
        assert history.list_recent() == []

    async def test_evidence_extracts_failed_step_names(self, _isolate_flaky_test_stores):
        pending, history = _isolate_flaky_test_stores
        pending.add("gh:org/checkout-service:555", "org/checkout-service", "CI", _ctx())

        fake_gh = MagicMock()
        fake_gh.list_jobs_for_run = AsyncMock(return_value=[
            {
                "name": "backend-tests", "conclusion": "failure", "run_attempt": 1,
                "steps": [{"name": "Run pytest", "conclusion": "failure"}, {"name": "Checkout", "conclusion": "success"}],
            },
            {"name": "backend-tests", "conclusion": "success", "run_attempt": 2, "steps": []},
        ])
        with patch("backend.services.enterprise_github_integration._get_gh", new=AsyncMock(return_value=fake_gh)):
            await _run(_ctx(conclusion="success"))

        evidence = history.list_recent()[0]["evidence"]
        assert "Run pytest" in evidence
        assert "Checkout" not in evidence  # only failed steps are surfaced

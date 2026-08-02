"""
Tests for the watcher continuous-polling wiring fixes:
  1. _poll_loop now sets watcher._task, so EnterpriseWatcher.shutdown()'s
     existing cancellation logic actually has something to cancel (before
     this fix, start_polling() created loop tasks but never stored them
     anywhere, so shutdown_all() silently cancelled nothing).
  2. evaluate_event_against_rules() is the shared helper both _poll_loop
     and the manual POST /api/monitoring/poll route now call, so the
     background loop actually triggers rule-driven auto-mission-creation
     instead of only detecting events and streaming them to the UI.
"""
from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from backend.services.enterprise_watchers import (
    DetectedEvent,
    EnterpriseWatcher,
    WatcherManager,
    evaluate_event_against_rules,
)

pytestmark = pytest.mark.asyncio


class _StubWatcher(EnterpriseWatcher):
    connector_type = "stub"
    poll_interval = 0.01

    def __init__(self, events_per_poll=None):
        self._events_per_poll = events_per_poll or []
        self._poll_count = 0

    async def poll(self):
        self._poll_count += 1
        return self._events_per_poll


class TestEvaluateEventAgainstRules:
    async def test_records_and_evaluates_event(self):
        fake_rules = MagicMock()
        fake_rules.record_event = MagicMock()
        fake_rules.evaluate_event = AsyncMock(return_value=[])
        with patch("backend.services.monitoring_rules_engine.monitoring_rules", fake_rules):
            result = await evaluate_event_against_rules({"connector_type": "github", "event_type": "issue_opened"})

        fake_rules.record_event.assert_called_once()
        fake_rules.evaluate_event.assert_awaited_once()
        assert result == {"rules_matched": 0, "missions_created": 0}

    async def test_creates_mission_for_matching_auto_create_rule(self):
        fake_rule = MagicMock(auto_create_mission=True)
        fake_rules = MagicMock()
        fake_rules.record_event = MagicMock()
        fake_rules.evaluate_event = AsyncMock(return_value=[fake_rule])
        fake_generator = MagicMock()
        fake_generator.create_mission = AsyncMock(return_value={"mission_id": "m1"})

        with patch("backend.services.monitoring_rules_engine.monitoring_rules", fake_rules), \
             patch("backend.services.autonomous_mission_generator.auto_mission_generator", fake_generator):
            result = await evaluate_event_against_rules({"connector_type": "github", "event_type": "issue_opened"})

        fake_generator.create_mission.assert_awaited_once_with(fake_rule, {"connector_type": "github", "event_type": "issue_opened"})
        assert result == {"rules_matched": 1, "missions_created": 1}

    async def test_does_not_create_mission_when_auto_create_mission_false(self):
        fake_rule = MagicMock(auto_create_mission=False)
        fake_rules = MagicMock()
        fake_rules.record_event = MagicMock()
        fake_rules.evaluate_event = AsyncMock(return_value=[fake_rule])
        fake_generator = MagicMock()
        fake_generator.create_mission = AsyncMock()

        with patch("backend.services.monitoring_rules_engine.monitoring_rules", fake_rules), \
             patch("backend.services.autonomous_mission_generator.auto_mission_generator", fake_generator):
            result = await evaluate_event_against_rules({"connector_type": "github", "event_type": "issue_opened"})

        fake_generator.create_mission.assert_not_awaited()
        assert result == {"rules_matched": 1, "missions_created": 0}


class TestPollLoopTaskTracking:
    async def test_poll_loop_sets_watcher_task(self):
        watcher = _StubWatcher()
        manager = WatcherManager()
        with patch("backend.services.enterprise_watchers.evaluate_event_against_rules", new=AsyncMock()):
            task = asyncio.create_task(manager._poll_loop(watcher))
            await asyncio.sleep(0.02)
            assert watcher._task is task
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass

    async def test_shutdown_actually_cancels_the_running_poll_loop(self):
        """Before the fix: watcher._task was always None, so shutdown()'s
        `if self._task and not self._task.done(): self._task.cancel()`
        silently cancelled nothing and the loop kept running forever."""
        watcher = _StubWatcher()
        manager = WatcherManager()
        with patch("backend.services.enterprise_watchers.evaluate_event_against_rules", new=AsyncMock()):
            outer_task = asyncio.create_task(manager._poll_loop(watcher))
            await asyncio.sleep(0.02)
            assert watcher._task is not None

            await watcher.shutdown()

            assert outer_task.done()
            assert watcher._task is None

    async def test_poll_loop_calls_evaluate_event_against_rules_per_detected_event(self):
        event = DetectedEvent(connector_type="stub", event_type="test", severity="medium", title="x")
        watcher = _StubWatcher(events_per_poll=[event])
        manager = WatcherManager()
        watcher.process_event = AsyncMock()

        with patch("backend.services.enterprise_watchers.evaluate_event_against_rules", new=AsyncMock()) as mock_eval:
            task = asyncio.create_task(manager._poll_loop(watcher))
            await asyncio.sleep(0.02)
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass

        mock_eval.assert_awaited()
        _, call_args, _ = mock_eval.mock_calls[0]
        assert call_args[0]["connector_type"] == "stub"

    async def test_evaluate_failure_does_not_kill_the_poll_loop(self):
        event = DetectedEvent(connector_type="stub", event_type="test", severity="medium", title="x")
        watcher = _StubWatcher(events_per_poll=[event])
        watcher.process_event = AsyncMock()
        manager = WatcherManager()

        with patch(
            "backend.services.enterprise_watchers.evaluate_event_against_rules",
            new=AsyncMock(side_effect=RuntimeError("boom")),
        ):
            task = asyncio.create_task(manager._poll_loop(watcher))
            await asyncio.sleep(0.02)
            still_running = not task.done()
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass

        assert still_running

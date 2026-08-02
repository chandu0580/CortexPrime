from __future__ import annotations

import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from backend.services.enterprise_approval_action_dispatcher import (
    PendingActionStore,
    _on_event,
    handle_approval_event,
    initialize,
)


@pytest.fixture
def store():
    with tempfile.TemporaryDirectory() as tmpdir:
        yield PendingActionStore(file_path=Path(tmpdir) / "pending_actions.json")


class TestPendingActionStore:
    def test_save_and_pop(self, store):
        store.save("wf_1", "rollback", {"service": "org/repo"})
        assert "wf_1" in store.list_pending()
        entry = store.pop("wf_1")
        assert entry == {"action_type": "rollback", "payload": {"service": "org/repo"}}
        assert "wf_1" not in store.list_pending()

    def test_pop_missing_returns_none(self, store):
        assert store.pop("nonexistent") is None

    def test_persists_across_instances(self, store):
        store.save("wf_1", "rollback", {"service": "org/repo"})
        reloaded = PendingActionStore(file_path=store._file_path)
        assert "wf_1" in reloaded.list_pending()

    def test_clear(self, store):
        store.save("wf_1", "rollback", {"service": "org/repo"})
        store.clear()
        assert store.list_pending() == {}


@pytest.mark.asyncio
class TestHandleApprovalEvent:
    async def test_no_workflow_id_is_noop(self, store):
        with patch("backend.services.enterprise_approval_action_dispatcher.pending_action_store", store):
            result = await handle_approval_event({"status": "approved"})
        assert result is None

    async def test_non_terminal_status_is_noop(self, store):
        with patch("backend.services.enterprise_approval_action_dispatcher.pending_action_store", store):
            result = await handle_approval_event({"workflow_id": "wf_1", "status": "pending"})
        assert result is None

    async def test_unknown_workflow_id_is_noop(self, store):
        with patch("backend.services.enterprise_approval_action_dispatcher.pending_action_store", store):
            result = await handle_approval_event({"workflow_id": "wf_never_seen", "status": "approved"})
        assert result is None

    async def test_rejected_discards_without_dispatching(self, store):
        store.save("wf_1", "rollback", {"service": "org/repo"})
        with patch("backend.services.enterprise_approval_action_dispatcher.pending_action_store", store), \
             patch("backend.services.enterprise_deploy_rollback_executor.replay_rollback", new=AsyncMock()) as mock_replay:
            result = await handle_approval_event({"workflow_id": "wf_1", "status": "rejected"})
        assert result is None
        mock_replay.assert_not_awaited()
        assert "wf_1" not in store.list_pending()

    async def test_expired_discards_without_dispatching(self, store):
        store.save("wf_1", "rollback", {"service": "org/repo"})
        with patch("backend.services.enterprise_approval_action_dispatcher.pending_action_store", store), \
             patch("backend.services.enterprise_deploy_rollback_executor.replay_rollback", new=AsyncMock()) as mock_replay:
            result = await handle_approval_event({"workflow_id": "wf_1", "status": "expired"})
        assert result is None
        mock_replay.assert_not_awaited()

    async def test_approved_replays_rollback(self, store):
        store.save("wf_1", "rollback", {"service": "org/repo", "deployment_id": "42", "reasons": ["x"], "ctx": {}, "ticket_key": None})
        with patch("backend.services.enterprise_approval_action_dispatcher.pending_action_store", store), \
             patch("backend.services.enterprise_deploy_rollback_executor.replay_rollback", new=AsyncMock()) as mock_replay:
            result = await handle_approval_event({"workflow_id": "wf_1", "status": "approved"})
        assert result == "rollback"
        mock_replay.assert_awaited_once_with({"service": "org/repo", "deployment_id": "42", "reasons": ["x"], "ctx": {}, "ticket_key": None})
        assert "wf_1" not in store.list_pending()

    async def test_break_glass_replays_vulnerability_fix(self, store):
        payload = {"owner": "o", "repo": "r", "manifest_path": "requirements.txt", "package": "lodash", "first_patched_version": "4.17.21"}
        store.save("wf_2", "vulnerability_fix_pr", payload)
        with patch("backend.services.enterprise_approval_action_dispatcher.pending_action_store", store), \
             patch("backend.services.enterprise_vulnerability_fix_executor.open_dependency_fix_pr", new=AsyncMock()) as mock_fix:
            result = await handle_approval_event({"workflow_id": "wf_2", "status": "break_glass"})
        assert result == "vulnerability_fix_pr"
        mock_fix.assert_awaited_once_with(**payload)

    async def test_approved_replays_branch_protection_fix(self, store):
        payload = {"owner": "o", "repo": "r", "branch": "main", "ticket_key": "OPS-1"}
        store.save("wf_3", "branch_protection_fix", payload)
        with patch("backend.services.enterprise_approval_action_dispatcher.pending_action_store", store), \
             patch("backend.services.enterprise_branch_protection_fix_executor.enable_minimal_protection", new=AsyncMock()) as mock_fix:
            result = await handle_approval_event({"workflow_id": "wf_3", "status": "approved"})
        assert result == "branch_protection_fix"
        mock_fix.assert_awaited_once_with(**payload)

    async def test_unknown_action_type_is_noop(self, store):
        store.save("wf_4", "some_future_action_type", {})
        with patch("backend.services.enterprise_approval_action_dispatcher.pending_action_store", store):
            result = await handle_approval_event({"workflow_id": "wf_4", "status": "approved"})
        assert result is None

    async def test_dispatch_exception_does_not_raise(self, store):
        store.save("wf_1", "rollback", {"service": "org/repo", "deployment_id": "42", "reasons": [], "ctx": {}, "ticket_key": None})
        with patch("backend.services.enterprise_approval_action_dispatcher.pending_action_store", store), \
             patch("backend.services.enterprise_deploy_rollback_executor.replay_rollback", new=AsyncMock(side_effect=RuntimeError("boom"))):
            result = await handle_approval_event({"workflow_id": "wf_1", "status": "approved"})
        assert result == "rollback"  # dispatched, even though the replay itself failed


class TestOnEvent:
    def test_ignores_events_from_other_agents(self):
        event = type("FakeEvent", (), {"agent": "some_other_agent", "event_type": "approval_workflow_completed", "payload": {}})()
        assert _on_event(event) is None

    def test_ignores_unrelated_event_types(self):
        event = type("FakeEvent", (), {"agent": "approval_center", "event_type": "approval_workflow_created", "payload": {}})()
        assert _on_event(event) is None

    def test_returns_coroutine_for_relevant_event(self):
        event = type("FakeEvent", (), {"agent": "approval_center", "event_type": "approval_workflow_completed", "payload": {}})()
        result = _on_event(event)
        assert result is not None
        result.close()  # avoid "coroutine was never awaited" warning


class TestInitialize:
    def test_subscribes_on_event_to_the_event_bus(self):
        from backend.events.event_bus import event_bus
        try:
            initialize()
            assert _on_event in event_bus._handlers
            initialize()  # idempotent — calling twice must not double-register
            assert event_bus._handlers.count(_on_event) == 1
        finally:
            event_bus.unsubscribe(_on_event)

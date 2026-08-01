from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from backend.services.enterprise_deploy_rollback_store import RollbackHistoryStore


@pytest.fixture
def store():
    with tempfile.TemporaryDirectory() as tmpdir:
        yield RollbackHistoryStore(file_path=Path(tmpdir) / "rollback_history.json")


class TestRollbackHistoryStore:
    def test_record_returns_entry_with_generated_id(self, store):
        entry = store.record(
            provider="github", service="org/repo", environment="production",
            bad_deployment_id="42", reasons=["p95 latency +30%"], triggered=True,
            target_sha="abc123", target_deployment_id=41, rollback_deployment_id=43,
        )
        assert entry["history_id"]
        assert entry["provider"] == "github"
        assert entry["triggered"] is True
        assert entry["target_sha"] == "abc123"

    def test_list_recent_returns_newest_first(self, store):
        store.record(provider="github", service="a", environment="prod", bad_deployment_id="1", reasons=[], triggered=True)
        store.record(provider="github", service="b", environment="prod", bad_deployment_id="2", reasons=[], triggered=True)
        recent = store.list_recent()
        assert [r["service"] for r in recent] == ["b", "a"]

    def test_list_recent_respects_limit(self, store):
        for i in range(5):
            store.record(provider="github", service=f"svc{i}", environment="prod", bad_deployment_id=str(i), reasons=[], triggered=True)
        assert len(store.list_recent(limit=2)) == 2

    def test_record_untriggered_attempt_carries_error(self, store):
        entry = store.record(
            provider="gitlab", service="grp/proj", environment="staging",
            bad_deployment_id="7", reasons=["error rate spike"], triggered=False,
            error="No known-good deployment found to roll back to",
        )
        assert entry["triggered"] is False
        assert entry["error"] == "No known-good deployment found to roll back to"
        assert entry["rollback_deployment_id"] is None

    def test_update_ticket_key_links_existing_entry(self, store):
        entry = store.record(provider="github", service="a", environment="prod", bad_deployment_id="1", reasons=[], triggered=True)
        store.update_ticket_key(entry["history_id"], "OPS-99")
        recent = store.list_recent()
        assert recent[0]["ticket_key"] == "OPS-99"

    def test_persists_across_store_instances(self, store):
        store.record(provider="github", service="a", environment="prod", bad_deployment_id="1", reasons=[], triggered=True)
        reloaded = RollbackHistoryStore(file_path=store._file_path)
        assert len(reloaded.list_recent()) == 1

    def test_clear_empties_history(self, store):
        store.record(provider="github", service="a", environment="prod", bad_deployment_id="1", reasons=[], triggered=True)
        store.clear()
        assert store.list_recent() == []

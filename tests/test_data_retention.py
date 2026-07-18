from __future__ import annotations

import json
import os
import sys
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from backend.core.data_retention import DataRetentionPolicy


@pytest.fixture
def temp_storage():
    with tempfile.TemporaryDirectory() as tmp:
        yield str(tmp)


@pytest.fixture
def policy(temp_storage):
    return DataRetentionPolicy(storage_dir=temp_storage)


class TestDataRetentionPolicy:
    def test_default_policy_values(self, policy):
        assert policy.get_policy("episodic_records") == 90
        assert policy.get_policy("audit_logs") == 90
        assert policy.get_policy("telemetry_metrics") == 180
        assert policy.get_policy("replay_data") == 30
        assert policy.get_policy("event_history") == 90
        assert policy.get_policy("temporary_uploads") == 7

    def test_get_policy_unknown_category_returns_default(self, policy):
        assert policy.get_policy("nonexistent") == 90

    def test_set_policy(self, policy):
        policy.set_policy("episodic_records", 45)
        assert policy.get_policy("episodic_records") == 45

    def test_set_policy_minimum_one(self, policy):
        policy.set_policy("audit_logs", 0)
        assert policy.get_policy("audit_logs") == 1

    def test_set_policy_negative(self, policy):
        policy.set_policy("replay_data", -10)
        assert policy.get_policy("replay_data") == 1

    def test_list_policies(self, policy):
        policies = policy.list_policies()
        assert isinstance(policies, dict)
        assert "episodic_records" in policies
        assert "audit_logs" in policies
        assert "telemetry_metrics" in policies

    def test_list_policies_after_update(self, policy):
        policy.set_policy("episodic_records", 30)
        policies = policy.list_policies()
        assert policies["episodic_records"] == 30

    def test_purge_old_records_file(self, temp_storage, policy):
        today = datetime.now(timezone.utc).isoformat()
        old = (datetime.now(timezone.utc) - timedelta(days=200)).isoformat()
        data = [
            {"id": 1, "timestamp": today},
            {"id": 2, "timestamp": old},
        ]
        test_file = Path(temp_storage) / "test_records.json"
        test_file.write_text(json.dumps(data))

        purged = policy.purge_old_records("episodic_records", str(test_file))
        assert purged == 1

        remaining = json.loads(test_file.read_text())
        assert len(remaining) == 1
        assert remaining[0]["id"] == 1

    def test_purge_old_records_directory(self, temp_storage, policy):
        today = datetime.now(timezone.utc).isoformat()
        old = (datetime.now(timezone.utc) - timedelta(days=200)).isoformat()
        data_dir = Path(temp_storage) / "records"
        data_dir.mkdir()
        file1 = data_dir / "a.json"
        file1.write_text(json.dumps([
            {"id": 1, "timestamp": today},
            {"id": 2, "timestamp": old},
        ]))
        file2 = data_dir / "b.json"
        file2.write_text(json.dumps([
            {"id": 3, "timestamp": old},
        ]))

        purged = policy.purge_old_records("episodic_records", str(data_dir))
        assert purged == 2

        assert len(json.loads(file1.read_text())) == 1
        assert len(json.loads(file2.read_text())) == 0

    def test_purge_nonexistent_file(self, policy):
        purged = policy.purge_old_records("episodic_records", "/nonexistent/path.json")
        assert purged == 0

    def test_purge_with_custom_date_field(self, temp_storage, policy):
        today = datetime.now(timezone.utc).isoformat()
        old = (datetime.now(timezone.utc) - timedelta(days=200)).isoformat()
        data = [
            {"id": 1, "created_at": today},
            {"id": 2, "created_at": old},
        ]
        test_file = Path(temp_storage) / "custom.json"
        test_file.write_text(json.dumps(data))

        purged = policy.purge_old_records("episodic_records", str(test_file), date_field="created_at")
        assert purged == 1

    def test_purge_no_old_records(self, temp_storage, policy):
        today = datetime.now(timezone.utc).isoformat()
        data = [{"id": 1, "timestamp": today}]
        test_file = Path(temp_storage) / "fresh.json"
        test_file.write_text(json.dumps(data))

        purged = policy.purge_old_records("episodic_records", str(test_file))
        assert purged == 0

    def test_purge_empty_list(self, temp_storage, policy):
        test_file = Path(temp_storage) / "empty.json"
        test_file.write_text(json.dumps([]))
        purged = policy.purge_old_records("episodic_records", str(test_file))
        assert purged == 0

    def test_purge_corrupted_file(self, temp_storage, policy):
        test_file = Path(temp_storage) / "corrupt.json"
        test_file.write_text("not valid json")
        purged = policy.purge_old_records("episodic_records", str(test_file))
        assert purged == 0

    def test_policy_persistence(self, temp_storage):
        p1 = DataRetentionPolicy(storage_dir=temp_storage)
        p1.set_policy("episodic_records", 15)

        p2 = DataRetentionPolicy(storage_dir=temp_storage)
        assert p2.get_policy("episodic_records") == 15

    def test_set_new_category(self, policy):
        policy.set_policy("custom_category", 60)
        assert policy.get_policy("custom_category") == 60

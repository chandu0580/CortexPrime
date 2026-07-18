from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from backend.auth.credential_store import CredentialStore


@pytest.fixture
def temp_storage():
    with tempfile.TemporaryDirectory() as tmp:
        yield str(tmp)


@pytest.fixture
def store(temp_storage):
    return CredentialStore(storage_dir=temp_storage)


class TestCredentialStore:
    def test_store_and_get(self, store):
        cid = store.store("my-creds", {"api_key": "secret123"})
        assert cid == "my-creds"
        retrieved = store.get("my-creds")
        assert retrieved == {"api_key": "secret123"}

    def test_get_nonexistent(self, store):
        assert store.get("no-such-id") is None

    def test_delete(self, store):
        store.store("del-me", {"key": "value"})
        result = store.delete("del-me")
        assert result is True
        assert store.get("del-me") is None

    def test_delete_nonexistent(self, store):
        result = store.delete("no-such-id")
        assert result is False

    def test_list_ids_empty(self, store):
        assert store.list_ids() == []

    def test_list_ids(self, store):
        store.store("a", {"k": "v1"})
        store.store("b", {"k": "v2"})
        ids = store.list_ids()
        assert sorted(ids) == ["a", "b"]

    def test_store_overwrite(self, store):
        store.store("key", {"original": "data"})
        store.store("key", {"updated": "data"})
        retrieved = store.get("key")
        assert retrieved == {"updated": "data"}

    def test_store_complex_data(self, store):
        data = {"nested": {"a": 1, "b": [1, 2, 3]}, "flag": True, "count": 42}
        store.store("complex", data)
        assert store.get("complex") == data

    def test_data_is_actually_encrypted(self, temp_storage, store):
        store.store("top-secret", {"password": "hunter2"})
        enc_path = Path(temp_storage) / "top-secret.enc"
        assert enc_path.exists()
        raw = enc_path.read_bytes()
        assert b"hunter2" not in raw
        assert b"password" not in raw
        assert raw != json.dumps({"password": "hunter2"}).encode()

    def test_multiple_stores_independent(self, store):
        store.store("c1", {"val": 1})
        store.store("c2", {"val": 2})
        assert store.get("c1") == {"val": 1}
        assert store.get("c2") == {"val": 2}

    def test_delete_removes_file(self, temp_storage, store):
        store.store("file-test", {"x": "y"})
        enc_path = Path(temp_storage) / "file-test.enc"
        assert enc_path.exists()
        store.delete("file-test")
        assert not enc_path.exists()

    def test_store_empty_dict(self, store):
        cid = store.store("empty", {})
        assert store.get(cid) == {}

    def test_reload_persists_data(self, temp_storage):
        s1 = CredentialStore(storage_dir=temp_storage)
        s1.store("persist-test", {"keep": "me"})

        s2 = CredentialStore(storage_dir=temp_storage)
        assert s2.get("persist-test") == {"keep": "me"}

"""
Tests for GitLabCIConnector.get_commit_with_diff — normalizes GitLab's
commit + diff API responses into the same shape
enterprise_deploy_root_cause_reasoner._build_diff_summary already expects
from GitHub, so that function stays provider-agnostic.
"""
from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from backend.connectors.gitlab_ci import GitLabCIConnector

pytestmark = pytest.mark.asyncio


def _connector() -> GitLabCIConnector:
    conn = GitLabCIConnector()
    conn.get_commit = AsyncMock(return_value={"id": "abc123", "message": "fix: batch the query"})
    conn.get_commit_diff = AsyncMock(return_value=[
        {"old_path": "app/queries.py", "new_path": "app/queries.py", "diff": "-select_one()\n+select_all()", "new_file": False, "deleted_file": False, "renamed_file": False},
        {"old_path": "", "new_path": "app/new_module.py", "diff": "+def new(): ...", "new_file": True, "deleted_file": False, "renamed_file": False},
        {"old_path": "app/old.py", "new_path": "", "diff": "-def old(): ...", "new_file": False, "deleted_file": True, "renamed_file": False},
        {"old_path": "app/a.py", "new_path": "app/b.py", "diff": "", "new_file": False, "deleted_file": False, "renamed_file": True},
    ])
    return conn


class TestGetCommitWithDiff:
    async def test_normalizes_message_into_github_shape(self):
        result = await _connector().get_commit_with_diff("group%2Fproj", "abc123")
        assert result["commit"]["message"] == "fix: batch the query"

    async def test_normalizes_modified_file(self):
        result = await _connector().get_commit_with_diff("group%2Fproj", "abc123")
        modified = next(f for f in result["files"] if f["filename"] == "app/queries.py")
        assert modified["status"] == "modified"
        assert modified["patch"] == "-select_one()\n+select_all()"

    async def test_normalizes_added_file(self):
        result = await _connector().get_commit_with_diff("group%2Fproj", "abc123")
        added = next(f for f in result["files"] if f["filename"] == "app/new_module.py")
        assert added["status"] == "added"

    async def test_normalizes_deleted_file_uses_old_path_as_filename(self):
        result = await _connector().get_commit_with_diff("group%2Fproj", "abc123")
        deleted = next(f for f in result["files"] if f["filename"] == "app/old.py")
        assert deleted["status"] == "removed"

    async def test_normalizes_renamed_file(self):
        result = await _connector().get_commit_with_diff("group%2Fproj", "abc123")
        renamed = next(f for f in result["files"] if f["filename"] == "app/b.py")
        assert renamed["status"] == "renamed"

    async def test_passes_project_id_and_sha_through_to_both_calls(self):
        conn = _connector()
        await conn.get_commit_with_diff("group%2Fproj", "abc123")
        conn.get_commit.assert_awaited_once_with("group%2Fproj", "abc123")
        conn.get_commit_diff.assert_awaited_once_with("group%2Fproj", "abc123")

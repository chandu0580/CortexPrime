"""
Tests for the GitHub connector methods added to support vulnerability
monitoring: list_dependabot_alerts (the detector's real signal source) and
get_file_contents/update_file_contents (the "actually fix it" primitive —
composes with the existing create_branch/create_pull_request to open a
real dependency-bump PR).
"""
from __future__ import annotations

import base64
from unittest.mock import AsyncMock

import pytest

from backend.connectors.github import GitHubConnector

pytestmark = pytest.mark.asyncio


class TestListDependabotAlerts:
    async def test_returns_alerts_list(self):
        conn = GitHubConnector()
        conn._request_list = AsyncMock(return_value=[
            {"number": 1, "state": "open", "dependency": {"package": {"name": "lodash"}}},
        ])
        result = await conn.list_dependabot_alerts("o", "r")
        assert len(result) == 1
        assert result[0]["number"] == 1

    async def test_passes_state_filter(self):
        conn = GitHubConnector()
        conn._request_list = AsyncMock(return_value=[])
        await conn.list_dependabot_alerts("o", "r", state="fixed")
        params = conn._request_list.call_args.args[-1]
        assert params["state"] == "fixed"

    async def test_does_not_use_page_based_pagination(self):
        # Dependabot alerts rejects ?page=N with a 400 — only
        # _request_list (single page) should be used, never
        # _request_list_paginated.
        conn = GitHubConnector()
        conn._request_list = AsyncMock(return_value=[])
        conn._request_list_paginated = AsyncMock(side_effect=AssertionError("must not paginate with page="))
        await conn.list_dependabot_alerts("o", "r")
        conn._request_list_paginated.assert_not_called()


class TestGetFileContents:
    async def test_returns_raw_response(self):
        conn = GitHubConnector()
        conn._request = AsyncMock(return_value={"content": "Zm9v", "sha": "abc123", "path": "requirements.txt"})
        result = await conn.get_file_contents("o", "r", "requirements.txt")
        assert result["sha"] == "abc123"

    async def test_passes_ref_when_given(self):
        conn = GitHubConnector()
        conn._request = AsyncMock(return_value={})
        await conn.get_file_contents("o", "r", "requirements.txt", ref="fix-branch")
        _, kwargs = conn._request.call_args
        assert kwargs["params"] == {"ref": "fix-branch"}


class TestUpdateFileContents:
    async def test_base64_encodes_content(self):
        conn = GitHubConnector()
        conn._request = AsyncMock(return_value={"commit": {"sha": "def456"}})
        await conn.update_file_contents(
            "o", "r", "requirements.txt", "bump lodash", "lodash==4.17.21\n", "abc123", "fix-branch",
        )
        _, kwargs = conn._request.call_args
        body = kwargs["json"]
        assert base64.b64decode(body["content"]).decode() == "lodash==4.17.21\n"
        assert body["sha"] == "abc123"
        assert body["branch"] == "fix-branch"
        assert body["message"] == "bump lodash"

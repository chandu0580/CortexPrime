"""Tests for JiraConnector.add_comment — added to support incident
correlation commenting on an already-open ticket instead of filing a
duplicate one (enterprise_alert_incident_reporter.comment_correlated_signal)."""
from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from backend.connectors.jira import JiraConnector

pytestmark = pytest.mark.asyncio


class TestAddComment:
    async def test_posts_to_comment_endpoint_with_adf_body(self):
        conn = JiraConnector()
        conn._request = AsyncMock(return_value={"id": "1001"})

        await conn.add_comment("OPS-1", "This is a correlated alert.")

        conn._request.assert_awaited_once()
        args, kwargs = conn._request.call_args
        assert args[0] == "POST"
        assert args[1] == "/rest/api/3/issue/OPS-1/comment"
        body = kwargs["json"]["body"]
        assert body["type"] == "doc"
        assert body["content"][0]["content"][0]["text"] == "This is a correlated alert."

    async def test_returns_the_created_comment(self):
        conn = JiraConnector()
        conn._request = AsyncMock(return_value={"id": "1001", "body": {}})

        result = await conn.add_comment("OPS-1", "text")
        assert result == {"id": "1001", "body": {}}

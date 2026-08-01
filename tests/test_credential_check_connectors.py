"""
Tests for check_credential() on the GitHub, GitLab, and Jira connectors —
the per-provider primitive used by enterprise_credential_monitor. GitLab
is the only one of the three with a real expiry-introspection endpoint;
GitHub's expiry is an advisory response header; Jira has no expiry
capability at all, only failure detection.
"""
from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from backend.connectors.github import GitHubConnector
from backend.connectors.gitlab_ci import GitLabCIConnector
from backend.connectors.jira import JiraConnector

pytestmark = pytest.mark.asyncio


class TestGitHubCheckCredential:
    async def test_valid_token_reports_valid(self):
        conn = GitHubConnector()
        conn.get_rate_limit = AsyncMock(return_value={"resources": {}})
        result = await conn.check_credential()
        assert result["valid"] is True
        assert result["error"] is None

    async def test_captures_advisory_expiry_header_if_previously_seen(self):
        conn = GitHubConnector()
        conn._token_expires_at = "2026-09-01 00:00:00 UTC"
        conn.get_rate_limit = AsyncMock(return_value={"resources": {}})
        result = await conn.check_credential()
        assert result["expires_at"] == "2026-09-01 00:00:00 UTC"
        assert result["expires_at_source"] == "advisory_header"

    async def test_permission_error_reports_invalid(self):
        conn = GitHubConnector()
        conn.get_rate_limit = AsyncMock(side_effect=PermissionError("GitHub API: 401 Unauthorized — check GITHUB_TOKEN"))
        result = await conn.check_credential()
        assert result["valid"] is False
        assert "401" in result["error"]


class TestGitLabCheckCredential:
    async def test_valid_token_reports_real_expiry(self):
        conn = GitLabCIConnector()
        conn._request = AsyncMock(return_value={"id": 1, "expires_at": "2026-12-01"})
        result = await conn.check_credential()
        assert result["valid"] is True
        assert result["expires_at"] == "2026-12-01"
        assert result["expires_at_source"] == "api"

    async def test_non_expiring_token_reports_none(self):
        conn = GitLabCIConnector()
        conn._request = AsyncMock(return_value={"id": 1, "expires_at": None})
        result = await conn.check_credential()
        assert result["valid"] is True
        assert result["expires_at"] is None

    async def test_permission_error_reports_invalid(self):
        conn = GitLabCIConnector()
        conn._request = AsyncMock(side_effect=PermissionError("GitLab CI: 401 Unauthorized"))
        result = await conn.check_credential()
        assert result["valid"] is False
        assert "401" in result["error"]


class TestJiraCheckCredential:
    async def test_valid_token_reports_valid_with_no_expiry(self):
        conn = JiraConnector()
        conn._request = AsyncMock(return_value={"displayName": "test"})
        result = await conn.check_credential()
        assert result["valid"] is True
        assert result["expires_at"] is None
        assert result["expires_at_source"] is None

    async def test_permission_error_reports_invalid(self):
        conn = JiraConnector()
        conn._request = AsyncMock(side_effect=PermissionError("Jira API: 401 Unauthorized — check JIRA_EMAIL / JIRA_API_TOKEN"))
        result = await conn.check_credential()
        assert result["valid"] is False
        assert "401" in result["error"]

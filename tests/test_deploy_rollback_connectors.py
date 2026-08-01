"""
Tests for get_last_successful_deployment on the GitHub and GitLab
connectors — the "find the rollback target" primitive used by
enterprise_deploy_rollback_executor.
"""
from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from backend.connectors.github import GitHubConnector
from backend.connectors.gitlab_ci import GitLabCIConnector

pytestmark = pytest.mark.asyncio


class TestGitHubGetLastSuccessfulDeployment:
    async def test_returns_most_recent_successful_deployment(self):
        conn = GitHubConnector()
        conn.list_deployments = AsyncMock(return_value=[
            {"id": 3, "sha": "sha3", "created_at": "2026-08-01T10:00:00Z"},
            {"id": 2, "sha": "sha2", "created_at": "2026-08-01T09:00:00Z"},
            {"id": 1, "sha": "sha1", "created_at": "2026-08-01T08:00:00Z"},
        ])

        async def statuses(owner, repo, deployment_id):
            return [{"state": "success"}] if deployment_id in (2, 1) else [{"state": "failure"}]

        conn.list_deployment_statuses = AsyncMock(side_effect=statuses)

        result = await conn.get_last_successful_deployment("o", "r", "production", before_deployment_id=3)
        assert result["id"] == 2

    async def test_excludes_the_bad_deployment_itself(self):
        conn = GitHubConnector()
        conn.list_deployments = AsyncMock(return_value=[
            {"id": 5, "sha": "sha5", "created_at": "2026-08-01T10:00:00Z"},
        ])
        conn.list_deployment_statuses = AsyncMock(return_value=[{"state": "success"}])

        result = await conn.get_last_successful_deployment("o", "r", "production", before_deployment_id=5)
        assert result is None
        conn.list_deployment_statuses.assert_not_called()

    async def test_returns_none_when_no_successful_deployment_exists(self):
        conn = GitHubConnector()
        conn.list_deployments = AsyncMock(return_value=[
            {"id": 1, "sha": "sha1", "created_at": "2026-08-01T08:00:00Z"},
        ])
        conn.list_deployment_statuses = AsyncMock(return_value=[{"state": "failure"}])

        result = await conn.get_last_successful_deployment("o", "r", "production")
        assert result is None

    async def test_sorts_by_created_at_descending_regardless_of_api_order(self):
        conn = GitHubConnector()
        conn.list_deployments = AsyncMock(return_value=[
            {"id": 1, "sha": "sha1", "created_at": "2026-08-01T08:00:00Z"},
            {"id": 2, "sha": "sha2", "created_at": "2026-08-01T09:00:00Z"},
        ])
        conn.list_deployment_statuses = AsyncMock(return_value=[{"state": "success"}])

        result = await conn.get_last_successful_deployment("o", "r", "production")
        assert result["id"] == 2


class TestGitLabGetLastSuccessfulDeployment:
    async def test_returns_most_recent_successful_deployment(self):
        conn = GitLabCIConnector()
        conn.list_deployments = AsyncMock(return_value=[
            {"id": 20, "sha": "shaB"},
            {"id": 10, "sha": "shaA"},
        ])

        result = await conn.get_last_successful_deployment(123, "production", before_deployment_id=20)
        assert result["id"] == 10
        conn.list_deployments.assert_awaited_once_with(123, environment="production", status="success")

    async def test_excludes_the_bad_deployment_itself(self):
        conn = GitLabCIConnector()
        conn.list_deployments = AsyncMock(return_value=[
            {"id": 20, "sha": "shaB"},
        ])

        result = await conn.get_last_successful_deployment(123, "production", before_deployment_id=20)
        assert result is None

    async def test_returns_none_when_no_deployments(self):
        conn = GitLabCIConnector()
        conn.list_deployments = AsyncMock(return_value=[])

        result = await conn.get_last_successful_deployment(123, "production")
        assert result is None

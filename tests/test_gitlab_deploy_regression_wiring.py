"""
Tests for the deploy-regression-detection hook wired into the GitLab
webhook flow (backend.services.enterprise_gitlab_integration).

Verifies the translation from a GitLab "Deployment Hook" payload into the
same ctx shape the GitHub path produces, and that it correctly reuses
backend.services.enterprise_github_integration._check_deploy_regression
rather than a separate detection path.
"""
from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from backend.services.enterprise_gitlab_integration import _process_deployment_event

pytestmark = pytest.mark.asyncio


def _payload(status: str, **overrides) -> dict:
    base = {
        "object_kind": "deployment",
        "status": status,
        "deployment_id": 42,
        "environment": "production",
        "commit_title": "Fix N+1 query in checkout",
        "deployable_url": "https://gitlab.com/group/proj/-/jobs/999",
        "project": {
            "path_with_namespace": "group/checkout-service",
            "web_url": "https://gitlab.com/group/checkout-service",
        },
        "user": {"username": "chandu"},
    }
    base.update(overrides)
    return base


class TestProcessDeploymentEvent:
    async def test_success_triggers_shared_regression_check(self):
        with patch(
            "backend.services.enterprise_gitlab_integration._check_deploy_regression",
            new=AsyncMock(return_value=None),
        ) as mock_check:
            await _process_deployment_event(_payload("success"))

        mock_check.assert_awaited_once()
        ctx = mock_check.call_args.args[0]
        assert ctx["repo_full_name"] == "group/checkout-service"
        assert ctx["deployment_id"] == 42
        assert ctx["environment"] == "production"
        assert ctx["source"] == "gitlab_webhook"

    async def test_running_state_does_not_trigger_check(self):
        with patch(
            "backend.services.enterprise_gitlab_integration._check_deploy_regression",
            new=AsyncMock(return_value=None),
        ) as mock_check:
            await _process_deployment_event(_payload("running"))
        mock_check.assert_not_awaited()

    async def test_failed_state_does_not_trigger_check(self):
        with patch(
            "backend.services.enterprise_gitlab_integration._check_deploy_regression",
            new=AsyncMock(return_value=None),
        ) as mock_check:
            await _process_deployment_event(_payload("failed"))
        mock_check.assert_not_awaited()

    async def test_missing_project_path_is_ignored(self):
        payload = _payload("success")
        payload["project"] = {}
        with patch(
            "backend.services.enterprise_gitlab_integration._check_deploy_regression",
            new=AsyncMock(return_value=None),
        ) as mock_check:
            await _process_deployment_event(payload)
        mock_check.assert_not_awaited()

    async def test_missing_deployment_id_is_ignored(self):
        payload = _payload("success")
        del payload["deployment_id"]
        with patch(
            "backend.services.enterprise_gitlab_integration._check_deploy_regression",
            new=AsyncMock(return_value=None),
        ) as mock_check:
            await _process_deployment_event(payload)
        mock_check.assert_not_awaited()

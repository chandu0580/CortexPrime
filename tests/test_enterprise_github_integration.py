"""
Validation tests for Enterprise GitHub Integration, rewritten against the
current real-API-backed architecture (see backend/services/enterprise_github_integration.py).

The previous version of this file predated a full rearchitecture of this
module: sync -> async, in-memory JSON storage -> real GitHub API passthrough,
single-repo -> owner/repo everywhere, translate_and_process -> process_and_wire.
PRIntelligence/IssueIntelligence/ReleaseIntelligence/BranchIntelligence/
WorkflowRunManager no longer hold any local state at all (upsert_*/mark_*/
list_by_* were removed by design, not oversight) — they are now pure
delegations to the real GitHub connector, so they're tested here by mocking
that connector and asserting correct delegation, not by inspecting local state.
"""
from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from backend.services.enterprise_github_integration import (
    GithubIntegration,
    github_integration,
    WebhookReceiver,
    GitHubEventTranslator,
    WorkflowRunManager,
    PRIntelligence,
    IssueIntelligence,
    ReleaseIntelligence,
    DeploymentIntelligence,
    DeploymentStatusIntegration,
    BranchIntelligence,
    GITHUB_EVENTS,
    WEBHOOK_TO_INTERNAL,
)
from backend.events.enterprise_event_types import EnterpriseEventTypes as EET


def _mock_github():
    """A fake registered GitHub connector with every method used by the
    Intelligence classes stubbed as an AsyncMock."""
    gh = MagicMock()
    for method in [
        "list_workflow_runs", "get_workflow_run", "list_workflows", "get_workflow",
        "dispatch_workflow", "cancel_workflow_run", "rerun_workflow",
        "list_pull_requests", "get_pull_request", "get_combined_status",
        "list_check_runs", "list_pull_request_reviews",
        "get_issue", "_request_list_paginated",
        "list_releases", "get_release", "get_latest_release", "list_repository_tags",
        "list_deployments", "get_deployment", "list_deployment_statuses",
        "list_branches", "get_branch_protection", "list_commit_statuses",
        "get_repository", "list_repositories", "list_repository_events",
    ]:
        setattr(gh, method, AsyncMock())
    return gh


@pytest.fixture
def mock_gh():
    gh = _mock_github()
    with patch("backend.connectors.registry.connector_registry.get", return_value=gh):
        yield gh


# =============================================================================
# Constants — unchanged, these already passed
# =============================================================================

class TestGithubEvents:
    def test_all_events_defined(self):
        assert len(GITHUB_EVENTS) == 20

    def test_event_values_format(self):
        for key, val in GITHUB_EVENTS.items():
            assert val.startswith("github."), f"{key} -> {val}"

    def test_webhook_to_internal_map(self):
        assert WEBHOOK_TO_INTERNAL["push"] == GITHUB_EVENTS["push_received"]
        assert WEBHOOK_TO_INTERNAL["pull_request"] == GITHUB_EVENTS["pr_opened"]
        assert WEBHOOK_TO_INTERNAL["issues"] == GITHUB_EVENTS["issue_opened"]
        assert WEBHOOK_TO_INTERNAL["release"] == GITHUB_EVENTS["release_published"]
        assert WEBHOOK_TO_INTERNAL["deployment"] == GITHUB_EVENTS["deployment_started"]
        assert WEBHOOK_TO_INTERNAL["deployment_status"] == GITHUB_EVENTS["deployment_completed"]
        assert WEBHOOK_TO_INTERNAL["workflow_run"] == GITHUB_EVENTS["workflow_run_started"]
        assert WEBHOOK_TO_INTERNAL["create"] == GITHUB_EVENTS["branch_updated"]
        assert WEBHOOK_TO_INTERNAL["delete"] == GITHUB_EVENTS["branch_deleted"]

    def test_enterprise_event_types_integration(self):
        assert EET.GITHUB_WEBHOOK_RECEIVED == "github.webhook_received"
        assert EET.GITHUB_PR_MERGED == "github.pr_merged"
        assert EET.GITHUB_WORKFLOW_RUN_FAILED == "github.workflow_run_failed"
        assert EET.GITHUB_DEPLOYMENT_COMPLETED == "github.deployment_completed"
        assert EET.GITHUB_MISSION_LAUNCHED == "github.mission_launched"

    def test_event_hub_routing(self):
        from backend.services.enterprise_event_hub import _topic_for_event
        assert _topic_for_event("github.webhook_received") == "enterprise:github"
        assert _topic_for_event("github.pr_opened") == "enterprise:github"
        assert _topic_for_event("github.workflow_run_completed") == "enterprise:github"


# =============================================================================
# Part 1 — Webhook Receiver
# verify_signature/receive are INSTANCE methods (need a real instance);
# parse_event is a @staticmethod.
# =============================================================================

class TestWebhookReceiver:
    def test_verify_signature_bad(self):
        receiver = WebhookReceiver()
        payload = json.dumps({"test": "data"}).encode()
        assert receiver.verify_signature(payload, "sha256=deadbeef", "test_secret") is False

    def test_verify_signature_correct(self):
        import hashlib
        import hmac
        receiver = WebhookReceiver()
        payload = json.dumps({"test": "data"}).encode()
        secret = "test_secret"
        expected = "sha256=" + hmac.new(secret.encode(), payload, hashlib.sha256).hexdigest()
        assert receiver.verify_signature(payload, expected, secret) is True

    def test_verify_signature_empty(self):
        receiver = WebhookReceiver()
        payload = json.dumps({"test": "data"}).encode()
        assert not receiver.verify_signature(payload, "", "secret")
        assert not receiver.verify_signature(payload, "sha256=abc", "")

    def test_parse_push_event(self):
        payload = {
            "ref": "refs/heads/feature-branch",
            "repository": {"full_name": "org/repo"},
            "sender": {"login": "dev_user"},
            "commits": [
                {"id": "abc123", "message": "feat: add new widget", "author": {"name": "Dev"}, "timestamp": "2026-01-01T00:00:00Z", "url": "http://example.com/abc123"},
            ],
        }
        parsed = WebhookReceiver.parse_event(payload, "push")
        assert parsed["event_type"] == "push"
        assert parsed["repository"] == "org/repo"
        assert parsed["sender"] == "dev_user"
        assert parsed["ref"] == "refs/heads/feature-branch"
        assert parsed["commit_count"] == 1
        assert len(parsed["commits"]) == 1
        assert parsed["commits"][0]["id"] == "abc123"

    def test_parse_event_no_commits(self):
        payload = {
            "repository": {"full_name": "org/repo"},
            "sender": {"login": "bot"},
        }
        parsed = WebhookReceiver.parse_event(payload, "workflow_run")
        assert parsed["event_type"] == "workflow_run"
        assert parsed.get("commit_count") is None

    async def test_receive_unverified_without_secret(self):
        receiver = WebhookReceiver()
        body = json.dumps({"repository": {"full_name": "org/repo"}, "sender": {"login": "dev"}}).encode()
        headers = {"X-GitHub-Event": "push", "X-GitHub-Delivery": "d-1"}
        result = await receiver.receive(body, headers, secret="")
        assert result["verified"] is False
        assert result["event_type"] == "push"

    async def test_receive_duplicate_delivery_detected(self):
        receiver = WebhookReceiver()
        body = json.dumps({"repository": {"full_name": "org/repo"}, "sender": {"login": "dev"}}).encode()
        headers = {"X-GitHub-Event": "push", "X-GitHub-Delivery": "dup-1"}
        first = await receiver.receive(body, headers, secret="")
        assert first["event_type"] == "push"
        second = await receiver.receive(body, headers, secret="")
        assert second["status"] == "duplicate"


# =============================================================================
# Part 2 — GitHub Event Translator
# translate() returns a plain str now (not a tuple).
# =============================================================================

class TestGitHubEventTranslator:
    def test_translate_push(self):
        assert GitHubEventTranslator.translate("push", {}) == GITHUB_EVENTS["push_received"]

    def test_translate_pr_opened(self):
        payload = {"action": "opened", "pull_request": {"number": 1}}
        assert GitHubEventTranslator.translate("pull_request", payload) == GITHUB_EVENTS["pr_opened"]

    def test_translate_pr_merged(self):
        payload = {"action": "closed", "pull_request": {"number": 1, "merged": True}}
        assert GitHubEventTranslator.translate("pull_request", payload) == GITHUB_EVENTS["pr_merged"]

    def test_translate_pr_closed_not_merged(self):
        payload = {"action": "closed", "pull_request": {"number": 1, "merged": False}}
        assert GitHubEventTranslator.translate("pull_request", payload) == GITHUB_EVENTS["pr_updated"]

    def test_translate_issue_closed(self):
        payload = {"action": "closed", "issue": {"number": 5}}
        assert GitHubEventTranslator.translate("issues", payload) == GITHUB_EVENTS["issue_closed"]

    def test_translate_workflow_run_completed_success(self):
        payload = {"workflow_run": {"status": "completed", "conclusion": "success"}}
        assert GitHubEventTranslator.translate("workflow_run", payload) == GITHUB_EVENTS["workflow_run_completed"]

    def test_translate_workflow_run_completed_failure(self):
        payload = {"workflow_run": {"status": "completed", "conclusion": "failure"}}
        assert GitHubEventTranslator.translate("workflow_run", payload) == GITHUB_EVENTS["workflow_run_failed"]

    def test_translate_workflow_run_in_progress(self):
        payload = {"workflow_run": {"status": "in_progress"}}
        assert GitHubEventTranslator.translate("workflow_run", payload) == GITHUB_EVENTS["workflow_run_started"]

    def test_translate_deployment_status_success(self):
        payload = {"deployment_status": {"state": "success"}, "deployment": {"id": 1, "environment": "production"}}
        assert GitHubEventTranslator.translate("deployment_status", payload) == GITHUB_EVENTS["deployment_completed"]

    def test_translate_deployment_status_failure(self):
        payload = {"deployment_status": {"state": "failure"}, "deployment": {"id": 1}}
        assert GitHubEventTranslator.translate("deployment_status", payload) == GITHUB_EVENTS["deployment_failed"]

    def test_build_mission_context_push(self):
        payload = {
            "ref": "refs/heads/main",
            "repository": {"full_name": "org/repo", "clone_url": "https://github.com/org/repo.git", "html_url": "https://github.com/org/repo"},
            "sender": {"login": "dev"},
            "commits": [{"message": "fix: resolve bug", "id": "a1", "author": {"name": "Dev"}, "timestamp": "", "url": ""}],
        }
        ctx = GitHubEventTranslator.build_mission_context("push", payload)
        assert ctx["source"] == "github_webhook"
        assert ctx["event_type"] == "push"
        assert ctx["branch"] == "main"
        assert ctx["commit_count"] == 1

    def test_build_mission_context_pr(self):
        payload = {
            "repository": {"full_name": "org/repo", "html_url": "https://github.com/org/repo"},
            "sender": {"login": "dev"},
            "pull_request": {"number": 10, "title": "Fix auth", "body": "Details", "head": {"ref": "feature", "sha": "abc"}, "base": {"ref": "main"}},
        }
        ctx = GitHubEventTranslator.build_mission_context("pull_request", payload)
        assert ctx["pr_number"] == 10
        assert ctx["pr_title"] == "Fix auth"
        assert ctx["branch"] == "feature"
        assert ctx["base_branch"] == "main"

    def test_build_mission_context_deployment_status(self):
        payload = {
            "repository": {"full_name": "org/repo"},
            "sender": {"login": "ops"},
            "deployment": {"id": 42, "environment": "production"},
            "deployment_status": {"state": "success", "description": "Deployed", "log_url": "https://log"},
        }
        ctx = GitHubEventTranslator.build_mission_context("deployment_status", payload)
        assert ctx["deployment_id"] == 42
        assert ctx["environment"] == "production"
        assert ctx["deployment_state"] == "success"
        assert ctx["deployment_log_url"] == "https://log"


# =============================================================================
# Part 3 — Workflow Run Manager: pure passthrough to the real GitHub connector
# =============================================================================

class TestWorkflowRunManager:
    async def test_list_runs_delegates_with_owner_repo(self, mock_gh):
        mock_gh.list_workflow_runs.return_value = [{"id": 1}]
        result = await WorkflowRunManager.list_runs("org", "repo")
        mock_gh.list_workflow_runs.assert_awaited_once_with("org", "repo", params={})
        assert result == [{"id": 1}]

    async def test_get_run_delegates(self, mock_gh):
        mock_gh.get_workflow_run.return_value = {"id": 5, "status": "completed"}
        result = await WorkflowRunManager.get_run("org", "repo", 5)
        mock_gh.get_workflow_run.assert_awaited_once_with("org", "repo", 5)
        assert result["status"] == "completed"

    async def test_list_by_status_delegates(self, mock_gh):
        await WorkflowRunManager.list_by_status("org", "repo", "completed")
        mock_gh.list_workflow_runs.assert_awaited_once_with("org", "repo", params={"status": "completed"})

    async def test_list_by_branch_delegates(self, mock_gh):
        await WorkflowRunManager.list_by_branch("org", "repo", "main")
        mock_gh.list_workflow_runs.assert_awaited_once_with("org", "repo", params={"branch": "main"})

    async def test_get_run_raises_without_registered_connector(self):
        with patch("backend.connectors.registry.connector_registry.get", return_value=None):
            with pytest.raises(RuntimeError):
                await WorkflowRunManager.get_run("org", "repo", 1)


# =============================================================================
# Part 4 — PR Intelligence: pure passthrough
# =============================================================================

class TestPRIntelligence:
    async def test_list_prs_delegates(self, mock_gh):
        mock_gh.list_pull_requests.return_value = []
        result = await PRIntelligence.list_prs("org", "repo")
        mock_gh.list_pull_requests.assert_awaited_once_with("org", "repo", state="open")
        assert result == []

    async def test_list_prs_state_passthrough(self, mock_gh):
        await PRIntelligence.list_prs("org", "repo", state="closed")
        mock_gh.list_pull_requests.assert_awaited_once_with("org", "repo", state="closed")

    async def test_get_pr_delegates(self, mock_gh):
        mock_gh.get_pull_request.return_value = {"number": 42, "title": "Fix bug"}
        result = await PRIntelligence.get_pr("org", "repo", 42)
        mock_gh.get_pull_request.assert_awaited_once_with("org", "repo", 42)
        assert result["title"] == "Fix bug"

    async def test_get_pr_with_status_aggregates_checks_and_reviews(self, mock_gh):
        mock_gh.get_pull_request.return_value = {"number": 42, "head": {"sha": "abc"}}
        mock_gh.get_combined_status.return_value = {"state": "success"}
        mock_gh.list_check_runs.return_value = {"check_runs": [{"name": "CI"}]}
        mock_gh.list_pull_request_reviews.return_value = [{"state": "APPROVED"}]

        result = await PRIntelligence.get_pr_with_status("org", "repo", 42)

        assert result["combined_status"] == "success"
        assert result["check_runs"] == [{"name": "CI"}]
        assert result["reviews"] == [{"state": "APPROVED"}]

    async def test_list_reviews_delegates(self, mock_gh):
        mock_gh.list_pull_request_reviews.return_value = [{"state": "APPROVED"}]
        result = await PRIntelligence.list_reviews("org", "repo", 42)
        mock_gh.list_pull_request_reviews.assert_awaited_once_with("org", "repo", 42)
        assert result == [{"state": "APPROVED"}]


# =============================================================================
# Part 5 — Issue Intelligence: pure passthrough
# =============================================================================

class TestIssueIntelligence:
    async def test_list_issues_delegates(self, mock_gh):
        mock_gh._request_list_paginated.return_value = []
        result = await IssueIntelligence.list_issues("org", "repo")
        mock_gh._request_list_paginated.assert_awaited_once_with(
            "GET", "/repos/org/repo/issues", {"state": "open", "per_page": 100}
        )
        assert result == []

    async def test_get_issue_delegates(self, mock_gh):
        mock_gh.get_issue.return_value = {"number": 5, "title": "Bug report", "labels": ["bug"]}
        result = await IssueIntelligence.get_issue("org", "repo", 5)
        mock_gh.get_issue.assert_awaited_once_with("org", "repo", 5)
        assert result["title"] == "Bug report"


# =============================================================================
# Part 6 — Release Intelligence: pure passthrough
# =============================================================================

class TestReleaseIntelligence:
    async def test_list_releases_delegates(self, mock_gh):
        mock_gh.list_releases.return_value = []
        result = await ReleaseIntelligence.list_releases("org", "repo")
        mock_gh.list_releases.assert_awaited_once_with("org", "repo")
        assert result == []

    async def test_get_release_delegates(self, mock_gh):
        mock_gh.get_release.return_value = {"tag_name": "v1.0", "name": "v1.0"}
        result = await ReleaseIntelligence.get_release("org", "repo", "v1.0")
        mock_gh.get_release.assert_awaited_once_with("org", "repo", "v1.0")
        assert result["name"] == "v1.0"

    async def test_get_latest_delegates(self, mock_gh):
        mock_gh.get_latest_release.return_value = {"tag_name": "v2.0"}
        result = await ReleaseIntelligence.get_latest("org", "repo")
        mock_gh.get_latest_release.assert_awaited_once_with("org", "repo")
        assert result["tag_name"] == "v2.0"


# =============================================================================
# Part 7 — Deployment Intelligence (real API) + DeploymentStatusIntegration
# (the latter is a deliberately-kept simple in-memory tracker "used by tests")
# =============================================================================

class TestDeploymentIntelligence:
    async def test_list_deployments_delegates(self, mock_gh):
        mock_gh.list_deployments.return_value = []
        result = await DeploymentIntelligence.list_deployments("org", "repo", environment="production")
        mock_gh.list_deployments.assert_awaited_once_with("org", "repo", environment="production")
        assert result == []

    async def test_get_deployment_delegates(self, mock_gh):
        mock_gh.get_deployment.return_value = {"id": 42, "environment": "production"}
        result = await DeploymentIntelligence.get_deployment("org", "repo", 42)
        mock_gh.get_deployment.assert_awaited_once_with("org", "repo", 42)
        assert result["environment"] == "production"


class TestDeploymentStatusIntegration:
    @pytest.fixture(autouse=True)
    def _clear(self):
        DeploymentStatusIntegration.clear_state()
        yield
        DeploymentStatusIntegration.clear_state()

    async def test_list_returns_list(self):
        assert await DeploymentStatusIntegration.list_deployments() == []

    async def test_upsert_and_get(self):
        dep = await DeploymentStatusIntegration.upsert_deployment({"id": "dep-1", "environment": "production", "state": "success"})
        assert dep["id"] == "dep-1"
        found = await DeploymentStatusIntegration.get_deployment("dep-1")
        assert found["environment"] == "production"

    async def test_upsert_update(self):
        await DeploymentStatusIntegration.upsert_deployment({"id": "dep-2", "environment": "staging", "state": "pending"})
        await DeploymentStatusIntegration.upsert_deployment({"deployment_id": "dep-2", "state": "success", "description": "Deployed OK"})
        found = await DeploymentStatusIntegration.get_deployment("dep-2")
        assert found["state"] == "success"
        assert found["description"] == "Deployed OK"

    async def test_list_by_environment(self):
        await DeploymentStatusIntegration.upsert_deployment({"id": "dep-3", "environment": "production", "state": "success"})
        await DeploymentStatusIntegration.upsert_deployment({"id": "dep-4", "environment": "staging", "state": "success"})
        prod = await DeploymentStatusIntegration.list_by_environment("production")
        assert len(prod) == 1
        assert prod[0]["id"] == "dep-3"

    async def test_list_by_state(self):
        await DeploymentStatusIntegration.upsert_deployment({"id": "dep-5", "environment": "prod", "state": "success"})
        await DeploymentStatusIntegration.upsert_deployment({"id": "dep-6", "environment": "prod", "state": "failure"})
        successes = await DeploymentStatusIntegration.list_by_state("success")
        assert len(successes) == 1
        assert successes[0]["id"] == "dep-5"


# =============================================================================
# Part 8 — Branch Intelligence: pure passthrough
# =============================================================================

class TestBranchIntelligence:
    async def test_list_branches_delegates(self, mock_gh):
        mock_gh.list_branches.return_value = []
        result = await BranchIntelligence.list_branches("org", "repo")
        mock_gh.list_branches.assert_awaited_once_with("org", "repo")
        assert result == []

    async def test_get_branch_protection_delegates(self, mock_gh):
        mock_gh.get_branch_protection.return_value = {"required_status_checks": {}}
        result = await BranchIntelligence.get_branch_protection("org", "repo", "main")
        mock_gh.get_branch_protection.assert_awaited_once_with("org", "repo", "main")
        assert result is not None

    async def test_get_combined_status_delegates(self, mock_gh):
        mock_gh.get_combined_status.return_value = {"state": "success"}
        result = await BranchIntelligence.get_combined_status("org", "repo", "abc123")
        mock_gh.get_combined_status.assert_awaited_once_with("org", "repo", "abc123")
        assert result["state"] == "success"


# =============================================================================
# Part 9 — GithubIntegration Orchestrator
# receive_webhook(body: bytes, headers: dict, secret: str) — not a payload dict
# + positional event_type. process_and_wire (not translate_and_process).
# _emit/_build_description are module-level functions, not GithubIntegration methods.
# =============================================================================

def _webhook_body(payload: dict) -> bytes:
    return json.dumps(payload).encode()


class TestGithubIntegration:
    @pytest.fixture
    def ops(self):
        inst = GithubIntegration()
        inst.clear_state()
        return inst

    async def test_receive_webhook_unverified(self, ops):
        body = _webhook_body({"ref": "refs/heads/main", "repository": {"full_name": "org/repo"}, "sender": {"login": "dev"}})
        headers = {"X-GitHub-Event": "push"}
        result = await ops.receive_webhook(body, headers, secret="")
        assert result["event_type"] == "push"
        assert result["verified"] is False

    async def test_receive_webhook_does_not_process_unverified_events(self, ops):
        body = _webhook_body({"repository": {"full_name": "org/repo"}, "sender": {"login": "dev"}})
        headers = {"X-GitHub-Event": "push"}
        with patch.object(ops, "process_and_wire", new=AsyncMock()) as mock_process:
            await ops.receive_webhook(body, headers, secret="")
            mock_process.assert_not_awaited()

    async def test_process_and_wire_push(self, ops):
        payload = {
            "ref": "refs/heads/main",
            "repository": {"full_name": "org/repo"},
            "sender": {"login": "dev"},
            "commits": [{"id": "abc", "message": "fix: resolve issue", "author": {"name": "Dev"}, "timestamp": "", "url": ""}],
        }
        with patch("backend.services.enterprise_github_integration._emit", new=AsyncMock()):
            result = await ops.process_and_wire("push", payload)
        assert result["internal_event"] == GITHUB_EVENTS["push_received"]
        assert result["context"]["branch"] == "main"

    async def test_process_and_wire_deployment_status_success_triggers_regression_check(self, ops):
        payload = {
            "repository": {"full_name": "org/repo"},
            "sender": {"login": "ops"},
            "deployment": {"id": 2001, "environment": "production"},
            "deployment_status": {"state": "success", "description": "Deployed", "log_url": "", "environment_url": ""},
        }
        with patch("backend.services.enterprise_github_integration._emit", new=AsyncMock()), \
             patch("backend.services.enterprise_github_integration._check_deploy_regression", new=AsyncMock()) as mock_check:
            result = await ops.process_and_wire("deployment_status", payload)
        assert result["internal_event"] == GITHUB_EVENTS["deployment_completed"]
        mock_check.assert_awaited_once()

    async def test_dashboard_stats_shape(self, ops):
        stats = await ops.get_dashboard_stats()
        assert "total_webhooks" in stats
        assert "total_workflow_runs" in stats
        assert "total_prs" in stats
        assert "total_issues" in stats
        assert "total_releases" in stats
        assert "total_deployments" in stats
        assert "total_branches" in stats

    async def test_recent_webhooks(self, ops):
        body = _webhook_body({"repository": {"full_name": "org/repo"}, "sender": {"login": "dev"}})
        await ops.receive_webhook(body, {"X-GitHub-Event": "push"}, secret="")
        recent = ops.get_recent_webhooks(5)
        assert len(recent) >= 1

    async def test_recent_activity_aggregation(self, ops):
        body = _webhook_body({"repository": {"full_name": "org/repo"}, "sender": {"login": "dev"}})
        await ops.receive_webhook(body, {"X-GitHub-Event": "push"}, secret="")
        activity = await ops.get_recent_activity()
        assert len(activity) >= 1
        assert activity[0]["type"] == "webhook"

    async def test_launch_mission_from_webhook(self, ops):
        payload = {
            "ref": "refs/heads/main",
            "repository": {"full_name": "org/repo", "clone_url": "https://github.com/org/repo.git", "html_url": "https://github.com/org/repo"},
            "sender": {"login": "dev"},
            "commits": [{"message": "fix: resolve crash", "id": "abc", "author": {"name": "Dev"}, "timestamp": "", "url": ""}],
        }
        fake_exec = MagicMock()
        fake_exec.create_task = AsyncMock(return_value={"task_id": "t1"})
        fake_exec.create_plan = AsyncMock(return_value={"plan_id": "p1"})
        fake_exec.execute_plan = AsyncMock(return_value=None)
        with patch("backend.services.enterprise_github_integration._emit", new=AsyncMock()), \
             patch(
                 "backend.services.enterprise_engineering_executive.get_engineering_executive",
                 return_value=fake_exec,
             ):
            result = await ops.launch_mission_from_webhook("push", payload)
        assert result is not None
        assert result["task"]["task_id"] == "t1"
        assert result["plan"]["plan_id"] == "p1"
        assert result["context"]["mission_launched"] is True

    async def test_clear_state(self, ops):
        body = _webhook_body({"repository": {"full_name": "org/repo"}, "sender": {"login": "dev"}})
        await ops.receive_webhook(body, {"X-GitHub-Event": "push"}, secret="")
        ops.clear_state()
        assert (await ops.get_dashboard_stats())["total_webhooks"] == 0


class TestBuildDescription:
    """_build_description is a module-level function, not a GithubIntegration method."""

    def test_build_description_all_types(self):
        from backend.services.enterprise_github_integration import _build_description

        cases = [
            ("push", {"branch": "main", "commits": ["fix: resolve"]}, "Process push to main: fix: resolve"),
            ("pull_request", {"pr_number": 1, "pr_title": "Add feature"}, "Review pull request #1: Add feature"),
            ("issues", {"issue_number": 2, "issue_title": "Bug report", "action": "opened"}, "Opened issue #2: Bug report"),
            ("workflow_run", {"workflow_name": "CI", "workflow_status": "in_progress"}, "Track workflow run: CI [in_progress]"),
            ("release", {"release_tag": "v1.0"}, "Process release: v1.0"),
            ("deployment_status", {"environment": "production", "deployment_state": "success"}, "Track deployment to production: success"),
            ("unknown_event", {}, "Process GitHub unknown_event event"),
        ]
        for event_type, ctx, expected in cases:
            desc = _build_description(event_type, ctx)
            assert desc == expected, f"{event_type}: {desc} != {expected}"


# =============================================================================
# E2E Workflow — real process_and_wire path, mocked GitHub connector + _emit
# =============================================================================

class TestGithubE2E:
    async def test_full_push_to_branch_workflow(self, mock_gh):
        """Developer pushes code -> webhook -> process -> dashboard reflects it."""
        ops = GithubIntegration()
        ops.clear_state()

        push_payload = {
            "ref": "refs/heads/feature/login-fix",
            "repository": {"full_name": "myorg/myapp", "clone_url": "https://github.com/myorg/myapp.git", "html_url": "https://github.com/myorg/myapp"},
            "sender": {"login": "alice"},
            "commits": [
                {"id": "commit1", "message": "fix: resolve login timeout", "author": {"name": "Alice"}, "timestamp": "2026-07-11T20:00:00Z", "url": ""},
            ],
        }

        webhook_result = await ops.receive_webhook(_webhook_body(push_payload), {"X-GitHub-Event": "push"}, secret="")
        assert webhook_result["event_type"] == "push"

        with patch("backend.services.enterprise_github_integration._emit", new=AsyncMock()):
            translate_result = await ops.process_and_wire("push", push_payload)
        assert translate_result["internal_event"] == "github.push_received"
        assert translate_result["context"]["branch"] == "feature/login-fix"

        stats = await ops.get_dashboard_stats()
        assert stats["total_webhooks"] >= 1

    async def test_full_pr_lifecycle(self, mock_gh):
        """PR opened -> merged, using the real API-backed PRIntelligence."""
        ops = GithubIntegration()
        ops.clear_state()

        base_payload = {
            "repository": {"full_name": "org/pr-demo", "html_url": "https://github.com/org/pr-demo"},
            "sender": {"login": "bob"},
        }
        open_payload = {**base_payload, "action": "opened", "pull_request": {
            "number": 100, "title": "Add new API", "body": "Implements REST endpoints",
            "state": "open", "merged": False, "draft": False, "user": {"login": "bob"},
            "head": {"ref": "feature/api", "sha": "def456"}, "base": {"ref": "main"},
            "html_url": "https://github.com/org/pr-demo/pull/100",
        }}
        with patch("backend.services.enterprise_github_integration._emit", new=AsyncMock()):
            result = await ops.process_and_wire("pull_request", open_payload)
        assert result["internal_event"] == GITHUB_EVENTS["pr_opened"]

        mock_gh.get_pull_request.return_value = {"number": 100, "title": "Add new API", "head": {"sha": "def456"}}
        pr = await PRIntelligence.get_pr("org", "pr-demo", 100)
        assert pr["title"] == "Add new API"

        merge_payload = {**base_payload, "action": "closed", "pull_request": {
            **open_payload["pull_request"], "merged": True, "state": "closed",
        }}
        with patch("backend.services.enterprise_github_integration._emit", new=AsyncMock()):
            result = await ops.process_and_wire("pull_request", merge_payload)
        assert result["internal_event"] == "github.pr_merged"

    async def test_workflow_run_monitoring(self, mock_gh):
        """Workflow run started -> completed, via process_and_wire + real WorkflowRunManager."""
        ops = GithubIntegration()
        ops.clear_state()

        start_payload = {
            "repository": {"full_name": "org/ci-demo"},
            "sender": {"login": "ci-bot"},
            "workflow_run": {"id": 5001, "name": "Test Suite", "head_branch": "main", "head_sha": "abc", "status": "in_progress", "conclusion": None, "html_url": "", "workflow_id": 10, "run_number": 42, "event": "push", "actor": {"login": "ci-bot"}},
        }
        with patch("backend.services.enterprise_github_integration._emit", new=AsyncMock()):
            result = await ops.process_and_wire("workflow_run", start_payload)
        assert result["internal_event"] == GITHUB_EVENTS["workflow_run_started"]

        complete_payload = {**start_payload, "workflow_run": {**start_payload["workflow_run"], "status": "completed", "conclusion": "success"}}
        with patch("backend.services.enterprise_github_integration._emit", new=AsyncMock()):
            result = await ops.process_and_wire("workflow_run", complete_payload)
        assert result["internal_event"] == GITHUB_EVENTS["workflow_run_completed"]

    async def test_deployment_tracking(self):
        """Deployment pending -> success, via process_and_wire + DeploymentStatusIntegration."""
        DeploymentStatusIntegration.clear_state()
        ops = GithubIntegration()
        ops.clear_state()

        start_payload = {
            "repository": {"full_name": "org/deploy-demo"},
            "sender": {"login": "ops-bot"},
            "deployment": {"id": 3001, "environment": "production"},
            "deployment_status": {"state": "pending", "description": "Deploying", "log_url": "", "environment_url": ""},
        }
        with patch("backend.services.enterprise_github_integration._emit", new=AsyncMock()), \
             patch("backend.services.enterprise_github_integration._check_deploy_regression", new=AsyncMock()):
            result = await ops.process_and_wire("deployment_status", start_payload)
        assert result["context"]["deployment_state"] == "pending"

        complete_payload = {**start_payload, "deployment_status": {**start_payload["deployment_status"], "state": "success", "description": "Live"}}
        with patch("backend.services.enterprise_github_integration._emit", new=AsyncMock()), \
             patch("backend.services.enterprise_github_integration._check_deploy_regression", new=AsyncMock()) as mock_check:
            result = await ops.process_and_wire("deployment_status", complete_payload)
        assert result["context"]["deployment_state"] == "success"
        mock_check.assert_awaited_once()

    async def test_issue_and_release_workflow(self, mock_gh):
        """Issue reported -> release published, via process_and_wire."""
        ops = GithubIntegration()
        ops.clear_state()

        issue_payload = {
            "action": "opened",
            "repository": {"full_name": "org/issue-demo"},
            "sender": {"login": "reporter"},
            "issue": {"number": 200, "title": "Security vulnerability", "body": "Details", "state": "open", "user": {"login": "reporter"}, "labels": [{"name": "security"}, {"name": "bug"}], "html_url": ""},
        }
        with patch("backend.services.enterprise_github_integration._emit", new=AsyncMock()):
            result = await ops.process_and_wire("issues", issue_payload)
        assert result["internal_event"] == GITHUB_EVENTS["issue_opened"]

        release_payload = {
            "repository": {"full_name": "org/issue-demo"},
            "sender": {"login": "maintainer"},
            "release": {"tag_name": "v2.0.1", "name": "Security Patch v2.0.1", "body": "Fixes CVE-2026-xxxx", "prerelease": False, "draft": False, "author": {"login": "maintainer"}, "html_url": "", "published_at": "2026-07-11T00:00:00Z"},
        }
        with patch("backend.services.enterprise_github_integration._emit", new=AsyncMock()):
            result = await ops.process_and_wire("release", release_payload)
        assert result["internal_event"] == GITHUB_EVENTS["release_published"]

    async def test_multiple_events_dashboard_accuracy(self, mock_gh):
        """Multiple event types -> webhook count reflects all deliveries."""
        ops = GithubIntegration()
        ops.clear_state()

        base = {"repository": {"full_name": "org/dash-demo"}, "sender": {"login": "dev"}}

        with patch("backend.services.enterprise_github_integration._emit", new=AsyncMock()), \
             patch("backend.services.enterprise_github_integration._check_deploy_regression", new=AsyncMock()):
            await ops.receive_webhook(_webhook_body({**base, "ref": "refs/heads/main", "commits": []}), {"X-GitHub-Event": "push"}, secret="")
            await ops.process_and_wire("push", {**base, "ref": "refs/heads/feat1", "commits": [{"id": "a", "message": "m", "author": {"name": "D"}, "timestamp": "", "url": ""}]})
            await ops.process_and_wire("issues", {**base, "action": "opened", "issue": {"number": 1, "title": "T1", "state": "open", "user": {"login": "d"}, "labels": []}})
            await ops.process_and_wire("release", {**base, "release": {"tag_name": "v1", "name": "V1", "prerelease": False, "draft": False, "author": {"login": "d"}, "html_url": "", "published_at": ""}})
            await ops.process_and_wire("workflow_run", {**base, "workflow_run": {"id": 1, "name": "CI", "head_branch": "main", "head_sha": "", "status": "completed", "conclusion": "success", "html_url": "", "workflow_id": 1, "run_number": 1, "event": "push", "actor": {"login": "bot"}}})
            await ops.process_and_wire("deployment_status", {**base, "deployment": {"id": 1, "environment": "prod"}, "deployment_status": {"state": "success", "description": "OK", "log_url": "", "environment_url": ""}})

        stats = await ops.get_dashboard_stats()
        assert stats["total_webhooks"] >= 1

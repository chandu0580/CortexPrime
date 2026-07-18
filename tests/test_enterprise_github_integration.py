"""
Comprehensive validation tests for Enterprise GitHub Integration.
Verifies all 8 subsystems plus orchestrator, events, routing, and E2E workflows.
"""
from __future__ import annotations

import json
import pytest
from unittest.mock import AsyncMock, patch

from backend.services.enterprise_github_integration import (
    GithubIntegration,
    github_integration,
    WebhookReceiver,
    GitHubEventTranslator,
    WorkflowRunManager,
    PRIntelligence,
    IssueIntelligence,
    ReleaseIntelligence,
    DeploymentStatusIntegration,
    BranchIntelligence,
    GITHUB_EVENTS,
    WEBHOOK_TO_INTERNAL,
)
from backend.events.enterprise_event_types import EnterpriseEventTypes as EET


# =============================================================================
# Constants
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
# =============================================================================

class TestWebhookReceiver:
    def test_verify_signature(self):
        payload = json.dumps({"test": "data"}).encode()
        sig = WebhookReceiver.verify_signature(payload, "sha256=6c4b7b8f...", "test_secret")
        assert sig is False  # bad signature

    def test_verify_signature_empty(self):
        payload = json.dumps({"test": "data"}).encode()
        assert not WebhookReceiver.verify_signature(payload, "", "secret")
        assert not WebhookReceiver.verify_signature(payload, "sha256=abc", "")

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


# =============================================================================
# Part 2 — GitHub Event Translator
# =============================================================================

class TestGitHubEventTranslator:
    def test_translate_push(self):
        internal, _ = GitHubEventTranslator.translate("push", {})
        assert internal == GITHUB_EVENTS["push_received"]

    def test_translate_pr_opened(self):
        payload = {"action": "opened", "pull_request": {"number": 1}}
        internal, _ = GitHubEventTranslator.translate("pull_request", payload)
        assert internal == GITHUB_EVENTS["pr_opened"]

    def test_translate_pr_merged(self):
        payload = {"action": "closed", "pull_request": {"number": 1, "merged": True}}
        internal, _ = GitHubEventTranslator.translate("pull_request", payload)
        assert internal == GITHUB_EVENTS["pr_merged"]

    def test_translate_pr_closed_not_merged(self):
        payload = {"action": "closed", "pull_request": {"number": 1, "merged": False}}
        internal, _ = GitHubEventTranslator.translate("pull_request", payload)
        assert internal == GITHUB_EVENTS["pr_updated"]

    def test_translate_issue_closed(self):
        payload = {"action": "closed", "issue": {"number": 5}}
        internal, _ = GitHubEventTranslator.translate("issues", payload)
        assert internal == GITHUB_EVENTS["issue_closed"]

    def test_translate_workflow_run_completed_success(self):
        payload = {"workflow_run": {"status": "completed", "conclusion": "success"}}
        internal, _ = GitHubEventTranslator.translate("workflow_run", payload)
        assert internal == GITHUB_EVENTS["workflow_run_completed"]

    def test_translate_workflow_run_completed_failure(self):
        payload = {"workflow_run": {"status": "completed", "conclusion": "failure"}}
        internal, _ = GitHubEventTranslator.translate("workflow_run", payload)
        assert internal == GITHUB_EVENTS["workflow_run_failed"]

    def test_translate_workflow_run_in_progress(self):
        payload = {"workflow_run": {"status": "in_progress"}}
        internal, _ = GitHubEventTranslator.translate("workflow_run", payload)
        assert internal == GITHUB_EVENTS["workflow_run_started"]

    def test_translate_deployment_status_success(self):
        payload = {"deployment_status": {"state": "success"}, "deployment": {"id": 1, "environment": "production"}}
        internal, _ = GitHubEventTranslator.translate("deployment_status", payload)
        assert internal == GITHUB_EVENTS["deployment_completed"]

    def test_translate_deployment_status_failure(self):
        payload = {"deployment_status": {"state": "failure"}, "deployment": {"id": 1}}
        internal, _ = GitHubEventTranslator.translate("deployment_status", payload)
        assert internal == GITHUB_EVENTS["deployment_failed"]

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


# =============================================================================
# Part 3 — Workflow Run Manager
# =============================================================================

class TestWorkflowRunManager:

    def test_list_runs_returns_list(self):
        assert isinstance(WorkflowRunManager.list_runs(), list)

    def test_upsert_and_get(self):
        run = WorkflowRunManager.upsert_run({"name": "CI", "status": "in_progress", "head_branch": "main"})
        assert run["run_id"] is not None
        assert run["name"] == "CI"
        assert WorkflowRunManager.get_run(run["run_id"]) is not None

    def test_upsert_update(self):
        run = WorkflowRunManager.upsert_run({"name": "Test", "status": "in_progress", "head_branch": "dev"})
        rid = run["run_id"]
        WorkflowRunManager.upsert_run({"run_id": rid, "conclusion": "success", "status": "completed"})
        updated = WorkflowRunManager.get_run(rid)
        assert updated["conclusion"] == "success"
        assert updated["status"] == "completed"

    def test_list_by_status(self):
        WorkflowRunManager.upsert_run({"name": "A", "status": "completed", "conclusion": "success", "head_branch": "main"})
        WorkflowRunManager.upsert_run({"name": "B", "status": "in_progress", "head_branch": "feature"})
        completed = WorkflowRunManager.list_by_status("completed")
        assert len(completed) >= 1
        in_progress = WorkflowRunManager.list_by_status("in_progress")
        assert len(in_progress) >= 1

    def test_list_by_branch(self):
        WorkflowRunManager.upsert_run({"name": "C", "status": "completed", "head_branch": "staging"})
        staging = WorkflowRunManager.list_by_branch("staging")
        assert len(staging) >= 1

    def test_get_nonexistent(self):
        assert WorkflowRunManager.get_run("nonexistent") is None


# =============================================================================
# Part 4 — PR Intelligence
# =============================================================================

class TestPRIntelligence:

    def test_list_prs_empty(self):
        assert PRIntelligence.list_prs() == []

    def test_upsert_and_get(self):
        pr = PRIntelligence.upsert_pr({"number": 1, "repo": "org/repo", "title": "Fix bug", "state": "open"})
        assert pr["number"] == 1
        found = PRIntelligence.get_pr(1)
        assert found["title"] == "Fix bug"

    def test_upsert_update(self):
        PRIntelligence.upsert_pr({"number": 2, "repo": "org/repo", "title": "Old title", "state": "open"})
        PRIntelligence.upsert_pr({"number": 2, "repo": "org/repo", "title": "Updated title", "state": "open"})
        found = PRIntelligence.get_pr(2)
        assert found["title"] == "Updated title"

    def test_list_by_state(self):
        PRIntelligence.upsert_pr({"number": 3, "repo": "org/repo", "title": "Open PR", "state": "open"})
        PRIntelligence.upsert_pr({"number": 4, "repo": "org/repo", "title": "Closed PR", "state": "closed"})
        open_prs = PRIntelligence.list_by_state("open")
        assert any(p["number"] == 3 for p in open_prs)
        closed_prs = PRIntelligence.list_by_state("closed")
        assert any(p["number"] == 4 for p in closed_prs)

    def test_list_by_repo(self):
        PRIntelligence.upsert_pr({"number": 5, "repo": "org/a", "title": "PR in A", "state": "open"})
        PRIntelligence.upsert_pr({"number": 6, "repo": "org/b", "title": "PR in B", "state": "open"})
        repo_a = PRIntelligence.list_by_repo("org/a")
        assert len(repo_a) >= 1
        assert repo_a[0]["repo"] == "org/a"

    def test_mark_checks(self):
        PRIntelligence.upsert_pr({"number": 7, "repo": "org/repo", "title": "With checks", "state": "open"})
        result = PRIntelligence.mark_checks(7, True, [{"name": "CI", "status": "completed", "conclusion": "success"}])
        assert result is not None
        assert result["checks_passed"] is True
        found = PRIntelligence.get_pr(7)
        assert found["checks_passed"] is True
        assert len(found["check_details"]) == 1

    def test_mark_checks_nonexistent(self):
        result = PRIntelligence.mark_checks(9999, False, [])
        assert result is None

    def test_get_pr_with_repo_filter(self):
        PRIntelligence.upsert_pr({"number": 8, "repo": "org/repo", "title": "Filtered", "state": "open"})
        assert PRIntelligence.get_pr(8, "org/repo") is not None
        assert PRIntelligence.get_pr(8, "other/repo") is None


# =============================================================================
# Part 5 — Issue Intelligence
# =============================================================================

class TestIssueIntelligence:

    def test_list_returns_list(self):
        assert isinstance(IssueIntelligence.list_issues(), list)

    def test_upsert_and_get(self):
        iss = IssueIntelligence.upsert_issue({"number": 1, "repo": "org/repo", "title": "Bug report", "state": "open"})
        assert iss["number"] == 1
        found = IssueIntelligence.get_issue(1)
        assert found["title"] == "Bug report"

    def test_upsert_update(self):
        IssueIntelligence.upsert_issue({"number": 2, "repo": "org/repo", "title": "Old", "state": "open"})
        IssueIntelligence.upsert_issue({"number": 2, "repo": "org/repo", "title": "Updated", "state": "open"})
        assert IssueIntelligence.get_issue(2)["title"] == "Updated"

    def test_list_by_state(self):
        IssueIntelligence.upsert_issue({"number": 3, "repo": "org/repo", "title": "Open", "state": "open"})
        IssueIntelligence.upsert_issue({"number": 4, "repo": "org/repo", "title": "Closed", "state": "closed"})
        open_issues = IssueIntelligence.list_by_state("open")
        assert any(i["number"] == 3 for i in open_issues)
        closed_issues = IssueIntelligence.list_by_state("closed")
        assert any(i["number"] == 4 for i in closed_issues)

    def test_labels_stored(self):
        IssueIntelligence.upsert_issue({"number": 5, "repo": "org/repo", "title": "Labeled", "state": "open", "labels": ["bug", "urgent"]})
        found = IssueIntelligence.get_issue(5)
        assert "bug" in found["labels"]
        assert "urgent" in found["labels"]


# =============================================================================
# Part 6 — Release Intelligence
# =============================================================================

class TestReleaseIntelligence:

    def test_list_returns_list(self):
        assert isinstance(ReleaseIntelligence.list_releases(), list)

    def test_upsert_and_get(self):
        rel = ReleaseIntelligence.upsert_release({"tag_name": "v1.0", "repo": "org/repo", "name": "v1.0", "prerelease": False})
        assert rel["tag_name"] == "v1.0"
        found = ReleaseIntelligence.get_release("v1.0")
        assert found["name"] == "v1.0"

    def test_upsert_update(self):
        ReleaseIntelligence.upsert_release({"tag_name": "v2.0", "repo": "org/repo", "name": "v2.0-beta", "prerelease": True})
        ReleaseIntelligence.upsert_release({"tag_name": "v2.0", "repo": "org/repo", "name": "v2.0-stable", "prerelease": False})
        found = ReleaseIntelligence.get_release("v2.0")
        assert found["name"] == "v2.0-stable"
        assert found["prerelease"] is False

    def test_list_by_prerelease(self):
        ReleaseIntelligence.upsert_release({"tag_name": "v3.0", "repo": "org/repo", "name": "Stable", "prerelease": False})
        ReleaseIntelligence.upsert_release({"tag_name": "v4.0-beta", "repo": "org/repo", "name": "Beta", "prerelease": True})
        prereleases = ReleaseIntelligence.list_by_prerelease(True)
        assert any(r["tag_name"] == "v4.0-beta" for r in prereleases)
        stables = ReleaseIntelligence.list_by_prerelease(False)
        assert any(r["tag_name"] == "v3.0" for r in stables)

    def test_get_with_repo_filter(self):
        ReleaseIntelligence.upsert_release({"tag_name": "v5.0", "repo": "org/repo", "name": "v5.0"})
        assert ReleaseIntelligence.get_release("v5.0", "org/repo") is not None
        assert ReleaseIntelligence.get_release("v5.0", "other/repo") is None


# =============================================================================
# Part 7 — Deployment Status Integration
# =============================================================================

class TestDeploymentStatusIntegration:

    def test_list_returns_list(self):
        assert isinstance(DeploymentStatusIntegration.list_deployments(), list)

    def test_upsert_and_get(self):
        dep = DeploymentStatusIntegration.upsert_deployment({"id": "dep-1", "environment": "production", "state": "success"})
        assert dep["deployment_id"] == "dep-1"
        found = DeploymentStatusIntegration.get_deployment("dep-1")
        assert found["environment"] == "production"

    def test_upsert_update(self):
        DeploymentStatusIntegration.upsert_deployment({"id": "dep-2", "environment": "staging", "state": "pending"})
        DeploymentStatusIntegration.upsert_deployment({"deployment_id": "dep-2", "state": "success", "description": "Deployed OK"})
        found = DeploymentStatusIntegration.get_deployment("dep-2")
        assert found["state"] == "success"
        assert found["description"] == "Deployed OK"

    def test_list_by_environment(self):
        DeploymentStatusIntegration.upsert_deployment({"id": "dep-3", "environment": "production", "state": "success"})
        DeploymentStatusIntegration.upsert_deployment({"id": "dep-4", "environment": "staging", "state": "success"})
        prod = DeploymentStatusIntegration.list_by_environment("production")
        assert len(prod) >= 1
        staging = DeploymentStatusIntegration.list_by_environment("staging")
        assert len(staging) >= 1

    def test_list_by_state(self):
        DeploymentStatusIntegration.upsert_deployment({"id": "dep-5", "environment": "prod", "state": "success"})
        DeploymentStatusIntegration.upsert_deployment({"id": "dep-6", "environment": "prod", "state": "failure"})
        successes = DeploymentStatusIntegration.list_by_state("success")
        assert len(successes) >= 1


# =============================================================================
# Part 8 — Branch Intelligence
# =============================================================================

class TestBranchIntelligence:

    def test_list_returns_list(self):
        assert isinstance(BranchIntelligence.list_branches(), list)

    def test_upsert_and_get(self):
        b = BranchIntelligence.upsert_branch({"name": "main", "repo": "org/repo", "ref": "refs/heads/main"})
        assert b["name"] == "main"
        found = BranchIntelligence.get_branch("main")
        assert found["repo"] == "org/repo"

    def test_upsert_update(self):
        BranchIntelligence.upsert_branch({"name": "feature-x", "repo": "org/repo", "commit_count": 1})
        BranchIntelligence.upsert_branch({"name": "feature-x", "repo": "org/repo", "commit_count": 5, "last_commit": "abc123"})
        found = BranchIntelligence.get_branch("feature-x")
        assert found["commit_count"] == 5
        assert found["last_commit"] == "abc123"

    def test_list_by_repo(self):
        BranchIntelligence.upsert_branch({"name": "main", "repo": "org/a", "ref": "refs/heads/main"})
        BranchIntelligence.upsert_branch({"name": "develop", "repo": "org/b", "ref": "refs/heads/develop"})
        repo_a = BranchIntelligence.list_by_repo("org/a")
        assert len(repo_a) >= 1
        assert all(b["repo"] == "org/a" for b in repo_a)

    def test_mark_deleted(self):
        BranchIntelligence.upsert_branch({"name": "old-feature", "repo": "org/repo", "ref": "refs/heads/old"})
        result = BranchIntelligence.mark_deleted("old-feature")
        assert result is True
        found = BranchIntelligence.get_branch("old-feature")
        assert found["deleted"] is True

    def test_mark_deleted_nonexistent(self):
        assert BranchIntelligence.mark_deleted("nonexistent") is False

    def test_get_with_repo_filter(self):
        BranchIntelligence.upsert_branch({"name": "develop", "repo": "org/repo", "ref": "refs/heads/develop"})
        assert BranchIntelligence.get_branch("develop", "org/repo") is not None
        assert BranchIntelligence.get_branch("develop", "other/repo") is None


# =============================================================================
# Part 9 — GithubIntegration Orchestrator
# =============================================================================

class TestGithubIntegration:
    @pytest.fixture
    def ops(self):
        inst = GithubIntegration()
        inst.clear_state()
        return inst

    @pytest.mark.asyncio
    async def test_receive_webhook(self, ops):
        payload = {"ref": "refs/heads/main", "repository": {"full_name": "org/repo"}, "sender": {"login": "dev"}}
        result = await ops.receive_webhook(payload, "push")
        assert result["event_type"] == "push"
        assert result["repository"] == "org/repo"
        assert result["verified"] is False

    @pytest.mark.asyncio
    async def test_receive_webhook_verified(self, ops):
        payload = {"test": True}
        result = await ops.receive_webhook(payload, "ping", signature="sha256=bad", secret="secret")
        assert result["verified"] is False

    @pytest.mark.asyncio
    async def test_translate_and_process_push(self, ops):
        payload = {
            "ref": "refs/heads/main",
            "repository": {"full_name": "org/repo"},
            "sender": {"login": "dev"},
            "commits": [{"id": "abc", "message": "fix: resolve issue", "author": {"name": "Dev"}, "timestamp": "", "url": ""}],
        }
        result = await ops.translate_and_process("push", payload)
        assert result["internal_event"] == GITHUB_EVENTS["push_received"]
        assert result["context"]["branch"] == "main"

        # Branch should be tracked
        branch = BranchIntelligence.get_branch("main")
        assert branch is not None
        assert branch["repo"] == "org/repo"

    @pytest.mark.asyncio
    async def test_translate_and_process_pr(self, ops):
        payload = {
            "action": "opened",
            "repository": {"full_name": "org/repo"},
            "sender": {"login": "dev"},
            "pull_request": {"number": 42, "title": "New feature", "body": "Description", "state": "open", "merged": False, "draft": False, "user": {"login": "dev"}, "head": {"ref": "feature", "sha": "abc"}, "base": {"ref": "main"}, "html_url": "https://github.com/org/repo/pull/42"},
        }
        await ops.translate_and_process("pull_request", payload)
        pr = PRIntelligence.get_pr(42)
        assert pr is not None
        assert pr["title"] == "New feature"
        assert pr["head_branch"] == "feature"

    @pytest.mark.asyncio
    async def test_translate_and_process_workflow_run(self, ops):
        payload = {
            "repository": {"full_name": "org/repo"},
            "sender": {"login": "bot"},
            "workflow_run": {"id": 1001, "name": "CI Pipeline", "head_branch": "main", "head_sha": "abc", "status": "completed", "conclusion": "success", "html_url": "", "workflow_id": 1, "run_number": 5, "event": "push", "actor": {"login": "bot"}},
        }
        result = await ops.translate_and_process("workflow_run", payload)
        assert result["internal_event"] == GITHUB_EVENTS["workflow_run_completed"]
        run = WorkflowRunManager.get_run("1001")
        assert run is not None
        assert run["conclusion"] == "success"

    @pytest.mark.asyncio
    async def test_translate_and_process_issue(self, ops):
        payload = {
            "action": "opened",
            "repository": {"full_name": "org/repo"},
            "sender": {"login": "dev"},
            "issue": {"number": 77, "title": "Bug found", "body": "Details", "state": "open", "user": {"login": "dev"}, "labels": [{"name": "bug"}], "html_url": ""},
        }
        await ops.translate_and_process("issues", payload)
        issue = IssueIntelligence.get_issue(77)
        assert issue["title"] == "Bug found"
        assert "bug" in issue["labels"]

    @pytest.mark.asyncio
    async def test_translate_and_process_release(self, ops):
        payload = {
            "repository": {"full_name": "org/repo"},
            "sender": {"login": "dev"},
            "release": {"tag_name": "v2.0", "name": "v2.0", "body": "Release notes", "prerelease": False, "draft": False, "author": {"login": "dev"}, "html_url": "", "published_at": "2026-01-01T00:00:00Z"},
        }
        await ops.translate_and_process("release", payload)
        rel = ReleaseIntelligence.get_release("v2.0")
        assert rel is not None
        assert rel["name"] == "v2.0"

    @pytest.mark.asyncio
    async def test_translate_and_process_deployment_status(self, ops):
        payload = {
            "repository": {"full_name": "org/repo"},
            "sender": {"login": "ops"},
            "deployment": {"id": 2001, "environment": "production"},
            "deployment_status": {"state": "success", "description": "Deployed", "log_url": "", "environment_url": ""},
        }
        await ops.translate_and_process("deployment_status", payload)
        dep = DeploymentStatusIntegration.get_deployment("2001")
        assert dep is not None
        assert dep["state"] == "success"
        assert dep["environment"] == "production"

    @pytest.mark.asyncio
    async def test_dashboard_stats(self, ops):
        stats = ops.get_dashboard_stats()
        assert "total_webhooks" in stats
        assert "total_workflow_runs" in stats
        assert "total_prs" in stats
        assert "total_issues" in stats
        assert "total_releases" in stats
        assert "total_deployments" in stats
        assert "total_branches" in stats

    @pytest.mark.asyncio
    async def test_recent_webhooks(self, ops):
        await ops.receive_webhook({"repository": {"full_name": "org/repo"}, "sender": {"login": "dev"}}, "push")
        recent = ops.get_recent_webhooks(5)
        assert len(recent) >= 1

    @pytest.mark.asyncio
    async def test_recent_activity_aggregation(self, ops):
        await ops.receive_webhook({"repository": {"full_name": "org/repo"}, "sender": {"login": "dev"}}, "push")
        activity = ops.get_recent_activity(10)
        assert len(activity) >= 1
        assert activity[0]["type"] == "webhook"

    @pytest.mark.asyncio
    async def test_launch_mission_from_webhook(self, ops):
        payload = {
            "ref": "refs/heads/main",
            "repository": {"full_name": "org/repo", "clone_url": "https://github.com/org/repo.git", "html_url": "https://github.com/org/repo"},
            "sender": {"login": "dev"},
            "commits": [{"message": "fix: resolve crash", "id": "abc", "author": {"name": "Dev"}, "timestamp": "", "url": ""}],
        }
        with patch("backend.services.enterprise_github_integration.GithubIntegration._emit", new_callable=AsyncMock):
            result = await ops.launch_mission_from_webhook("push", payload)
            assert result is not None
            assert "task" in result
            assert "plan" in result
            assert result["context"]["mission_launched"] is True

    @pytest.mark.asyncio
    async def test_clear_state(self, ops):
        await ops.receive_webhook({"repository": {"full_name": "org/repo"}, "sender": {"login": "dev"}}, "push")
        ops.clear_state()
        assert ops.get_dashboard_stats()["total_webhooks"] == 0
        assert ops.get_dashboard_stats()["total_workflow_runs"] == 0

    def test_build_description_all_types(self, ops):
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
            desc = ops._build_description(event_type, ctx)
            assert desc == expected, f"{event_type}: {desc} != {expected}"


# =============================================================================
# E2E Workflow
# =============================================================================

class TestGithubE2E:
    @pytest.mark.asyncio
    async def test_full_push_to_branch_workflow(self):
        """Developer pushes code → webhook → translate → branch tracked."""
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

        # 1. Receive webhook
        webhook_result = await ops.receive_webhook(push_payload, "push")
        assert webhook_result["event_type"] == "push"

        # 2. Translate and process
        with patch("backend.services.enterprise_github_integration.GithubIntegration._emit", new_callable=AsyncMock):
            translate_result = await ops.translate_and_process("push", push_payload)
        assert translate_result["internal_event"] == "github.push_received"

        # 3. Verify branch tracked
        branch = BranchIntelligence.get_branch("feature/login-fix")
        assert branch is not None
        assert branch["commit_count"] == 1
        assert branch["last_commit"] == "fix: resolve login timeout"

        # 4. Dashboard should reflect
        stats = ops.get_dashboard_stats()
        assert stats["total_webhooks"] >= 1
        assert stats["total_branches"] >= 1

    @pytest.mark.asyncio
    async def test_full_pr_lifecycle(self):
        """PR opened → reviewed → checks passed → merged."""
        ops = GithubIntegration()
        ops.clear_state()

        base_payload = {
            "repository": {"full_name": "org/pr-demo", "html_url": "https://github.com/org/pr-demo"},
            "sender": {"login": "bob"},
        }

        # Open PR
        open_payload = {**base_payload, "action": "opened", "pull_request": {
            "number": 100, "title": "Add new API", "body": "Implements REST endpoints",
            "state": "open", "merged": False, "draft": False, "user": {"login": "bob"},
            "head": {"ref": "feature/api", "sha": "def456"}, "base": {"ref": "main"},
            "html_url": "https://github.com/org/pr-demo/pull/100",
        }}
        with patch("backend.services.enterprise_github_integration.GithubIntegration._emit", new_callable=AsyncMock):
            await ops.translate_and_process("pull_request", open_payload)

        pr = PRIntelligence.get_pr(100)
        assert pr["state"] == "open"
        assert pr["title"] == "Add new API"

        # Mark checks
        PRIntelligence.mark_checks(100, True, [{"name": "CI", "status": "completed", "conclusion": "success"}])
        assert PRIntelligence.get_pr(100)["checks_passed"] is True

        # Merge PR
        merge_payload = {**base_payload, "action": "closed", "pull_request": {
            **open_payload["pull_request"], "merged": True, "state": "closed",
        }}
        with patch("backend.services.enterprise_github_integration.GithubIntegration._emit", new_callable=AsyncMock):
            result = await ops.translate_and_process("pull_request", merge_payload)
        assert result["internal_event"] == "github.pr_merged"

        # Verify dash stats
        stats = ops.get_dashboard_stats()
        assert stats["total_prs"] >= 1

    @pytest.mark.asyncio
    async def test_workflow_run_monitoring(self):
        """Workflow run started → completed → tracked."""
        ops = GithubIntegration()
        ops.clear_state()

        start_payload = {
            "repository": {"full_name": "org/ci-demo"},
            "sender": {"login": "ci-bot"},
            "workflow_run": {"id": 5001, "name": "Test Suite", "head_branch": "main", "head_sha": "abc", "status": "in_progress", "conclusion": None, "html_url": "", "workflow_id": 10, "run_number": 42, "event": "push", "actor": {"login": "ci-bot"}},
        }
        with patch("backend.services.enterprise_github_integration.GithubIntegration._emit", new_callable=AsyncMock):
            await ops.translate_and_process("workflow_run", start_payload)
        assert WorkflowRunManager.get_run("5001")["status"] == "in_progress"

        # Complete
        complete_payload = {**start_payload, "workflow_run": {**start_payload["workflow_run"], "status": "completed", "conclusion": "success"}}
        with patch("backend.services.enterprise_github_integration.GithubIntegration._emit", new_callable=AsyncMock):
            await ops.translate_and_process("workflow_run", complete_payload)
        assert WorkflowRunManager.get_run("5001")["conclusion"] == "success"

    @pytest.mark.asyncio
    async def test_deployment_tracking(self):
        """Deployment started → completed → tracked."""
        ops = GithubIntegration()
        ops.clear_state()

        start_payload = {
            "repository": {"full_name": "org/deploy-demo"},
            "sender": {"login": "ops-bot"},
            "deployment": {"id": 3001, "environment": "production"},
            "deployment_status": {"state": "pending", "description": "Deploying", "log_url": "", "environment_url": ""},
        }
        with patch("backend.services.enterprise_github_integration.GithubIntegration._emit", new_callable=AsyncMock):
            await ops.translate_and_process("deployment_status", start_payload)
        dep_pending = DeploymentStatusIntegration.get_deployment("3001")
        assert dep_pending["state"] == "pending"

        # Complete
        complete_payload = {**start_payload, "deployment_status": {**start_payload["deployment_status"], "state": "success", "description": "Live"}}
        with patch("backend.services.enterprise_github_integration.GithubIntegration._emit", new_callable=AsyncMock):
            await ops.translate_and_process("deployment_status", complete_payload)
        dep_done = DeploymentStatusIntegration.get_deployment("3001")
        assert dep_done["state"] == "success"

    @pytest.mark.asyncio
    async def test_issue_and_release_workflow(self):
        """Issue reported → release published → both tracked."""
        ops = GithubIntegration()
        ops.clear_state()

        # Issue
        issue_payload = {
            "action": "opened",
            "repository": {"full_name": "org/issue-demo"},
            "sender": {"login": "reporter"},
            "issue": {"number": 200, "title": "Security vulnerability", "body": "Details", "state": "open", "user": {"login": "reporter"}, "labels": [{"name": "security"}, {"name": "bug"}], "html_url": ""},
        }
        with patch("backend.services.enterprise_github_integration.GithubIntegration._emit", new_callable=AsyncMock):
            await ops.translate_and_process("issues", issue_payload)
        issue = IssueIntelligence.get_issue(200)
        assert issue["title"] == "Security vulnerability"
        assert "security" in issue["labels"]

        # Release
        release_payload = {
            "repository": {"full_name": "org/issue-demo"},
            "sender": {"login": "maintainer"},
            "release": {"tag_name": "v2.0.1", "name": "Security Patch v2.0.1", "body": "Fixes CVE-2026-xxxx", "prerelease": False, "draft": False, "author": {"login": "maintainer"}, "html_url": "", "published_at": "2026-07-11T00:00:00Z"},
        }
        with patch("backend.services.enterprise_github_integration.GithubIntegration._emit", new_callable=AsyncMock):
            await ops.translate_and_process("release", release_payload)
        rel = ReleaseIntelligence.get_release("v2.0.1")
        assert rel["name"] == "Security Patch v2.0.1"
        assert rel["prerelease"] is False

    @pytest.mark.asyncio
    async def test_multiple_events_dashboard_accuracy(self):
        """Multiple event types → dashboard stats reflect all."""
        ops = GithubIntegration()
        ops.clear_state()

        base = {"repository": {"full_name": "org/dash-demo"}, "sender": {"login": "dev"}}

        with patch("backend.services.enterprise_github_integration.GithubIntegration._emit", new_callable=AsyncMock):
            await ops.receive_webhook({**base, "ref": "refs/heads/main", "commits": []}, "push")
            await ops.translate_and_process("push", {**base, "ref": "refs/heads/feat1", "commits": [{"id": "a", "message": "m", "author": {"name": "D"}, "timestamp": "", "url": ""}]})
            await ops.translate_and_process("push", {**base, "ref": "refs/heads/feat2", "commits": [{"id": "b", "message": "m", "author": {"name": "D"}, "timestamp": "", "url": ""}]})
            await ops.translate_and_process("issues", {**base, "action": "opened", "issue": {"number": 1, "title": "T1", "state": "open", "user": {"login": "d"}, "labels": []}})
            await ops.translate_and_process("release", {**base, "release": {"tag_name": "v1", "name": "V1", "prerelease": False, "draft": False, "author": {"login": "d"}, "html_url": "", "published_at": ""}})
            await ops.translate_and_process("workflow_run", {**base, "workflow_run": {"id": 1, "name": "CI", "head_branch": "main", "head_sha": "", "status": "completed", "conclusion": "success", "html_url": "", "workflow_id": 1, "run_number": 1, "event": "push", "actor": {"login": "bot"}}})
            await ops.translate_and_process("deployment_status", {**base, "deployment": {"id": 1, "environment": "prod"}, "deployment_status": {"state": "success", "description": "OK", "log_url": "", "environment_url": ""}})

        stats = ops.get_dashboard_stats()
        assert stats["total_webhooks"] >= 1
        assert stats["total_branches"] >= 2
        assert stats["total_issues"] >= 1
        assert stats["total_releases"] >= 1
        assert stats["total_workflow_runs"] >= 1
        assert stats["total_deployments"] >= 1

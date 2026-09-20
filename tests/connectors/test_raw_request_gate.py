"""Phase 11.1-K — audit findings S-1 and S-2, closed at the boundary that matters.

S-1: ``POST /api/git/*`` reached ``GitHubConnector._request`` writes (branch
delete, blob/tree/commit, a ref PATCH, comments, labels) without going through
``BaseConnector._execute`` -- so without the effect gate and without the legacy
flag. S-2: three V1 autonomy routes had no legacy guard while their sibling
``/execute`` routes did.

Two independent layers are proven here, so neither is load-bearing alone:

* connector layer -- every connector's raw request method refuses a
  state-changing HTTP method that did not arrive through an admitted
  ``_execute`` operation, whoever the caller is;
* route layer -- the mutating ``/api/git`` routes and the S-2 routes refuse with
  503 unless ``CORTEXPRIME_ENABLE_LEGACY_EXECUTION`` is set.
"""

from __future__ import annotations

import asyncio
import importlib

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.api.legacy_execution_boundary import (
    LEGACY_EXECUTION_FLAG,
    LEGACY_EXECUTION_SURFACES,
    LegacyExecutionRefused,
)
from backend.connectors.effects import effect_scope, guard_raw_request

RAW_METHODS = {
    "argocd": ("ArgoCDConnector", "_post"),
    "azure_devops": ("AzureDevOpsConnector", "_request"),
    "circleci": ("CircleCIConnector", "_request"),
    "confluence": ("ConfluenceConnector", "_request"),
    "github": ("GitHubConnector", "_request"),
    "gitlab_ci": ("GitLabCIConnector", "_request"),
    "jenkins": ("JenkinsConnector", "_request"),
    "jira": ("JiraConnector", "_request"),
    "loki": ("LokiConnector", "_post"),
    "notion": ("NotionConnector", "_request"),
    "servicenow": ("ServiceNowConnector", "_request"),
    "slack": ("SlackConnector", "_request"),
    "teams": ("TeamsConnector", "_request"),
}


@pytest.fixture(autouse=True)
def _flag_unset(monkeypatch):
    monkeypatch.delenv(LEGACY_EXECUTION_FLAG, raising=False)


class _RecordingClient:
    """Stands where httpx would. Any call reaching it means the gate let a
    request through; the tests below assert it is never reached on a refusal."""

    def __init__(self):
        self.calls = []

    async def request(self, *args, **kwargs):  # pragma: no cover - must not run
        self.calls.append((args, kwargs))
        raise AssertionError("the provider was reached")

    async def post(self, *args, **kwargs):  # pragma: no cover - must not run
        self.calls.append((args, kwargs))
        raise AssertionError("the provider was reached")


def _bare(connector_type: str):
    module = importlib.import_module(f"backend.connectors.{connector_type}")
    class_name, method = RAW_METHODS[connector_type]
    cls = getattr(module, class_name)
    instance = cls.__new__(cls)
    instance._client = _RecordingClient()
    return instance, method


# -- the gate itself ---------------------------------------------------------

class TestGuardRawRequest:
    @pytest.mark.parametrize("verb", ["POST", "PUT", "PATCH", "DELETE", "post", "Merge"])
    def test_a_state_changing_raw_request_outside_execute_refuses(self, verb):
        with pytest.raises(LegacyExecutionRefused):
            guard_raw_request("github", verb)

    @pytest.mark.parametrize("verb", ["GET", "HEAD", "OPTIONS", "get"])
    def test_safe_methods_pass(self, verb):
        guard_raw_request("github", verb)

    def test_inside_an_admitted_operation_of_the_same_connector_it_passes(self):
        with effect_scope("notion"):
            guard_raw_request("notion", "POST")  # a POST-shaped read via _execute

    def test_another_connectors_scope_does_not_admit(self):
        with effect_scope("notion"):
            with pytest.raises(LegacyExecutionRefused):
                guard_raw_request("github", "POST")

    def test_the_scope_ends_with_the_operation(self):
        with effect_scope("github"):
            pass
        with pytest.raises(LegacyExecutionRefused):
            guard_raw_request("github", "DELETE")

    def test_the_legacy_flag_still_admits_deliberate_migration(self, monkeypatch):
        monkeypatch.setenv(LEGACY_EXECUTION_FLAG, "1")
        guard_raw_request("github", "DELETE")

    def test_the_refusal_names_the_connector_and_verb(self):
        with pytest.raises(LegacyExecutionRefused) as refused:
            guard_raw_request("github", "patch")
        assert "github" in str(refused.value) and "PATCH" in str(refused.value)

    def test_the_scope_does_not_leak_into_a_task_started_elsewhere(self):
        async def outside():
            guard_raw_request("github", "POST")

        async def run():
            task = asyncio.get_running_loop().create_task(outside())
            with effect_scope("github"):
                await asyncio.sleep(0)
            await task

        with pytest.raises(LegacyExecutionRefused):
            asyncio.run(run())


# -- every connector's raw request method -------------------------------------

class TestEveryConnectorRawMethod:
    @pytest.mark.parametrize("connector_type", sorted(RAW_METHODS))
    def test_a_direct_state_changing_call_refuses_before_the_provider(self, connector_type):
        connector, method = _bare(connector_type)
        call = getattr(connector, method)
        with pytest.raises(LegacyExecutionRefused):
            if method == "_post":
                asyncio.run(call("/any"))
            else:
                asyncio.run(call("POST", "/any", json={"x": 1}))
        assert connector._client.calls == []

    def test_execute_admits_a_post_shaped_read_through_the_same_raw_method(self):
        from backend.connectors.base import BaseConnector

        seen = []

        class PostReader(BaseConnector):
            connector_type = "notion"
            connector_name = "notion"

            async def initialize(self):  # pragma: no cover
                return None

            async def shutdown(self):  # pragma: no cover
                return None

            async def health(self):  # pragma: no cover
                return None

            async def _request(self, method, path, **kwargs):
                guard_raw_request(self.connector_type, method)
                seen.append((method, path))
                return {"ok": True}

        reader = PostReader.__new__(PostReader)

        async def search():
            return await reader._request("POST", "/v1/search")

        async def go():
            import backend.connectors.base as base_module

            async def _no_record(**_kwargs):
                return None

            original = base_module.ConnectorActivityService.record
            base_module.ConnectorActivityService.record = staticmethod(_no_record)
            try:
                return await reader._execute("search", "search", search)
            finally:
                base_module.ConnectorActivityService.record = original

        assert asyncio.run(go()) == {"ok": True}
        assert seen == [("POST", "/v1/search")]


# -- the service that bypassed the gate ----------------------------------------

class TestEnterpriseGitOperationsBypassIsClosed:
    """Exactly the S-1 call sites, with and without a configured token."""

    @pytest.fixture
    def registered_github(self, monkeypatch):
        from backend.connectors.registry import connector_registry

        connector, _ = _bare("github")
        monkeypatch.setitem(connector_registry._connectors, "github", connector)
        return connector

    @pytest.mark.parametrize("token", [None, "a-configured-token-value"])
    @pytest.mark.parametrize("call", ["comment", "labels", "delete_branch", "close_issue"])
    def test_every_raw_write_refuses(self, registered_github, monkeypatch, token, call):
        if token is None:
            monkeypatch.delenv("GITHUB_TOKEN", raising=False)
        else:
            monkeypatch.setenv("GITHUB_TOKEN", token)
        from backend.services.enterprise_git_operations import GitBranchManager, IssueSyncManager

        repo = "https://github.com/owner/repo"
        calls = {
            "comment": lambda: IssueSyncManager.comment_github_issue(repo, 1, "hello"),
            "labels": lambda: IssueSyncManager.update_github_labels(repo, 1, ["bug"]),
            "delete_branch": lambda: GitBranchManager.delete_branch(repo, "feature"),
            "close_issue": lambda: IssueSyncManager.close_github_issue(repo, 1, 2),
        }
        outcome = None
        try:
            outcome = asyncio.run(calls[call]())
        except LegacyExecutionRefused:
            outcome = "refused"
        # Some managers swallow exceptions and report failure; either way the
        # provider must not have been reached.
        assert outcome in ("refused", False, None) or (isinstance(outcome, dict) and not outcome.get("success", False))
        assert registered_github._client.calls == []


# -- the routes ---------------------------------------------------------------

def _git_app():
    from backend.api.enterprise_git_routes import router

    app = FastAPI()
    app.include_router(router)
    return app


def _v1_app(authenticated: bool):
    from backend.api.routes.orchestrator_routes import router as orchestrator_router
    from backend.api.runtime_api import router as runtime_router
    from backend.auth.dependencies import require_user

    app = FastAPI()
    app.include_router(orchestrator_router, prefix="/api/orchestrator")
    app.include_router(runtime_router)
    if authenticated:
        app.dependency_overrides[require_user] = lambda: {"user_id": "u-1", "tenant_id": "t-1"}
    return app


GIT_WRITES = [
    ("/api/git/branches", {"repo_url": "owner/repo", "branch_name": "b"}),
    ("/api/git/commit", {"repo_url": "owner/repo", "branch": "main", "description": "x", "files": []}),
    ("/api/git/pull-request", {"repo_url": "owner/repo", "title": "t", "head": "b", "base": "main"}),
    ("/api/git/pull-request/7/merge", {"repo_url": "owner/repo"}),
    ("/api/git/issues/sync", {"repo_url": "owner/repo", "issue_number": 1}),
]


class TestRoutes:
    @pytest.mark.parametrize("path,body", GIT_WRITES)
    def test_every_mutating_git_route_refuses_503(self, path, body):
        response = TestClient(_git_app()).post(path, json=body)
        assert response.status_code == 503, (path, response.text)

    @pytest.mark.parametrize("path,body", GIT_WRITES)
    def test_a_trailing_slash_alias_does_not_bypass(self, path, body):
        response = TestClient(_git_app()).post(path + "/", json=body)
        assert response.status_code in (503, 404, 405), (path, response.status_code)

    def test_git_reads_are_not_swept_in(self):
        routes = {(r.path, tuple(sorted(r.methods))) for r in _git_app().routes if hasattr(r, "methods")}
        assert ("/api/git/history", ("GET",)) in routes

    @pytest.mark.parametrize("path", ["/api/orchestrator/autonomous", "/api/orchestrator/route",
                                      "/api/orchestrator/reflect", "/api/runtime/autonomous-loop"])
    def test_s2_routes_refuse_an_authenticated_caller_503(self, path):
        response = TestClient(_v1_app(authenticated=True)).post(path, json={"goal": "x", "objective": "x"})
        assert response.status_code == 503, (path, response.text)

    @pytest.mark.parametrize("path", ["/api/orchestrator/autonomous", "/api/orchestrator/route",
                                      "/api/orchestrator/reflect", "/api/runtime/autonomous-loop"])
    def test_s2_routes_refuse_an_unauthenticated_caller(self, path):
        response = TestClient(_v1_app(authenticated=False)).post(path, json={"goal": "x"})
        assert response.status_code in (401, 403, 503), (path, response.status_code)

    def test_the_legacy_flag_is_the_only_way_through(self, monkeypatch):
        monkeypatch.setenv(LEGACY_EXECUTION_FLAG, "1")
        # With the flag the guard steps aside; the request then reaches the V1
        # handler (which may fail for its own reasons -- the point is it is no
        # longer refused by the boundary).
        response = TestClient(_git_app()).post("/api/git/issues/sync", json={"repo_url": "o/r"})
        assert response.status_code != 503 or "LEGACY" not in response.text.upper()


class TestInventory:
    def test_the_new_surfaces_are_inventoried_as_gated(self):
        routes = {s.route: s for s in LEGACY_EXECUTION_SURFACES}
        for route in ("POST /api/runtime/autonomous-loop",
                      "POST /api/orchestrator/{autonomous,route,reflect}"):
            assert routes[route].gated is True
        assert any(r.startswith("POST /api/git/") and s.gated for r, s in routes.items())

    def test_the_runtime_execute_label_matches_the_real_prefix(self):
        routes = {s.route for s in LEGACY_EXECUTION_SURFACES}
        assert "POST /api/runtime/execute" in routes
        assert "POST /api/v1/runtime/execute" not in routes


class TestFitnessRule:
    def test_the_rule_requires_the_raw_guard_first_in_every_raw_method(self):
        from backend.platform.architecture.boundary_rules import ConnectorEffectGateRule

        sites = {(s[0], s[1]): s for s in ConnectorEffectGateRule().gate_sites}
        for connector_type, (_cls, method) in RAW_METHODS.items():
            site = sites[(f"backend.connectors.{connector_type}", method)]
            assert site[2] is True and site[3] == "guard_raw_request"

    def test_the_rule_passes_on_the_current_tree(self):
        from pathlib import Path

        from backend.platform.architecture.boundary_rules import ConnectorEffectGateRule
        from backend.platform.architecture.rules import ModuleGraph

        graph = ModuleGraph.build(Path(__file__).resolve().parents[2] / "backend")
        result = ConnectorEffectGateRule().evaluate(graph)
        assert result.violations == (), result.violations

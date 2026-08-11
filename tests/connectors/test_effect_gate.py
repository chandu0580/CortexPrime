"""Phase 6.1 — the V1 connector effect gate (L1: One Plane of Action).

Proves, at the unit level:
  * classification is fail-closed (unknown operation or connector ⇒ WRITE),
  * a write refuses with the same ``LegacyExecutionRefused`` every other
    quarantined V1 surface raises, under the same flag,
  * the gate runs *before* the operation body in ``BaseConnector._execute``
    and in the three bypass seams (argocd ``_post``, github
    ``graphql_request``, terraform ``_run``),
  * the classification table cannot silently drift: every public async
    operation of every V1 connector must be classified.
"""

from __future__ import annotations

import inspect

import pytest

from backend.api.legacy_execution_boundary import (
    LEGACY_EXECUTION_FLAG,
    LegacyExecutionRefused,
)
from backend.connectors.effects import (
    EFFECT_READ,
    EFFECT_WRITE,
    KNOWN_OPERATIONS,
    WRITE_OPERATIONS,
    assert_effect_permitted,
    classify_effect,
)


@pytest.fixture(autouse=True)
def _flag_unset(monkeypatch):
    """Every test starts with the legacy flag unset — the production default."""
    monkeypatch.delenv(LEGACY_EXECUTION_FLAG, raising=False)


class TestClassification:
    def test_known_read_classifies_read(self):
        assert classify_effect("github", "get_repository") == EFFECT_READ
        assert classify_effect("docker", "list_containers") == EFFECT_READ
        assert classify_effect("prometheus", "query") == EFFECT_READ

    def test_known_write_classifies_write(self):
        assert classify_effect("github", "create_pull_request") == EFFECT_WRITE
        assert classify_effect("docker", "restart_container") == EFFECT_WRITE
        assert classify_effect("jira", "create_issue") == EFFECT_WRITE
        assert classify_effect("terraform", "apply") == EFFECT_WRITE

    def test_unknown_operation_fails_closed(self):
        assert classify_effect("github", "do_something_new") == EFFECT_WRITE

    def test_unknown_connector_fails_closed(self):
        assert classify_effect("brand_new_connector", "get_thing") == EFFECT_WRITE

    def test_graphql_is_a_write(self):
        # An arbitrary GraphQL document can carry any mutation.
        assert classify_effect("github", "graphql_request") == EFFECT_WRITE

    def test_every_terraform_operation_is_a_write(self):
        for op in KNOWN_OPERATIONS["terraform"]:
            assert classify_effect("terraform", op) == EFFECT_WRITE, op

    def test_kubernetes_has_no_writes(self):
        assert WRITE_OPERATIONS["kubernetes"] == frozenset()


class TestGateBehaviour:
    def test_read_passes_without_flag(self):
        assert_effect_permitted("github", "get_repository")  # no raise

    def test_write_refuses_without_flag(self):
        with pytest.raises(LegacyExecutionRefused):
            assert_effect_permitted("github", "create_issue")

    def test_unknown_refuses_without_flag(self):
        with pytest.raises(LegacyExecutionRefused):
            assert_effect_permitted("github", "brand_new_method")

    def test_write_passes_with_flag(self, monkeypatch):
        monkeypatch.setenv(LEGACY_EXECUTION_FLAG, "1")
        assert_effect_permitted("github", "create_issue")  # no raise

    def test_refusal_names_the_surface(self):
        with pytest.raises(LegacyExecutionRefused) as exc:
            assert_effect_permitted("jira", "create_issue")
        assert "connector:jira.create_issue" in str(exc.value)


class TestExecuteWiring:
    """The gate must run before the operation body — a refused write performs
    nothing, records nothing."""

    @pytest.mark.anyio
    async def test_execute_refuses_write_before_running_func(self):
        from backend.connectors.jira import JiraConnector

        connector = JiraConnector()
        ran = []

        async def op():
            ran.append(True)
            return {"id": "X-1"}

        with pytest.raises(LegacyExecutionRefused):
            await connector._execute("create_issue", func=op)
        assert ran == []

    @pytest.mark.anyio
    async def test_execute_permits_read(self):
        from backend.connectors.jira import JiraConnector

        connector = JiraConnector()

        async def op():
            return {"id": "X-1"}

        result = await connector._execute("get_issue", func=op)
        assert result == {"id": "X-1"}

    @pytest.mark.anyio
    async def test_argocd_post_refuses_uninitialized(self):
        from backend.connectors.argocd import ArgoCDConnector

        connector = ArgoCDConnector()
        with pytest.raises(LegacyExecutionRefused):
            await connector.sync_application("some-app")

    @pytest.mark.anyio
    async def test_github_graphql_refuses_uninitialized(self):
        from backend.connectors.github import GitHubConnector

        connector = GitHubConnector()
        with pytest.raises(LegacyExecutionRefused):
            await connector.graphql_request("mutation { }")

    @pytest.mark.anyio
    async def test_terraform_run_refuses(self):
        from backend.connectors.terraform import TerraformConnector

        connector = TerraformConnector()
        with pytest.raises(LegacyExecutionRefused):
            await connector._run("apply -auto-approve")

    @pytest.mark.anyio
    async def test_terraform_read_verbs_also_refuse(self):
        # Every terraform invocation is a subprocess — reads included.
        from backend.connectors.terraform import TerraformConnector

        connector = TerraformConnector()
        with pytest.raises(LegacyExecutionRefused):
            await connector._run("plan")


_CONNECTOR_CLASSES = {
    "github": ("backend.connectors.github", "GitHubConnector"),
    "gitlab_ci": ("backend.connectors.gitlab_ci", "GitLabCIConnector"),
    "jenkins": ("backend.connectors.jenkins", "JenkinsConnector"),
    "circleci": ("backend.connectors.circleci", "CircleCIConnector"),
    "azure_devops": ("backend.connectors.azure_devops", "AzureDevOpsConnector"),
    "jira": ("backend.connectors.jira", "JiraConnector"),
    "confluence": ("backend.connectors.confluence", "ConfluenceConnector"),
    "notion": ("backend.connectors.notion", "NotionConnector"),
    "servicenow": ("backend.connectors.servicenow", "ServiceNowConnector"),
    "slack": ("backend.connectors.slack", "SlackConnector"),
    "teams": ("backend.connectors.teams", "TeamsConnector"),
    "docker": ("backend.connectors.docker", "DockerConnector"),
    "kubernetes": ("backend.connectors.kubernetes", "KubernetesConnector"),
    "argocd": ("backend.connectors.argocd", "ArgoCDConnector"),
    "prometheus": ("backend.connectors.prometheus", "PrometheusConnector"),
    "loki": ("backend.connectors.loki", "LokiConnector"),
    "grafana": ("backend.connectors.grafana", "GrafanaConnector"),
    "opentelemetry": ("backend.connectors.opentelemetry", "OpenTelemetryConnector"),
    "terraform": ("backend.connectors.terraform", "TerraformConnector"),
}

_LIFECYCLE = {
    "initialize", "shutdown", "health", "configure", "close", "request",
    "get_paginated", "set_auth", "get_operations",
}


class TestClassificationCompleteness:
    """A new public async method on any connector must be classified before it
    can run — otherwise it refuses (fail-closed) AND this test fails, so the
    unclassified state cannot survive CI."""

    @pytest.mark.parametrize("connector_type", sorted(_CONNECTOR_CLASSES))
    def test_every_public_operation_is_classified(self, connector_type):
        module_name, class_name = _CONNECTOR_CLASSES[connector_type]
        module = __import__(module_name, fromlist=[class_name])
        cls = getattr(module, class_name)

        public_async = {
            name
            for name in dir(cls)
            if not name.startswith("_")
            and name not in _LIFECYCLE
            and inspect.iscoroutinefunction(getattr(cls, name, None))
        }
        unclassified = public_async - KNOWN_OPERATIONS[connector_type]
        assert unclassified == set(), (
            f"{connector_type}: unclassified operations {sorted(unclassified)} — "
            "add them to backend/connectors/effects.py (write or read) before "
            "they can execute"
        )

    def test_write_sets_are_subsets_of_known(self):
        for ctype, writes in WRITE_OPERATIONS.items():
            assert writes <= KNOWN_OPERATIONS[ctype], ctype

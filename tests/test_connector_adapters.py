from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

pytestmark = pytest.mark.asyncio


# ==============================================================================
# GitHub adapter
# ==============================================================================

class TestGitHubAdapter:
    @patch("backend.connector.adapters.github.httpx.AsyncClient")
    @patch("backend.connector.adapters.github.os.getenv", return_value="ghp_test_token")
    async def test_initialize_success(self, mock_getenv, mock_client_cls):
        from backend.connector.adapters.github import GitHubAdapter
        adapter = GitHubAdapter()
        mock_client = AsyncMock()
        mock_client_cls.return_value = mock_client
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"resources": {"core": {"remaining": 4500, "reset": 0}}}
        mock_client.get.return_value = mock_resp
        result = await adapter.initialize()
        assert result is True
        assert adapter._initialized is True
        assert adapter._rate_limit_remaining == 4500

    @patch("backend.connector.adapters.github.os.getenv", return_value="")
    async def test_initialize_no_token(self, mock_getenv):
        from backend.connector.adapters.github import GitHubAdapter
        adapter = GitHubAdapter()
        result = await adapter.initialize()
        assert result is False

    async def test_health_check_unhealthy(self):
        from backend.connector.adapters.github import GitHubAdapter
        from backend.connector.adapter.interfaces import AdapterHealthStatus
        adapter = GitHubAdapter()
        status = await adapter.health_check()
        assert status == AdapterHealthStatus.UNHEALTHY

    async def test_capabilities(self):
        from backend.connector.adapters.github import GitHubAdapter
        from backend.connector.models import Capability
        adapter = GitHubAdapter()
        caps = await adapter.capabilities()
        assert Capability.SEARCH in caps
        assert Capability.BUILD in caps
        assert Capability.DEPLOY in caps

    async def test_execute_unsupported(self):
        from backend.connector.adapters.github import GitHubAdapter
        from backend.connector.models import Capability
        adapter = GitHubAdapter()
        result = await adapter.execute(Capability.NOTIFY, {})
        assert result.success is False
        assert "Unsupported" in (result.error or "")

    async def test_connector_type_and_name(self):
        from backend.connector.adapters.github import GitHubAdapter
        adapter = GitHubAdapter()
        assert adapter.connector_type == "github"
        assert adapter.connector_name == "GitHub"

    async def test_shutdown(self):
        from backend.connector.adapters.github import GitHubAdapter
        adapter = GitHubAdapter()
        adapter._client = AsyncMock()
        await adapter.shutdown()
        assert adapter._initialized is False
        assert adapter._client is None

    async def test_metadata(self):
        from backend.connector.adapters.github import GitHubAdapter
        adapter = GitHubAdapter()
        meta = await adapter.metadata()
        assert meta["connector_type"] == "github"
        assert meta["connector_name"] == "GitHub"

    async def test_execute_search_missing_query(self):
        from backend.connector.adapters.github import GitHubAdapter
        from backend.connector.models import Capability
        adapter = GitHubAdapter()
        result = await adapter.execute(Capability.SEARCH, {})
        assert result.success is False
        assert "Missing" in (result.error or "")


# ==============================================================================
# Jira adapter
# ==============================================================================

class TestJiraAdapter:
    @patch("backend.connector.adapters.jira.httpx.AsyncClient")
    @patch("backend.connector.adapters.jira.os.getenv")
    async def test_initialize_success(self, mock_getenv, mock_client_cls):
        def side_effect(key: str, default: str = ""):
            env = {"JIRA_BASE_URL": "https://test.atlassian.net", "JIRA_EMAIL": "test@test.com", "JIRA_API_TOKEN": "token123"}
            return env.get(key, default)
        mock_getenv.side_effect = side_effect
        from backend.connector.adapters.jira import JiraAdapter
        adapter = JiraAdapter()
        mock_client = AsyncMock()
        mock_client_cls.return_value = mock_client
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"displayName": "Test User"}
        mock_client.get.return_value = mock_resp
        result = await adapter.initialize()
        assert result is True

    @patch("backend.connector.adapters.jira.os.getenv", return_value="")
    async def test_initialize_missing_creds(self, mock_getenv):
        from backend.connector.adapters.jira import JiraAdapter
        adapter = JiraAdapter()
        result = await adapter.initialize()
        assert result is False

    async def test_health_check_unhealthy(self):
        from backend.connector.adapters.jira import JiraAdapter
        from backend.connector.adapter.interfaces import AdapterHealthStatus
        adapter = JiraAdapter()
        status = await adapter.health_check()
        assert status == AdapterHealthStatus.UNHEALTHY

    async def test_capabilities(self):
        from backend.connector.adapters.jira import JiraAdapter
        from backend.connector.models import Capability
        adapter = JiraAdapter()
        caps = await adapter.capabilities()
        assert Capability.SEARCH in caps
        assert Capability.EXECUTE in caps
        assert Capability.NOTIFY in caps

    async def test_execute_unsupported(self):
        from backend.connector.adapters.jira import JiraAdapter
        from backend.connector.models import Capability
        adapter = JiraAdapter()
        result = await adapter.execute(Capability.DEPLOY, {})
        assert result.success is False

    async def test_execute_search_missing_jql(self):
        from backend.connector.adapters.jira import JiraAdapter
        from backend.connector.models import Capability
        adapter = JiraAdapter()
        result = await adapter.execute(Capability.SEARCH, {})
        assert result.success is False

    async def test_connector_type_and_name(self):
        from backend.connector.adapters.jira import JiraAdapter
        adapter = JiraAdapter()
        assert adapter.connector_type == "jira"
        assert adapter.connector_name == "Jira"


# ==============================================================================
# Slack adapter
# ==============================================================================

class TestSlackAdapter:
    @patch("backend.connector.adapters.slack.httpx.AsyncClient")
    @patch("backend.connector.adapters.slack.os.getenv", return_value="xoxb-test-token")
    async def test_initialize_success(self, mock_getenv, mock_client_cls):
        from backend.connector.adapters.slack import SlackAdapter
        adapter = SlackAdapter()
        mock_client = AsyncMock()
        mock_client_cls.return_value = mock_client
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"ok": True, "user_id": "U123", "user": "TestBot"}
        mock_client.get.return_value = mock_resp
        result = await adapter.initialize()
        assert result is True
        assert adapter._bot_user_id == "U123"

    @patch("backend.connector.adapters.slack.os.getenv", return_value="")
    async def test_initialize_no_token(self, mock_getenv):
        from backend.connector.adapters.slack import SlackAdapter
        adapter = SlackAdapter()
        result = await adapter.initialize()
        assert result is False

    async def test_health_check_unhealthy(self):
        from backend.connector.adapters.slack import SlackAdapter
        from backend.connector.adapter.interfaces import AdapterHealthStatus
        adapter = SlackAdapter()
        status = await adapter.health_check()
        assert status == AdapterHealthStatus.UNHEALTHY

    async def test_capabilities(self):
        from backend.connector.adapters.slack import SlackAdapter
        from backend.connector.models import Capability
        adapter = SlackAdapter()
        caps = await adapter.capabilities()
        assert Capability.NOTIFY in caps
        assert Capability.SEARCH in caps

    async def test_execute_notify_missing_channel(self):
        from backend.connector.adapters.slack import SlackAdapter
        from backend.connector.models import Capability
        adapter = SlackAdapter()
        result = await adapter.execute(Capability.NOTIFY, {})
        assert result.success is False

    async def test_connector_type_and_name(self):
        from backend.connector.adapters.slack import SlackAdapter
        adapter = SlackAdapter()
        assert adapter.connector_type == "slack"
        assert adapter.connector_name == "Slack"


# ==============================================================================
# Kubernetes adapter
# ==============================================================================

class TestKubernetesAdapter:
    async def test_initialize_no_config(self):
        from kubernetes.config import ConfigException
        from backend.connector.adapters.kubernetes import KubernetesAdapter
        adapter = KubernetesAdapter()
        with patch("kubernetes.config.load_incluster_config", side_effect=ConfigException("no cluster")):
            with patch("kubernetes.config.load_kube_config", side_effect=ConfigException("no kubeconfig")):
                with patch("kubernetes.config.list_kube_config_contexts", side_effect=ConfigException("no kubeconfig")):
                    result = await adapter.initialize()
                    assert result is False

    async def test_health_check_unhealthy(self):
        from backend.connector.adapters.kubernetes import KubernetesAdapter
        from backend.connector.adapter.interfaces import AdapterHealthStatus
        adapter = KubernetesAdapter()
        status = await adapter.health_check()
        assert status == AdapterHealthStatus.UNHEALTHY

    async def test_capabilities(self):
        from backend.connector.adapters.kubernetes import KubernetesAdapter
        from backend.connector.models import Capability
        adapter = KubernetesAdapter()
        caps = await adapter.capabilities()
        assert Capability.OBSERVE in caps
        assert Capability.DEPLOY in caps
        assert Capability.SCALE in caps
        assert Capability.RESTART in caps

    async def test_execute_unsupported(self):
        from backend.connector.adapters.kubernetes import KubernetesAdapter
        from backend.connector.models import Capability
        adapter = KubernetesAdapter()
        result = await adapter.execute(Capability.NOTIFY, {})
        assert result.success is False

    async def test_connector_type_and_name(self):
        from backend.connector.adapters.kubernetes import KubernetesAdapter
        adapter = KubernetesAdapter()
        assert adapter.connector_type == "kubernetes"
        assert adapter.connector_name == "Kubernetes"


# ==============================================================================
# Docker adapter
# ==============================================================================

class TestDockerAdapter:
    async def test_initialize_no_docker(self):
        from backend.connector.adapters.docker import DockerAdapter
        adapter = DockerAdapter()
        result = await adapter.initialize()
        assert result is False

    async def test_health_check_unhealthy(self):
        from backend.connector.adapters.docker import DockerAdapter
        from backend.connector.adapter.interfaces import AdapterHealthStatus
        adapter = DockerAdapter()
        status = await adapter.health_check()
        assert status == AdapterHealthStatus.UNHEALTHY

    async def test_capabilities(self):
        from backend.connector.adapters.docker import DockerAdapter
        from backend.connector.models import Capability
        adapter = DockerAdapter()
        caps = await adapter.capabilities()
        assert Capability.OBSERVE in caps
        assert Capability.EXECUTE in caps
        assert Capability.RESTART in caps

    async def test_execute_unsupported(self):
        from backend.connector.adapters.docker import DockerAdapter
        from backend.connector.models import Capability
        adapter = DockerAdapter()
        result = await adapter.execute(Capability.NOTIFY, {})
        assert result.success is False

    async def test_connector_type_and_name(self):
        from backend.connector.adapters.docker import DockerAdapter
        adapter = DockerAdapter()
        assert adapter.connector_type == "docker"
        assert adapter.connector_name == "Docker"


# ==============================================================================
# Prometheus adapter
# ==============================================================================

class TestPrometheusAdapter:
    @patch("backend.connector.adapters.prometheus.httpx.AsyncClient")
    @patch("backend.connector.adapters.prometheus.os.getenv", return_value="http://prometheus:9090")
    async def test_initialize_success(self, mock_getenv, mock_client_cls):
        from backend.connector.adapters.prometheus import PrometheusAdapter
        adapter = PrometheusAdapter()
        mock_client = AsyncMock()
        mock_client_cls.return_value = mock_client
        mock_resp = MagicMock()
        mock_resp.is_success = True
        mock_resp.json.return_value = {"status": "success", "data": {"version": "2.45.0"}}
        mock_client.get.return_value = mock_resp
        result = await adapter.initialize()
        assert result is True

    async def test_initialize_fallback_default(self):
        from backend.connector.adapters.prometheus import PrometheusAdapter
        adapter = PrometheusAdapter()
        with patch.object(adapter, "_client") as mock_client:
            mock_client.get.side_effect = Exception("connection refused")
            result = await adapter.initialize()
            assert result is False

    async def test_health_check_unhealthy(self):
        from backend.connector.adapters.prometheus import PrometheusAdapter
        from backend.connector.adapter.interfaces import AdapterHealthStatus
        adapter = PrometheusAdapter()
        status = await adapter.health_check()
        assert status == AdapterHealthStatus.UNHEALTHY

    async def test_capabilities(self):
        from backend.connector.adapters.prometheus import PrometheusAdapter
        from backend.connector.models import Capability
        adapter = PrometheusAdapter()
        caps = await adapter.capabilities()
        assert Capability.OBSERVE in caps
        assert Capability.SEARCH in caps

    async def test_execute_observe_missing_query(self):
        from backend.connector.adapters.prometheus import PrometheusAdapter
        from backend.connector.models import Capability
        adapter = PrometheusAdapter()
        result = await adapter.execute(Capability.OBSERVE, {})
        assert result.success is False

    async def test_execute_unsupported(self):
        from backend.connector.adapters.prometheus import PrometheusAdapter
        from backend.connector.models import Capability
        adapter = PrometheusAdapter()
        result = await adapter.execute(Capability.DEPLOY, {})
        assert result.success is False

    async def test_connector_type_and_name(self):
        from backend.connector.adapters.prometheus import PrometheusAdapter
        adapter = PrometheusAdapter()
        assert adapter.connector_type == "prometheus"
        assert adapter.connector_name == "Prometheus"

    async def test_shutdown(self):
        from backend.connector.adapters.prometheus import PrometheusAdapter
        adapter = PrometheusAdapter()
        adapter._client = AsyncMock()
        await adapter.shutdown()
        assert adapter._initialized is False


# ==============================================================================
# Grafana adapter
# ==============================================================================

class TestGrafanaAdapter:
    @patch("backend.connector.adapters.grafana.httpx.AsyncClient")
    @patch("backend.connector.adapters.grafana.os.getenv")
    async def test_initialize_success(self, mock_getenv, mock_client_cls):
        def side_effect(key: str, default: str = ""):
            env = {"GRAFANA_URL": "http://grafana:3000", "GRAFANA_API_TOKEN": "glc_test_token"}
            return env.get(key, default)
        mock_getenv.side_effect = side_effect
        from backend.connector.adapters.grafana import GrafanaAdapter
        adapter = GrafanaAdapter()
        mock_client = AsyncMock()
        mock_client_cls.return_value = mock_client
        health_resp = MagicMock()
        health_resp.is_success = True
        org_resp = MagicMock()
        org_resp.is_success = True
        org_resp.json.return_value = {"name": "Test Org"}
        mock_client.get.side_effect = [health_resp, org_resp]
        result = await adapter.initialize()
        assert result is True
        assert adapter._org_name == "Test Org"

    async def test_initialize_fallback_default(self):
        from backend.connector.adapters.grafana import GrafanaAdapter
        adapter = GrafanaAdapter()
        with patch.object(adapter, "_client") as mock_client:
            mock_client.get.side_effect = Exception("connection refused")
            result = await adapter.initialize()
            assert result is False

    async def test_health_check_unhealthy(self):
        from backend.connector.adapters.grafana import GrafanaAdapter
        from backend.connector.adapter.interfaces import AdapterHealthStatus
        adapter = GrafanaAdapter()
        status = await adapter.health_check()
        assert status == AdapterHealthStatus.UNHEALTHY

    async def test_capabilities(self):
        from backend.connector.adapters.grafana import GrafanaAdapter
        from backend.connector.models import Capability
        adapter = GrafanaAdapter()
        caps = await adapter.capabilities()
        assert Capability.OBSERVE in caps
        assert Capability.SEARCH in caps

    async def test_execute_unsupported(self):
        from backend.connector.adapters.grafana import GrafanaAdapter
        from backend.connector.models import Capability
        adapter = GrafanaAdapter()
        result = await adapter.execute(Capability.DEPLOY, {})
        assert result.success is False

    async def test_connector_type_and_name(self):
        from backend.connector.adapters.grafana import GrafanaAdapter
        adapter = GrafanaAdapter()
        assert adapter.connector_type == "grafana"
        assert adapter.connector_name == "Grafana"

    async def test_shutdown(self):
        from backend.connector.adapters.grafana import GrafanaAdapter
        adapter = GrafanaAdapter()
        adapter._client = AsyncMock()
        await adapter.shutdown()
        assert adapter._initialized is False


# ==============================================================================
# Registry integration
# ==============================================================================

class TestAdapterRegistration:
    async def test_registry_accepts_all_adapters(self):
        from backend.connector.registry import ConnectorRegistry
        from backend.connector.adapters import ADAPTER_CLASSES
        registry = ConnectorRegistry()
        for adapter_cls in ADAPTER_CLASSES:
            adapter = adapter_cls()
            registry.register(adapter)
        assert registry.count() == 7

    async def test_registry_list_contains_all(self):
        from backend.connector.registry import ConnectorRegistry
        from backend.connector.adapters import ADAPTER_CLASSES
        registry = ConnectorRegistry()
        for adapter_cls in ADAPTER_CLASSES:
            adapter = adapter_cls()
            registry.register(adapter)
        listing = registry.list()
        types = {e["connector_type"] for e in listing}
        assert "github" in types
        assert "jira" in types
        assert "slack" in types
        assert "kubernetes" in types
        assert "docker" in types
        assert "prometheus" in types
        assert "grafana" in types

    async def test_each_adapter_implements_interface(self):
        from backend.connector.adapters import ADAPTER_CLASSES
        for adapter_cls in ADAPTER_CLASSES:
            adapter = adapter_cls()
            assert adapter.connector_type
            assert adapter.connector_name
            assert adapter.adapter_version

    async def test_each_adapter_has_unique_type(self):
        from backend.connector.adapters import ADAPTER_CLASSES
        types = [cls().connector_type for cls in ADAPTER_CLASSES]
        assert len(types) == len(set(types))

    @patch("backend.connector.di.connector_registry")
    async def test_di_registers_all_adapters(self, mock_registry):
        from backend.connector.di import _register_default_adapters
        mock_registry.count.return_value = 7
        await _register_default_adapters()


# ==============================================================================
# AdapterResult structure
# ==============================================================================

class TestAdapterResultStructure:
    async def test_adapter_result_fields(self):
        from backend.connector.adapter.interfaces import AdapterResult
        result = AdapterResult(success=True, outputs={"key": "value"}, error=None, duration_ms=42.5, metadata={"extra": "info"})
        assert result.success is True
        assert result.outputs["key"] == "value"
        assert result.error is None
        assert result.duration_ms == 42.5
        assert result.metadata["extra"] == "info"

    async def test_adapter_result_defaults(self):
        from backend.connector.adapter.interfaces import AdapterResult
        result = AdapterResult(success=False)
        assert result.outputs == {}
        assert result.error is None
        assert result.duration_ms is None


# ==============================================================================
# AdapterHealthStatus enum
# ==============================================================================

class TestAdapterHealthStatus:
    def test_enum_values(self):
        from backend.connector.adapter.interfaces import AdapterHealthStatus
        assert AdapterHealthStatus.HEALTHY.value == "healthy"
        assert AdapterHealthStatus.DEGRADED.value == "degraded"
        assert AdapterHealthStatus.UNHEALTHY.value == "unhealthy"
        assert AdapterHealthStatus.UNKNOWN.value == "unknown"

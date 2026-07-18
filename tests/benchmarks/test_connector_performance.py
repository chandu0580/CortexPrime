import pytest
import httpx
import contextlib
from unittest.mock import AsyncMock, patch, MagicMock
from tests.benchmarks.benchmark_utils import BenchmarkRunner


CONNECTOR_TYPES = ["github", "jira", "slack", "teams", "azure_devops", "confluence", "notion", "servicenow"]


@pytest.fixture
def bench():
    return BenchmarkRunner(iterations=30, warmup=5)


@pytest.mark.asyncio
async def test_connector_initialization_benchmark(bench):
    for ctype in CONNECTOR_TYPES:
        with patch("httpx.AsyncClient") as mock_client:
            mock_client.return_value = AsyncMock()
            mock_client.return_value.get = AsyncMock(
                return_value=MagicMock(status_code=200, json=lambda: {})
            )
            mock_client.return_value.__aenter__ = AsyncMock(return_value=mock_client.return_value)
            mock_client.return_value.__aexit__ = AsyncMock()

            import importlib
            connector_map = {
                "github": "backend.connectors.github.GitHubConnector",
                "jira": "backend.connectors.jira.JiraConnector",
                "slack": "backend.connectors.slack.SlackConnector",
                "teams": "backend.connectors.teams.TeamsConnector",
                "azure_devops": "backend.connectors.azure_devops.AzureDevOpsConnector",
                "confluence": "backend.connectors.confluence.ConfluenceConnector",
                "notion": "backend.connectors.notion.NotionConnector",
                "servicenow": "backend.connectors.servicenow.ServiceNowConnector",
            }
            mod_path, cls_name = connector_map[ctype].rsplit(".", 1)
            mod = importlib.import_module(mod_path)
            cls = getattr(mod, cls_name)
            instance = cls()

            with patch.object(instance, "_load_credentials", return_value={"token": "test"}):
                await bench.run_async(
                    f"Connector init — {ctype}",
                    instance.initialize,
                    iterations=20,
                )

    report = bench.report()
    print("\n--- Connector Initialization Benchmarks ---\n")
    print(report)


@pytest.mark.asyncio
async def test_connector_health_benchmark(bench):
    for ctype in CONNECTOR_TYPES:
        import importlib
        connector_map = {
            "github": "backend.connectors.github.GitHubConnector",
            "jira": "backend.connectors.jira.JiraConnector",
            "slack": "backend.connectors.slack.SlackConnector",
            "teams": "backend.connectors.teams.TeamsConnector",
            "azure_devops": "backend.connectors.azure_devops.AzureDevOpsConnector",
            "confluence": "backend.connectors.confluence.ConfluenceConnector",
            "notion": "backend.connectors.notion.NotionConnector",
            "servicenow": "backend.connectors.servicenow.ServiceNowConnector",
        }
        mod_path, cls_name = connector_map[ctype].rsplit(".", 1)
        mod = importlib.import_module(mod_path)
        cls = getattr(mod, cls_name)
        instance = cls()
        instance._available = True

        await bench.run_async(
            f"Connector health — {ctype}",
            instance.health,
            iterations=30,
        )

    report = bench.report()
    print("\n--- Connector Health Benchmarks ---\n")
    print(report)


@pytest.mark.asyncio
async def test_connector_operations_enumeration(bench):
    for ctype in CONNECTOR_TYPES:
        import importlib
        connector_map = {
            "github": "backend.connectors.github.GitHubConnector",
            "jira": "backend.connectors.jira.JiraConnector",
            "slack": "backend.connectors.slack.SlackConnector",
            "teams": "backend.connectors.teams.TeamsConnector",
            "azure_devops": "backend.connectors.azure_devops.AzureDevOpsConnector",
            "confluence": "backend.connectors.confluence.ConfluenceConnector",
            "notion": "backend.connectors.notion.NotionConnector",
            "servicenow": "backend.connectors.servicenow.ServiceNowConnector",
        }
        mod_path, cls_name = connector_map[ctype].rsplit(".", 1)
        mod = importlib.import_module(mod_path)
        cls = getattr(mod, cls_name)
        instance = cls()

        bench.run_sync(
            f"Connector get_operations — {ctype}",
            instance.get_operations,
            iterations=50,
        )

    report = bench.report()
    print("\n--- Connector Operations Enumeration Benchmarks ---\n")
    print(report)


@pytest.mark.asyncio
def _mock_resp(status_code, json_data):
    m = MagicMock()
    m.status_code = status_code
    m.json = lambda: json_data
    return m


@pytest.mark.asyncio
async def test_connector_execution_with_retry(bench):
    from backend.connectors.github import GitHubConnector

    instance = GitHubConnector()
    instance._client = AsyncMock()
    async def _mock_request(method, path, **kw):
        return MagicMock(status_code=200, json=lambda: {"id": 1, "name": "repo1"})
    instance._client.request = _mock_request
    instance._headers = {"Authorization": "Bearer test"}

    with contextlib.ExitStack() as stack:
        stack.enter_context(patch.object(instance, "_load_credentials", return_value={"token": "test"}))
        stack.enter_context(patch("backend.connectors.activity_service.ConnectorActivityService.record", AsyncMock()))
        await bench.run_async(
            "Connector execution — list_repositories (success)",
            lambda: instance.list_repositories("test-owner"),
            iterations=30,
        )

    report = bench.report()
    print("\n--- Connector Execution Benchmarks ---\n")
    print(report)


@pytest.mark.asyncio
async def test_connector_retry_behavior(bench):
    from backend.connectors.github import GitHubConnector

    instance = GitHubConnector()
    instance._client = AsyncMock()
    _call_count = [0]
    async def _mock_retry_request(method, path, **kw):
        _call_count[0] += 1
        if _call_count[0] <= 2:
            return MagicMock(status_code=502, json=lambda: {})
        return MagicMock(status_code=200, json=lambda: [{"name": "repo1"}])
    instance._client.request = _mock_retry_request
    instance._headers = {"Authorization": "Bearer test"}

    with contextlib.ExitStack() as stack:
        stack.enter_context(patch.object(instance, "_load_credentials", return_value={"token": "test"}))
        stack.enter_context(patch("backend.connectors.activity_service.ConnectorActivityService.record", AsyncMock()))
        await bench.run_async(
            "Connector retry — 502 x2 then success",
            lambda: instance.list_repositories("test-owner"),
            iterations=10,
        )

    report = bench.report()
    print("\n--- Connector Retry Benchmarks ---\n")
    print(report)


@pytest.mark.asyncio
async def test_connector_failure_recovery(bench):
    from backend.connectors.github import GitHubConnector

    instance = GitHubConnector()
    instance._client = AsyncMock()
    async def _mock_fail_request(method, path, **kw):
        raise httpx.RequestError("connection refused", request=MagicMock())
    instance._client.request = _mock_fail_request
    instance._headers = {"Authorization": "Bearer test"}

    with contextlib.ExitStack() as stack:
        stack.enter_context(patch.object(instance, "_load_credentials", return_value={"token": "test"}))
        stack.enter_context(patch("backend.connectors.activity_service.ConnectorActivityService.record", AsyncMock()))
        with pytest.raises(RuntimeError):
            await instance.list_repositories("test-owner")

    report = bench.report()
    print("\n--- Connector Failure Recovery Benchmarks ---\n")
    print(report)


@pytest.mark.asyncio
async def test_credential_service_performance(bench):
    from backend.services.credential_service import CredentialService

    svc = CredentialService()
    bench.run_sync(
        "CredentialService — store + load",
        lambda: (svc.store("test_connector", {"token": "test-123", "url": "https://example.com"}),
                 svc.load("test_connector")),
        iterations=50,
    )

    bench.run_sync(
        "CredentialService — exists + remove",
        lambda: (svc.exists("test_connector"), svc.remove("test_connector")),
        iterations=50,
    )

    report = bench.report()
    print("\n--- Credential Service Benchmarks ---\n")
    print(report)


@pytest.mark.asyncio
async def test_connector_registry_benchmark(bench):
    from backend.connectors.registry import ConnectorRegistry

    registry = ConnectorRegistry()
    mock_connectors = {}
    for ctype in CONNECTOR_TYPES:
        mock_conn = MagicMock()
        mock_conn.connector_type = ctype
        mock_conn.get_operations.return_value = {"op1": {"description": "op1", "required_params": []}}
        mock_conn.health = AsyncMock(return_value={"status": "available"})
        mock_conn.initialize = AsyncMock(return_value=True)
        mock_conn.shutdown = AsyncMock(return_value=True)
        registry.register(mock_conn)
        mock_connectors[ctype] = mock_conn

    bench.run_sync(
        "ConnectorRegistry — get_all_operations (8 connectors)",
        registry.get_all_operations,
        iterations=50,
    )

    bench.run_sync(
        "ConnectorRegistry — get_capabilities_prompt (8 connectors)",
        registry.get_capabilities_prompt,
        iterations=50,
    )

    bench.run_sync(
        "ConnectorRegistry — validate_operation",
        lambda: registry.validate_operation("github", "op1", {}),
        iterations=100,
    )

    report = bench.report()
    print("\n--- Connector Registry Benchmarks ---\n")
    print(report)

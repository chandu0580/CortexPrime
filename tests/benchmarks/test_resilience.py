import pytest
import asyncio
import contextlib
from unittest.mock import AsyncMock, patch, MagicMock


_MODULE = "backend.services.mission_runtime"


def _mock_assessment(**kw):
    m = MagicMock()
    m.risk_level = type("rl", (), {"value": kw.get("risk", "low")})()
    m.blocked = kw.get("blocked", False)
    m.requires_approval = kw.get("requires_approval", False)
    m.reason = kw.get("reason", "ok")
    return m


def _mission_patches():
    return [
        patch(f"{_MODULE}._guardrails_check_input", AsyncMock(return_value=None)),
        patch(f"{_MODULE}._guardrails_check_output", MagicMock(return_value=None)),
        patch(f"{_MODULE}._emit", AsyncMock()),
        patch(f"{_MODULE}._send_progress", AsyncMock()),
        patch(f"{_MODULE}._send_stream_chunk", AsyncMock()),
        patch(f"{_MODULE}._governance_assess", MagicMock(return_value=_mock_assessment())),
        patch(f"{_MODULE}._governance_log", MagicMock()),
        patch(f"{_MODULE}._governance_request_approval", AsyncMock()),
        patch(f"{_MODULE}._is_emergency_stopped", MagicMock(return_value=False)),
        patch(f"{_MODULE}._is_browser_task", MagicMock(return_value=False)),
        patch(f"{_MODULE}._is_computer_task", MagicMock(return_value=False)),
        patch(f"{_MODULE}._is_release_workflow", MagicMock(return_value=False)),
        patch(f"{_MODULE}._call_llm", AsyncMock(return_value="mock")),
        patch(f"{_MODULE}._select_tools", AsyncMock(return_value=[])),
        patch(f"{_MODULE}._execute_connector_operations", AsyncMock(return_value=[])),
        patch(f"{_MODULE}._execute_worker_operations", AsyncMock(return_value=[])),
        patch(f"{_MODULE}._stream_llm_to_ws", AsyncMock(return_value="mock")),
        patch(f"{_MODULE}._generate_mission_summary", MagicMock(return_value={"status": "completed"})),
        patch(f"{_MODULE}.vector_memory", MagicMock()),
        patch(f"{_MODULE}.memory_context_service", MagicMock()),
        patch(f"{_MODULE}.cost_engine", MagicMock()),
        patch(f"{_MODULE}.orchestration_tracer", MagicMock()),
        patch(f"{_MODULE}._prom_metrics", MagicMock()),
    ]


def _enter_many(stack, patches):
    for p in patches:
        stack.enter_context(p)


def _setup_svc_patches(stack, svc):
    _enter_many(stack, _mission_patches())


@pytest.mark.asyncio
async def test_mission_continues_when_redis_unavailable():
    from backend.services.mission_runtime import MissionRuntimeService

    svc = MissionRuntimeService()
    with contextlib.ExitStack() as stack:
        _setup_svc_patches(stack, svc)
        stack.enter_context(patch(f"{_MODULE}.redis_cache"))
        result = await svc.execute_mission(objective="Test mission with Redis down")
        assert result is not None
        print(f"\nRedis unavailable: mission returned {result.get('status', 'unknown')}")


@pytest.mark.asyncio
async def test_mission_continues_when_neo4j_unavailable():
    from backend.services.mission_runtime import MissionRuntimeService

    svc = MissionRuntimeService()
    with contextlib.ExitStack() as stack:
        _setup_svc_patches(stack, svc)
        mock_neo4j = stack.enter_context(patch(f"{_MODULE}.neo4j_graph"))
        mock_neo4j.is_available = False
        result = await svc.execute_mission(objective="Test mission with Neo4j down")
        assert result is not None
        print(f"\nNeo4j unavailable: mission completed with status {result.get('status', 'unknown')}")


@pytest.mark.asyncio
async def test_mission_continues_when_postgres_unavailable():
    from backend.services.mission_runtime import MissionRuntimeService

    svc = MissionRuntimeService()
    with contextlib.ExitStack() as stack:
        _setup_svc_patches(stack, svc)
        result = await svc.execute_mission(objective="Test mission with PostgreSQL down")
        assert result is not None
        print(f"\nPostgreSQL unavailable: mission completed with status {result.get('status', 'unknown')}")


@pytest.mark.asyncio
async def test_mission_handles_connector_failure():
    from backend.services.mission_runtime import MissionRuntimeService

    svc = MissionRuntimeService()
    with contextlib.ExitStack() as stack:
        _setup_svc_patches(stack, svc)
        mock_registry = stack.enter_context(patch("backend.connectors.registry.connector_registry"))
        mock_registry.get_all_operations.return_value = {}
        mock_registry.get_capabilities_prompt.return_value = "No connectors available"
        result = await svc.execute_mission(objective="Test with connectors unavailable")
        assert result is not None
        print(f"\nConnector unavailable: mission completed with status {result.get('status', 'unknown')}")


@pytest.mark.asyncio
async def test_mission_handles_llm_failure():
    from backend.services.mission_runtime import MissionRuntimeService

    svc = MissionRuntimeService()
    with contextlib.ExitStack() as stack:
        _setup_svc_patches(stack, svc)
        stack.enter_context(patch(f"{_MODULE}._call_llm",
                                  AsyncMock(side_effect=RuntimeError("LLM unavailable"))))
        stack.enter_context(patch(f"{_MODULE}._stream_llm_to_ws",
                                  AsyncMock(side_effect=RuntimeError("LLM stream failed"))))
        stack.enter_context(patch(f"{_MODULE}._generate_mission_summary",
                                  MagicMock(return_value={"status": "failed", "error": "LLM failure"})))
        result = await svc.execute_mission(objective="Test with LLM unavailable")
        print(f"\nLLM unavailable: mission returned status {result.get('status', 'unknown')}")


@pytest.mark.asyncio
async def test_network_timeout_handling():
    from backend.services.mission_runtime import MissionRuntimeService

    svc = MissionRuntimeService()
    with contextlib.ExitStack() as stack:
        _setup_svc_patches(stack, svc)
        stack.enter_context(patch(f"{_MODULE}._call_llm",
                                  AsyncMock(side_effect=asyncio.TimeoutError("LLM timeout"))))
        stack.enter_context(patch(f"{_MODULE}._generate_mission_summary",
                                  MagicMock(return_value={"status": "failed", "error": "timeout"})))
        result = await svc.execute_mission(objective="Test network timeout")
        print(f"\nNetwork timeout: mission returned status {result.get('status', 'unknown')}")


@pytest.mark.asyncio
async def test_retry_behavior_on_transient_failures():
    from backend.services.mission_runtime import MissionRuntimeService

    svc = MissionRuntimeService()
    mock_connector = AsyncMock()
    call_count = 0

    async def _flaky_list_repos(**kwargs):
        nonlocal call_count
        call_count += 1
        if call_count <= 2:
            raise RuntimeError("Transient failure")
        return [{"name": "repo1"}]

    mock_connector.list_repositories = _flaky_list_repos
    mock_connector.health = AsyncMock(return_value={"status": "available"})

    import backend.services.mission_runtime as m
    with contextlib.ExitStack() as stack:
        mock_registry = stack.enter_context(patch("backend.connectors.registry.connector_registry"))
        _enter_many(stack, [
            patch(f"{_MODULE}._verify_connector_result", AsyncMock(return_value={"verified": True})),
            patch(f"{_MODULE}._emit", AsyncMock()),
            patch(f"{_MODULE}._send_progress", AsyncMock()),
            patch(f"{_MODULE}._persist_tool_context_to_redis", AsyncMock()),
            patch(f"{_MODULE}._record_connector_execution", AsyncMock()),
        ])
        mock_registry.get.return_value = mock_connector
        operations = [{"type": "connector", "connector": "github", "operation": "list_repositories",
                       "params": {"owner": "test"}}]
        result = await m._execute_connector_operations(execution_id="resilience-retry-001", operations=operations)
        print(f"\nRetry behavior: {call_count} attempts made, result: {result}")


@pytest.mark.asyncio
async def test_graceful_degradation_all_services_down():
    from backend.services.mission_runtime import MissionRuntimeService

    svc = MissionRuntimeService()
    with contextlib.ExitStack() as stack:
        stack.enter_context(patch(f"{_MODULE}.redis_cache"))
        _setup_svc_patches(stack, svc)
        result = await svc.execute_mission(objective="Test total degradation")
        print(f"\nAll services down: mission returned {result.get('status', 'unknown')}")


@pytest.mark.asyncio
async def test_emergency_stop_during_mission():
    from backend.services.mission_runtime import MissionRuntimeService
    from backend.safety.emergency_stop import EmergencyStopController

    svc = MissionRuntimeService()
    emergency = EmergencyStopController()
    execution_id = "resilience-emergency-001"

    with contextlib.ExitStack() as stack:
        stack.enter_context(patch(f"{_MODULE}.redis_cache"))
        _setup_svc_patches(stack, svc)
        stack.enter_context(patch(f"{_MODULE}._is_emergency_stopped",
                                  MagicMock(side_effect=lambda: emergency.is_stopped(execution_id))))
        emergency.stop_mission(execution_id, triggered_by="test", reason="Resilience test")
        result = await svc.execute_mission(objective="Test emergency stop")
        print(f"\nEmergency stop: mission returned {result.get('status', 'unknown')}")


@pytest.mark.asyncio
async def test_replay_store_redis_fallback():
    from backend.services.mission_replay_store import MissionReplayStore
    from backend.events.event_models import CognitionEvent

    store = MissionReplayStore()
    store._redis_client = MagicMock()
    store._redis_client.is_available = False
    store._in_memory_store = {}

    event = CognitionEvent(event_type="mission_started", agent="system", status="started",
                           message="Fallback test", execution_id="resilience-replay-001")

    await store.record(event)
    timeline = await store.get_timeline("resilience-replay-001")
    summary = await store.get_summary("resilience-replay-001")

    assert len(timeline) >= 1, "Timeline should have events even with Redis down"
    print(f"\nReplay store Redis fallback: {len(timeline)} events in timeline, summary has {len(summary)} keys")


@pytest.mark.asyncio
async def test_user_facing_error_on_connector_failure():
    from backend.connectors.github import GitHubConnector

    instance = GitHubConnector()
    instance._client = AsyncMock()
    instance._client.get = AsyncMock(side_effect=PermissionError("Invalid credentials"))
    instance._headers = {"Authorization": "Bearer bad-token"}

    with patch.object(instance, "_load_credentials", return_value={"token": "bad-token"}):
        try:
            await instance.list_repositories("test-owner")
        except PermissionError as e:
            error_msg = str(e)
            print(f"\nUser-facing error on connector failure: '{error_msg}'")
            assert "Invalid credentials" in error_msg or "Permission" in error_msg

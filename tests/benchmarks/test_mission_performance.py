import pytest
import contextlib
from unittest.mock import AsyncMock, patch, MagicMock
from tests.benchmarks.benchmark_utils import BenchmarkRunner


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
        patch(f"{_MODULE}._call_llm", AsyncMock(return_value="mock LLM response")),
        patch(f"{_MODULE}._select_tools", AsyncMock(return_value=[])),
        patch(f"{_MODULE}._execute_connector_operations", AsyncMock(return_value=[])),
        patch(f"{_MODULE}._execute_worker_operations", AsyncMock(return_value=[])),
        patch(f"{_MODULE}._stream_llm_to_ws", AsyncMock(return_value="mock stream")),
        patch(f"{_MODULE}._generate_mission_summary", MagicMock(return_value={"status": "completed"})),
        patch(f"{_MODULE}.vector_memory", MagicMock()),
        patch(f"{_MODULE}.memory_context_service", MagicMock()),
        patch(f"{_MODULE}.cost_engine", MagicMock()),
        patch(f"{_MODULE}.orchestration_tracer", MagicMock()),
        patch(f"{_MODULE}._prom_metrics", MagicMock()),
        patch(f"{_MODULE}.runtime_state", MagicMock()),
        patch(f"{_MODULE}.runtime_state_store", MagicMock()),
        patch(f"{_MODULE}.neo4j_graph", MagicMock()),
    ]


def _enter_many(stack, patches):
    for p in patches:
        stack.enter_context(p)


@pytest.fixture
def bench():
    return BenchmarkRunner(iterations=50, warmup=5)


@pytest.mark.asyncio
async def test_mission_creation_performance(bench):
    from backend.services.mission_runtime import MissionRuntimeService

    svc = MissionRuntimeService()
    with contextlib.ExitStack() as stack:
        _enter_many(stack, _mission_patches())
        await bench.run_async(
            "MissionRuntimeService.execute_mission — cold start",
            svc.execute_mission,
            iterations=20,
            kwargs={"objective": "analyze Q3 revenue trends"},
        )

    assert bench.results
    report = bench.report()
    print("\n--- Mission Performance Benchmarks ---\n")
    print(report)


@pytest.mark.skip(reason="Requires deep dependency injection for _run_pipeline internals")
@pytest.mark.asyncio
async def test_planning_stage_latency(bench):
    from backend.services.mission_runtime import MissionRuntimeService

    svc = MissionRuntimeService()
    with contextlib.ExitStack() as stack:
        _enter_many(stack, _mission_patches())
        await bench.run_async(
            "Planning stage — LLM call + state update",
            svc._run_pipeline,
            iterations=20,
            kwargs={"execution_id": "perf-001", "objective": "analyze Q3 revenue trends",
                    "session_id": "sess-001"},
        )

    report = bench.report()
    print("\n--- Planning Stage Benchmarks ---\n")
    print(report)


@pytest.mark.asyncio
async def test_tool_selection_performance(bench):
    with contextlib.ExitStack() as stack:
        stack.enter_context(patch(f"{_MODULE}._build_tool_selector_system_prompt", MagicMock(return_value="prompt")))
        stack.enter_context(patch(f"{_MODULE}._call_llm",
                                  AsyncMock(return_value='[{"connector":"github","operation":"list_repos"}]')))
        stack.enter_context(patch(f"{_MODULE}._parse_tool_selection",
                                  MagicMock(return_value=[{"type": "connector", "connector": "github"}])))
        stack.enter_context(patch(f"{_MODULE}._validate_tool_selection_with_capabilities", MagicMock(return_value=True)))
        stack.enter_context(patch("backend.connectors.registry.connector_registry", MagicMock()))
        import backend.services.mission_runtime as m
        await bench.run_async(
            "Tool selection — LLM + parse + validate",
            m._select_tools,
            iterations=30,
            kwargs={"execution_id": "perf-002", "objective": "analyze Q3 revenue", "plan_text": "1. Gather data"},
        )

    report = bench.report()
    print("\n--- Tool Selection Benchmarks ---\n")
    print(report)


@pytest.mark.asyncio
async def test_connector_execution_chain(bench):
    import backend.services.mission_runtime as m

    mock_connector = AsyncMock()
    mock_connector.health = AsyncMock(return_value={"status": "available"})
    mock_connector.list_repositories = AsyncMock(return_value=[{"name": "repo1"}, {"name": "repo2"}])

    with contextlib.ExitStack() as stack:
        mock_registry = stack.enter_context(patch("backend.connectors.registry.connector_registry"))
        stack.enter_context(patch(f"{_MODULE}._verify_connector_result", AsyncMock(return_value={"verified": True})))
        stack.enter_context(patch(f"{_MODULE}._emit", AsyncMock()))
        stack.enter_context(patch(f"{_MODULE}._send_progress", AsyncMock()))
        stack.enter_context(patch(f"{_MODULE}._persist_tool_context_to_redis", AsyncMock()))
        stack.enter_context(patch(f"{_MODULE}._record_connector_execution", AsyncMock()))
        mock_registry.get.return_value = mock_connector
        operations = [{"type": "connector", "name": "github", "operation": "list_repositories", "params": {"owner": "test"}}]
        await bench.run_async(
            "Connector execution — single operation",
            m._execute_connector_operations,
            iterations=30,
            kwargs={"execution_id": "perf-003", "operations": operations},
        )

    report = bench.report()
    print("\n--- Connector Execution Benchmarks ---\n")
    print(report)


@pytest.mark.asyncio
async def test_verification_performance(bench):
    from backend.services.verification_service import VerificationService

    svc = VerificationService()
    mock_connector = AsyncMock()
    mock_connector.get_repository = AsyncMock(return_value={"id": 1, "name": "test-repo"})
    svc._get_verify_fn = MagicMock(return_value=("get_repository", {"owner": "test", "repo": "test-repo"}))

    await bench.run_async(
        "Verification — single operation",
        svc.verify_operation,
        iterations=30,
        kwargs={"connector": mock_connector, "operation": "create_repository",
                "params": {"owner": "test", "repo": "test-repo", "description": "test"},
                "execution_id": "perf-004"},
    )

    report = bench.report()
    print("\n--- Verification Benchmarks ---\n")
    print(report)


@pytest.mark.asyncio
async def test_replay_generation_performance(bench):
    from backend.services.mission_replay_store import MissionReplayStore

    store = MissionReplayStore()
    store._mem = {}
    store._seq = {}

    events = [
        {"event_type": "mission_started", "agent": "system", "status": "started", "message": "Mission started"},
        {"event_type": "planning_started", "agent": "planner", "status": "running", "message": "Planning phase"},
        {"event_type": "tool_called", "agent": "github", "status": "completed", "message": "Tool execution"},
        {"event_type": "mission_completed", "agent": "system", "status": "completed", "message": "Mission completed"},
    ]
    from backend.events.event_models import CognitionEvent
    for evt in events:
        ce = CognitionEvent(**evt)
        seq = len(store._mem.get("perf-replay-001", []))
        store._seq["perf-replay-001"] = seq
        store._mem.setdefault("perf-replay-001", [])
        store._mem["perf-replay-001"].append({
            "event_id": ce.event_id,
            "execution_id": "perf-replay-001",
            "event_type": evt["event_type"],
            "agent": evt["agent"],
            "status": evt["status"],
            "message": evt["message"],
            "timestamp": ce.timestamp,
            "sequence": seq + 1,
            "payload": {},
        })

    await bench.run_async("Replay — get_timeline (4 events)", store.get_timeline, iterations=50,
                          kwargs={"execution_id": "perf-replay-001"})
    await bench.run_async("Replay — get_summary (4 events)", store.get_summary, iterations=50,
                          kwargs={"execution_id": "perf-replay-001"})
    await bench.run_async("Replay — get_graph (4 events)", store.get_graph, iterations=50,
                          kwargs={"execution_id": "perf-replay-001"})

    report = bench.report()
    print("\n--- Replay/Timeline Benchmarks ---\n")
    print(report)


@pytest.mark.asyncio
async def test_memory_update_performance(bench):
    from backend.services.memory_context_service import MemoryContextService

    svc = MemoryContextService()
    with contextlib.ExitStack() as stack:
        mock_orch = MagicMock()
        mock_orch.retrieve_context = AsyncMock(return_value="episodic memory")
        mock_orch.search_memories = AsyncMock(return_value="semantic memory")
        mock_orch.init_session = AsyncMock()
        stack.enter_context(patch("backend.memory.memory_orchestrator.memory_orchestrator", mock_orch))
        stack.enter_context(patch("backend.services.memory_context_service._get_vector_memory", MagicMock()))

        await bench.run_async("Memory — retrieve_for_mission", svc.retrieve_for_mission, iterations=30,
                              kwargs={"objective": "analyze Q3 revenue", "session_id": "sess-001",
                                      "execution_id": "perf-005"})

    report = bench.report()
    print("\n--- Memory Update Benchmarks ---\n")
    print(report)


@pytest.mark.asyncio
async def test_full_mission_lifecycle_benchmark(bench):
    from backend.services.mission_runtime import MissionRuntimeService

    svc = MissionRuntimeService()
    with contextlib.ExitStack() as stack:
        _enter_many(stack, _mission_patches())
        await bench.run_async("Full mission lifecycle — e2e mocked", svc.execute_mission, iterations=15,
                              kwargs={"objective": "analyze Q3 revenue trends"})

    report = bench.report()
    print("\n--- Full Mission Lifecycle Benchmarks ---\n")
    print(report)

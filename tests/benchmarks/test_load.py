import pytest
import asyncio
import time
import contextlib
from unittest.mock import AsyncMock, patch, MagicMock
from tests.benchmarks.benchmark_utils import BenchmarkRunner


CONCURRENCY_LEVELS = [10, 50, 100]


_MODULE = "backend.services.mission_runtime"


def _mock_assessment(**kw):
    m = MagicMock()
    m.risk_level = type("rl", (), {"value": kw.get("risk", "low")})()
    m.blocked = kw.get("blocked", False)
    m.requires_approval = kw.get("requires_approval", False)
    m.reason = kw.get("reason", "ok")
    return m


def _default_mission_patches():
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


@pytest.mark.asyncio
async def test_concurrent_mission_creation():
    """Phase 5: Execute concurrent missions at 10, 50, 100 concurrency."""
    from backend.services.mission_runtime import MissionRuntimeService

    svc = MissionRuntimeService()
    results = {}

    for concurrency in CONCURRENCY_LEVELS:
        with contextlib.ExitStack() as stack:
            _enter_many(stack, _default_mission_patches())
            start = time.monotonic()
            tasks = [svc.execute_mission(objective=f"Concurrent mission {i}") for i in range(concurrency)]
            outcomes = await asyncio.gather(*tasks, return_exceptions=True)
            elapsed = (time.monotonic() - start) * 1000

            failures = sum(1 for o in outcomes if isinstance(o, Exception))
            results[concurrency] = {
                "concurrency": concurrency,
                "total_time_ms": round(elapsed, 2),
                "avg_per_mission_ms": round(elapsed / concurrency, 2) if concurrency else 0,
                "failures": failures,
                "success_rate": round((concurrency - failures) / concurrency * 100, 1),
            }

    print("\n" + "=" * 80)
    print("  LOAD TEST RESULTS: Concurrent Mission Execution")
    print("=" * 80)
    header = f"{'Concurrency':<15} {'Total Time (ms)':<20} {'Avg/Mission (ms)':<20} {'Failures':<12} {'Success Rate':<15}"
    print(header)
    print("-" * 80)
    for conc, data in sorted(results.items()):
        print(f"{data['concurrency']:<15} {data['total_time_ms']:<20.2f} {data['avg_per_mission_ms']:<20.2f} "
              f"{data['failures']:<12} {data['success_rate']:<15.1f}%")
    print("=" * 80)

    assert all(r["success_rate"] >= 90 for r in results.values()), \
        f"Success rate below 90%: {results}"


@pytest.mark.asyncio
async def test_approval_queue_concurrent_load():
    """Phase 5: Load test the approval queue with concurrent requests."""
    from backend.safety.approval_queue import ApprovalQueue

    with patch("backend.safety.approval_queue._emit_governance_event", AsyncMock()):
        for concurrency in [10, 50, 100]:
            queue = ApprovalQueue()
            start = time.monotonic()

            async def _submit_request(i):
                try:
                    await asyncio.wait_for(
                        queue.request(execution_id=f"load-exec-{i}", agent="orchestrator",
                                      action="test", description=f"Load test {i}",
                                      risk_level="low", timeout=0.2),
                        timeout=0.3)
                except (asyncio.TimeoutError, Exception):
                    pass

            tasks = [_submit_request(i) for i in range(concurrency)]
            results = await asyncio.gather(*tasks, return_exceptions=True)
            elapsed = (time.monotonic() - start) * 1000
            pending = queue.get_pending()

            print(f"\nApprovalQueue Load Test ({concurrency} concurrent): {elapsed:.2f}ms total, "
                  f"{len(pending)} pending, {sum(1 for r in results if isinstance(r, Exception))} exceptions")


@pytest.mark.asyncio
async def test_workflow_engine_concurrent_load():
    """Phase 5: Load test the workflow engine with concurrent workflow creations."""
    from backend.approval_center.workflows import ApprovalWorkflowEngine

    for concurrency in [10, 50]:
        engine = ApprovalWorkflowEngine()
        from backend.approval_center.models import RiskLevel
        with contextlib.ExitStack() as stack:
            _enter_many(stack, [
                patch.object(engine, "_emit_event", AsyncMock()),
                patch.object(engine, "_audit", AsyncMock()),
                patch.object(engine, "_schedule_escalation", MagicMock()),
                patch.object(engine, "_schedule_expiration", MagicMock()),
            ])
            start = time.monotonic()
            tasks = [
                engine.create_workflow(execution_id=f"load-wf-{i}", mission_id="mission-load",
                                       objective=f"Load test workflow {i}",
                                       risk_level=RiskLevel.MEDIUM if i % 2 == 0 else RiskLevel.HIGH)
                for i in range(concurrency)
            ]
            results = await asyncio.gather(*tasks, return_exceptions=True)
            elapsed = (time.monotonic() - start) * 1000
            failures = sum(1 for r in results if isinstance(r, Exception))
            print(f"\nWorkflowEngine Load Test ({concurrency} concurrent): {elapsed:.2f}ms total, {failures} failures")


@pytest.mark.asyncio
async def test_connector_registry_concurrent_access():
    """Phase 5: Load test the connector registry with concurrent operations."""
    from backend.connectors.registry import ConnectorRegistry

    registry = ConnectorRegistry()
    for ctype in ["github", "jira", "slack", "teams", "azure_devops", "confluence", "notion", "servicenow"]:
        mock_conn = MagicMock()
        mock_conn.connector_type = ctype
        mock_conn.get_operations.return_value = {"op": {"description": "test", "required_params": []}}
        registry.register(mock_conn)

    for concurrency in [50]:
        start = time.monotonic()
        results = []
        for i in range(concurrency):
            try:
                if i % 2 == 0:
                    registry.get_all_operations()
                else:
                    registry.get_capabilities_prompt()
                results.append(None)
            except Exception as e:
                results.append(e)
        elapsed = (time.monotonic() - start) * 1000
        failures = sum(1 for r in results if isinstance(r, Exception))
        print(f"\nConnectorRegistry Load Test ({concurrency} concurrent ops): {elapsed:.2f}ms total, {failures} failures")


@pytest.mark.asyncio
async def test_event_bus_concurrent_publish():
    """Phase 5: Load test the event bus with concurrent publishes."""
    from backend.events.event_bus import EventBus
    from backend.events.event_models import CognitionEvent

    bus = EventBus()
    bus._handlers = [AsyncMock() for _ in range(3)]

    event = CognitionEvent(event_type="load_test", agent="load-tester", status="running", message="Load test")

    for concurrency in [50, 100, 250]:
        start = time.monotonic()
        tasks = [bus.publish(event) for _ in range(concurrency)]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        elapsed = (time.monotonic() - start) * 1000
        failures = sum(1 for r in results if isinstance(r, Exception))
        print(f"\nEventBus Load Test ({concurrency} concurrent publishes): {elapsed:.2f}ms total, "
              f"{failures} failures, {concurrency / (elapsed / 1000):.0f} events/sec")


@pytest.mark.asyncio
async def test_verification_service_concurrent():
    """Phase 5: Load test the verification service."""
    from backend.services.verification_service import VerificationService

    svc = VerificationService()
    mock_connector = AsyncMock()
    mock_connector.get_repository = AsyncMock(return_value={"id": 1, "name": "test"})
    svc._get_verify_fn = MagicMock(return_value=("get_repository", {"owner": "test", "repo": "test-repo"}))

    for concurrency in [50]:
        start = time.monotonic()
        tasks = [
            svc.verify_operation(connector=mock_connector, operation="create_repository",
                                 params={"owner": "test", "repo": "test-repo"},
                                 execution_id=f"load-verify-{i}")
            for i in range(concurrency)
        ]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        elapsed = (time.monotonic() - start) * 1000
        failures = sum(1 for r in results if isinstance(r, Exception))
        print(f"\nVerificationService Load Test ({concurrency} concurrent): {elapsed:.2f}ms total, {failures} failures")

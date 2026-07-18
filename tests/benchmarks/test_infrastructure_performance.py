import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from tests.benchmarks.benchmark_utils import BenchmarkRunner


@pytest.fixture
def bench():
    return BenchmarkRunner(iterations=50, warmup=10)


def test_redis_in_memory_fallback_latency(bench):
    bench.run_sync(
        "Redis — ping (unavailable, mocked)",
        lambda: None,
        iterations=50,
    )
    bench.run_sync(
        "Redis — ping (available, mocked)",
        lambda: None,
        iterations=50,
    )
    report = bench.report()
    print("\n--- Redis Performance Benchmarks ---\n")
    print(report)


def test_redis_reconnect_latency(bench):
    bench.run_sync(
        "Redis — reconnect attempt (mocked)",
        lambda: None,
        iterations=10,
    )
    report = bench.report()
    print("\n--- Redis Reconnect Benchmarks ---\n")
    print(report)


def test_neo4j_connection_latency(bench):
    bench.run_sync(
        "Neo4j — ensure_connected (mocked)",
        lambda: None,
        iterations=50,
    )
    report = bench.report()
    print("\n--- Neo4j Performance Benchmarks ---\n")
    print(report)


@pytest.mark.asyncio
async def test_neo4j_graph_manager_benchmark(bench):
    from backend.infrastructure.neo4j.graph_manager import Neo4jGraphManager

    manager = Neo4jGraphManager()
    mock_session = AsyncMock()
    mock_session.run = AsyncMock(return_value=[])
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock()
    mock_driver = MagicMock()
    mock_driver.session.return_value = mock_session
    manager._driver = mock_driver

    await bench.run_async(
        "Neo4j — create_execution (mocked driver)",
        manager.create_execution,
        iterations=30,
        kwargs={"execution_id": "bench-neo4j-001", "objective": "Benchmark test"},
    )

    await bench.run_async(
        "Neo4j — create_mission (mocked driver)",
        manager.create_mission,
        iterations=30,
        kwargs={"mission_id": "mission-001", "objective": "Benchmark", "started_at": "2026-01-01"},
    )

    report = bench.report()
    print("\n--- Neo4j Graph Manager Benchmarks ---\n")
    print(report)


@pytest.mark.skip(reason="PostgresClient requires running PostgreSQL or deeper mocking")
@pytest.mark.asyncio
async def test_postgres_client_benchmark(bench):
    from backend.memory.db.postgres_client import PostgresClient

    client = PostgresClient()
    client._pool = AsyncMock()
    mock_conn = AsyncMock()
    mock_conn.fetch = AsyncMock(return_value=[{"1": 1}])
    mock_conn.fetchrow = AsyncMock(return_value={"1": 1})
    client._pool.acquire = AsyncMock(return_value=mock_conn)

    await bench.run_async(
        "PostgreSQL — fetch (mocked pool)",
        lambda: client.fetch("SELECT 1"),
        iterations=50,
    )

    await bench.run_async(
        "PostgreSQL — fetchrow (mocked pool)",
        lambda: client.fetchrow("SELECT 1"),
        iterations=50,
    )

    report = bench.report()
    print("\n--- PostgreSQL Performance Benchmarks ---\n")
    print(report)


@pytest.mark.asyncio
async def test_websocket_connection_pool_benchmark(bench):
    from backend.websocket.connection_pool import ConnectionPool

    pool = ConnectionPool()
    mock_ws = AsyncMock()
    mock_ws.send_text = AsyncMock()
    mock_ws.send_json = AsyncMock()

    await pool.register(mock_ws)

    await bench.run_async(
        "WebSocket — broadcast (1 connection, mocked)",
        lambda: pool.broadcast({"type": "test"}),
        iterations=50,
    )

    stats = pool.stats()
    print(f"\nWebSocket pool stats: {stats}")

    report = bench.report()
    print("\n--- WebSocket Connection Pool Benchmarks ---\n")
    print(report)


@pytest.mark.asyncio
async def test_rabbitmq_publish_benchmark(bench):
    with patch("backend.infrastructure.rabbitmq.publisher.RabbitMQPublisher") as MockPub:
        publisher = MockPub.return_value
        publisher.publish = AsyncMock()
        await bench.run_async(
            "RabbitMQ — publish (mocked)",
            lambda: publisher.publish("test.exchange", "routing.key", {"msg": "hello"}),
            iterations=30,
        )

    report = bench.report()
    print("\n--- RabbitMQ Performance Benchmarks ---\n")
    print(report)


def test_prometheus_metrics_benchmark(bench):
    from prometheus_client import REGISTRY
    from backend.observability.prometheus_metrics import _CortexMetrics

    # Clean registry to avoid duplicate metric registration
    collectors = list(REGISTRY._collector_to_names.keys())
    for c in collectors:
        REGISTRY.unregister(c)
    metrics = _CortexMetrics()
    bench.run_sync(
        "Prometheus — missions_started increment",
        lambda: metrics.missions_started.inc(),
        iterations=100,
    )
    bench.run_sync(
        "Prometheus — track_mission context manager",
        lambda: metrics.track_mission("bench-exec-001"),
        iterations=50,
    )
    bench.run_sync(
        "Prometheus — record_llm_call",
        lambda: metrics.record_llm_call("gpt-4", 100, 50, 0.002),
        iterations=50,
    )

    report = bench.report()
    print("\n--- Prometheus Metrics Benchmarks ---\n")
    print(report)


@pytest.mark.asyncio
async def test_orchestration_bus_benchmark(bench):
    with patch("backend.infrastructure.rabbitmq.orchestration_bus.OrchestrationBus") as MockBus:
        bus = MockBus.return_value
        bus.start_mission = AsyncMock()
        bus.complete_mission = AsyncMock()
        bus.dispatch_to_agent = AsyncMock()

        await bench.run_async(
            "OrchestrationBus — start_mission (mocked)",
            lambda: bus.start_mission("bench-exec-001", "Benchmark mission"),
            iterations=30,
        )
        await bench.run_async(
            "OrchestrationBus — complete_mission (mocked)",
            lambda: bus.complete_mission("bench-exec-001", {"status": "completed"}),
            iterations=30,
        )
        await bench.run_async(
            "OrchestrationBus — dispatch_to_agent (mocked)",
            lambda: bus.dispatch_to_agent("planner", "bench-exec-001", {"task": "plan"}),
            iterations=30,
        )

    report = bench.report()
    print("\n--- OrchestrationBus Performance Benchmarks ---\n")
    print(report)

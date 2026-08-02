"""
Structural regression test for RedisConnectionPool.

Found live: a module-level helper (_use_ssl) was accidentally defined at
column 0 in the middle of the class body (right after _pool_kwargs),
which silently closed the class early. Everything after it — connect(),
ensure_connected(), the client/pub_client/is_available/failure_count
properties, close(), ping() — became dead code nested inside _use_ssl()'s
function body instead of being part of RedisConnectionPool. The class
still imported fine and instantiated fine (only __init__ and
_pool_kwargs were real methods), so nothing caught this until a live
health check surfaced "'RedisConnectionPool' object has no attribute
'is_available'" — which had been silently misattributed to "Redis isn't
running" for the whole session, even when a real Redis server was up.

This test exists so a similar accidental-class-body-break can't silently
ship again: it doesn't need a running Redis, just confirms the class
actually has the public surface its own docstring and every caller
throughout the codebase (memory/stores/context_store.py,
memory_orchestrator.py, enterprise_recommendation_engine.py, etc.)
assumes it has.
"""
from __future__ import annotations

from backend.infrastructure.redis.connection import RedisConnectionPool


class TestRedisConnectionPoolStructure:
    def test_has_all_expected_public_members(self):
        expected = {
            "client", "pub_client", "is_available", "failure_count",
            "connect", "ensure_connected", "close", "ping",
            "reset_circuit_breaker",
        }
        actual = {n for n in dir(RedisConnectionPool) if not n.startswith("__")}
        missing = expected - actual
        assert not missing, f"RedisConnectionPool is missing: {missing}"

    def test_is_available_is_a_property_not_a_bound_method(self):
        pool = RedisConnectionPool()
        # Accessing without calling — a real @property returns bool directly.
        # If this were dead code outside the class, this line raises
        # AttributeError before the assert ever runs.
        assert pool.is_available is False

    def test_client_and_pub_client_start_none(self):
        pool = RedisConnectionPool()
        assert pool.client is None
        assert pool.pub_client is None

    def test_failure_count_starts_zero(self):
        pool = RedisConnectionPool()
        assert pool.failure_count == 0

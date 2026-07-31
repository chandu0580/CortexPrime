"""
Tests for the CortexPrime Multi-LLM Router
==========================================
Covers:
  - Task type detection from prompt keywords
  - Routing table: each task type selects the correct primary provider
  - Failover: primary provider unavailable → uses fallback
  - Circuit breaker: provider opens after N failures and is skipped
  - Circuit reset: provider is retried after CIRCUIT_OPEN_SECS
  - All providers fail → RouterResult.success == False
  - Telemetry: stats updated correctly after success and failure
  - Health endpoint returns correct availability states
  - API: GET /health/llm returns 200
  - API: POST /health/llm/reset clears stats
"""
from __future__ import annotations

import time
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def client():
    from backend.main import app
    return TestClient(app)


@pytest.fixture(scope="module")
def admin_headers():
    from backend.auth.jwt_handler import create_access_token

    token = create_access_token(user_id="llm-admin", role="admin")
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture(autouse=True)
def _no_blacklist():
    """Suppress Redis blacklist check for all route tests in this module."""
    mock_redis = AsyncMock()
    mock_redis.get = AsyncMock(return_value=None)
    with patch(
        "backend.auth.token_blacklist.TokenBlacklist._get_redis",
        new_callable=AsyncMock,
        return_value=mock_redis,
    ):
        yield


@pytest.fixture()
def fresh_router():
    """Return a fresh LLMRouter instance (not the singleton) for isolation."""
    from backend.llm.llm_router import LLMRouter
    return LLMRouter()


# ---------------------------------------------------------------------------
# Unit: detect_task_type
# ---------------------------------------------------------------------------

class TestDetectTaskType:

    def test_coding_keywords(self):
        from backend.llm.llm_router import detect_task_type, TaskType
        assert detect_task_type("write code to parse JSON")          == TaskType.CODING
        assert detect_task_type("implement a binary search algorithm") == TaskType.CODING
        assert detect_task_type("debug this function please")          == TaskType.CODING
        assert detect_task_type("refactor the authentication module")  == TaskType.CODING

    def test_research_keywords(self):
        from backend.llm.llm_router import detect_task_type, TaskType
        assert detect_task_type("research the latest AI trends")       == TaskType.RESEARCH
        assert detect_task_type("what is the latest news about GPT")   == TaskType.RESEARCH
        assert detect_task_type("summarize the paper on transformers")  == TaskType.RESEARCH

    def test_reasoning_keywords(self):
        from backend.llm.llm_router import detect_task_type, TaskType
        assert detect_task_type("analyze the pros and cons of this")   == TaskType.REASONING
        assert detect_task_type("reason through this decision step by step") == TaskType.REASONING
        assert detect_task_type("evaluate the pros of microservices")  == TaskType.REASONING

    def test_offline_keywords(self):
        from backend.llm.llm_router import detect_task_type, TaskType
        assert detect_task_type("run this offline using local model")  == TaskType.OFFLINE
        assert detect_task_type("use ollama for this task")            == TaskType.OFFLINE
        assert detect_task_type("keep it private and on-device")       == TaskType.OFFLINE

    def test_general_fallback(self):
        from backend.llm.llm_router import detect_task_type, TaskType
        assert detect_task_type("hello, how are you?")   == TaskType.GENERAL
        assert detect_task_type("what time is it?")      == TaskType.GENERAL
        assert detect_task_type("")                      == TaskType.GENERAL

    def test_offline_takes_priority_over_coding(self):
        """offline keywords should override coding keywords."""
        from backend.llm.llm_router import detect_task_type, TaskType
        assert detect_task_type("write code offline using local model") == TaskType.OFFLINE


# ---------------------------------------------------------------------------
# Unit: Routing table — each task type maps to expected primary provider
# ---------------------------------------------------------------------------

class TestRoutingTable:

    def _primary(self, task_type_str: str) -> str:
        from backend.llm.llm_router import _ROUTING, TaskType
        return _ROUTING[TaskType(task_type_str)][0]

    def test_coding_routes_to_azure(self):
        assert self._primary("coding") == "azure"

    def test_reasoning_routes_to_claude(self):
        assert self._primary("reasoning") == "claude"

    def test_research_routes_to_gemini(self):
        assert self._primary("research") == "gemini"

    def test_offline_routes_to_ollama(self):
        assert self._primary("offline") == "ollama"

    def test_general_routes_to_azure(self):
        assert self._primary("general") == "azure"

    def test_all_chains_have_at_least_two_providers(self):
        from backend.llm.llm_router import _ROUTING
        for task_type, chain in _ROUTING.items():
            assert len(chain) >= 2, f"Chain for {task_type} has fewer than 2 providers"

    def test_groq_present_as_fallback_in_every_chain(self):
        from backend.llm.llm_router import _ROUTING
        for task_type, chain in _ROUTING.items():
            assert "groq" in chain, f"Chain for {task_type} is missing groq as a fallback"


# ---------------------------------------------------------------------------
# Unit: _call_groq — direct HTTP fallback path
# ---------------------------------------------------------------------------

class TestCallGroq:
    @pytest.mark.asyncio
    async def test_raises_when_api_key_missing(self, monkeypatch):
        from backend.llm.llm_router import _call_groq
        monkeypatch.delenv("GROQ_API_KEY", raising=False)
        with patch(
            "backend.llm.llm_router._llm_service_generate",
            new_callable=AsyncMock, side_effect=RuntimeError("provider runtime unavailable"),
        ):
            with pytest.raises(RuntimeError, match="GROQ_API_KEY"):
                await _call_groq("prompt", "system")

    @pytest.mark.asyncio
    async def test_direct_http_call_returns_output(self, monkeypatch):
        from backend.llm.llm_router import _call_groq
        monkeypatch.setenv("GROQ_API_KEY", "gsk_test_key")

        fake_response = MagicMock()
        fake_response.json.return_value = {"choices": [{"message": {"content": "hello from groq"}}]}
        fake_response.raise_for_status = MagicMock()

        fake_client = AsyncMock()
        fake_client.post = AsyncMock(return_value=fake_response)
        fake_client.__aenter__ = AsyncMock(return_value=fake_client)
        fake_client.__aexit__ = AsyncMock(return_value=False)

        with patch(
            "backend.llm.llm_router._llm_service_generate",
            new_callable=AsyncMock, side_effect=RuntimeError("provider runtime unavailable"),
        ), patch("httpx.AsyncClient", return_value=fake_client):
            output = await _call_groq("write a haiku", "be concise")

        assert output == "hello from groq"
        _, kwargs = fake_client.post.call_args
        assert kwargs["headers"]["Authorization"] == "Bearer gsk_test_key"
        assert kwargs["json"]["messages"][1]["content"] == "write a haiku"

    @pytest.mark.asyncio
    async def test_raises_on_empty_output(self, monkeypatch):
        from backend.llm.llm_router import _call_groq
        monkeypatch.setenv("GROQ_API_KEY", "gsk_test_key")

        fake_response = MagicMock()
        fake_response.json.return_value = {"choices": [{"message": {"content": ""}}]}
        fake_response.raise_for_status = MagicMock()

        fake_client = AsyncMock()
        fake_client.post = AsyncMock(return_value=fake_response)
        fake_client.__aenter__ = AsyncMock(return_value=fake_client)
        fake_client.__aexit__ = AsyncMock(return_value=False)

        with patch(
            "backend.llm.llm_router._llm_service_generate",
            new_callable=AsyncMock, side_effect=RuntimeError("provider runtime unavailable"),
        ), patch("httpx.AsyncClient", return_value=fake_client):
            with pytest.raises(RuntimeError, match="empty output"):
                await _call_groq("prompt", "system")


# ---------------------------------------------------------------------------
# Unit: ProviderStats — circuit breaker logic
# ---------------------------------------------------------------------------

class TestProviderStats:

    def test_initial_state(self):
        from backend.llm.llm_router import ProviderStats, CIRCUIT_FAIL_THRESHOLD
        s = ProviderStats(provider="test")
        assert s.call_count       == 0
        assert s.fail_count       == 0
        assert s.circuit_open     is False
        assert s.error_rate       == 0.0
        assert s.avg_latency_ms   == 0.0

    def test_record_success(self):
        from backend.llm.llm_router import ProviderStats
        s = ProviderStats(provider="test")
        s.record_success(latency_ms=120.0)
        assert s.call_count        == 1
        assert s.fail_count        == 0
        assert s.consecutive_fails == 0
        assert s.avg_latency_ms    == 120.0

    def test_record_failure_increments_counters(self):
        from backend.llm.llm_router import ProviderStats
        s = ProviderStats(provider="test")
        s.record_failure("timeout")
        assert s.call_count        == 1
        assert s.fail_count        == 1
        assert s.consecutive_fails == 1
        assert s.last_error        == "timeout"
        assert s.error_rate        == 1.0

    def test_circuit_opens_after_threshold_failures(self):
        from backend.llm.llm_router import ProviderStats, CIRCUIT_FAIL_THRESHOLD
        s = ProviderStats(provider="test")
        for _ in range(CIRCUIT_FAIL_THRESHOLD):
            s.record_failure("err")
        assert s.circuit_open is True

    def test_success_resets_consecutive_fails(self):
        from backend.llm.llm_router import ProviderStats, CIRCUIT_FAIL_THRESHOLD
        s = ProviderStats(provider="test")
        for _ in range(CIRCUIT_FAIL_THRESHOLD - 1):
            s.record_failure("err")
        s.record_success(50.0)
        assert s.consecutive_fails == 0
        assert s.circuit_open is False

    def test_circuit_closes_after_timeout(self):
        from backend.llm.llm_router import ProviderStats, CIRCUIT_FAIL_THRESHOLD
        s = ProviderStats(provider="test")
        for _ in range(CIRCUIT_FAIL_THRESHOLD):
            s.record_failure("err")
        # Simulate circuit_opened_at being old enough
        s.circuit_opened_at = time.time() - 9999
        assert s.circuit_open is False

    def test_to_dict_has_expected_keys(self):
        from backend.llm.llm_router import ProviderStats
        s = ProviderStats(provider="azure")
        d = s.to_dict()
        for key in ("provider", "call_count", "fail_count", "avg_latency_ms",
                    "error_rate", "circuit_open", "last_error"):
            assert key in d


# ---------------------------------------------------------------------------
# Unit: LLMRouter.route — provider unavailability + failover
# ---------------------------------------------------------------------------

class TestLLMRouterFailover:

    async def test_primary_success_returns_immediately(self, fresh_router):
        from backend.llm.llm_router import TaskType
        with patch("backend.llm.llm_router._call_azure", new_callable=AsyncMock,
                   return_value="azure response"):
            result = await fresh_router.route(
                prompt="write code for sorting",
                task_type=TaskType.CODING,
            )
        assert result.success        is True
        assert result.output         == "azure response"
        assert result.provider_used  == "azure"
        assert result.fallback_count == 0

    async def test_primary_fails_uses_fallback(self, fresh_router):
        """Coding: azure fails → openai should succeed."""
        from backend.llm.llm_router import TaskType
        with (
            patch("backend.llm.llm_router._call_azure",
                  new_callable=AsyncMock,
                  side_effect=RuntimeError("Azure unavailable")),
            patch("backend.llm.llm_router._call_openai",
                  new_callable=AsyncMock,
                  return_value="openai response"),
        ):
            result = await fresh_router.route(
                prompt="write code for sorting",
                task_type=TaskType.CODING,
            )
        assert result.success        is True
        assert result.output         == "openai response"
        assert result.provider_used  == "openai"
        assert result.fallback_count == 1

    async def test_all_providers_fail_returns_failure(self, fresh_router):
        from backend.llm.llm_router import TaskType
        with (
            patch("backend.llm.llm_router._call_azure",
                  new_callable=AsyncMock, side_effect=RuntimeError("fail")),
            patch("backend.llm.llm_router._call_openai",
                  new_callable=AsyncMock, side_effect=RuntimeError("fail")),
            patch("backend.llm.llm_router._call_claude",
                  new_callable=AsyncMock, side_effect=RuntimeError("fail")),
            patch("backend.llm.llm_router._call_gemini",
                  new_callable=AsyncMock, side_effect=RuntimeError("fail")),
            patch("backend.llm.llm_router._call_groq",
                  new_callable=AsyncMock, side_effect=RuntimeError("fail")),
        ):
            result = await fresh_router.route(
                prompt="write code",
                task_type=TaskType.CODING,
            )
        assert result.success is False
        assert result.output  == ""
        assert "failed" in result.error.lower()
        assert result.fallback_count >= 1

    async def test_reasoning_task_starts_with_claude(self, fresh_router):
        from backend.llm.llm_router import TaskType
        with patch("backend.llm.llm_router._call_claude",
                   new_callable=AsyncMock, return_value="claude reasoning"):
            result = await fresh_router.route(
                prompt="analyze this decision",
                task_type=TaskType.REASONING,
            )
        assert result.success       is True
        assert result.provider_used == "claude"

    async def test_research_task_starts_with_gemini(self, fresh_router):
        from backend.llm.llm_router import TaskType
        with patch("backend.llm.llm_router._call_gemini",
                   new_callable=AsyncMock, return_value="gemini research"):
            result = await fresh_router.route(
                prompt="research AI trends",
                task_type=TaskType.RESEARCH,
            )
        assert result.success       is True
        assert result.provider_used == "gemini"

    async def test_offline_task_starts_with_ollama(self, fresh_router):
        from backend.llm.llm_router import TaskType
        with patch("backend.llm.llm_router._call_ollama",
                   new_callable=AsyncMock, return_value="ollama offline"):
            result = await fresh_router.route(
                prompt="run offline",
                task_type=TaskType.OFFLINE,
            )
        assert result.success       is True
        assert result.provider_used == "ollama"

    async def test_circuit_open_provider_is_skipped(self, fresh_router):
        """Open azure circuit → should fall straight to openai."""
        from backend.llm.llm_router import TaskType, CIRCUIT_FAIL_THRESHOLD
        # Trip the circuit
        for _ in range(CIRCUIT_FAIL_THRESHOLD):
            fresh_router._stats["azure"].record_failure("injected")

        assert fresh_router._stats["azure"].circuit_open is True

        with patch("backend.llm.llm_router._call_openai",
                   new_callable=AsyncMock, return_value="openai fallback"):
            result = await fresh_router.route(
                prompt="write code",
                task_type=TaskType.CODING,
            )
        assert result.success       is True
        assert result.provider_used == "openai"
        # azure[circuit-open] should appear in tried list
        assert any("circuit-open" in p for p in result.tried_providers)

    async def test_task_type_auto_detected(self, fresh_router):
        with patch("backend.llm.llm_router._call_azure",
                   new_callable=AsyncMock, return_value="auto-detected"):
            result = await fresh_router.route(prompt="write code for a parser")
        assert result.success   is True
        assert result.task_type == "coding"


# ---------------------------------------------------------------------------
# Unit: Telemetry
# ---------------------------------------------------------------------------

class TestRouterTelemetry:

    async def test_success_recorded_in_stats(self, fresh_router):
        from backend.llm.llm_router import TaskType
        with patch("backend.llm.llm_router._call_azure",
                   new_callable=AsyncMock, return_value="ok"):
            await fresh_router.route(prompt="test", task_type=TaskType.GENERAL)

        stats = fresh_router._stats["azure"]
        assert stats.call_count == 1
        assert stats.fail_count == 0

    async def test_failure_recorded_in_stats(self, fresh_router):
        from backend.llm.llm_router import TaskType
        with (
            patch("backend.llm.llm_router._call_azure",
                  new_callable=AsyncMock, side_effect=RuntimeError("boom")),
            patch("backend.llm.llm_router._call_openai",
                  new_callable=AsyncMock, return_value="ok"),
        ):
            await fresh_router.route(prompt="test", task_type=TaskType.CODING)

        azure_stats = fresh_router._stats["azure"]
        assert azure_stats.fail_count == 1
        assert azure_stats.last_error == "boom"

    async def test_fallback_count_total_accumulates(self, fresh_router):
        from backend.llm.llm_router import TaskType
        with (
            patch("backend.llm.llm_router._call_azure",
                  new_callable=AsyncMock, side_effect=RuntimeError("fail")),
            patch("backend.llm.llm_router._call_openai",
                  new_callable=AsyncMock, return_value="ok"),
        ):
            await fresh_router.route(prompt="test", task_type=TaskType.CODING)
            await fresh_router.route(prompt="test", task_type=TaskType.CODING)

        assert fresh_router._fallback_count_total == 2

    async def test_recent_requests_logged(self, fresh_router):
        from backend.llm.llm_router import TaskType
        with patch("backend.llm.llm_router._call_azure",
                   new_callable=AsyncMock, return_value="ok"):
            await fresh_router.route(prompt="test", task_type=TaskType.GENERAL)
        assert len(fresh_router._recent) == 1
        assert fresh_router._recent[0]["provider"] == "azure"

    def test_reset_stats_clears_all(self, fresh_router):
        from backend.llm.llm_router import ProviderStats
        fresh_router._stats["azure"].record_failure("err")
        fresh_router._fallback_count_total = 5
        fresh_router.reset_stats()
        assert fresh_router._stats["azure"].fail_count       == 0
        assert fresh_router._fallback_count_total            == 0

    def test_reset_stats_single_provider(self, fresh_router):
        fresh_router._stats["azure"].record_failure("err")
        fresh_router._stats["openai"].record_failure("err")
        fresh_router.reset_stats("azure")
        assert fresh_router._stats["azure"].fail_count  == 0
        assert fresh_router._stats["openai"].fail_count == 1


# ---------------------------------------------------------------------------
# Unit: Health output
# ---------------------------------------------------------------------------

class TestLLMRouterHealth:

    def test_health_includes_all_providers(self, fresh_router):
        h = fresh_router.health()
        for name in ("azure", "openai", "claude", "gemini", "ollama"):
            assert name in h["providers"]

    def test_health_not_configured_when_key_missing(self, fresh_router):
        with patch.dict("os.environ", {"ANTHROPIC_API_KEY": ""}, clear=False):
            h = fresh_router.health()
        assert h["providers"]["claude"]["availability"] == "not_configured"

    def test_health_circuit_open_shown_in_availability(self, fresh_router):
        from backend.llm.llm_router import CIRCUIT_FAIL_THRESHOLD
        for _ in range(CIRCUIT_FAIL_THRESHOLD):
            fresh_router._stats["openai"].record_failure("err")
        h = fresh_router.health()
        assert h["providers"]["openai"]["availability"] == "circuit_open"

    def test_health_global_error_rate_calculated(self, fresh_router):
        fresh_router._stats["azure"].record_success(100)
        fresh_router._stats["azure"].record_failure("err")
        h = fresh_router.health()
        assert 0.0 < h["global_error_rate"] <= 1.0

    def test_telemetry_includes_recent_requests(self, fresh_router):
        t = fresh_router.telemetry()
        assert "recent_requests" in t
        assert isinstance(t["recent_requests"], list)


# ---------------------------------------------------------------------------
# Integration: API routes
# ---------------------------------------------------------------------------

class TestLLMHealthAPI:

    def test_get_health_llm_returns_200(self, client):
        resp = client.get("/health/llm")
        assert resp.status_code == 200
        data = resp.json()
        assert "providers" in data
        assert "status"    in data
        for name in ("azure", "openai", "claude", "gemini", "ollama"):
            assert name in data["providers"]

    def test_get_health_llm_telemetry_returns_200(self, client, admin_headers):
        resp = client.get("/health/llm/telemetry", headers=admin_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert "recent_requests" in data

    def test_reset_all_providers(self, client, admin_headers):
        resp = client.post("/health/llm/reset", json={}, headers=admin_headers)
        assert resp.status_code == 200
        assert resp.json()["reset"] == "all"

    def test_reset_single_provider(self, client, admin_headers):
        resp = client.post("/health/llm/reset", json={"provider": "azure"}, headers=admin_headers)
        assert resp.status_code == 200
        assert resp.json()["reset"] == "azure"

    def test_reset_unknown_provider_returns_400(self, client, admin_headers):
        resp = client.post("/health/llm/reset", json={"provider": "nonexistent"}, headers=admin_headers)
        assert resp.status_code == 400

"""Phase 11.3 (ADR-123 D-18): the governed investigator's hosted provider.

An OpenAI-compatible endpoint configured entirely by environment (LLM_API_KEY,
LLM_BASE_URL, LLM_MODEL). The one rule that is not a convenience: a plain-HTTP
URL to a non-loopback host sends the key and every prompt across the network
unencrypted, so it is refused unless LLM_ALLOW_PLAINTEXT_HTTP=1 says, in the
operator's own configuration, that this is accepted."""
from __future__ import annotations

import asyncio
from types import SimpleNamespace

import pytest

from backend.llm_provider.models import FinishReason, LLMRequest
from backend.llm_provider.providers import openai_compatible_adapter as module
from backend.llm_provider.providers.openai_compatible_adapter import OpenAICompatibleAdapter

KEY = "sk-test-not-a-real-key-000"


def _env(monkeypatch, *, base="https://llm.example.test/v1/", model="glm-5.2", key=KEY, plaintext=None):
    for name, value in (("LLM_API_KEY", key), ("LLM_BASE_URL", base), ("LLM_MODEL", model),
                        ("LLM_ALLOW_PLAINTEXT_HTTP", plaintext)):
        if value is None:
            monkeypatch.delenv(name, raising=False)
        else:
            monkeypatch.setenv(name, value)


class _FakeCompletions:
    def __init__(self, *, content='{"ok": true}', error=None):
        self.calls: list = []
        self._content, self._error = content, error

    async def create(self, **kwargs):
        self.calls.append(kwargs)
        if self._error:
            raise self._error
        usage = SimpleNamespace(model_dump=lambda: {"prompt_tokens": 11, "completion_tokens": 4, "total_tokens": 15})
        return SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content=self._content), finish_reason="stop")],
            usage=usage)


class _FakeClient:
    def __init__(self, **kwargs):
        self.kwargs = kwargs
        self.chat = SimpleNamespace(completions=_FakeCompletions())
        self.closed = False

    async def close(self):
        self.closed = True


@pytest.fixture
def fake_sdk(monkeypatch):
    made: list = []

    def factory(**kwargs):
        client = _FakeClient(**kwargs)
        made.append(client)
        return client

    monkeypatch.setattr(module, "AsyncOpenAI", factory)
    return made


class TestTransportRule:
    def test_plain_http_to_a_remote_host_is_refused_without_the_opt_in(self, monkeypatch, fake_sdk):
        _env(monkeypatch, base="http://203.0.113.7:4000/v1/")
        adapter = OpenAICompatibleAdapter()
        assert asyncio.run(adapter.initialize()) is False
        assert fake_sdk == [], "no client may be built for a refused transport"
        reason = OpenAICompatibleAdapter.plaintext_refusal("http://203.0.113.7:4000/v1/")
        assert reason and "unencrypted" in reason and KEY not in reason

    def test_the_explicit_opt_in_accepts_plain_http(self, monkeypatch, fake_sdk):
        _env(monkeypatch, base="http://203.0.113.7:4000/v1/", plaintext="1")
        adapter = OpenAICompatibleAdapter()
        assert asyncio.run(adapter.initialize()) is True
        assert fake_sdk[0].kwargs["base_url"] == "http://203.0.113.7:4000/v1/"

    @pytest.mark.parametrize("base", ["https://llm.example.test/v1/", "http://127.0.0.1:4000/v1/",
                                      "http://localhost:4000/v1/"])
    def test_https_and_loopback_need_no_opt_in(self, monkeypatch, fake_sdk, base):
        _env(monkeypatch, base=base)
        assert asyncio.run(OpenAICompatibleAdapter().initialize()) is True

    def test_missing_configuration_leaves_the_provider_unavailable(self, monkeypatch, fake_sdk):
        _env(monkeypatch, key=None)
        assert asyncio.run(OpenAICompatibleAdapter().initialize()) is False
        assert fake_sdk == []


class TestDeclarationAndCalls:
    def test_the_configured_model_is_declared_so_the_router_can_find_it(self, monkeypatch):
        _env(monkeypatch)
        adapter = OpenAICompatibleAdapter()
        assert adapter.name == "openai-compatible"
        assert [m.name for m in adapter.provider_info.models] == ["glm-5.2"]

    def test_generate_passes_model_format_budget_and_timeout_and_maps_usage(self, monkeypatch, fake_sdk):
        _env(monkeypatch)
        adapter = OpenAICompatibleAdapter()
        assert asyncio.run(adapter.initialize()) is True
        request = LLMRequest(model="glm-5.2", system_prompt="sys", messages=[{"role": "user", "content": "hi"}],
                             max_tokens=900, temperature=0.0, timeout_seconds=120.0,
                             response_format={"type": "json_object"})
        response = asyncio.run(adapter.generate(request))
        call = fake_sdk[0].chat.completions.calls[0]
        assert call["model"] == "glm-5.2" and call["max_tokens"] == 900 and call["timeout"] == 120.0
        assert call["response_format"] == {"type": "json_object"}
        assert call["messages"][0] == {"role": "system", "content": "sys"}
        assert response.error is None and response.content == '{"ok": true}'
        assert response.usage == {"prompt_tokens": 11, "completion_tokens": 4, "total_tokens": 15}
        assert response.finish_reason == FinishReason.STOP and response.provider == "openai-compatible"

    def test_a_provider_error_is_surfaced_not_swallowed_and_never_carries_the_key(self, monkeypatch, fake_sdk):
        _env(monkeypatch)
        adapter = OpenAICompatibleAdapter()
        asyncio.run(adapter.initialize())
        fake_sdk[0].chat.completions._error = RuntimeError("upstream 503")
        response = asyncio.run(adapter.generate(LLMRequest(model="glm-5.2", messages=[{"role": "user", "content": "x"}])))
        assert response.error and "upstream 503" in response.error and KEY not in response.error
        assert response.finish_reason == FinishReason.ERROR

    def test_shutdown_closes_the_client(self, monkeypatch, fake_sdk):
        _env(monkeypatch)
        adapter = OpenAICompatibleAdapter()
        asyncio.run(adapter.initialize())
        asyncio.run(adapter.shutdown())
        assert fake_sdk[0].closed is True

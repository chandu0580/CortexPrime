from __future__ import annotations

import pytest

from backend.llm_provider.models import ModelCapability, ProviderHealth
from backend.llm_provider.providers.openai_adapter import OpenAIAdapter
from backend.llm_provider.providers.anthropic_adapter import AnthropicAdapter
from backend.llm_provider.providers.gemini_adapter import GeminiAdapter
from backend.llm_provider.providers.ollama_adapter import OllamaAdapter
from backend.llm_provider.providers.deepseek_provider import DeepSeekAdapter
from backend.llm_provider.registry import ProviderRegistry
from backend.llm_provider.router import ModelRouter, RoutingStrategy


@pytest.fixture
def registry():
    return ProviderRegistry()


@pytest.fixture
def router():
    return ModelRouter()


def test_registry_register_get(registry):
    adapter = OpenAIAdapter()
    registry.register(adapter)
    retrieved = registry.get("openai")
    assert retrieved is adapter


def test_registry_register_overwrite(registry):
    a1 = OpenAIAdapter()
    a2 = OpenAIAdapter()
    registry.register(a1)
    registry.register(a2)
    assert registry.get("openai") is a2


def test_registry_unregister(registry):
    adapter = OpenAIAdapter()
    registry.register(adapter)
    registry.unregister("openai")
    assert registry.get("openai") is None


def test_registry_list(registry):
    registry.register(OpenAIAdapter())
    registry.register(AnthropicAdapter())
    providers = registry.list_providers()
    names = [p.name for p in providers]
    assert "openai" in names
    assert "anthropic" in names


def test_registry_list_available_all_uninitialized(registry):
    registry.register(OpenAIAdapter())
    assert len(registry.list_available()) == 0


def test_registry_get_by_capability(registry):
    registry.register(OpenAIAdapter())
    registry.register(OllamaAdapter())
    chat_providers = registry.get_by_capability(ModelCapability.CHAT.value)
    names = [p.name for p in chat_providers]
    assert "openai" in names
    assert "ollama" in names


def test_registry_discover(registry):
    registry.discover()
    providers = registry.list_providers()
    names = [p.name for p in providers]
    assert "openai" in names
    assert "anthropic" in names
    assert "gemini" in names
    assert "ollama" in names
    assert "deepseek" in names


@pytest.mark.asyncio
async def test_registry_initialize_all(registry):
    registry.discover()
    results = await registry.initialize_all()
    assert isinstance(results, dict)


@pytest.mark.asyncio
async def test_registry_health_check_all(registry):
    registry.discover()
    results = await registry.health_check_all()
    assert isinstance(results, dict)
    for name, health in results.items():
        assert isinstance(health, ProviderHealth)
        assert health.provider == name


@pytest.mark.asyncio
async def test_health_check_all_cache(registry):
    registry.discover()
    r1 = await registry.health_check_all()
    r2 = await registry.health_check_all()
    assert r1.keys() == r2.keys()


def test_registry_get_providers_info(registry):
    registry.discover()
    info = registry.get_providers_info()
    assert len(info) >= 5
    for p in info:
        assert "name" in p
        assert "display_name" in p
        assert "models" in p


@pytest.mark.asyncio
async def test_registry_shutdown_all(registry):
    registry.discover()
    await registry.shutdown_all()
    assert len(registry.list_providers()) == 0


def test_router_select_model_priority(router):
    model_name, provider_name = router.select_model(provider="openai")
    assert provider_name == "openai"
    assert model_name is not None


def test_router_select_model_fallback(router):
    model_name, provider_name = router.select_model(provider="nonexistent")
    assert provider_name is not None
    assert model_name is not None


def test_router_select_models_top_n(router):
    router._registry.discover()
    for p in router._registry.list_providers():
        p.provider_info.is_available = True
    models = router.select_models(count=3)
    assert len(models) >= 1


def test_router_strategy_round_robin(router):
    router._registry.discover()
    for p in router._registry.list_providers():
        p.provider_info.is_available = True
    r1 = router.select_model(strategy=RoutingStrategy.ROUND_ROBIN)
    r2 = router.select_model(strategy=RoutingStrategy.ROUND_ROBIN)
    assert r1 != r2


def test_router_strategy_cost_lowest(router):
    router._registry.discover()
    for p in router._registry.list_providers():
        p.provider_info.is_available = True
    models = router.select_models(count=5)
    assert len(models) >= 1


def test_router_strategy_capability(router):
    model_name, provider_name = router.select_model(
        strategy=RoutingStrategy.CAPABILITY,
        provider="openai",
        required_capabilities={"chat"},
    )
    assert provider_name == "openai"
    assert model_name is not None

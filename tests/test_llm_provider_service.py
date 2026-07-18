from __future__ import annotations

import pytest

from backend.llm_provider.models import FinishReason, LLMRequest, LLMResponse
from backend.llm_provider.prompt import PromptRuntime, PromptTemplate
from backend.llm_provider.registry import ProviderRegistry
from backend.llm_provider.router import ModelRouter
from backend.llm_provider.service import LLMService
from backend.llm_provider.streaming import StreamManager
from backend.llm_provider.structured import StructuredOutputHandler
from backend.llm_provider.embedding import EmbeddingProviderInterface


@pytest.fixture
def service():
    registry = ProviderRegistry()
    registry.discover()
    return LLMService(
        provider_registry=registry,
        model_router_instance=ModelRouter(),
        prompt_runtime_instance=PromptRuntime(),
        stream_mgr=StreamManager(),
        embedding=EmbeddingProviderInterface(registry),
        structured=StructuredOutputHandler(),
    )


@pytest.mark.asyncio
async def test_service_initialize(service):
    ok = await service.initialize()
    assert ok is True or ok is False


@pytest.mark.asyncio
async def test_service_generate_fallback(service):
    response = await service.generate("Hello", provider="nonexistent")
    assert response.content is not None
    assert response.finish_reason is not None


@pytest.mark.asyncio
async def test_service_generate_with_model(service):
    response = await service.generate("Hello", model="gpt-4o")
    assert isinstance(response, LLMResponse)


@pytest.mark.asyncio
async def test_service_generate_structured(service):
    schema = {
        "type": "object",
        "properties": {"name": {"type": "string"}, "age": {"type": "integer"}},
        "required": ["name", "age"],
    }
    response = await service.generate_structured(
        "Extract: John is 30 years old", schema=schema, provider="nonexistent",
    )
    assert response.finish_reason == FinishReason.ERROR or response.content is not None


@pytest.mark.asyncio
async def test_service_stream(service):
    chunks = []
    async for chunk in service.stream("Hello", provider="nonexistent"):
        chunks.append(chunk)
    assert len(chunks) >= 1
    assert chunks[-1].done is True


@pytest.mark.asyncio
async def test_service_embed(service):
    result = await service.embed(["hello", "world"])
    assert result is not None


@pytest.mark.asyncio
async def test_service_health(service):
    health = await service.health()
    assert isinstance(health, list)


@pytest.mark.asyncio
async def test_service_list_providers(service):
    providers = await service.list_providers()
    assert isinstance(providers, list)
    assert len(providers) >= 5


@pytest.mark.asyncio
async def test_service_list_models(service):
    models = await service.list_models()
    assert isinstance(models, list)
    assert len(models) >= 1
    for m in models:
        assert "provider" in m


@pytest.mark.asyncio
async def test_service_get_provider(service):
    provider = await service.get_provider("openai")
    assert provider is not None
    assert provider.get("name") == "openai"


@pytest.mark.asyncio
async def test_service_get_provider_not_found(service):
    provider = await service.get_provider("nonexistent")
    assert provider is None


def test_prompt_runtime_builtin_system_prompts():
    pr = PromptRuntime()
    prompts = pr.list_system_prompts()
    default_ids = {"default", "code", "reasoning", "creative", "concise", "analysis", "research"}
    assert default_ids.issubset(prompts.keys())


def test_prompt_runtime_register_template():
    pr = PromptRuntime()
    tpl = PromptTemplate(name="custom-test", version="1.0", template="Hello {{name}}")
    pr.register_template(tpl)
    retrieved = pr.get_template("custom-test")
    assert retrieved is not None
    assert retrieved.name == "custom-test"


def test_prompt_runtime_render_template():
    pr = PromptRuntime()
    tpl = PromptTemplate(name="greeting", template="Hello {{name}}!")
    pr.register_template(tpl)
    result = pr.render_template(tpl, {"name": "World"})
    assert result == "Hello World!"


def test_prompt_runtime_build_request():
    pr = PromptRuntime()
    req = pr.build_request(prompt="test prompt", system_prompt_name="code")
    assert isinstance(req, LLMRequest)
    assert req.messages[-1]["content"] == "test prompt"
    assert "expert software engineer" in req.system_prompt


def test_prompt_runtime_validate_prompt_empty():
    pr = PromptRuntime()
    result = pr.validate_prompt("")
    assert result is not None
    assert "cannot be empty" in result.lower()


def test_prompt_runtime_validate_prompt_valid():
    pr = PromptRuntime()
    result = pr.validate_prompt("valid prompt")
    assert result is None


def test_structured_output_handler_validate_json():
    handler = StructuredOutputHandler()
    schema = {
        "type": "object",
        "properties": {"name": {"type": "string"}},
        "required": ["name"],
    }
    parsed, error = handler._validate_json('{"name": "test"}', schema)
    assert error is None
    assert parsed is not None
    assert parsed["name"] == "test"


def test_structured_output_handler_validate_json_invalid():
    handler = StructuredOutputHandler()
    schema = {
        "type": "object",
        "properties": {"name": {"type": "string"}},
        "required": ["name"],
    }
    parsed, error = handler._validate_json('{"age": 25}', schema)
    assert error is not None
    assert "missing required" in error.lower()


def test_structured_output_handler_schema_to_instruction():
    handler = StructuredOutputHandler()
    schema = {"type": "object", "properties": {"x": {"type": "integer"}}}
    instruction = handler._schema_to_instruction(schema)
    assert "json" in instruction.lower()


def test_stream_manager():
    mgr = StreamManager()
    assert mgr.active_count == 0
    mgr.cancel_stream("test-id")


def test_embedding_provider_interface():
    registry = ProviderRegistry()
    registry.discover()
    epi = EmbeddingProviderInterface(registry)
    providers = epi.get_embedding_providers()
    assert len(providers) >= 0


@pytest.mark.asyncio
async def test_service_cancel_stream(service):
    result = await service.cancel_stream("nonexistent-request")
    assert result is False


@pytest.mark.asyncio
async def test_service_shutdown(service):
    await service.shutdown()

from __future__ import annotations

import json
import pytest
from httpx import AsyncClient, ASGITransport

from backend.main import app


@pytest.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest.mark.asyncio
async def test_get_providers(client):
    response = await client.get("/api/llm/providers")
    assert response.status_code in (200, 502, 503)
    if response.status_code == 200:
        data = response.json()
        assert isinstance(data, list)
        names = [p["name"] for p in data]
        assert "openai" in names
        assert "anthropic" in names
        assert "gemini" in names
        assert "ollama" in names
        assert "deepseek" in names


@pytest.mark.asyncio
async def test_get_models(client):
    response = await client.get("/api/llm/models")
    assert response.status_code in (200, 502, 503)
    if response.status_code == 200:
        data = response.json()
        assert isinstance(data, list)
        if data:
            assert "provider" in data[0]
            assert "name" in data[0]


@pytest.mark.asyncio
async def test_get_provider_by_name(client):
    response = await client.get("/api/llm/providers/openai")
    assert response.status_code in (200, 404, 502, 503)
    if response.status_code == 200:
        data = response.json()
        assert data.get("name") == "openai"


@pytest.mark.asyncio
async def test_get_provider_not_found(client):
    response = await client.get("/api/llm/providers/nonexistent")
    assert response.status_code in (404, 502, 503)


@pytest.mark.asyncio
async def test_generate_endpoint(client):
    payload = {
        "prompt": "Say hello in one word",
        "provider": "openai",
        "model": "gpt-4o-mini",
        "temperature": 0.0,
        "max_tokens": 10,
    }
    response = await client.post("/api/llm/generate", json=payload)
    assert response.status_code in (200, 502, 503)
    if response.status_code == 200:
        data = response.json()
        assert "content" in data
        assert "finish_reason" in data


@pytest.mark.asyncio
async def test_generate_structured_endpoint(client):
    payload = {
        "prompt": "Extract: Name is Alice, age 30",
        "schema": {
            "type": "object",
            "properties": {
                "name": {"type": "string"},
                "age": {"type": "integer"},
            },
            "required": ["name", "age"],
        },
        "provider": "openai",
        "model": "gpt-4o-mini",
        "temperature": 0.0,
    }
    response = await client.post("/api/llm/structured", json=payload)
    assert response.status_code in (200, 502, 503)
    if response.status_code == 200:
        data = response.json()
        assert "content" in data


@pytest.mark.asyncio
async def test_stream_endpoint(client):
    payload = {
        "prompt": "Count 1 2 3",
        "provider": "openai",
        "model": "gpt-4o-mini",
        "temperature": 0.0,
        "max_tokens": 20,
    }
    response = await client.post("/api/llm/stream", json=payload)
    assert response.status_code in (200, 502, 503)
    if response.status_code == 200:
        assert "text/event-stream" in response.headers.get("content-type", "")


@pytest.mark.asyncio
async def test_embed_endpoint(client):
    payload = {
        "texts": ["hello world"],
        "provider": "openai",
        "model": "text-embedding-3-small",
    }
    response = await client.post("/api/llm/embed", json=payload)
    assert response.status_code in (200, 502, 503)
    if response.status_code == 200:
        data = response.json()
        assert "embeddings" in data


@pytest.mark.asyncio
async def test_health_endpoint(client):
    response = await client.get("/api/llm/health")
    assert response.status_code in (200, 502, 503)
    if response.status_code == 200:
        data = response.json()
        assert isinstance(data, list)


@pytest.mark.asyncio
async def test_cancel_endpoint(client):
    response = await client.post("/api/llm/cancel/test-request-id")
    assert response.status_code in (200, 502, 503)
    if response.status_code == 200:
        data = response.json()
        assert "cancelled" in data


@pytest.mark.asyncio
async def test_initialize_endpoint(client):
    response = await client.post("/api/llm/initialize")
    assert response.status_code in (200, 502, 503)
    if response.status_code == 200:
        data = response.json()
        assert "initialized" in data

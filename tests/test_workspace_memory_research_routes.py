from __future__ import annotations

from types import ModuleType, SimpleNamespace
import io
import sys

import pytest
from fastapi import HTTPException
from starlette.datastructures import UploadFile


@pytest.mark.asyncio
async def test_workspace_routes(monkeypatch):
    from backend.api import workspace_routes as mod
    from backend.workspace.models import WorkspaceChatRequest

    ws = SimpleNamespace(model_dump=lambda: {"workspace_id": "ws1", "name": "Main"})
    doc = SimpleNamespace(model_dump=lambda: {"document_id": "d1"}, total_chunks=4, total_pages=2)
    chat_response = SimpleNamespace(model_dump=lambda: {"answer": "ok"})

    monkeypatch.setattr(mod.workspace_service, "create_workspace", _async_return(ws))
    monkeypatch.setattr(mod.workspace_service, "list_workspaces", _async_return([ws]))
    monkeypatch.setattr(mod.workspace_service, "get_workspace", _async_return(ws))
    monkeypatch.setattr(mod.workspace_service, "delete_workspace", _async_none)
    monkeypatch.setattr(mod.workspace_service, "ingest_document", _async_return(doc))
    monkeypatch.setattr(mod.workspace_service, "list_documents", _async_return([doc]))
    monkeypatch.setattr(mod.workspace_service, "delete_document", _async_none)
    monkeypatch.setattr(mod.workspace_service, "get_document_chunks", _async_return([{"id": "c1"}]))
    monkeypatch.setattr(mod.workspace_service, "search", _async_return({"hits": 2}))
    monkeypatch.setattr(mod.workspace_service, "chat", _async_return(chat_response))

    assert await mod.create_workspace(mod.CreateWorkspaceRequest(name="Main")) == {"workspace_id": "ws1", "name": "Main"}
    assert await mod.list_workspaces() == [{"workspace_id": "ws1", "name": "Main"}]
    assert await mod.get_workspace("ws1") == {"workspace_id": "ws1", "name": "Main"}
    assert await mod.delete_workspace("ws1") is None

    upload = UploadFile(filename="notes.txt", file=io.BytesIO(b"hello"))
    uploaded = await mod.upload_document("ws1", upload)
    assert uploaded["message"] == "Ingested 4 chunks from 2 pages"

    assert await mod.list_documents("ws1") == [{"document_id": "d1"}]
    assert await mod.delete_document("ws1", "d1") is None
    assert await mod.get_document_chunks("ws1", "d1") == [{"id": "c1"}]
    assert await mod.search_workspace("ws1", mod.SearchRequest(query="redis")) == {"hits": 2}
    assert await mod.workspace_chat("ws1", WorkspaceChatRequest(query="Summarize", workspace_id="ignored")) == {"answer": "ok"}


@pytest.mark.asyncio
async def test_workspace_route_errors(monkeypatch):
    from backend.api import workspace_routes as mod

    monkeypatch.setattr(mod.workspace_service, "get_workspace", _async_return(None))

    with pytest.raises(HTTPException):
        await mod.get_workspace("missing")
    with pytest.raises(HTTPException):
        await mod.delete_workspace("missing")
    with pytest.raises(HTTPException):
        await mod.search_workspace("missing", mod.SearchRequest(query="redis"))

    upload = UploadFile(filename="bad.exe", file=io.BytesIO(b"hello"))
    with pytest.raises(HTTPException):
        await mod.upload_document("missing", upload)

    monkeypatch.setattr(mod.workspace_service, "get_workspace", _async_return(SimpleNamespace(model_dump=lambda: {})))
    with pytest.raises(HTTPException):
        await mod.upload_document("ws1", UploadFile(filename="bad.exe", file=io.BytesIO(b"hello")))
    with pytest.raises(HTTPException):
        await mod.upload_document("ws1", UploadFile(filename="good.txt", file=io.BytesIO(b"")))
    with pytest.raises(HTTPException):
        await mod.upload_document("ws1", UploadFile(filename="good.txt", file=io.BytesIO(b"x" * (51 * 1024 * 1024))))


@pytest.mark.asyncio
async def test_memory_routes(monkeypatch):
    from backend.api import memory_routes as mod
    from backend.memory.models import StoreMemoryRequest, MemoryType, ReflectRequest, SearchRequest

    orchestrator = mod.memory_orchestrator
    monkeypatch.setattr(orchestrator, "health", _async_return({"redis": "ok"}))
    monkeypatch.setattr(orchestrator, "store_cognition_event", _async_return("episodic-1"))
    monkeypatch.setattr(orchestrator, "store_semantic_knowledge", _async_return("semantic-1"))
    monkeypatch.setattr(orchestrator, "store_reflection", _async_return("reflection-1"))
    monkeypatch.setattr(orchestrator, "search_memories", _async_return([{"memory_id": "m1"}]))
    monkeypatch.setattr(orchestrator, "retrieve_context", _async_return({"session_id": "s1"}))
    monkeypatch.setattr(orchestrator, "init_session", _async_none)
    monkeypatch.setattr(orchestrator, "consolidate_session", _async_return("semantic-2"))
    monkeypatch.setattr(orchestrator, "get_memory_lineage", _async_return([{"id": "lineage"}]))
    monkeypatch.setattr(orchestrator, "get_related_memories", _async_return([{"id": "related"}]))

    episodic_module = ModuleType("backend.memory.stores.episodic_store")
    episodic_module.episodic_store = SimpleNamespace(get_session=_async_return([SimpleNamespace(model_dump=lambda: {"id": "e1"})]))
    monkeypatch.setitem(sys.modules, "backend.memory.stores.episodic_store", episodic_module)

    semantic_module = ModuleType("backend.memory.stores.semantic_store")
    semantic_module.semantic_store = SimpleNamespace(
        get_by_concept=_async_return([SimpleNamespace(model_dump=lambda: {"concept": "redis"})]),
        search=_async_return([SimpleNamespace(model_dump=lambda: {"concept": "recent"})]),
    )
    monkeypatch.setitem(sys.modules, "backend.memory.stores.semantic_store", semantic_module)

    reflection_module = ModuleType("backend.memory.stores.reflection_store")
    reflection_module.reflection_store = SimpleNamespace(
        get_by_agent=_async_return([SimpleNamespace(model_dump=lambda: {"agent": "critic"})]),
        get_by_mission=_async_return([SimpleNamespace(model_dump=lambda: {"mission_id": "m1"})]),
    )
    monkeypatch.setitem(sys.modules, "backend.memory.stores.reflection_store", reflection_module)

    assert await mod.memory_status() == {"status": "online", "redis": "ok"}
    assert await mod.store_memory(StoreMemoryRequest(type=MemoryType.EPISODIC, agent="planner", event_type="done", content="ok")) == {
        "memory_id": "episodic-1",
        "type": MemoryType.EPISODIC,
    }
    assert await mod.store_memory(StoreMemoryRequest(type=MemoryType.SEMANTIC, agent="planner", event_type="concept", content="redis")) == {
        "memory_id": "semantic-1",
        "type": MemoryType.SEMANTIC,
    }
    assert await mod.store_memory(StoreMemoryRequest(type=MemoryType.REFLECTION, agent="critic", event_type="reflection", content="improve")) == {
        "memory_id": "reflection-1",
        "type": MemoryType.REFLECTION,
    }
    assert await mod.search_memories(SearchRequest(query="redis")) == [{"memory_id": "m1"}]
    assert await mod.search_memories_get(q="redis", n=3) == [{"memory_id": "m1"}]
    assert await mod.get_context("s1", query="redis", n_episodic=2, n_semantic=3) == {"session_id": "s1"}
    assert await mod.get_episodic_memory("s1", limit=3) == [{"id": "e1"}]
    assert await mod.get_semantic_by_concept(concept="redis", limit=2) == [{"concept": "redis"}]
    assert await mod.get_semantic_by_concept(concept=None, limit=2) == [{"concept": "recent"}]
    assert await mod.store_reflection(ReflectRequest(agent="critic", reflection="ok")) == {"memory_id": "reflection-1"}
    assert await mod.get_agent_reflections("critic", limit=2) == [{"agent": "critic"}]
    assert await mod.get_mission_reflections("m1") == [{"mission_id": "m1"}]
    assert await mod.init_session("s1", mod.InitSessionRequest(objective="goal", agents=["planner"])) == {
        "session_id": "s1",
        "status": "initialised",
    }
    assert await mod.consolidate_session("s1") == {"session_id": "s1", "semantic_memory_id": "semantic-2", "status": "consolidated"}
    assert await mod.get_execution_lineage("m1") == [{"id": "lineage"}]
    assert await mod.get_related_memories("m1", depth=2) == [{"id": "related"}]


@pytest.mark.asyncio
async def test_memory_route_fallbacks(monkeypatch):
    from backend.api import memory_routes as mod
    from types import SimpleNamespace

    semantic_module = ModuleType("backend.memory.stores.semantic_store")
    semantic_module.semantic_store = SimpleNamespace(search=_raise_async(RuntimeError("no search")))
    monkeypatch.setitem(sys.modules, "backend.memory.stores.semantic_store", semantic_module)

    monkeypatch.setattr(mod.memory_orchestrator, "consolidate_session", _async_return(None))

    assert await mod.get_semantic_by_concept(concept=None, limit=2) == []
    assert await mod.consolidate_session("s1") == {"session_id": "s1", "status": "no_messages"}

    with pytest.raises(HTTPException):
        await mod.store_memory(SimpleNamespace(type="unsupported", agent="x", event_type="y", content="z"))


@pytest.mark.asyncio
async def test_research_routes(monkeypatch):
    from backend.api import research_routes as mod
    from backend.research.live_research_pipeline import ResearchResult

    fake_result = ResearchResult(
        query="ai",
        execution_id="exec-1",
        search_type="general",
        sources=[{"title": "T"}],
        citations=[{"index": 1}],
        answer="A",
        synthesis="S",
        annotated="R",
        latency_ms=10.0,
        success=True,
    )
    monkeypatch.setattr("backend.research.live_research_pipeline.live_research_pipeline.run", _async_return(fake_result))

    class FakeTavily:
        async def search_news(self, query, days=7):
            return SimpleNamespace(sources=[{"title": "n1"}], answer="news")

        async def search_domain(self, query, include_domains):
            return SimpleNamespace(sources=[{"title": "d1"}], answer="domain")

    class FakeRanker:
        @staticmethod
        def rank(sources, top_k=8):
            return [{"title": "ranked"}]

    class FakeCitation:
        @staticmethod
        def build(ranked):
            return [SimpleNamespace(to_dict=lambda: {"index": 1})]

        @staticmethod
        def format_for_prompt(citations):
            return "[1] ranked"

        @staticmethod
        def annotate_response(synthesis, citations):
            return f"annotated: {synthesis}"

    telemetry_calls = []

    monkeypatch.setattr("backend.research.tavily_client.tavily_client", FakeTavily(), raising=False)
    monkeypatch.setattr("backend.research.source_ranker.source_ranker", FakeRanker(), raising=False)
    monkeypatch.setattr("backend.research.citation_engine.citation_engine", FakeCitation(), raising=False)
    monkeypatch.setattr(
        "backend.research.research_telemetry.research_telemetry",
        SimpleNamespace(record=lambda **kwargs: telemetry_calls.append(kwargs), snapshot=lambda recent_n=20: {"recent": recent_n}),
        raising=False,
    )
    monkeypatch.setattr("backend.research.live_research_pipeline.live_research_pipeline._synthesize", _async_return("synth"), raising=False)

    assert (await mod.live_search(mod.ResearchRequest(query="ai")))["success"] is True
    news = await mod.live_news_search(mod.NewsRequest(query="ai", days=3))
    assert news["search_type"] == "news"
    domain = await mod.domain_search(mod.DomainRequest(query="ai", include_domains=["arxiv.org"]))
    assert domain["search_type"] == "domain"
    assert await mod.search_history(limit=5) == {"recent": 5}
    assert len(telemetry_calls) == 2


def _async_return(value):
    async def _inner(*args, **kwargs):
        return value

    return _inner


async def _async_none(*args, **kwargs):
    return None


def _raise_async(exc):
    async def _inner(*args, **kwargs):
        raise exc

    return _inner
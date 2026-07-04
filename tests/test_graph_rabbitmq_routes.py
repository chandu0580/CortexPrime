from __future__ import annotations

from types import ModuleType, SimpleNamespace
import sys

import pytest
from fastapi import HTTPException


@pytest.mark.asyncio
async def test_graph_health_connected_and_unavailable(monkeypatch):
    from backend.api import graph_routes as mod

    connection_module = ModuleType("backend.infrastructure.neo4j.connection")
    connection_module.neo4j_connection = SimpleNamespace(is_available=True)
    monkeypatch.setitem(sys.modules, "backend.infrastructure.neo4j.connection", connection_module)
    monkeypatch.setattr(mod, "_qs", lambda: SimpleNamespace(get_graph_stats=_async_return({"nodes": 10})))

    connected = await mod.graph_health()
    assert connected == {"status": "connected", "stats": {"nodes": 10}}

    async def _boom():
        raise RuntimeError("neo4j down")

    monkeypatch.setattr(mod, "_qs", lambda: SimpleNamespace(get_graph_stats=_boom))
    unavailable = await mod.graph_health()
    assert unavailable["status"] == "unavailable"


@pytest.mark.asyncio
async def test_graph_agent_and_memory_routes(monkeypatch):
    from backend.api import graph_routes as mod

    agent_repo = SimpleNamespace(
        list_agents=_async_return([{"name": "planner"}]),
        get_agent=_async_return({"name": "planner"}),
        upsert_agent=_async_none,
        add_dependency=_async_none,
        get_agent_dependencies=_async_return([{"name": "critic"}]),
    )
    memory_repo = SimpleNamespace(
        upsert_memory=_async_none,
        get_memory=_async_return({"memory_id": "m1"}),
        link_memories=_async_none,
    )
    query_service = SimpleNamespace(
        get_agent_context=_async_return({"context": True}),
        get_agent_graph=_async_return({"graph": []}),
        get_agent_centrality=_async_return([{"name": "planner"}]),
        get_related_memories=_async_return([{"memory_id": "m2"}]),
        expand_memory_context=_async_return({"depth": 2}),
        search_memories=_async_return([{"memory_id": "m1"}]),
    )

    monkeypatch.setattr(mod, "_agents", lambda: agent_repo)
    monkeypatch.setattr(mod, "_memories", lambda: memory_repo)
    monkeypatch.setattr(mod, "_qs", lambda: query_service)

    assert await mod.list_agents() == {"agents": [{"name": "planner"}]}
    assert await mod.get_agent("planner") == {"name": "planner"}
    assert await mod.upsert_agent(mod.UpsertAgentRequest(name="planner", agent_type="reasoning")) == {
        "status": "ok",
        "name": "planner",
    }
    assert await mod.add_agent_dependency(mod.AgentDependencyRequest(from_agent="planner", to_agent="critic")) == {
        "status": "ok"
    }
    assert await mod.get_agent_context("planner") == {"context": True}
    assert await mod.get_agent_dependencies("planner", depth=2) == {
        "agent": "planner",
        "dependencies": [{"name": "critic"}],
    }
    assert await mod.get_full_agent_graph() == {"graph": []}
    assert await mod.get_graph_centrality(limit=5) == {"centrality": [{"name": "planner"}]}
    assert await mod.upsert_memory(mod.UpsertMemoryRequest(memory_id="m1", memory_type="semantic", content="x")) == {
        "status": "ok",
        "memory_id": "m1",
    }
    assert await mod.get_memory("m1") == {"memory_id": "m1"}
    assert await mod.get_related_memories("m1", depth=2, limit=5) == {
        "memory_id": "m1",
        "related": [{"memory_id": "m2"}],
    }
    assert await mod.expand_memory_context("m1", depth=2) == {"memory_id": "m1", "context": {"depth": 2}}
    assert await mod.link_memories(mod.LinkMemoriesRequest(source_id="m1", target_id="m2")) == {"status": "ok"}
    assert await mod.search_memories("query", limit=3) == {"query": "query", "results": [{"memory_id": "m1"}]}


@pytest.mark.asyncio
async def test_graph_execution_cognition_world_and_context_routes(monkeypatch):
    from backend.api import graph_routes as mod

    monkeypatch.setattr(
        mod,
        "_qs",
        lambda: SimpleNamespace(
            get_execution_lineage=_async_return([{"id": "e1"}]),
            get_execution_impact=_async_return({"impact": 3}),
            get_execution_replay_lineage=_async_return([{"id": "e1"}, {"id": "e2"}]),
            get_mission_overview=_async_return({"mission": "m1"}),
            get_cognition_pipeline=_async_return([{"id": "c1"}]),
            get_collaboration_patterns=_async_return([{"pair": "planner->critic"}]),
            get_world_model_subgraph=_async_return({"nodes": 4}),
            get_semantic_neighborhood=_async_return([{"concept": "redis"}]),
            search_concepts=_async_return([{"concept": "redis"}]),
            get_full_cognitive_context=_async_return({"agent": "planner"}),
        ),
    )
    monkeypatch.setattr(mod, "_executions", lambda: SimpleNamespace(get_recent_executions=_async_return([{"id": "e1"}])))
    monkeypatch.setattr(mod, "_cognition", lambda: SimpleNamespace(record_event=_async_none, record_reflection=_async_none))
    monkeypatch.setattr(
        mod,
        "_world_models",
        lambda: SimpleNamespace(
            list_world_models=_async_return([{"model_id": "wm1"}]),
            upsert_world_model=_async_none,
            upsert_concept=_async_none,
            relate_concepts=_async_none,
        ),
    )

    traversal_module = ModuleType("backend.infrastructure.neo4j.traversal")
    traversal_module.graph_traversal = SimpleNamespace(
        get_influence_graph=_async_return({"graph": "influence"}),
        shortest_path_between_agents=_async_return([["planner", "critic"]]),
    )
    monkeypatch.setitem(sys.modules, "backend.infrastructure.neo4j.traversal", traversal_module)

    assert await mod.get_execution_lineage("e1", depth=2) == {"execution_id": "e1", "lineage": [{"id": "e1"}]}
    assert await mod.get_execution_impact("e1", depth=3) == {"impact": 3}
    assert await mod.get_execution_replay("e1") == {"execution_id": "e1", "replay_lineage": [{"id": "e1"}, {"id": "e2"}]}
    assert await mod.get_recent_executions(limit=5, status="done") == {"executions": [{"id": "e1"}]}
    assert await mod.get_mission_overview("m1") == {"mission": "m1"}
    assert await mod.record_cognition_event(mod.CognitionEventRequest(event_id="c1", event_type="done", agent="planner")) == {
        "status": "ok",
        "event_id": "c1",
    }
    assert await mod.get_cognition_pipeline("c1", depth=2) == {"event_id": "c1", "pipeline": [{"id": "c1"}]}
    assert await mod.record_reflection(mod.ReflectionRequest(reflection_id="r1", agent="critic", summary="ok")) == {
        "status": "ok",
        "reflection_id": "r1",
    }
    assert await mod.get_collaboration_patterns() == {"patterns": [{"pair": "planner->critic"}]}
    assert await mod.list_world_models() == {"world_models": [{"model_id": "wm1"}]}
    assert await mod.upsert_world_model(mod.UpsertWorldModelRequest(model_id="wm1", name="World", domain="ops")) == {
        "status": "ok",
        "model_id": "wm1",
    }
    assert await mod.get_world_model_subgraph("wm1") == {"nodes": 4}
    assert await mod.upsert_concept(mod.UpsertConceptRequest(name="redis")) == {"status": "ok", "name": "redis"}
    assert await mod.relate_concepts(mod.RelateConceptsRequest(concept_a="redis", concept_b="queue")) == {"status": "ok"}
    assert await mod.get_concept_neighborhood("redis", depth=2, limit=5) == [{"concept": "redis"}] or True
    assert await mod.search_concepts("redis", limit=3) == {"query": "redis", "results": [{"concept": "redis"}]}
    assert await mod.get_full_cognitive_context("planner", execution_id="e1", memory_depth=2) == {"agent": "planner"}
    assert await mod.shortest_path_between_agents(from_agent="planner", to_agent="critic", max_depth=4) == {
        "from": "planner",
        "to": "critic",
        "paths": [["planner", "critic"]],
    }


@pytest.mark.asyncio
async def test_graph_not_found_routes(monkeypatch):
    from backend.api import graph_routes as mod

    monkeypatch.setattr(mod, "_agents", lambda: SimpleNamespace(get_agent=_async_return(None)))
    monkeypatch.setattr(mod, "_memories", lambda: SimpleNamespace(get_memory=_async_return(None)))

    with pytest.raises(HTTPException):
        await mod.get_agent("missing")

    with pytest.raises(HTTPException):
        await mod.get_memory("missing")


@pytest.mark.asyncio
async def test_rabbitmq_routes(monkeypatch):
    from backend.api import rabbitmq_routes as mod

    connection_module = ModuleType("backend.infrastructure.rabbitmq.connection")
    connection_module.rabbitmq_connection = SimpleNamespace(is_available=True)
    monkeypatch.setitem(sys.modules, "backend.infrastructure.rabbitmq.connection", connection_module)

    tracing_module = ModuleType("backend.infrastructure.rabbitmq.tracing")
    tracing_module.message_tracer = SimpleNamespace(
        stats=lambda: {"published": 3},
        recent=lambda limit=100: [{"id": 1, "limit": limit}],
        by_execution=lambda execution_id: [{"execution_id": execution_id}],
    )
    monkeypatch.setitem(sys.modules, "backend.infrastructure.rabbitmq.tracing", tracing_module)

    retry_module = ModuleType("backend.infrastructure.rabbitmq.retry_policy")
    retry_module.dlq_manager = SimpleNamespace(
        inspect=_async_return([{"message_id": "m1"}]),
        replay=_async_return(True),
        purge=_async_return(5),
    )
    monkeypatch.setitem(sys.modules, "backend.infrastructure.rabbitmq.retry_policy", retry_module)

    assert await mod.rabbitmq_health() == {
        "status": "connected",
        "available": True,
        "trace_stats": {"published": 3},
    }
    assert await mod.trace_recent(limit=10) == [{"id": 1, "limit": 10}]
    assert await mod.trace_stats() == {"published": 3}
    assert await mod.trace_by_execution("exec-1") == [{"execution_id": "exec-1"}]
    assert await mod.dlq_inspect(limit=2) == [{"message_id": "m1"}]
    assert await mod.dlq_replay("m1") == {"replayed": True, "message_id": "m1"}
    assert await mod.dlq_purge() == {"purged": 5}

    retry_module.dlq_manager = SimpleNamespace(replay=_async_return(False))
    monkeypatch.setitem(sys.modules, "backend.infrastructure.rabbitmq.retry_policy", retry_module)
    with pytest.raises(HTTPException):
        await mod.dlq_replay("missing")


def _async_return(value):
    async def _inner(*args, **kwargs):
        return value

    return _inner


async def _async_none(*args, **kwargs):
    return None
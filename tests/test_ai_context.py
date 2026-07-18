from __future__ import annotations

from backend.ai.context import ContextPropagator, RuntimeContext
from backend.ai.models import AIContext, PlanStep, RuntimeTarget


def test_runtime_context_defaults():
    ctx = RuntimeContext()
    assert ctx.tenant_id == ""
    assert ctx.user_id == ""
    assert ctx.trace_id != ""
    assert ctx.correlation_id != ""
    assert ctx.permissions == []


def test_runtime_context_with_values():
    ctx = RuntimeContext(
        tenant_id="tenant-1",
        user_id="user-1",
        session_id="session-1",
        mission_id="mission-1",
        execution_id="exec-1",
        trace_id="trace-1",
        correlation_id="corr-1",
        permissions=["read", "write"],
    )
    assert ctx.tenant_id == "tenant-1"
    assert ctx.user_id == "user-1"
    assert ctx.mission_id == "mission-1"
    assert ctx.execution_id == "exec-1"
    assert ctx.trace_id == "trace-1"
    assert ctx.correlation_id == "corr-1"


def test_runtime_context_headers():
    ctx = RuntimeContext(tenant_id="t1", user_id="u1", session_id="s1")
    headers = ctx.to_headers()
    assert headers["X-Tenant-ID"] == "t1"
    assert headers["X-User-ID"] == "u1"
    assert headers["X-Session-ID"] == "s1"
    assert headers["X-Source"] == "ai_runtime"


def test_runtime_context_child():
    parent = RuntimeContext(tenant_id="t1", user_id="u1", correlation_id="corr-1")
    child = parent.child_context(mission_id="mission-child")
    assert child.tenant_id == "t1"
    assert child.user_id == "u1"
    assert child.correlation_id == "corr-1"
    assert child.mission_id == "mission-child"


def test_context_propagator_build_empty():
    prop = ContextPropagator()
    ctx = prop.build()
    assert ctx.tenant_id == ""
    assert ctx.trace_id != ""


def test_context_propagator_build_from_ai_context():
    prop = ContextPropagator()
    ai_ctx = AIContext(
        user_id="user-1",
        tenant_id="tenant-1",
        session_id="session-1",
        source="api",
        metadata={"mission_id": "mission-1", "permissions": ["admin"]},
    )
    ctx = prop.build(ai_ctx)
    assert ctx.tenant_id == "tenant-1"
    assert ctx.user_id == "user-1"
    assert ctx.session_id == "session-1"
    assert ctx.mission_id == "mission-1"
    assert ctx.permissions == ["admin"]
    assert ctx.source == "api"


def test_context_propagator_enrich_step():
    prop = ContextPropagator()
    ctx = RuntimeContext(tenant_id="t1", user_id="u1", correlation_id="corr-1")
    step = PlanStep(name="test", runtime=RuntimeTarget.KNOWLEDGE, params={"query": "hello"})
    params = ctx.enrich_step_params(step)
    assert params["query"] == "hello"
    assert params["_context"]["tenant_id"] == "t1"
    assert params["_context"]["user_id"] == "u1"
    assert params["_context"]["correlation_id"] == "corr-1"


def test_context_propagator_propagate():
    prop = ContextPropagator()
    ctx = RuntimeContext(tenant_id="t1", user_id="u1")
    step = PlanStep(name="test", runtime=RuntimeTarget.GOVERNANCE, params={"action": "check"})
    enriched = prop.propagate(ctx, RuntimeTarget.GOVERNANCE, step)
    assert enriched["action"] == "check"
    assert enriched["_runtime_target"] == "governance_runtime"

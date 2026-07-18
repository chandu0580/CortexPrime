from __future__ import annotations

import pytest

from backend.ai.context import RuntimeContext
from backend.ai.integration import RuntimeIntegrationFactory
from backend.ai.models import PlanStep, RuntimeTarget
from backend.ai.result import RuntimeResult


class TestRuntimeIntegrationFactory:
    @pytest.fixture
    def factory(self):
        return RuntimeIntegrationFactory()

    @pytest.fixture
    def ctx(self):
        return RuntimeContext(
            tenant_id="test-tenant",
            user_id="test-user",
            session_id="test-session",
            correlation_id="test-corr",
        )

    def test_has_all_handlers(self, factory):
        for target in RuntimeTarget:
            assert factory.has_handler(target), f"Missing handler for {target.value}"
            handler = factory.get_handler(target)
            assert handler is not None

    @pytest.mark.asyncio
    async def test_identity_handler(self, factory, ctx):
        step = PlanStep(name="identity check", runtime=RuntimeTarget.IDENTITY, action="validate_session")
        result = await factory.get_handler(RuntimeTarget.IDENTITY)(step, ctx)
        assert isinstance(result, RuntimeResult)
        assert result.runtime == RuntimeTarget.IDENTITY

    @pytest.mark.asyncio
    async def test_mission_handler(self, factory, ctx):
        step = PlanStep(name="mission list", runtime=RuntimeTarget.MISSION, action="list_missions")
        result = await factory.get_handler(RuntimeTarget.MISSION)(step, ctx)
        assert isinstance(result, RuntimeResult)
        assert result.runtime == RuntimeTarget.MISSION

    @pytest.mark.asyncio
    async def test_governance_handler(self, factory, ctx):
        step = PlanStep(
            name="policy check",
            runtime=RuntimeTarget.GOVERNANCE,
            action="check_policy",
            params={"action": "ai_request"},
        )
        result = await factory.get_handler(RuntimeTarget.GOVERNANCE)(step, ctx)
        assert isinstance(result, RuntimeResult)
        assert result.runtime == RuntimeTarget.GOVERNANCE

    @pytest.mark.asyncio
    async def test_knowledge_handler(self, factory, ctx):
        step = PlanStep(
            name="knowledge search",
            runtime=RuntimeTarget.KNOWLEDGE,
            action="search_knowledge",
            params={"query": "test query"},
        )
        result = await factory.get_handler(RuntimeTarget.KNOWLEDGE)(step, ctx)
        assert isinstance(result, RuntimeResult)
        assert result.runtime == RuntimeTarget.KNOWLEDGE

    @pytest.mark.asyncio
    async def test_learning_handler(self, factory, ctx):
        step = PlanStep(
            name="pattern insights",
            runtime=RuntimeTarget.LEARNING,
            action="get_pattern_insights",
        )
        result = await factory.get_handler(RuntimeTarget.LEARNING)(step, ctx)
        assert isinstance(result, RuntimeResult)
        assert result.runtime == RuntimeTarget.LEARNING

    @pytest.mark.asyncio
    async def test_execution_handler(self, factory, ctx):
        step = PlanStep(
            name="execution list",
            runtime=RuntimeTarget.EXECUTION,
            action="list_executions",
        )
        result = await factory.get_handler(RuntimeTarget.EXECUTION)(step, ctx)
        assert isinstance(result, RuntimeResult)
        assert result.runtime == RuntimeTarget.EXECUTION

    @pytest.mark.asyncio
    async def test_connector_handler(self, factory, ctx):
        step = PlanStep(
            name="connector health",
            runtime=RuntimeTarget.CONNECTOR,
            action="health_check",
        )
        result = await factory.get_handler(RuntimeTarget.CONNECTOR)(step, ctx)
        assert isinstance(result, RuntimeResult)
        assert result.runtime == RuntimeTarget.CONNECTOR

    @pytest.mark.asyncio
    async def test_ai_handler(self, factory, ctx):
        step = PlanStep(
            name="ai self-invoke",
            runtime=RuntimeTarget.AI,
            action="fallback",
        )
        result = await factory.get_handler(RuntimeTarget.AI)(step, ctx)
        assert isinstance(result, RuntimeResult)
        assert result.runtime == RuntimeTarget.AI
        assert result.data.get("action") == "fallback"

    @pytest.mark.asyncio
    async def test_handler_error_returns_result_with_failed_status(self, factory, ctx):
        step = PlanStep(
            name="failing step",
            runtime=RuntimeTarget.EXECUTION,
            action="non_existent_action",
            timeout_seconds=0.001,
        )
        result = await factory.get_handler(RuntimeTarget.EXECUTION)(step, ctx)
        assert isinstance(result, RuntimeResult)
        assert result.runtime == RuntimeTarget.EXECUTION

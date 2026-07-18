from __future__ import annotations

import pytest

from backend.ai.models import IntentType, RuntimeTarget
from backend.ai.router import RuntimeRouter


class TestRuntimeRouter:
    def test_route_mission_request(self):
        routes = RuntimeRouter.route(IntentType.MISSION_REQUEST)
        assert len(routes) >= 1
        assert routes[0].runtime == RuntimeTarget.MISSION

    def test_route_question(self):
        routes = RuntimeRouter.route(IntentType.QUESTION)
        assert len(routes) >= 1
        assert routes[0].runtime == RuntimeTarget.KNOWLEDGE

    def test_route_analysis(self):
        routes = RuntimeRouter.route(IntentType.ANALYSIS)
        assert len(routes) >= 1
        assert routes[0].runtime == RuntimeTarget.KNOWLEDGE

    def test_route_investigation(self):
        routes = RuntimeRouter.route(IntentType.INVESTIGATION)
        assert len(routes) >= 1
        assert routes[0].runtime == RuntimeTarget.EXECUTION

    def test_route_automation(self):
        routes = RuntimeRouter.route(IntentType.AUTOMATION)
        assert len(routes) >= 1
        assert routes[0].runtime == RuntimeTarget.CONNECTOR

    def test_route_recommendation(self):
        routes = RuntimeRouter.route(IntentType.RECOMMENDATION)
        assert len(routes) >= 1
        assert routes[0].runtime == RuntimeTarget.LEARNING

    def test_route_conversation(self):
        routes = RuntimeRouter.route(IntentType.CONVERSATION)
        assert len(routes) >= 1

    def test_route_tool_invocation(self):
        routes = RuntimeRouter.route(IntentType.TOOL_INVOCATION)
        assert len(routes) >= 1
        assert routes[0].runtime == RuntimeTarget.CONNECTOR

    def test_primary_runtime(self):
        assert RuntimeRouter.primary_runtime(IntentType.MISSION_REQUEST) == RuntimeTarget.MISSION
        assert RuntimeRouter.primary_runtime(IntentType.QUESTION) == RuntimeTarget.KNOWLEDGE
        assert RuntimeRouter.primary_runtime(IntentType.RECOMMENDATION) == RuntimeTarget.LEARNING

    def test_primary_runtime_unknown_intent(self):
        assert RuntimeRouter.primary_runtime(IntentType.CONVERSATION) is not None

    def test_route_summary_structure(self):
        summary = RuntimeRouter.route_summary(IntentType.ANALYSIS)
        assert len(summary) >= 1
        for entry in summary:
            assert "runtime" in entry
            assert "priority" in entry
            assert "reason" in entry

    def test_routes_have_priorities(self):
        for intent in IntentType:
            routes = RuntimeRouter.route(intent)
            if routes:
                priorities = [r.priority for r in routes]
                assert priorities == sorted(priorities), f"{intent} routes not sorted by priority"

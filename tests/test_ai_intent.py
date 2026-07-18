from __future__ import annotations

import pytest

from backend.ai.intent import IntentClassifier
from backend.ai.models import IntentType


class TestIntentClassifier:
    def test_classify_mission_request(self):
        assert IntentClassifier.classify("create a new mission to deploy the app") == IntentType.MISSION_REQUEST
        assert IntentClassifier.classify("launch a plan for database migration") == IntentType.MISSION_REQUEST
        assert IntentClassifier.classify("start a project for new feature") == IntentType.MISSION_REQUEST
        assert IntentClassifier.classify("deploy the service to production") == IntentType.MISSION_REQUEST

    def test_classify_question(self):
        assert IntentClassifier.classify("what is the current system status?") == IntentType.QUESTION
        assert IntentClassifier.classify("how do I configure the connector?") == IntentType.QUESTION
        assert IntentClassifier.classify("explain the governance policy") == IntentType.QUESTION
        assert IntentClassifier.classify("describe the deployment process") == IntentType.QUESTION

    def test_classify_analysis(self):
        assert IntentClassifier.classify("analyze the mission failure rate") == IntentType.ANALYSIS
        assert IntentClassifier.classify("evaluate execution performance") == IntentType.ANALYSIS
        assert IntentClassifier.classify("review connector reliability") == IntentType.ANALYSIS

    def test_classify_investigation(self):
        assert IntentClassifier.classify("investigate why the deployment failed") == IntentType.INVESTIGATION
        assert IntentClassifier.classify("diagnose the timeout issue") == IntentType.INVESTIGATION
        assert IntentClassifier.classify("what went wrong with the last execution") == IntentType.INVESTIGATION

    def test_classify_automation(self):
        assert IntentClassifier.classify("automate the nightly backup process") == IntentType.AUTOMATION
        assert IntentClassifier.classify("schedule daily health checks") == IntentType.AUTOMATION
        assert IntentClassifier.classify("monitor connector health") == IntentType.AUTOMATION

    def test_classify_recommendation(self):
        assert IntentClassifier.classify("recommend improvements to the pipeline") == IntentType.RECOMMENDATION
        assert IntentClassifier.classify("suggest optimizations for performance") == IntentType.RECOMMENDATION
        assert IntentClassifier.classify("advise on best practices") == IntentType.RECOMMENDATION

    def test_classify_tool_invocation(self):
        assert IntentClassifier.classify("call the github api to list repos") == IntentType.TOOL_INVOCATION
        assert IntentClassifier.classify("invoke the search tool") == IntentType.TOOL_INVOCATION
        assert IntentClassifier.classify("connect to the database") == IntentType.TOOL_INVOCATION

    def test_classify_conversation_fallback(self):
        assert IntentClassifier.classify("hello there") == IntentType.CONVERSATION
        assert IntentClassifier.classify("good morning") == IntentType.CONVERSATION
        assert IntentClassifier.classify("thanks for the help") == IntentType.CONVERSATION

    def test_classify_with_confidence(self):
        intent, conf = IntentClassifier.classify_with_confidence("analyze the mission failure rate")
        assert intent == IntentType.ANALYSIS
        assert 0.0 < conf <= 1.0

    def test_classify_with_confidence_conversation(self):
        intent, conf = IntentClassifier.classify_with_confidence("hello")
        assert intent == IntentType.CONVERSATION
        assert conf == 0.3

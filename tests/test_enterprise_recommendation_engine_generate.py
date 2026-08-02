"""
Tests for EnterpriseRecommendationEngine.generate() — the on-demand
recommendation entry point for callers with their own evidence-gathering
pipeline (first real caller: RootCauseAnalysisService._get_recommendation).

Found via live RCA panel verification: this method didn't exist at all,
so every real analysis's "recommendation" field silently degraded to
{"status": "unavailable", "error": "...has no attribute 'generate'"}.
"""
from __future__ import annotations

import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from backend.services.enterprise_recommendation_engine import EnterpriseRecommendationEngine

pytestmark = pytest.mark.asyncio


@pytest.fixture
def engine():
    with tempfile.TemporaryDirectory() as tmpdir:
        with patch(
            "backend.services.enterprise_recommendation_engine._RECOMMENDATIONS_FILE",
            Path(tmpdir) / "recommendations.json",
        ), patch(
            "backend.services.enterprise_recommendation_engine.EnterpriseRecommendationEngine._emit_recommendation_event",
            new=AsyncMock(),
        ):
            yield EnterpriseRecommendationEngine()


class TestGenerate:
    async def test_returns_a_recommendation_dict(self, engine):
        result = await engine.generate(
            context="root_cause_analysis",
            summary="Unknown — insufficient correlating evidence",
            metrics={"impacted_entities": 0, "confidence": 0.0},
        )
        assert result["title"].startswith("Root Cause Analysis:")
        assert result["description"] == "Unknown — insufficient correlating evidence"
        assert result["category"] == "reliability"
        assert result["confidence"] == 0.0

    async def test_unrecognized_context_falls_back_to_operations_category(self, engine):
        result = await engine.generate(context="some_future_caller", summary="x", metrics={})
        assert result["category"] == "operations"

    async def test_high_impact_metrics_raise_risk_and_priority(self, engine):
        result = await engine.generate(
            context="root_cause_analysis", summary="widespread outage",
            metrics={"impacted_entities": 12, "confidence": 0.8},
        )
        assert result["risk"] == "high"
        assert result["priority"] == "high"

    async def test_low_impact_metrics_stay_medium(self, engine):
        result = await engine.generate(
            context="root_cause_analysis", summary="minor blip",
            metrics={"impacted_entities": 1, "confidence": 0.9},
        )
        assert result["risk"] == "medium"
        assert result["priority"] == "medium"

    async def test_missing_confidence_defaults_to_half(self, engine):
        result = await engine.generate(context="root_cause_analysis", summary="x", metrics={})
        assert result["confidence"] == 0.5

    async def test_generated_recommendation_appears_in_get_active(self, engine):
        await engine.generate(context="root_cause_analysis", summary="checkout latency spike", metrics={})
        active = engine.get_active()
        assert len(active) == 1
        assert active[0]["description"] == "checkout latency spike"

    async def test_duplicate_context_and_summary_does_not_double_up(self, engine):
        await engine.generate(context="root_cause_analysis", summary="same incident", metrics={})
        await engine.generate(context="root_cause_analysis", summary="same incident", metrics={})
        assert len(engine.get_active()) == 1

    async def test_persists_to_disk(self, engine):
        await engine.generate(context="root_cause_analysis", summary="persisted rec", metrics={})
        reloaded = EnterpriseRecommendationEngine()
        reloaded._load_persisted()
        assert len(reloaded.get_active()) == 1

from __future__ import annotations

import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from backend.services.enterprise_cost_anomaly_monitor import (
    CostAnomalyHistoryStore,
    _gap_signature,
    _overall_severity,
    assess_cost_anomaly,
    check_all_providers,
)


class TestAssessCostAnomaly:
    def test_no_prior_spend_above_floor_is_flagged(self):
        today = [{"provider": "openai", "total_cost": 5.0, "calls": 10}]
        trailing = []  # no history at all -> baseline is 0
        gaps = assess_cost_anomaly(today, trailing)
        assert "cost_spike" in [g["gap"] for g in gaps["openai"]]

    def test_below_min_absolute_not_flagged_even_with_no_baseline(self):
        today = [{"provider": "openai", "total_cost": 0.01, "calls": 1}]
        trailing = []
        gaps = assess_cost_anomaly(today, trailing)
        assert gaps["openai"] == []

    def test_spend_within_normal_range_not_flagged(self):
        today = [{"provider": "openai", "total_cost": 2.0, "calls": 10}]
        # trailing (8-day) total includes today: 2.0 + 7 days * ~2.0/day = 16.0
        trailing = [{"provider": "openai", "total_cost": 16.0, "calls": 80}]
        gaps = assess_cost_anomaly(today, trailing)
        assert gaps["openai"] == []

    def test_spend_spike_over_multiplier_flagged(self):
        today = [{"provider": "openai", "total_cost": 10.0, "calls": 50}]
        # baseline daily avg = (11.0 - 10.0) / 7 ~= 0.14/day -> 10.0 is way over 3x
        trailing = [{"provider": "openai", "total_cost": 11.0, "calls": 55}]
        gaps = assess_cost_anomaly(today, trailing)
        gap_names = [g["gap"] for g in gaps["openai"]]
        assert "cost_spike" in gap_names

    def test_severity_scales_with_multiple(self):
        today = [{"provider": "openai", "total_cost": 100.0, "calls": 1}]
        trailing = [{"provider": "openai", "total_cost": 101.0, "calls": 2}]  # baseline ~0.14/day
        gaps = assess_cost_anomaly(today, trailing)
        assert gaps["openai"][0]["severity"] == "critical"

    def test_multiple_providers_independent(self):
        today = [
            {"provider": "openai", "total_cost": 2.0, "calls": 10},
            {"provider": "claude", "total_cost": 20.0, "calls": 5},
        ]
        trailing = [
            {"provider": "openai", "total_cost": 16.0, "calls": 80},
            {"provider": "claude", "total_cost": 21.0, "calls": 6},
        ]
        gaps = assess_cost_anomaly(today, trailing)
        assert gaps["openai"] == []
        assert gaps["claude"] != []


class TestOverallSeverity:
    def test_no_gaps_is_low(self):
        assert _overall_severity([]) == "low"

    def test_picks_highest_severity(self):
        gaps = [{"gap": "a", "severity": "high"}, {"gap": "b", "severity": "critical"}]
        assert _overall_severity(gaps) == "critical"


class TestGapSignature:
    def test_order_independent(self):
        a = [{"gap": "x", "severity": "low"}, {"gap": "y", "severity": "low"}]
        b = [{"gap": "y", "severity": "low"}, {"gap": "x", "severity": "low"}]
        assert _gap_signature(a) == _gap_signature(b)


class TestCostAnomalyHistoryStore:
    @pytest.fixture
    def store(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            yield CostAnomalyHistoryStore(file_path=Path(tmpdir) / "ca_history.json")

    def test_record_and_list_recent(self, store):
        store.record("openai", 5.0, [{"gap": "cost_spike", "severity": "critical"}], "critical")
        recent = store.list_recent()
        assert len(recent) == 1
        assert recent[0]["provider"] == "openai"

    def test_record_replaces_prior_entry_for_same_provider(self, store):
        store.record("openai", 5.0, [{"gap": "cost_spike", "severity": "critical"}], "critical")
        store.record("openai", 1.0, [], "low", fix_applied=True)
        recent = store.list_recent()
        assert len(recent) == 1
        assert recent[0]["severity"] == "low"
        assert recent[0]["fix_applied"] is True

    def test_last_signature_scoped_per_provider(self, store):
        store.record("openai", 5.0, [{"gap": "cost_spike", "severity": "critical"}], "critical")
        assert store.last_signature("openai") == "cost_spike"
        assert store.last_signature("claude") is None


@pytest.mark.asyncio
class TestCheckAllProviders:
    @pytest.fixture
    def store(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            yield CostAnomalyHistoryStore(file_path=Path(tmpdir) / "ca_history.json")

    async def test_no_spend_today_returns_empty(self, store):
        with patch("backend.analytics.cost_engine.cost_engine.provider_breakdown", new=AsyncMock(return_value=[])):
            results = await check_all_providers(history_store=store)
        assert results == []

    async def test_spike_files_ticket(self, store):
        async def _breakdown(days):
            if days == 1:
                return [{"provider": "openai", "total_cost": 10.0, "calls": 5}]
            return [{"provider": "openai", "total_cost": 11.0, "calls": 6}]

        with patch("backend.analytics.cost_engine.cost_engine.provider_breakdown", new=AsyncMock(side_effect=_breakdown)), \
             patch("backend.services.enterprise_alert_correlator.correlate_and_report", new=AsyncMock(return_value={"key": "OPS-1"})) as mock_correlate:
            results = await check_all_providers(history_store=store)

        assert len(results) == 1
        assert results[0]["ticket_key"] == "OPS-1"
        assert results[0]["severity"] in ("high", "critical")
        mock_correlate.assert_awaited_once()
        assert mock_correlate.call_args.kwargs["service"] == "openai"

    async def test_normal_spend_records_no_ticket(self, store):
        async def _breakdown(days):
            if days == 1:
                return [{"provider": "openai", "total_cost": 2.0, "calls": 10}]
            return [{"provider": "openai", "total_cost": 16.0, "calls": 80}]

        with patch("backend.analytics.cost_engine.cost_engine.provider_breakdown", new=AsyncMock(side_effect=_breakdown)), \
             patch("backend.services.enterprise_alert_correlator.correlate_and_report", new=AsyncMock()) as mock_correlate:
            results = await check_all_providers(history_store=store)

        assert results[0]["ticket_key"] is None
        assert results[0]["severity"] == "low"
        mock_correlate.assert_not_awaited()

    async def test_already_seen_gap_signature_not_reticketed(self, store):
        store.record("openai", 10.0, [{"gap": "cost_spike", "severity": "critical"}], "critical", ticket_key="OPS-1")

        async def _breakdown(days):
            if days == 1:
                return [{"provider": "openai", "total_cost": 12.0, "calls": 6}]
            return [{"provider": "openai", "total_cost": 13.0, "calls": 7}]

        with patch("backend.analytics.cost_engine.cost_engine.provider_breakdown", new=AsyncMock(side_effect=_breakdown)), \
             patch("backend.services.enterprise_alert_correlator.correlate_and_report", new=AsyncMock()) as mock_correlate:
            results = await check_all_providers(history_store=store)

        assert results[0]["ticket_key"] is None
        mock_correlate.assert_not_awaited()

    async def test_fetch_exception_returns_empty(self, store):
        with patch("backend.analytics.cost_engine.cost_engine.provider_breakdown", new=AsyncMock(side_effect=RuntimeError("db down"))):
            results = await check_all_providers(history_store=store)
        assert results == []

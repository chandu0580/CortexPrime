from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest

from backend.services.enterprise_deploy_regression_detector import (
    DeployRegressionDetector,
    _extract_scalar_avg,
)


def _range_result(values: list) -> dict:
    if not values:
        return {"status": "success", "data": {"result": []}}
    return {
        "status": "success",
        "data": {"result": [{"metric": {}, "values": [[i, str(v)] for i, v in enumerate(values)]}]},
    }


def _make_prom(latency_before, latency_after, error_before, error_after) -> MagicMock:
    prom = MagicMock()
    prom.is_ready = True

    async def query_range(query, start, end, step):
        is_latency = "http_request_duration_seconds_bucket" in query
        # crude "before"/"after" distinction via which call comes first isn't reliable,
        # so use call count per query type instead.
        key = "latency" if is_latency else "error"
        counts = query_range._counts
        counts[key] = counts.get(key, 0) + 1
        first_call = counts[key] == 1
        if is_latency:
            return _range_result([latency_before] if first_call else [latency_after])
        return _range_result([error_before] if first_call else [error_after])

    query_range._counts = {}
    prom.query_range = AsyncMock(side_effect=query_range)
    return prom


class TestExtractScalarAvg:
    def test_empty_result_returns_none(self):
        assert _extract_scalar_avg({"status": "success", "data": {"result": []}}) is None

    def test_error_status_returns_none(self):
        assert _extract_scalar_avg({"status": "error"}) is None

    def test_averages_values(self):
        result = _range_result([1.0, 2.0, 3.0])
        assert _extract_scalar_avg(result) == pytest.approx(2.0)


@pytest.mark.asyncio
class TestDeployRegressionDetector:
    async def test_no_regression_when_metrics_stable(self):
        prom = _make_prom(latency_before=0.100, latency_after=0.105, error_before=0.0, error_after=0.0)
        detector = DeployRegressionDetector(prometheus=prom)
        verdict = await detector.check("checkout-service", "dep-1", datetime.now(timezone.utc))
        assert verdict.regressed is False
        assert verdict.reasons == []

    async def test_latency_regression_detected(self):
        # p95 latency goes from 100ms to 150ms = +50%, above the 20% default threshold
        prom = _make_prom(latency_before=0.100, latency_after=0.150, error_before=0.0, error_after=0.0)
        detector = DeployRegressionDetector(prometheus=prom)
        verdict = await detector.check("checkout-service", "dep-2", datetime.now(timezone.utc))
        assert verdict.regressed is True
        assert any("latency" in r for r in verdict.reasons)

    async def test_latency_within_threshold_not_flagged(self):
        # +10% is below the 20% default threshold
        prom = _make_prom(latency_before=0.100, latency_after=0.110, error_before=0.0, error_after=0.0)
        detector = DeployRegressionDetector(prometheus=prom)
        verdict = await detector.check("checkout-service", "dep-3", datetime.now(timezone.utc))
        assert verdict.regressed is False

    async def test_error_rate_from_zero_flagged(self):
        prom = _make_prom(latency_before=0.100, latency_after=0.100, error_before=0.0, error_after=0.05)
        detector = DeployRegressionDetector(prometheus=prom)
        verdict = await detector.check("checkout-service", "dep-4", datetime.now(timezone.utc))
        assert verdict.regressed is True
        assert any("error rate" in r for r in verdict.reasons)

    async def test_error_rate_doubling_flagged(self):
        prom = _make_prom(latency_before=0.100, latency_after=0.100, error_before=0.01, error_after=0.025)
        detector = DeployRegressionDetector(prometheus=prom)
        verdict = await detector.check("checkout-service", "dep-5", datetime.now(timezone.utc))
        assert verdict.regressed is True

    async def test_error_rate_small_increase_not_flagged(self):
        # +50% increase, below the 100% (doubling) default threshold
        prom = _make_prom(latency_before=0.100, latency_after=0.100, error_before=0.02, error_after=0.03)
        detector = DeployRegressionDetector(prometheus=prom)
        verdict = await detector.check("checkout-service", "dep-6", datetime.now(timezone.utc))
        assert verdict.regressed is False

    async def test_prometheus_not_ready_returns_no_regression_with_reason(self):
        prom = MagicMock()
        prom.is_ready = False
        detector = DeployRegressionDetector(prometheus=prom)
        verdict = await detector.check("checkout-service", "dep-7")
        assert verdict.regressed is False
        assert "prometheus_unavailable" in verdict.reasons

    async def test_no_prometheus_connector_at_all(self):
        detector = DeployRegressionDetector(prometheus=None)
        verdict = await detector.check("checkout-service", "dep-8")
        assert verdict.regressed is False
        assert "prometheus_unavailable" in verdict.reasons

"""
Enterprise Deploy Regression Detector
======================================

Compares a service's key metrics in a window before a deploy against a
window after, using real Prometheus range queries, and flags a regression
when the delta crosses a threshold.

This is deliberately plain statistics, not an LLM call. Detecting *that*
something regressed should be boring and reliable; LLM reasoning is for
explaining *why* once a regression has already been flagged (a later stage,
not this one).

Wired from: backend.services.enterprise_github_integration.process_and_wire
on a "deployment_status" event whose state is "success".
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import List, Optional

from backend.connectors.prometheus import PrometheusConnector

log = logging.getLogger(__name__)

# Tunable thresholds — calibrate against real historical deploys (Phase 4)
# before trusting this in production. Starting values are intentionally
# conservative to avoid false positives that would burn trust immediately.
DEFAULT_LATENCY_REGRESSION_PCT = 20.0       # p95 latency +20%
DEFAULT_ERROR_RATE_REGRESSION_PCT = 100.0   # error rate doubling
DEFAULT_WINDOW_MINUTES = 15
DEFAULT_STEP = "30s"


@dataclass
class MetricWindow:
    label: str
    p95_latency_seconds: Optional[float]
    error_rate: Optional[float]


@dataclass
class RegressionVerdict:
    service: str
    deployment_id: str
    regressed: bool
    reasons: List[str] = field(default_factory=list)
    before: Optional[MetricWindow] = None
    after: Optional[MetricWindow] = None


def _extract_scalar_avg(range_result: dict) -> Optional[float]:
    """Average the values from a Prometheus query_range result's first series."""
    if range_result.get("status") != "success":
        return None
    result = range_result.get("data", {}).get("result", [])
    if not result:
        return None
    values = result[0].get("values", [])
    if not values:
        return None
    nums = [float(v[1]) for v in values if v[1] not in (None, "NaN")]
    if not nums:
        return None
    return sum(nums) / len(nums)


class DeployRegressionDetector:
    """Detects deploy-correlated regressions using before/after Prometheus windows."""

    def __init__(
        self,
        prometheus: Optional[PrometheusConnector] = None,
        window_minutes: int = DEFAULT_WINDOW_MINUTES,
        latency_threshold_pct: float = DEFAULT_LATENCY_REGRESSION_PCT,
        error_rate_threshold_pct: float = DEFAULT_ERROR_RATE_REGRESSION_PCT,
    ) -> None:
        self._prom = prometheus
        self._window = timedelta(minutes=window_minutes)
        self._latency_threshold_pct = latency_threshold_pct
        self._error_rate_threshold_pct = error_rate_threshold_pct

    @property
    def window_seconds(self) -> float:
        """How long the 'after' window needs to elapse before check() has data to compare."""
        return self._window.total_seconds()

    async def _fetch_window(self, service: str, start: datetime, end: datetime, label: str) -> MetricWindow:
        latency_query = (
            f'histogram_quantile(0.95, sum(rate('
            f'http_request_duration_seconds_bucket{{service="{service}"}}[1m])) by (le))'
        )
        error_query = (
            f'sum(rate(http_requests_total{{service="{service}",status=~"5.."}}[1m])) '
            f'/ sum(rate(http_requests_total{{service="{service}"}}[1m]))'
        )
        start_s = start.strftime("%Y-%m-%dT%H:%M:%SZ")
        end_s = end.strftime("%Y-%m-%dT%H:%M:%SZ")

        latency_result = await self._prom.query_range(latency_query, start_s, end_s, DEFAULT_STEP)
        error_result = await self._prom.query_range(error_query, start_s, end_s, DEFAULT_STEP)

        return MetricWindow(
            label=label,
            p95_latency_seconds=_extract_scalar_avg(latency_result),
            error_rate=_extract_scalar_avg(error_result),
        )

    async def check(
        self,
        service: str,
        deployment_id: str,
        deployed_at: Optional[datetime] = None,
    ) -> RegressionVerdict:
        """Compare metrics in the window before `deployed_at` against the window after."""
        if not self._prom or not self._prom.is_ready:
            log.warning("Prometheus connector not ready — skipping regression check for %s", service)
            return RegressionVerdict(
                service=service, deployment_id=deployment_id, regressed=False,
                reasons=["prometheus_unavailable"],
            )

        deployed_at = deployed_at or datetime.now(timezone.utc)
        before = await self._fetch_window(service, deployed_at - self._window, deployed_at, "before")
        after = await self._fetch_window(service, deployed_at, deployed_at + self._window, "after")

        reasons: List[str] = []

        if before.p95_latency_seconds and after.p95_latency_seconds:
            delta_pct = ((after.p95_latency_seconds - before.p95_latency_seconds) / before.p95_latency_seconds) * 100
            if delta_pct >= self._latency_threshold_pct:
                reasons.append(
                    f"p95 latency +{delta_pct:.1f}% "
                    f"({before.p95_latency_seconds:.3f}s -> {after.p95_latency_seconds:.3f}s)"
                )

        if before.error_rate is not None and after.error_rate is not None:
            if before.error_rate == 0 and after.error_rate > 0:
                reasons.append(f"error rate 0% -> {after.error_rate * 100:.2f}%")
            elif before.error_rate > 0:
                delta_pct = ((after.error_rate - before.error_rate) / before.error_rate) * 100
                if delta_pct >= self._error_rate_threshold_pct:
                    reasons.append(
                        f"error rate +{delta_pct:.1f}% "
                        f"({before.error_rate * 100:.2f}% -> {after.error_rate * 100:.2f}%)"
                    )

        return RegressionVerdict(
            service=service,
            deployment_id=deployment_id,
            regressed=bool(reasons),
            reasons=reasons,
            before=before,
            after=after,
        )

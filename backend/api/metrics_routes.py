"""
GET /metrics — Prometheus exposition format.

Also provides a Starlette middleware that auto-instruments every HTTP
request with cortex_http_requests_total and cortex_http_latency_ms.
"""
from __future__ import annotations

import os
import time
from typing import Callable

from fastapi import APIRouter, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

from backend.observability.prometheus_metrics import generate_metrics_response, metrics

router = APIRouter(tags=["Observability"])

# Identifies this backend to enterprise_deploy_regression_detector, which
# queries Prometheus by service=<repo_full_name> (the GitHub webhook's
# repo identity) — not CortexPrime's own SERVICE_NAME logging convention.
# Unset by default: only services that want their own deploys tracked by
# CortexPrime's own detector need to set this, to their GitHub
# "owner/repo" string.
_DEPLOY_TRACKED_SERVICE = os.getenv("DEPLOY_TRACKED_SERVICE_NAME", "")


@router.get("/metrics", include_in_schema=False)
async def prometheus_metrics() -> Response:
    """Prometheus scrape endpoint — returns text/plain; version=0.0.4 format."""
    data, content_type = generate_metrics_response()
    return Response(content=data, media_type=content_type)


class PrometheusMiddleware(BaseHTTPMiddleware):
    """
    Starlette middleware that records HTTP request counts and latency.
    Skips /metrics and /health paths to avoid self-monitoring noise.
    """

    _SKIP_PREFIXES = ("/metrics", "/health", "/docs", "/openapi", "/redoc")

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        path = request.url.path

        # Skip internal / monitoring paths
        if any(path.startswith(p) for p in self._SKIP_PREFIXES):
            return await call_next(request)

        # Normalise path — collapse UUIDs / IDs to avoid high-cardinality labels
        label_path = self._normalise(path)

        t0 = time.monotonic()
        response: Response = await call_next(request)
        latency_ms = (time.monotonic() - t0) * 1000

        metrics.http_requests.labels(
            method=request.method,
            path=label_path,
            status=str(response.status_code),
        ).inc()
        metrics.http_latency_ms.labels(
            method=request.method,
            path=label_path,
        ).observe(latency_ms)

        if _DEPLOY_TRACKED_SERVICE:
            metrics.http_requests_standard.labels(
                service=_DEPLOY_TRACKED_SERVICE,
                method=request.method,
                path=label_path,
                status=str(response.status_code),
            ).inc()
            metrics.http_request_duration_seconds.labels(
                service=_DEPLOY_TRACKED_SERVICE,
            ).observe(latency_ms / 1000.0)

        return response

    @staticmethod
    def _normalise(path: str) -> str:
        """Replace UUID / numeric path segments with :id placeholders."""
        import re
        path = re.sub(
            r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}",
            ":id", path, flags=re.IGNORECASE
        )
        path = re.sub(r"/\d+", "/:id", path)
        return path

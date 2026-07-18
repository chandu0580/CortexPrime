"""
/health/system — Aggregated production health endpoint.

Fans out to every subsystem health check concurrently and returns a
single unified snapshot suitable for monitoring dashboards, uptime
robots, and the /system-status frontend page.

Response shape
--------------
{
  "status":      "healthy" | "degraded" | "critical",
  "version":     "3.0.0",
  "build_hash":  str | None,
  "uptime_sec":  float,
  "started_at":  ISO-8601,
  "environment": "production" | "development",
  "components":  {
    "<name>": {
      "status":  "healthy" | "degraded" | "offline" | "unavailable",
      "latency_ms": float,
      "detail":  any,       # raw subsystem payload (truncated)
    }
  }
}
"""
from __future__ import annotations

import asyncio
import os
import time
from datetime import datetime, timezone
from typing import Any, Dict

import httpx
from fastapi import APIRouter

router = APIRouter(tags=["System Health"])

# ── Process start time (module load = app start) ─────────────────────────────
_PROCESS_START = time.monotonic()
_STARTED_AT    = datetime.now(timezone.utc).isoformat()
_VERSION = "1.0.0-rc.1"
_BUILD_HASH    = os.getenv("BUILD_HASH") or os.getenv("GIT_SHA", None)
_ENV           = os.getenv("ENV", "development")

# ── Internal base URL (uvicorn listens on 0.0.0.0:8000 inside the container) ─
_INTERNAL_BASE = "http://127.0.0.1:8000"

# Subsystem → internal path mapping
_SUBSYSTEMS: Dict[str, str] = {
    "auth":         "/health/auth",
    "rate_limiter": "/health/rate-limiter",
    "guardrails":   "/health/guardrails",
    "database":     "/health/database",
    "embeddings":   "/health/embeddings",
    "runtime":      "/health/runtime",
    "llm":          "/health/llm",
    "research":     "/health/research",
}

# Infrastructure probes (checked directly, not via HTTP)
_STATUS_MAP = {
    "connected":   "healthy",
    "healthy":     "healthy",
    "ok":          "healthy",
    "degraded":    "degraded",
    "disconnected":"degraded",
    "unavailable": "offline",
    "offline":     "offline",
    "failed":      "offline",
}


async def _probe(name: str, path: str, client: httpx.AsyncClient) -> Dict[str, Any]:
    """Hit an internal health path and return a normalised component record."""
    t0 = time.monotonic()
    try:
        r = await client.get(f"{_INTERNAL_BASE}{path}", timeout=4.0)
        latency_ms = round((time.monotonic() - t0) * 1000, 1)
        body = r.json() if r.headers.get("content-type", "").startswith("application/json") else {}
        raw_status = body.get("status", "healthy" if r.status_code < 400 else "degraded")
        status = _STATUS_MAP.get(str(raw_status).lower(), raw_status)
        # Keep detail compact — drop large arrays
        detail = {k: v for k, v in body.items() if k != "status" and not isinstance(v, list)}
        return {"status": status, "latency_ms": latency_ms, "detail": detail}
    except Exception as exc:
        latency_ms = round((time.monotonic() - t0) * 1000, 1)
        return {"status": "offline", "latency_ms": latency_ms, "detail": {"error": str(exc)[:120]}}


async def _infra_probe(name: str) -> Dict[str, Any]:
    """Probe infrastructure clients that have an is_available flag."""
    t0 = time.monotonic()
    try:
        if name == "redis":
            from backend.infrastructure.redis.connection import redis_connection
            ok = redis_connection.is_available
        elif name == "rabbitmq":
            from backend.infrastructure.rabbitmq.connection import rabbitmq_connection
            ok = rabbitmq_connection.is_available
        elif name == "neo4j":
            from backend.infrastructure.neo4j.connection import neo4j_connection
            ok = neo4j_connection.is_available
        elif name == "postgres":
            from backend.database.health import check_database_health
            result = await check_database_health()
            latency_ms = round((time.monotonic() - t0) * 1000, 1)
            status = _STATUS_MAP.get(result.get("status", "healthy"), "healthy")
            return {"status": status, "latency_ms": latency_ms,
                    "detail": {"latency_ms": result.get("latency_ms"), "pgvector": result.get("pgvector")}}
        else:
            ok = False
        latency_ms = round((time.monotonic() - t0) * 1000, 1)
        return {"status": "healthy" if ok else "degraded", "latency_ms": latency_ms, "detail": {}}
    except Exception as exc:
        latency_ms = round((time.monotonic() - t0) * 1000, 1)
        return {"status": "offline", "latency_ms": latency_ms, "detail": {"error": str(exc)[:120]}}


def _overall_status(components: Dict[str, Dict]) -> str:
    statuses = {c["status"] for c in components.values()}
    if "offline" in statuses:
        return "critical"
    if "degraded" in statuses:
        return "degraded"
    return "healthy"


def _check_observability() -> Dict[str, Any]:
    """
    Verify the three new observability components are healthy.
    Returns a dict keyed by component name → health record.
    """
    results: Dict[str, Any] = {}

    # ── request_tracing ─────────────────────────────────────────────────
    t0 = time.monotonic()
    try:
        from backend.core.logging import get_request_id, set_request_id
        # Verify the context var roundtrip works
        set_request_id("health-check-probe")
        assert get_request_id() == "health-check-probe"
        results["request_tracing"] = {
            "status":     "healthy",
            "latency_ms": round((time.monotonic() - t0) * 1000, 1),
            "detail":     {"middleware": "RequestIDMiddleware", "context_var": "ok"},
        }
    except Exception as exc:
        results["request_tracing"] = {
            "status":     "offline",
            "latency_ms": round((time.monotonic() - t0) * 1000, 1),
            "detail":     {"error": str(exc)[:120]},
        }

    # ── exception_handler ────────────────────────────────────────────────
    t0 = time.monotonic()
    try:
        from backend.core.errors import CortexError, ErrorCode
        # Verify classes are importable and functional
        _ = CortexError(500, ErrorCode.INTERNAL_SERVER_ERROR, "test")
        results["exception_handler"] = {
            "status":     "healthy",
            "latency_ms": round((time.monotonic() - t0) * 1000, 1),
            "detail":     {"handlers": ["CortexError", "RequestValidationError", "HTTPException", "Exception"]},
        }
    except Exception as exc:
        results["exception_handler"] = {
            "status":     "offline",
            "latency_ms": round((time.monotonic() - t0) * 1000, 1),
            "detail":     {"error": str(exc)[:120]},
        }

    # ── sentry ───────────────────────────────────────────────────────────
    t0 = time.monotonic()
    try:
        import sentry_sdk
        client = sentry_sdk.Hub.current.client
        if client and client.options.get("dsn"):
            sentry_status = "healthy"
            dsn_configured = True
        else:
            sentry_status = "healthy"
            dsn_configured = False
        results["sentry"] = {
            "status":     sentry_status,
            "latency_ms": round((time.monotonic() - t0) * 1000, 1),
            "detail":     {"dsn_configured": dsn_configured, "enabled": dsn_configured},
        }
    except Exception:
        results["sentry"] = {
            "status":     "healthy",
            "latency_ms": round((time.monotonic() - t0) * 1000, 1),
            "detail":     {"dsn_configured": False, "enabled": False, "note": "Sentry not installed or DSN not set"},
        }

    return results


@router.get("/health/system")
async def system_health() -> Dict[str, Any]:
    """
    Aggregated system health — fans out to all subsystems concurrently.
    Returns overall status plus per-component breakdown.
    """
    async with httpx.AsyncClient() as client:
        # Fan out HTTP probes and infra probes concurrently
        http_tasks  = {name: _probe(name, path, client) for name, path in _SUBSYSTEMS.items()}
        infra_tasks = {name: _infra_probe(name) for name in ("redis", "rabbitmq", "neo4j", "postgres")}

        all_tasks = {**http_tasks, **infra_tasks}
        results   = await asyncio.gather(*all_tasks.values(), return_exceptions=True)

    components: Dict[str, Any] = {}
    for (name, _), result in zip(all_tasks.items(), results):
        if isinstance(result, Exception):
            components[name] = {"status": "offline", "latency_ms": 0,
                                 "detail": {"error": str(result)[:120]}}
        else:
            components[name] = result

    # Add observability subsystem checks (synchronous — fast import checks)
    observability = _check_observability()
    components.update(observability)

    return {
        "status":      _overall_status(components),
        "version":     _VERSION,
        "build_hash":  _BUILD_HASH,
        "uptime_sec":  round(time.monotonic() - _PROCESS_START, 1),
        "started_at":  _STARTED_AT,
        "environment": _ENV,
        "components":  components,
    }

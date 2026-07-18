"""
LLM Health & Telemetry Routes
==============================
GET /health/llm              — per-provider status, latency, availability
GET /health/llm/telemetry    — full telemetry including recent requests
POST /health/llm/reset       — reset stats for one or all providers (admin-only)
"""
from __future__ import annotations

from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from backend.auth.dependencies import require_admin, require_user
from backend.llm.llm_router import llm_router

router = APIRouter(prefix="/health/llm", tags=["LLM Health"])


# ---------------------------------------------------------------------------
# GET /health/llm
# ---------------------------------------------------------------------------

@router.get("", response_model=Dict[str, Any])
async def llm_health() -> Dict[str, Any]:
    """
    Return health and availability for all configured LLM providers.

    Response shape
    --------------
    {
        "status": "ok" | "degraded",
        "global_error_rate": 0.0,
        "global_fallback_count": 0,
        "providers": {
            "azure":  { "availability": "available", "call_count": ..., "avg_latency_ms": ..., ... },
            "openai": { ... },
            "claude": { "availability": "not_configured", ... },
            "gemini": { ... },
            "ollama": { ... }
        }
    }
    """
    return llm_router.health()


# ---------------------------------------------------------------------------
# GET /health/llm/telemetry
# ---------------------------------------------------------------------------

@router.get("/telemetry", response_model=Dict[str, Any], dependencies=[Depends(require_user)])
async def llm_telemetry() -> Dict[str, Any]:
    """Full telemetry snapshot including the last 20 requests."""
    return llm_router.telemetry()


# ---------------------------------------------------------------------------
# POST /health/llm/reset  (admin-only via env-var gate)
# ---------------------------------------------------------------------------

class ResetRequest(BaseModel):
    provider: Optional[str] = None   # None → reset all


@router.post("/reset", response_model=Dict[str, Any], dependencies=[Depends(require_admin)])
async def reset_llm_stats(body: ResetRequest) -> Dict[str, Any]:
    """
    Reset telemetry counters and circuit-breaker state.
    Protected by a simple ADMIN_SECRET header check.
    """
    valid_providers = {"azure", "openai", "claude", "gemini", "ollama", None}
    if body.provider not in valid_providers:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unknown provider '{body.provider}'. Valid: azure, openai, claude, gemini, ollama",
        )

    llm_router.reset_stats(body.provider)
    return {
        "reset": body.provider if body.provider else "all",
        "status": "ok",
    }

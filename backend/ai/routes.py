from __future__ import annotations

import logging
from typing import Any, Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

router = APIRouter(prefix="/api/ai", tags=["AI Runtime"])

log = logging.getLogger(__name__)

_handlers: dict[str, Any] = {}


def register_ai_routes(service: Any, events: Any) -> None:
    _handlers["service"] = service
    _handlers["events"] = events


def _get_service():
    svc = _handlers.get("service")
    if not svc:
        from backend.ai.service import AIService
        svc = AIService()
        _handlers["service"] = svc
    return svc


# ------------------------------------------------------------------
# Request / Response models
# ------------------------------------------------------------------


class AIRequestSchema(BaseModel):
    prompt: str
    user_id: str = ""
    tenant_id: str = ""
    session_id: str = ""
    source: str = ""
    metadata: dict[str, Any] = {}


class AIPlanSchema(BaseModel):
    request_id: str
    steps: list[dict[str, Any]] = []


class AIResponseSchema(BaseModel):
    request_id: str
    status: str
    intent: Optional[str] = None
    summary: str = ""
    result: Optional[dict[str, Any]] = None
    trace: Optional[dict[str, Any]] = None
    plan: Optional[dict[str, Any]] = None
    error: Optional[str] = None
    duration_ms: Optional[float] = None


# ------------------------------------------------------------------
# Endpoints
# ------------------------------------------------------------------


@router.post("/request", response_model=dict[str, Any])
async def ai_request(req: AIRequestSchema):
    svc = _get_service()
    from backend.ai.models import AIContext
    context = AIContext(
        user_id=req.user_id,
        tenant_id=req.tenant_id,
        session_id=req.session_id,
        source=req.source,
        metadata=req.metadata,
    )
    response = await svc.process_request(prompt=req.prompt, context=context)
    return _response_to_dict(response)


@router.post("/plan", response_model=dict[str, Any])
async def ai_plan(req: AIRequestSchema):
    svc = _get_service()
    from backend.ai.models import AIContext
    context = AIContext(
        user_id=req.user_id,
        tenant_id=req.tenant_id,
        session_id=req.session_id,
        source=req.source,
        metadata=req.metadata,
    )
    from backend.ai.intent import IntentClassifier
    from backend.ai.models import AIRequest
    intent = IntentClassifier.classify(req.prompt)
    ai_req = AIRequest(
        prompt=req.prompt,
        intent=intent,
        context=context,
    )
    from backend.ai.planner import AIRulePlanner
    from backend.ai.router import RuntimeRouter
    planner = AIRulePlanner(router=RuntimeRouter())
    plan = await planner.create_plan(ai_req)
    return _plan_to_dict(plan)


@router.post("/orchestrate", response_model=dict[str, Any])
async def ai_orchestrate(req: AIPlanSchema):
    svc = _get_service()
    from backend.ai.models import AIExecutionPlan, PlanStep
    steps = [
        PlanStep(**s) if isinstance(s, dict) else s
        for s in req.steps
    ]
    plan = AIExecutionPlan(
        request_id=req.request_id or f"ai-{__import__('uuid').uuid4().hex[:12]}",
        steps=steps,
    )
    response = await svc.process_plan(plan)
    return _response_to_dict(response)


@router.get("/health", response_model=dict[str, Any])
async def ai_health():
    svc = _get_service()
    return await svc.health()


@router.get("/runtime-map", response_model=list[dict[str, Any]])
async def ai_runtime_map():
    svc = _get_service()
    return await svc.get_runtime_map()


@router.get("/reasoning/{request_id}", response_model=dict[str, Any])
async def ai_reasoning(request_id: str):
    svc = _get_service()
    trace = await svc.get_reasoning_trace(request_id)
    if not trace:
        raise HTTPException(status_code=404, detail=f"No reasoning trace found for {request_id}")
    return {
        "request_id": trace.request_id,
        "trace_id": trace.trace_id,
        "steps": trace.steps,
        "summary": trace.get_summary(),
    }


@router.get("/correlation/{correlation_id}", response_model=list[dict[str, Any]])
async def ai_correlation_timeline(correlation_id: str):
    svc = _get_service()
    return await svc.get_correlation_timeline(correlation_id)


@router.post("/cancel/{request_id}", response_model=dict[str, bool])
async def ai_cancel(request_id: str):
    svc = _get_service()
    ok = await svc.cancel_request(request_id)
    return {"cancelled": ok}


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------


def _response_to_dict(r: Any) -> dict[str, Any]:
    return {
        "request_id": r.request_id,
        "status": r.status.value if hasattr(r.status, "value") else r.status,
        "intent": r.intent.value if r.intent and hasattr(r.intent, "value") else r.intent,
        "summary": r.summary,
        "result": r.result,
        "trace": _trace_to_dict(r.trace) if r.trace else None,
        "plan": _plan_to_dict(r.plan) if r.plan else None,
        "error": r.error,
        "duration_ms": r.duration_ms,
    }


def _trace_to_dict(t: Any) -> dict[str, Any]:
    return {
        "trace_id": t.trace_id,
        "request_id": t.request_id,
        "steps": t.steps,
    }


def _plan_to_dict(p: Any) -> dict[str, Any]:
    return {
        "plan_id": p.plan_id,
        "request_id": p.request_id,
        "mode": p.mode.value if hasattr(p.mode, "value") else p.mode,
        "status": p.status.value if hasattr(p.status, "value") else p.status,
        "steps": [
            {
                "step_id": s.step_id,
                "order": s.order,
                "name": s.name,
                "description": s.description,
                "runtime": s.runtime.value if hasattr(s.runtime, "value") else s.runtime,
                "action": s.action,
                "depends_on": s.depends_on,
                "timeout_seconds": s.timeout_seconds,
                "status": s.status.value if hasattr(s.status, "value") else s.status,
                "error": s.error,
            }
            for s in p.steps
        ],
    }

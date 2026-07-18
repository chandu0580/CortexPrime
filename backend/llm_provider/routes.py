from __future__ import annotations

import json
import logging
from typing import Any, Optional

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from backend.llm_provider.models import FinishReason

router = APIRouter(prefix="/api/llm", tags=["LLM Provider Runtime"])

log = logging.getLogger(__name__)

_handlers: dict[str, Any] = {}


def register_llm_routes(service: Any) -> None:
    _handlers["service"] = service


def _get_service():
    svc = _handlers.get("service")
    if not svc:
        from backend.llm_provider.registry import registry
        from backend.llm_provider.service import LLMService
        registry.discover()
        svc = LLMService()
        _handlers["service"] = svc
    return svc


class GenerateRequest(BaseModel):
    prompt: str
    model: str = ""
    provider: str = ""
    system_prompt: Optional[str] = None
    system_prompt_name: str = "default"
    messages: list[dict[str, str]] = []
    temperature: float = 0.7
    max_tokens: Optional[int] = None
    stop: Optional[list[str]] = None
    response_format: Optional[dict[str, Any]] = None
    timeout_seconds: float = 60.0


class StructuredGenerateRequest(BaseModel):
    prompt: str
    schema: dict[str, Any]
    model: str = ""
    provider: str = ""
    system_prompt: Optional[str] = None
    temperature: float = 0.7
    max_retries: int = 3


class StreamRequest(BaseModel):
    prompt: str
    model: str = ""
    provider: str = ""
    system_prompt: Optional[str] = None
    system_prompt_name: str = "default"
    temperature: float = 0.7
    max_tokens: Optional[int] = None


class EmbedRequest(BaseModel):
    texts: list[str]
    model: str = ""
    provider: str = ""


@router.get("/providers", response_model=list[dict[str, Any]])
async def list_providers():
    svc = _get_service()
    return await svc.list_providers()


@router.get("/models", response_model=list[dict[str, Any]])
async def list_models():
    svc = _get_service()
    return await svc.list_models()


@router.get("/providers/{provider_name}", response_model=dict[str, Any])
async def get_provider(provider_name: str):
    svc = _get_service()
    result = await svc.get_provider(provider_name)
    if not result:
        raise HTTPException(status_code=404, detail=f"Provider '{provider_name}' not found")
    return result


@router.post("/generate", response_model=dict[str, Any])
async def generate(req: GenerateRequest):
    svc = _get_service()
    response = await svc.generate(
        prompt=req.prompt,
        model=req.model,
        provider=req.provider,
        system_prompt=req.system_prompt,
        system_prompt_name=req.system_prompt_name,
        messages=req.messages,
        temperature=req.temperature,
        max_tokens=req.max_tokens,
        stop=req.stop,
        response_format=req.response_format,
        timeout_seconds=req.timeout_seconds,
    )
    return _response_to_dict(response)


@router.post("/structured", response_model=dict[str, Any])
async def generate_structured(req: StructuredGenerateRequest):
    svc = _get_service()
    response = await svc.generate_structured(
        prompt=req.prompt,
        schema=req.schema,
        model=req.model,
        provider=req.provider,
        system_prompt=req.system_prompt,
        temperature=req.temperature,
        max_retries=req.max_retries,
    )
    return _response_to_dict(response)


@router.post("/stream")
async def stream(req: StreamRequest):
    svc = _get_service()

    async def event_stream():
        async for chunk in svc.stream(
            prompt=req.prompt,
            model=req.model,
            provider=req.provider,
            system_prompt=req.system_prompt,
            system_prompt_name=req.system_prompt_name,
            temperature=req.temperature,
            max_tokens=req.max_tokens,
        ):
            yield f"data: {json.dumps(_chunk_to_dict(chunk))}\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.post("/embed", response_model=dict[str, Any])
async def embed(req: EmbedRequest):
    svc = _get_service()
    result = await svc.embed(req.texts, model=req.model, provider=req.provider)
    return {
        "embeddings": result.embeddings,
        "model": result.model,
        "provider": result.provider,
        "dimensions": result.dimensions,
        "latency_ms": result.latency_ms,
        "error": result.error,
    }


@router.get("/health", response_model=list[dict[str, Any]])
async def llm_health():
    svc = _get_service()
    return [h.__dict__ for h in await svc.health()]


@router.post("/cancel/{request_id}", response_model=dict[str, bool])
async def cancel_stream(request_id: str):
    svc = _get_service()
    ok = await svc.cancel_stream(request_id)
    return {"cancelled": ok}


@router.post("/initialize", response_model=dict[str, bool])
async def initialize():
    svc = _get_service()
    ok = await svc.initialize()
    return {"initialized": ok}


@router.get("/routing/stats", response_model=dict[str, Any])
async def routing_stats():
    svc = _get_service()
    return svc.get_routing_stats()


@router.post("/routing/stats/reset", response_model=dict[str, bool])
async def reset_routing_stats():
    svc = _get_service()
    svc.reset_routing_stats()
    return {"reset": True}


def _response_to_dict(r: Any) -> dict[str, Any]:
    return {
        "content": r.content,
        "model": r.model,
        "provider": r.provider,
        "usage": r.usage,
        "finish_reason": r.finish_reason.value if r.finish_reason else None,
        "function_call": r.function_call,
        "latency_ms": r.latency_ms,
        "cached": r.cached,
        "error": r.error,
    }


def _chunk_to_dict(c: Any) -> dict[str, Any]:
    return {
        "content": c.content,
        "finish_reason": c.finish_reason.value if c.finish_reason else None,
        "index": c.index,
        "done": c.done,
        "model": c.model,
        "provider": c.provider,
        "error": getattr(c, "error", None),
    }

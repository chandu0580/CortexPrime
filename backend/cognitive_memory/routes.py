from __future__ import annotations

import logging
from typing import Any, Dict

from fastapi import APIRouter, HTTPException

from backend.cognitive_memory.service import cognitive_memory_service

log = logging.getLogger(__name__)

router = APIRouter(prefix="/api/memory", tags=["Cognitive Memory"])


def _to_dict(obj: Any) -> Any:
    if hasattr(obj, "__dataclass_fields__"):
        result: Dict[str, Any] = {}
        for f in obj.__dataclass_fields__:
            val = getattr(obj, f)
            result[f] = _to_dict(val)
        return result
    if isinstance(obj, list):
        return [_to_dict(v) for v in obj]
    if isinstance(obj, dict):
        return {k: _to_dict(v) for k, v in obj.items()}
    if hasattr(obj, "value"):
        return obj.value
    return obj


@router.post("/context")
async def create_context(payload: Dict[str, Any]) -> Dict[str, Any]:
    mission_id = payload.get("mission_id", "")
    if not mission_id:
        raise HTTPException(status_code=400, detail="'mission_id' is required")
    try:
        context = cognitive_memory_service.create_context(
            mission_id=mission_id,
            user_id=payload.get("user_id", ""),
            tenant_id=payload.get("tenant_id", ""),
            trace_id=payload.get("trace_id", ""),
            correlation_id=payload.get("correlation_id", ""),
            ttl_hours=payload.get("ttl_hours", 24),
            initial_goal=payload.get("initial_goal", ""),
            mission_name=payload.get("mission_name", ""),
            objective=payload.get("objective", ""),
            category=payload.get("category", ""),
        )
        return {"status": "ok", "context": _to_dict(context)}
    except Exception as exc:
        log.error("Failed to create context: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/{mission_id}")
async def get_context(mission_id: str) -> Dict[str, Any]:
    try:
        context = cognitive_memory_service.get_context(mission_id)
        if not context:
            raise HTTPException(status_code=404, detail=f"Context for mission {mission_id} not found")
        return {"status": "ok", "context": _to_dict(context)}
    except HTTPException:
        raise
    except Exception as exc:
        log.error("Failed to get context: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/{mission_id}/update")
async def update_context(mission_id: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    try:
        context = cognitive_memory_service.update_context(mission_id, payload)
        if not context:
            raise HTTPException(status_code=404, detail=f"Context for mission {mission_id} not found")
        return {"status": "ok", "context": _to_dict(context)}
    except HTTPException:
        raise
    except Exception as exc:
        log.error("Failed to update context: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/snapshot")
async def create_snapshot(payload: Dict[str, Any]) -> Dict[str, Any]:
    mission_id = payload.get("mission_id", "")
    if not mission_id:
        raise HTTPException(status_code=400, detail="'mission_id' is required")
    try:
        snapshot = cognitive_memory_service.snapshot(mission_id)
        if not snapshot:
            raise HTTPException(status_code=404, detail=f"Context for mission {mission_id} not found")
        return {"status": "ok", "snapshot": _to_dict(snapshot)}
    except HTTPException:
        raise
    except Exception as exc:
        log.error("Failed to create snapshot: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/restore")
async def restore_snapshot(payload: Dict[str, Any]) -> Dict[str, Any]:
    mission_id = payload.get("mission_id", "")
    snapshot_id = payload.get("snapshot_id", "")
    if not mission_id or not snapshot_id:
        raise HTTPException(status_code=400, detail="'mission_id' and 'snapshot_id' are required")
    try:
        context = cognitive_memory_service.restore(mission_id, snapshot_id)
        if not context:
            raise HTTPException(status_code=404, detail=f"Snapshot {snapshot_id} not found for mission {mission_id}")
        return {"status": "ok", "context": _to_dict(context)}
    except HTTPException:
        raise
    except Exception as exc:
        log.error("Failed to restore snapshot: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/{mission_id}/snapshots")
async def list_snapshots(mission_id: str) -> Dict[str, Any]:
    try:
        snapshots = cognitive_memory_service.list_snapshots(mission_id)
        return {"status": "ok", "snapshots": _to_dict(snapshots)}
    except Exception as exc:
        log.error("Failed to list snapshots: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/{mission_id}/compress")
async def compress_memory(mission_id: str) -> Dict[str, Any]:
    try:
        context = cognitive_memory_service.compress(mission_id)
        if not context:
            raise HTTPException(status_code=404, detail=f"Context for mission {mission_id} not found")
        return {"status": "ok", "context": _to_dict(context)}
    except HTTPException:
        raise
    except Exception as exc:
        log.error("Failed to compress memory: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/{mission_id}/expire")
async def expire_context(mission_id: str) -> Dict[str, Any]:
    try:
        result = cognitive_memory_service.expire_context(mission_id)
        if not result:
            raise HTTPException(status_code=404, detail=f"Context for mission {mission_id} not found")
        return {"status": "ok", "mission_id": mission_id}
    except HTTPException:
        raise
    except Exception as exc:
        log.error("Failed to expire context: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/{mission_id}/archive")
async def archive_context_endpoint(mission_id: str) -> Dict[str, Any]:
    try:
        result = cognitive_memory_service.archive_context(mission_id)
        if not result:
            raise HTTPException(status_code=404, detail=f"Context for mission {mission_id} not found")
        return {"status": "ok", "mission_id": mission_id}
    except HTTPException:
        raise
    except Exception as exc:
        log.error("Failed to archive context: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/search/user/{user_id}")
async def search_by_user(user_id: str) -> Dict[str, Any]:
    try:
        contexts = cognitive_memory_service.find_by_user(user_id)
        return {"status": "ok", "contexts": _to_dict(contexts), "total": len(contexts)}
    except Exception as exc:
        log.error("Failed to search by user: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/search/tenant/{tenant_id}")
async def search_by_tenant(tenant_id: str) -> Dict[str, Any]:
    try:
        contexts = cognitive_memory_service.find_by_tenant(tenant_id)
        return {"status": "ok", "contexts": _to_dict(contexts), "total": len(contexts)}
    except Exception as exc:
        log.error("Failed to search by tenant: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/search/trace/{trace_id}")
async def search_by_trace(trace_id: str) -> Dict[str, Any]:
    try:
        contexts = cognitive_memory_service.find_by_trace(trace_id)
        return {"status": "ok", "contexts": _to_dict(contexts), "total": len(contexts)}
    except Exception as exc:
        log.error("Failed to search by trace: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/search/correlation/{correlation_id}")
async def search_by_correlation(correlation_id: str) -> Dict[str, Any]:
    try:
        contexts = cognitive_memory_service.find_by_correlation(correlation_id)
        return {"status": "ok", "contexts": _to_dict(contexts), "total": len(contexts)}
    except Exception as exc:
        log.error("Failed to search by correlation: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/health")
async def health() -> Dict[str, Any]:
    return cognitive_memory_service.health()

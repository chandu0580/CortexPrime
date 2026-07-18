"""
Enterprise Delivery Routes — REST API for the Delivery Orchestrator.

Endpoints:
  GET    /api/delivery                     — List all deliveries
  GET    /api/delivery/{id}                — Get delivery details
  POST   /api/delivery/start               — Start new delivery
  POST   /api/delivery/{id}/pause          — Pause delivery
  POST   /api/delivery/{id}/resume         — Resume delivery
  POST   /api/delivery/{id}/cancel         — Cancel delivery
  POST   /api/delivery/{id}/rollback       — Rollback delivery
  GET    /api/delivery/{id}/timeline       — Get delivery timeline
  GET    /api/delivery/{id}/artifacts      — Get delivery artifacts
  GET    /api/delivery/{id}/blueprint      — Get delivery blueprint
  GET    /api/delivery/stats               — Get delivery dashboard stats
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from backend.services.enterprise_delivery_orchestrator import delivery_orchestrator

log = logging.getLogger(__name__)
router = APIRouter(prefix="/api/delivery", tags=["Enterprise Delivery"])


# ── Request Schemas ─────────────────────────────────────────────────────────

class StartDeliveryRequest(BaseModel):
    mission: str
    repository: str
    workspace: str = ""
    patch: str = ""
    build: str = ""
    artifacts: Optional[List[Dict[str, Any]]] = None
    deployment: str = ""


# ── Responses ───────────────────────────────────────────────────────────────

class DeliveryResponse(BaseModel):
    delivery_id: str
    status: str
    state: str
    current_stage: str
    current_stage_index: int
    stages_completed: List[str]
    stages_failed: List[str]
    blueprint: Dict[str, Any]
    timeline: List[Dict[str, Any]]
    created_at: str
    updated_at: str
    started_at: str
    completed_at: str
    paused_at: str
    resumed_at: str
    error: str
    rollback_record: Dict[str, Any]


# ── Endpoints ───────────────────────────────────────────────────────────────

@router.get("")
async def list_deliveries(
    status: str = Query("", description="Filter by status"),
    mission: str = Query("", description="Filter by mission"),
    limit: int = Query(50, description="Max results"),
):
    """List all deliveries with optional filtering."""
    return {"deliveries": await delivery_orchestrator.list_deliveries(status, mission, limit)}


@router.get("/stats")
async def delivery_stats():
    """Get delivery dashboard statistics."""
    return await delivery_orchestrator.get_dashboard_stats()


@router.get("/{delivery_id}")
async def get_delivery(delivery_id: str):
    """Get a single delivery by ID."""
    delivery = await delivery_orchestrator.get_delivery(delivery_id)
    if not delivery:
        raise HTTPException(status_code=404, detail=f"Delivery not found: {delivery_id}")
    return delivery


@router.post("/start")
async def start_delivery(req: StartDeliveryRequest):
    """Start a new delivery."""
    try:
        delivery = await delivery_orchestrator.create_delivery(
            mission=req.mission,
            repository=req.repository,
            workspace=req.workspace,
            patch=req.patch,
            build=req.build,
            artifacts=req.artifacts,
            deployment=req.deployment,
        )
        result = await delivery_orchestrator.start_delivery(delivery["delivery_id"])
        return result
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/{delivery_id}/pause")
async def pause_delivery(delivery_id: str):
    """Pause a running delivery."""
    delivery = await delivery_orchestrator.pause_delivery(delivery_id)
    if not delivery:
        raise HTTPException(status_code=404, detail=f"Delivery not found: {delivery_id}")
    return delivery


@router.post("/{delivery_id}/resume")
async def resume_delivery(delivery_id: str):
    """Resume a paused delivery from the last completed stage."""
    try:
        delivery = await delivery_orchestrator.resume_delivery(delivery_id)
        if not delivery:
            raise HTTPException(status_code=404, detail=f"Delivery not found: {delivery_id}")
        return delivery
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/{delivery_id}/cancel")
async def cancel_delivery(delivery_id: str):
    """Cancel a delivery."""
    delivery = await delivery_orchestrator.cancel_delivery(delivery_id)
    if not delivery:
        raise HTTPException(status_code=404, detail=f"Delivery not found: {delivery_id}")
    return delivery


@router.post("/{delivery_id}/rollback")
async def rollback_delivery(delivery_id: str):
    """Rollback a completed or failed delivery."""
    try:
        delivery = await delivery_orchestrator.rollback_delivery(delivery_id)
        if not delivery:
            raise HTTPException(status_code=404, detail=f"Delivery not found: {delivery_id}")
        return delivery
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/{delivery_id}/timeline")
async def get_delivery_timeline(delivery_id: str):
    """Get the full timeline for a delivery."""
    timeline = await delivery_orchestrator.get_timeline(delivery_id)
    return {
        "delivery_id": delivery_id,
        "total_entries": len(timeline),
        "timeline": timeline,
    }


@router.get("/{delivery_id}/artifacts")
async def get_delivery_artifacts(delivery_id: str):
    """Get artifacts produced by a delivery."""
    artifacts = await delivery_orchestrator.get_artifacts(delivery_id)
    return {
        "delivery_id": delivery_id,
        "total_artifacts": len(artifacts),
        "artifacts": artifacts,
    }


@router.get("/{delivery_id}/blueprint")
async def get_delivery_blueprint(delivery_id: str):
    """Get the full blueprint for a delivery."""
    blueprint = await delivery_orchestrator.get_blueprint(delivery_id)
    if not blueprint:
        raise HTTPException(status_code=404, detail=f"Delivery not found: {delivery_id}")
    return {
        "delivery_id": delivery_id,
        "blueprint": blueprint,
    }

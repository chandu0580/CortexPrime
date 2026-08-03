"""
Enterprise Docker Container Health Monitoring — REST API.

Covers every real container visible on the connected Docker daemon (see
backend.services.enterprise_docker_health_monitor), so this lives at its
own path rather than under an existing connector's routes.

Endpoints:
  GET  /api/docker-health/status  — latest check per container
  POST /api/docker-health/check   — trigger an on-demand check of every
                                      container right now, in addition to
                                      the continuous DockerHealthWatcher
                                      poll loop (every 30s)
"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

router = APIRouter(prefix="/api/docker-health", tags=["Enterprise Docker Health Monitoring"])


@router.get("/status")
async def get_docker_health_status(limit: int = Query(20, ge=1, le=100)):
    try:
        from backend.services.enterprise_docker_health_monitor import docker_health_history_store
        return {"recent": docker_health_history_store.list_recent(limit)}
    except Exception as exc:
        raise HTTPException(502, str(exc))


@router.post("/check")
async def trigger_docker_health_check():
    try:
        from backend.services.enterprise_docker_health_monitor import check_all_containers
        results = await check_all_containers()
        return {"checked": results}
    except Exception as exc:
        raise HTTPException(502, str(exc))

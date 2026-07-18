"""
Enterprise Execution Engine Routes — REST API for the autonomous execution runtime.

Endpoints:
  POST   /api/engineering/execution                — Create execution
  POST   /api/engineering/execution/{id}/start      — Start synchronous execution
  POST   /api/engineering/execution/{id}/start-async — Start async execution
  GET    /api/engineering/execution/{id}             — Get execution detail
  GET    /api/engineering/executions                 — List executions
  POST   /api/engineering/execution/{id}/cancel      — Cancel execution
  POST   /api/engineering/execution/{id}/rollback    — Rollback execution
  POST   /api/engineering/execution/{id}/retry       — Retry execution
  GET    /api/engineering/execution/dashboard        — Dashboard
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from backend.services.enterprise_execution_engine import enterprise_execution_engine

log = logging.getLogger(__name__)

router = APIRouter(prefix="/api/engineering/execution", tags=["Enterprise Execution Engine"])


class CreateExecutionRequest(BaseModel):
    repository: str = ""
    branch: str = "main"
    commit_sha: str = ""
    service: str = ""
    environment: str = "production"
    source: str = "manual"
    source_event: str = "manual_trigger"
    objective: str = ""


class StartExecutionRequest(BaseModel):
    auto_approve: bool = False


@router.post("")
async def create_execution(req: CreateExecutionRequest) -> Dict[str, Any]:
    """Create a new autonomous execution."""
    try:
        return await enterprise_execution_engine.create_execution(
            repository=req.repository,
            branch=req.branch,
            commit_sha=req.commit_sha,
            service=req.service,
            environment=req.environment,
            source=req.source,
            source_event=req.source_event,
            objective=req.objective,
        )
    except Exception as exc:
        log.error("Create execution failed: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post("/{execution_id}/start")
async def start_execution(execution_id: str, req: StartExecutionRequest) -> Dict[str, Any]:
    """Start an execution synchronously — blocks until completion."""
    try:
        result = await enterprise_execution_engine.execute(
            execution_id, auto_approve=req.auto_approve,
        )
        if "error" in result:
            raise HTTPException(status_code=404, detail=result["error"])
        return result
    except HTTPException:
        raise
    except Exception as exc:
        log.error("Start execution failed: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post("/{execution_id}/start-async")
async def start_execution_async(execution_id: str, req: StartExecutionRequest) -> Dict[str, Any]:
    """Start an execution asynchronously — returns immediately."""
    try:
        exec_id = await enterprise_execution_engine.execute_async(
            execution_id, auto_approve=req.auto_approve,
        )
        return {"execution_id": exec_id, "status": "started"}
    except Exception as exc:
        log.error("Start async execution failed: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get("/dashboard")
async def get_execution_dashboard() -> Dict[str, Any]:
    """Get execution engine dashboard with counts and recent executions."""
    try:
        return enterprise_execution_engine.get_dashboard()
    except Exception as exc:
        log.error("Execution dashboard failed: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get("/{execution_id}")
async def get_execution(execution_id: str) -> Dict[str, Any]:
    """Get execution detail by ID."""
    try:
        result = enterprise_execution_engine.get_execution(execution_id)
        if not result:
            raise HTTPException(status_code=404, detail=f"Execution {execution_id} not found")
        return result
    except HTTPException:
        raise
    except Exception as exc:
        log.error("Get execution failed: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get("")
async def list_executions(
    status: str = Query(default=""),
    repository: str = Query(default=""),
    limit: int = Query(default=50),
) -> List[Dict[str, Any]]:
    """List all executions, optionally filtered by status or repository."""
    try:
        return enterprise_execution_engine.list_executions(
            status=status, repository=repository, limit=limit,
        )
    except Exception as exc:
        log.error("List executions failed: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post("/{execution_id}/cancel")
async def cancel_execution(execution_id: str) -> Dict[str, Any]:
    """Cancel a running execution."""
    try:
        result = await enterprise_execution_engine.cancel_execution(execution_id)
        if "error" in result:
            raise HTTPException(status_code=404, detail=result["error"])
        return result
    except HTTPException:
        raise
    except Exception as exc:
        log.error("Cancel execution failed: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post("/{execution_id}/rollback")
async def rollback_execution(execution_id: str) -> Dict[str, Any]:
    """Rollback an execution."""
    try:
        result = await enterprise_execution_engine.rollback_execution(execution_id)
        if "error" in result:
            raise HTTPException(status_code=404, detail=result["error"])
        return result
    except HTTPException:
        raise
    except Exception as exc:
        log.error("Rollback execution failed: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post("/{execution_id}/retry")
async def retry_execution(execution_id: str) -> Dict[str, Any]:
    """Retry a failed execution."""
    try:
        result = await enterprise_execution_engine.retry_execution(execution_id)
        if "error" in result:
            raise HTTPException(status_code=404, detail=result["error"])
        return result
    except HTTPException:
        raise
    except Exception as exc:
        log.error("Retry execution failed: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc)) from exc

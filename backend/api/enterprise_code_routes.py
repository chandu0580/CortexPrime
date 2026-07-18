"""
Enterprise Code Intelligence — REST API.

Endpoints:
  GET    /api/code/repositories    — List scanned repositories
  POST   /api/code/scan            — Scan a repository
  GET    /api/code/graph           — Get dependency graph
  GET    /api/code/functions       — List functions
  GET    /api/code/classes         — List classes
  GET    /api/code/dependencies    — Get dependencies
  POST   /api/code/impact          — Analyze impact of changed file
"""
from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from backend.services.enterprise_code_intelligence import code_intelligence

log = logging.getLogger(__name__)
router = APIRouter(prefix="/api/code", tags=["Enterprise Code Intelligence"])


class ScanRequest(BaseModel):
    path: str


class ImpactRequest(BaseModel):
    changed_file: str
    repo_id: str = ""


# ── Endpoints ───────────────────────────────────────────────────────────────

@router.get("/repositories")
async def list_repositories():
    """List all scanned repositories."""
    return {"repositories": await code_intelligence.list_repositories()}


@router.post("/scan")
async def scan_repository(req: ScanRequest):
    """Scan a repository for code intelligence."""
    result = await code_intelligence.scan_repository(req.path)
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
    return result


@router.get("/graph")
async def get_graph(
    repo_id: str = Query("", description="Filter by repository ID"),
):
    """Get the dependency/knowledge graph."""
    return await code_intelligence.get_graph(repo_id)


@router.get("/functions")
async def get_functions(
    repo_id: str = Query("", description="Filter by repository ID"),
):
    """List all parsed functions."""
    return {"functions": await code_intelligence.get_functions(repo_id)}


@router.get("/classes")
async def get_classes(
    repo_id: str = Query("", description="Filter by repository ID"),
):
    """List all parsed classes."""
    return {"classes": await code_intelligence.get_classes(repo_id)}


@router.get("/dependencies")
async def get_dependencies(
    node_id: str = Query("", description="Filter by node ID"),
):
    """Get dependency graph."""
    return await code_intelligence.get_dependencies(node_id)


@router.post("/impact")
async def analyze_impact(req: ImpactRequest):
    """Analyze the impact of a changed file."""
    result = await code_intelligence.analyze_impact(req.changed_file, req.repo_id)
    return result

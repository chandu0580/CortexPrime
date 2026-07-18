"""
Enterprise Architecture Routes — REST API for the AI CTO architecture intelligence.
"""
from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException

from backend.services.enterprise_architecture_intelligence import (
    architecture_intelligence,
)

log = logging.getLogger(__name__)
router = APIRouter(prefix="/api/architecture", tags=["Architecture"])


# ── Projects ─────────────────────────────────────────────────────────────────


@router.get("/projects")
async def list_projects(status: str = "", limit: int = 50):
    return await architecture_intelligence.list_projects(status=status, limit=limit)


@router.post("/projects")
async def create_project(
    name: str,
    description: str = "",
    input_text: str = "",
    input_type: str = "plain_text",
):
    return await architecture_intelligence.create_project(
        name=name,
        description=description,
        input_text=input_text,
        input_type=input_type,
    )


@router.get("/projects/{project_id}")
async def get_project(project_id: str):
    project = await architecture_intelligence.get_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail=f"Project not found: {project_id}")
    return project


@router.delete("/projects/{project_id}")
async def delete_project(project_id: str):
    ok = await architecture_intelligence.delete_project(project_id)
    if not ok:
        raise HTTPException(status_code=404, detail=f"Project not found: {project_id}")
    return {"status": "deleted", "project_id": project_id}


# ── Analysis ─────────────────────────────────────────────────────────────────


@router.post("/analyze")
async def analyze_project(name: str = "", description: str = "", input_text: str = ""):
    project = await architecture_intelligence.create_project(
        name=name or input_text[:50],
        description=description,
        input_text=input_text,
    )
    result = await architecture_intelligence.analyze(project["project_id"])
    return {"status": "analyzed", "project": result}


@router.post("/projects/{project_id}/analyze")
async def analyze_existing_project(project_id: str):
    project = await architecture_intelligence.get_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail=f"Project not found: {project_id}")
    result = await architecture_intelligence.analyze(project_id)
    return {"status": "analyzed", "project": result}


# ── Sub-views ────────────────────────────────────────────────────────────────


@router.get("/{project_id}/domains")
async def get_domains(project_id: str):
    return await architecture_intelligence.get_domains(project_id)


@router.get("/{project_id}/services")
async def get_services(project_id: str):
    return await architecture_intelligence.get_services(project_id)


@router.get("/{project_id}/database")
async def get_database(project_id: str):
    return await architecture_intelligence.get_database(project_id)


@router.get("/{project_id}/apis")
async def get_apis(project_id: str):
    return await architecture_intelligence.get_apis(project_id)


@router.get("/{project_id}/events")
async def get_events(project_id: str):
    return await architecture_intelligence.get_events(project_id)


@router.get("/{project_id}/missions")
async def get_missions(project_id: str):
    return await architecture_intelligence.get_missions(project_id)


@router.get("/{project_id}/graph")
async def get_graph(project_id: str):
    return await architecture_intelligence.get_graph(project_id)


# ── Dashboard ────────────────────────────────────────────────────────────────


@router.get("/dashboard")
async def architecture_dashboard():
    return await architecture_intelligence.get_dashboard_stats()

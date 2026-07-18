"""
Enterprise Engineering Memory Routes — REST API for engineering experience.

Endpoints:
  POST /api/engineering/memory/experience/build     — Build experience from execution
  GET  /api/engineering/memory/experience/{id}      — Get experience by ID
  GET  /api/engineering/memory/experiences          — List experiences
  POST /api/engineering/memory/similar              — Find similar experiences
  GET  /api/engineering/memory/patterns             — Mined patterns
  GET  /api/engineering/memory/report               — Full executive report
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from backend.services.enterprise_engineering_memory import enterprise_engineering_memory

log = logging.getLogger(__name__)

router = APIRouter(prefix="/api/engineering/memory", tags=["Enterprise Engineering Memory"])


class BuildExperienceRequest(BaseModel):
    execution_id: str


class SimilarityRequest(BaseModel):
    categories: List[str] = []
    services: List[str] = []
    files: List[str] = []
    repository: str = ""


@router.post("/experience/build")
async def build_experience(req: BuildExperienceRequest) -> Dict[str, Any]:
    """Build an engineering experience from an execution."""
    try:
        exp = await enterprise_engineering_memory.build_experience(req.execution_id)
        if not exp:
            raise HTTPException(status_code=404, detail=f"Execution {req.execution_id} not found")
        return exp.to_dict()
    except HTTPException:
        raise
    except Exception as exc:
        log.error("Experience build failed: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get("/experience/{experience_id}")
async def get_experience(experience_id: str) -> Dict[str, Any]:
    """Get an experience by ID."""
    try:
        exp = enterprise_engineering_memory.get_experience(experience_id)
        if not exp:
            raise HTTPException(status_code=404, detail=f"Experience {experience_id} not found")
        return exp.to_dict()
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get("/experiences")
async def list_experiences(
    limit: int = Query(50, ge=1, le=200),
) -> Dict[str, Any]:
    """List engineering experiences."""
    try:
        exps = enterprise_engineering_memory.list_experiences(limit=limit)
        return {
            "experiences": [e.to_dict() for e in exps],
            "total": len(exps),
        }
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post("/similar")
async def find_similar(req: SimilarityRequest) -> Dict[str, Any]:
    """Find similar historical experiences."""
    try:
        result = await enterprise_engineering_memory.find_similar(
            categories=req.categories,
            services=req.services,
            files=req.files,
            repository=req.repository,
        )
        return result
    except Exception as exc:
        log.error("Similarity search failed: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get("/patterns")
async def get_patterns() -> Dict[str, Any]:
    """Get mined patterns from accumulated experiences."""
    try:
        patterns = enterprise_engineering_memory.mine_patterns()
        return {"patterns": patterns}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get("/report")
async def get_executive_report() -> Dict[str, Any]:
    """Generate full executive report from engineering experience."""
    try:
        report = enterprise_engineering_memory.generate_report()
        return report
    except Exception as exc:
        log.error("Executive report generation failed: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc)) from exc

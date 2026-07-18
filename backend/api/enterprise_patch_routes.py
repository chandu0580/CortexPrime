"""
Enterprise Patch Pipeline — REST API.

Endpoints:
  GET    /api/patches/plans              — List all plans
  POST   /api/patches/generate           — Create plan + generate candidates
  POST   /api/patches/validate           — Validate a candidate
  POST   /api/patches/compare            — Compare candidates for a plan
  POST   /api/refactor/analyze           — Analyze directory for refactoring
  POST   /api/refactor/apply             — Apply a refactoring suggestion
"""
from __future__ import annotations

import logging
from typing import List, Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from backend.services.enterprise_patch_pipeline import patch_pipeline

log = logging.getLogger(__name__)
router = APIRouter(prefix="/api/patches", tags=["Enterprise Patch Pipeline"])

# ── Schemas ─────────────────────────────────────────────────────────────────

class GenerateRequest(BaseModel):
    input_type: str = "bug"
    description: str
    source: str = "manual"
    affected_areas: Optional[List[str]] = None
    candidate_count: int = 3

class ValidateRequest(BaseModel):
    candidate_id: str
    sandbox_id: str = ""

class CompareRequest(BaseModel):
    plan_id: str

class AnalyzeRequest(BaseModel):
    directory: str

class ApplyRefactorRequest(BaseModel):
    suggestion_id: str


# ── Endpoints ───────────────────────────────────────────────────────────────

@router.get("/plans")
async def list_plans():
    """List all patch plans."""
    return {"plans": await patch_pipeline.list_plans()}


@router.get("/candidates")
async def list_candidates(plan_id: str = Query("", description="Filter by plan ID")):
    """List patch candidates, optionally filtered by plan_id."""
    return {"candidates": await patch_pipeline.list_candidates(plan_id)}


@router.post("/generate")
async def generate_patches(req: GenerateRequest):
    """Create a plan and generate candidate patches."""
    plan = await patch_pipeline.create_plan(
        input_type=req.input_type,
        description=req.description,
        source=req.source,
        affected_areas=req.affected_areas,
    )
    candidates = await patch_pipeline.generate_candidates(
        plan_id=plan["plan_id"],
        count=req.candidate_count,
    )
    return {"plan": plan, "candidates": candidates}


@router.post("/validate")
async def validate_candidate(req: ValidateRequest):
    """Validate a candidate patch in the sandbox."""
    try:
        result = await patch_pipeline.validate_candidate(
            candidate_id=req.candidate_id,
            sandbox_id=req.sandbox_id or "",
        )
        if result is None:
            raise HTTPException(status_code=404, detail=f"Candidate not found: {req.candidate_id}")
        return result
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/compare")
async def compare_candidates(req: CompareRequest):
    """Compare validated candidates for a plan and select the best."""
    try:
        result = await patch_pipeline.compare_candidates(plan_id=req.plan_id)
        return result
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/refactor/analyze")
async def analyze_refactoring(req: AnalyzeRequest):
    """Analyze a directory for refactoring opportunities."""
    try:
        result = await patch_pipeline.analyze_refactoring(directory=req.directory)
        return result
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/refactor/apply")
async def apply_refactoring(req: ApplyRefactorRequest):
    """Apply a refactoring suggestion."""
    try:
        result = await patch_pipeline.apply_refactoring(suggestion_id=req.suggestion_id)
        return result
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

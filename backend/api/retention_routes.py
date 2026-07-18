"""
REST API for data retention policy management.
"""
from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel

from backend.core.data_retention import get_retention_policy

router = APIRouter(prefix="/api/admin/retention", tags=["retention"])


class PolicyUpdate(BaseModel):
    category: str
    retention_days: int


class PurgeRequest(BaseModel):
    category: str
    storage_path: str


@router.get("/policies")
async def list_policies():
    return get_retention_policy().list_policies()


@router.put("/policies")
async def update_policy(update: PolicyUpdate):
    get_retention_policy().set_policy(update.category, update.retention_days)
    return {"status": "updated", "category": update.category, "retention_days": update.retention_days}


@router.post("/purge")
async def purge_records(request: PurgeRequest):
    purged = get_retention_policy().purge_old_records(request.category, request.storage_path)
    return {"status": "completed", "category": request.category, "records_purged": purged}

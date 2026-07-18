"""
Admin API routes for autonomy configuration and system management.
"""
from __future__ import annotations

from typing import Any, Dict

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from backend.auth.dependencies import require_user
from backend.core.autonomy_config import get_autonomy_config

router = APIRouter(prefix="/api/admin", tags=["admin"])


class ConfigUpdate(BaseModel):
    key: str
    value: Any


@router.get("/autonomy")
async def get_autonomy_settings(user: Dict = Depends(require_user)):
    return get_autonomy_config().get_all()


@router.put("/autonomy")
async def update_autonomy_setting(update: ConfigUpdate, user: Dict = Depends(require_user)):
    success = get_autonomy_config().set(update.key, update.value)
    if not success:
        raise HTTPException(status_code=400, detail=f"Unknown setting: {update.key}")
    return {"status": "updated", "key": update.key, "value": update.value}


@router.post("/autonomy/reset")
async def reset_autonomy(key: str = None, user: Dict = Depends(require_user)):
    config = get_autonomy_config()
    if key:
        config.reset(key)
    else:
        config.reset_all()
    return {"status": "reset", "key": key or "all"}

from __future__ import annotations

import logging
from typing import Any, Dict

from fastapi import APIRouter, Depends, Response

from backend.auth.dependencies import require_user
from backend.services.diagnostics_service import diagnostics_service

log = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/operations/diagnostics",
    tags=["Enterprise Operations — Diagnostics"],
    dependencies=[Depends(require_user)],
)


@router.get("")
async def get_diagnostics_json() -> Dict[str, Any]:
    return await diagnostics_service.generate_diagnostics()


@router.get("/download")
async def download_diagnostics() -> Response:
    diagnostics = await diagnostics_service.generate_diagnostics()
    serialized = diagnostics_service.serialize_diagnostics(diagnostics)
    return Response(
        content=serialized,
        media_type="application/json",
        headers={
            "Content-Disposition": f'attachment; filename="cortexprime-diagnostics-{diagnostics["diagnostics_id"]}.json"',
        },
    )

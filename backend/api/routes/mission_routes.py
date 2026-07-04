from fastapi import APIRouter, Depends, HTTPException

from backend.orchestrator.master_agent_runtime import (
    master_agent_runtime
)
from backend.auth.dependencies import require_user

router = APIRouter(dependencies=[Depends(require_user)])


# ==========================================
# ACTIVE MISSIONS
# ==========================================

@router.get("/active")

async def get_active_missions():

    try:

        result = await (
            master_agent_runtime
            .get_active_missions()
        )

        return result

    except Exception as error:

        raise HTTPException(

            status_code=500,

            detail=str(error)
        )


# ==========================================
# COMPLETED MISSIONS
# ==========================================

@router.get("/completed")

async def get_completed_missions():

    try:

        result = await (
            master_agent_runtime
            .get_completed_missions()
        )

        return result

    except Exception as error:

        raise HTTPException(

            status_code=500,

            detail=str(error)
        )
from fastapi import APIRouter, Depends, HTTPException

from typing import Dict, Any

from backend.orchestrator.master_agent_runtime import (
    master_agent_runtime
)

from backend.orchestrator.autonomous_reasoning_loop import (
    autonomous_reasoning_loop
)

from backend.orchestrator.agent_router import (
    agent_router
)

from backend.orchestrator.reflection_engine import (
    reflection_engine
)
from backend.auth.dependencies import require_user

router = APIRouter(dependencies=[Depends(require_user)])


# ==========================================
# EXECUTE GOAL
# ==========================================

@router.post("/execute")

async def execute_goal(
    payload: Dict[str, Any]
):

    try:

        result = await (
            master_agent_runtime
            .execute_goal(payload)
        )

        return result

    except Exception as error:

        raise HTTPException(
            status_code=500,
            detail=str(error)
        )


# ==========================================
# AUTONOMOUS LOOP
# ==========================================

@router.post("/autonomous")

async def autonomous_execution(
    payload: Dict[str, Any]
):

    try:

        result = await (
            autonomous_reasoning_loop
            .execute_goal(payload)
        )

        return result

    except Exception as error:

        raise HTTPException(
            status_code=500,
            detail=str(error)
        )


# ==========================================
# ROUTE GOAL
# ==========================================

@router.post("/route")

async def route_goal(
    payload: Dict[str, Any]
):

    try:

        result = await (
            agent_router
            .route_goal(payload)
        )

        return result

    except Exception as error:

        raise HTTPException(
            status_code=500,
            detail=str(error)
        )


# ==========================================
# REFLECT
# ==========================================

@router.post("/reflect")

async def reflect(
    payload: Dict[str, Any]
):

    try:

        result = await (
            reflection_engine
            .analyze_result(payload)
        )

        return result

    except Exception as error:

        raise HTTPException(
            status_code=500,
            detail=str(error)
        )


# ==========================================
# ACTIVE LOOPS
# ==========================================

@router.get("/loops/active")

async def get_active_loops():

    try:

        result = await (
            autonomous_reasoning_loop
            .get_active_loops()
        )

        return result

    except Exception as error:

        raise HTTPException(
            status_code=500,
            detail=str(error)
        )


# ==========================================
# LOOP HISTORY
# ==========================================

@router.get("/loops/history")

async def get_loop_history():

    try:

        result = await (
            autonomous_reasoning_loop
            .get_loop_history()
        )

        return result

    except Exception as error:

        raise HTTPException(
            status_code=500,
            detail=str(error)
        )
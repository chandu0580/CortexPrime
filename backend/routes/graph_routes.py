from fastapi import APIRouter

from backend.api.graph_routes import graph_router as api_router

router = APIRouter()
router.include_router(api_router)

from fastapi import APIRouter
from backend.api.memory_routes import router as api_router

router = APIRouter()
router.include_router(api_router)

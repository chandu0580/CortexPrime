from pydantic import BaseModel
from typing import Optional
from datetime import datetime


# ==========================================
# VECTOR MEMORY RECORD
# ==========================================

class VectorMemoryRecord(BaseModel):

    session_id: str

    created_at: str = (
        datetime.utcnow().isoformat()
    )

    user_goal: str

    final_output: Optional[str] = None

    workflow_status: str

    final_confidence: float = 0.0
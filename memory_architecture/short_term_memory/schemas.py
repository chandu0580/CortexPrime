from pydantic import BaseModel
from typing import Dict, List
from datetime import datetime


class MemoryRecord(BaseModel):

    session_id: str

    timestamp: str

    user_goal: str

    research_summary: str

    planning_summary: str

    critique_summary: str

    optimization_summary: str

    final_output: str

    metadata: Dict
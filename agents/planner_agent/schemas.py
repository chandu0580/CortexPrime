from pydantic import BaseModel
from typing import List, Dict


class PlanningOutput(BaseModel):

    agent: str
    status: str

    execution_strategy: str

    execution_phases: List[Dict]

    dependencies: List[str]

    technical_requirements: List[str]

    risks: List[str]

    scalability_considerations: List[str]

    estimated_complexity: str

    confidence: float

    metadata: Dict
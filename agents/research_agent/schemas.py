from pydantic import BaseModel
from typing import List


class ResearchOutput(BaseModel):
    agent: str
    status: str

    domain: str
    complexity: str
    confidence: float

    summary: str

    insights: List[str]
    risks: List[str]
    opportunities: List[str]

    reasoning_scope: List[str]

    metadata: dict
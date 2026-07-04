from pydantic import BaseModel
from typing import List, Dict


class CriticOutput(BaseModel):

    agent: str
    status: str

    reasoning_validity: str

    hallucination_risk: str

    execution_feasibility: str

    contradictions_detected: List[str]

    scalability_concerns: List[str]

    security_risks: List[str]

    compliance_issues: List[str]

    operational_weaknesses: List[str]

    recommendations: List[str]

    confidence: float

    metadata: Dict
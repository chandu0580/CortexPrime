from pydantic import BaseModel
from typing import List, Dict


class OptimizerOutput(BaseModel):

    agent: str
    status: str

    optimized_execution_strategy: str

    optimized_architecture_decisions: List[str]

    scalability_improvements: List[str]

    security_enhancements: List[str]

    operational_optimizations: List[str]

    hallucination_reduction_measures: List[str]

    deployment_readiness_improvements: List[str]

    refined_execution_phases: List[Dict]

    confidence: float

    metadata: Dict
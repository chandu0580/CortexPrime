from pydantic import BaseModel
from typing import List, Dict


class WorkflowExecutionResult(BaseModel):

    status: str

    workflow_id: str

    active_agent: str | None

    completed_agents: List[str]

    failed_agents: List[str]

    execution_trace: List[Dict]

    final_output: str

    overall_confidence: float

    metadata: Dict
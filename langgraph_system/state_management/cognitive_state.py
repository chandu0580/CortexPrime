from pydantic import BaseModel, Field
from typing import Dict, List, Optional
from datetime import datetime
import uuid


class CognitiveState(BaseModel):

    # ==========================================
    # SESSION / USER CONTEXT
    # ==========================================

    session_id: str = Field(
        default_factory=lambda: str(uuid.uuid4())
    )

    created_at: str = Field(
        default_factory=lambda: (
            datetime.utcnow().isoformat()
        )
    )

    user_goal: str = ""

    workflow_status: str = "initialized"

    active_agent: Optional[str] = None

    # ==========================================
    # REFLECTION CONTROL
    # ==========================================

    reflection_count: int = 0

    max_reflections: int = 3

    # ==========================================
    # RESEARCH LAYER
    # ==========================================

    research_data: Dict = Field(
        default_factory=dict
    )

    research_confidence: float = 0.0

    # ==========================================
    # PLANNING LAYER
    # ==========================================

    planning_data: Dict = Field(
        default_factory=dict
    )

    planning_confidence: float = 0.0

    # ==========================================
    # CRITIQUE LAYER
    # ==========================================

    critique_data: Dict = Field(
        default_factory=dict
    )

    critique_confidence: float = 0.0

    # ==========================================
    # OPTIMIZATION LAYER
    # ==========================================

    optimization_data: Dict = Field(
        default_factory=dict
    )

    optimization_confidence: float = 0.0

    # ==========================================
    # MEMORY LAYER
    # ==========================================

    memory_references: List[Dict] = Field(
        default_factory=list
    )

    relevant_memories: List[Dict] = Field(
        default_factory=list
    )

    semantic_context: List[Dict] = Field(
        default_factory=list
    )

    # ==========================================
    # OBSERVABILITY / EXECUTION TRACE
    # ==========================================

    execution_trace: List[Dict] = Field(
        default_factory=list
    )

    runtime_metrics: Dict = Field(
        default_factory=dict
    )

    agent_timings: Dict = Field(
        default_factory=dict
    )

    errors: List[str] = Field(
        default_factory=list
    )

    # ==========================================
    # FINAL OUTPUT
    # ==========================================

    final_output: Optional[str] = None

    final_confidence: float = 0.0
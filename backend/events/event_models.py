
from typing import Dict, Any, Optional

from pydantic import BaseModel

from datetime import datetime

from uuid import uuid4


# ==========================================
# BASE EVENT
# ==========================================

class CognitionEvent(

    BaseModel

):

    # ==========================================
    # CORE
    # ==========================================

    event_id: str = str(
        uuid4()
    )

    agent: str

    event_type: str

    status: str

    message: str

    timestamp: str = (

        datetime.utcnow()
        .isoformat()
    )

    # ==========================================
    # COGNITION PHASE
    # ==========================================

    phase: Optional[
        str
    ] = None

    # ==========================================
    # STREAMING
    # ==========================================

    stream: bool = False

    stream_chunk: Optional[
        str
    ] = None

    stream_completed: bool = False

    # ==========================================
    # EXECUTION
    # ==========================================

    execution_id: Optional[
        str
    ] = None

    parent_execution_id: Optional[
        str
    ] = None

    retry_count: int = 0

    orchestration_depth: int = 0

    # ==========================================
    # PERFORMANCE
    # ==========================================

    latency_ms: Optional[
        float
    ] = None

    token_usage: Optional[
        Dict[str, Any]
    ] = None

    # ==========================================
    # GOVERNANCE
    # ==========================================

    hallucination_score: Optional[
        float
    ] = None

    confidence_score: Optional[
        float
    ] = None

    governance_status: Optional[
        str
    ] = None

    # ==========================================
    # SWARM INTELLIGENCE
    # ==========================================

    consensus_score: Optional[
        float
    ] = None

    debate_round: int = 0

    participating_agents: Optional[
        list[str]
    ] = None

    # ==========================================
    # PAYLOAD
    # ==========================================

    payload: Optional[
        Dict[str, Any]
    ] = None

    # ==========================================
    # SESSION ROUTING
    # Set this to route the event only to the
    # originating client's WebSocket session.
    # Leave None for global broadcast.
    # ==========================================

    session_id: Optional[str] = None


# ==========================================
# EVENT TYPES
# ==========================================

class EventTypes:

    # ==========================================
    # EXECUTION
    # ==========================================

    EXECUTION_STARTED = (
        "execution_started"
    )

    EXECUTION_COMPLETED = (
        "execution_completed"
    )

    EXECUTION_FAILED = (
        "execution_failed"
    )

    # ==========================================
    # STREAMING
    # ==========================================

    TOKEN_STREAM = (
        "token_stream"
    )

    STREAM_STARTED = (
        "stream_started"
    )

    STREAM_COMPLETED = (
        "stream_completed"
    )

    # ==========================================
    # RESEARCH
    # ==========================================

    RESEARCH_STARTED = (
        "research_started"
    )

    RESEARCH_COMPLETED = (
        "research_completed"
    )

    # ==========================================
    # PLANNING
    # ==========================================

    PLANNING_STARTED = (
        "planning_started"
    )

    PLANNING_COMPLETED = (
        "planning_completed"
    )

    # ==========================================
    # CRITIC
    # ==========================================

    CRITIC_STARTED = (
        "critic_started"
    )

    CRITIC_COMPLETED = (
        "critic_completed"
    )

    # ==========================================
    # OPTIMIZATION
    # ==========================================

    OPTIMIZATION_STARTED = (
        "optimization_started"
    )

    OPTIMIZATION_COMPLETED = (
        "optimization_completed"
    )

    # ==========================================
    # MEMORY
    # ==========================================

    MEMORY_STORED = (
        "memory_stored"
    )

    MEMORY_RETRIEVED = (
        "memory_retrieved"
    )

    # ==========================================
    # ORCHESTRATION
    # ==========================================

    ORCHESTRATION_STARTED = (
        "orchestration_started"
    )

    ORCHESTRATION_COMPLETED = (
        "orchestration_completed"
    )

    ORCHESTRATION_FAILED = (
        "orchestration_failed"
    )

    # ==========================================
    # REFLECTION
    # ==========================================

    REFLECTION_STARTED = (
        "reflection_started"
    )

    REFLECTION_COMPLETED = (
        "reflection_completed"
    )

    # ==========================================
    # GOVERNANCE
    # ==========================================

    GOVERNANCE_VALIDATION = (
        "governance_validation"
    )

    GOVERNANCE_APPROVED = (
        "governance_approved"
    )

    GOVERNANCE_REJECTED = (
        "governance_rejected"
    )

    # ==========================================
    # COGNITION PHASES
    # ==========================================

    PHASE_RESEARCHING = (
        "phase_researching"
    )

    PHASE_PLANNING = (
        "phase_planning"
    )

    PHASE_ANALYZING = (
        "phase_analyzing"
    )

    PHASE_VALIDATING = (
        "phase_validating"
    )

    PHASE_OPTIMIZING = (
        "phase_optimizing"
    )

    PHASE_MEMORY = (
        "phase_memory"
    )

    PHASE_STREAMING = (
        "phase_streaming"
    )

    # ==========================================
    # SWARM INTELLIGENCE
    # ==========================================

    SWARM_EXECUTION = (
        "swarm_execution"
    )

    AGENT_DEBATE = (
        "agent_debate"
    )

    CONSENSUS_REACHED = (
        "consensus_reached"
    )

    CONSENSUS_FAILED = (
        "consensus_failed"
    )

    # ==========================================
    # RUNTIME
    # ==========================================

    RUNTIME_STATE = (
        "runtime_state"
    )

    RUNTIME_METRICS = (
        "runtime_metrics"
    )

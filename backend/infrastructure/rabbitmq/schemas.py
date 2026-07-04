"""
RabbitMQ Event Schemas
-----------------------
Centralized definition of:
  - Queue and exchange name constants
  - Message type enum (all event kinds in the system)
  - Base message envelope (with distributed-tracing headers)
  - Typed message factories for every event kind
  - Agent-to-agent, cognition, pipeline, memory, reflection schemas
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
from uuid import uuid4

from pydantic import BaseModel, Field


# =========================================================
# QUEUE NAMES
# =========================================================

class Queues:
    # Primary runtime queues
    ORCHESTRATION         = "cortex.orchestration"
    COGNITION_PIPELINE    = "cortex.cognition.pipeline"
    AGENT_TASKS           = "cortex.agent.tasks"
    AGENT_RESULTS         = "cortex.agent.results"
    MEMORY_OPERATIONS     = "cortex.memory.operations"
    REFLECTION_TRIGGERS   = "cortex.reflection.triggers"
    EXECUTION_EVENTS      = "cortex.execution.events"

    # Per-agent queues  (routing key pattern: cortex.agent.{name})
    AGENT_PLANNER         = "cortex.agent.planner"
    AGENT_RESEARCHER      = "cortex.agent.researcher"
    AGENT_CRITIC          = "cortex.agent.critic"
    AGENT_OPTIMIZER       = "cortex.agent.optimizer"
    AGENT_ORCHESTRATOR    = "cortex.agent.orchestrator"

    # Distributed cognition
    COGNITION_BROADCAST   = "cortex.cognition.broadcast"
    PIPELINE_STAGES       = "cortex.pipeline.stages"

    # DLQ
    DEAD_LETTER           = "cortex.dead.letter"

    # Retry staging (messages are republished here with a per-msg TTL)
    RETRY                 = "cortex.retry"

    @classmethod
    def for_agent(cls, agent_name: str) -> str:
        """Return the per-agent dedicated queue name."""
        return f"cortex.agent.{agent_name.lower()}"


# =========================================================
# EXCHANGE NAMES
# =========================================================

class Exchanges:
    COGNITION     = "cortex.cognition"        # topic  — broadcast events
    ORCHESTRATION = "cortex.orchestration"    # direct — task dispatch
    AGENTS        = "cortex.agents"           # topic  — agent-to-agent routing
    EVENTS        = "cortex.events"           # fanout — all-subscriber broadcast
    DEAD_LETTER   = "cortex.dead.letter.x"   # direct — DLQ
    RETRY         = "cortex.retry.x"          # direct — retry staging


# =========================================================
# ROUTING KEYS
# =========================================================

class RoutingKeys:
    # Topic keys for Exchanges.COGNITION (pattern: cognition.{phase}.{agent})
    COGNITION_ALL      = "cognition.#"
    COGNITION_THINKING = "cognition.thinking.#"
    COGNITION_ACTING   = "cognition.acting.#"
    COGNITION_DONE     = "cognition.done.#"

    # Topic keys for Exchanges.AGENTS  (pattern: agent.{name}.{action})
    AGENT_TASK         = "agent.{name}.task"
    AGENT_RESULT       = "agent.{name}.result"
    AGENT_ALL          = "agent.#"

    @staticmethod
    def agent_task(agent_name: str) -> str:
        return f"agent.{agent_name.lower()}.task"

    @staticmethod
    def agent_result(agent_name: str) -> str:
        return f"agent.{agent_name.lower()}.result"

    @staticmethod
    def cognition(phase: str, agent: str = "#") -> str:
        return f"cognition.{phase}.{agent.lower()}"


# =========================================================
# MESSAGE TYPES
# =========================================================

class MessageType(str, Enum):
    # ── Orchestration ────────────────────────────────────────
    MISSION_START        = "mission.start"
    MISSION_COMPLETE     = "mission.complete"
    MISSION_FAILED       = "mission.failed"
    MISSION_PAUSED       = "mission.paused"
    MISSION_RESUMED      = "mission.resumed"

    # ── Agent lifecycle ──────────────────────────────────────
    AGENT_TASK_DISPATCH  = "agent.task.dispatch"
    AGENT_TASK_RESULT    = "agent.task.result"
    AGENT_TASK_FAILED    = "agent.task.failed"
    AGENT_STATUS_UPDATE  = "agent.status.update"
    AGENT_MESSAGE        = "agent.message"          # agent-to-agent

    # ── Cognition pipeline stages ────────────────────────────
    PIPELINE_STAGE_START = "pipeline.stage.start"
    PIPELINE_STAGE_DONE  = "pipeline.stage.done"
    PIPELINE_STAGE_FAIL  = "pipeline.stage.fail"
    COGNITION_EVENT      = "cognition.event"         # generic stream event

    # ── Memory ───────────────────────────────────────────────
    MEMORY_STORE         = "memory.store"
    MEMORY_QUERY         = "memory.query"
    MEMORY_RETRIEVED     = "memory.retrieved"

    # ── Reflection ───────────────────────────────────────────
    REFLECTION_TRIGGER   = "reflection.trigger"
    REFLECTION_COMPLETE  = "reflection.complete"

    # ── Execution events (forwarded to WebSocket) ────────────
    EXECUTION_EVENT      = "execution.event"
    EXECUTION_STARTED    = "execution.started"
    EXECUTION_COMPLETED  = "execution.completed"
    EXECUTION_FAILED     = "execution.failed"

    # ── Distributed runtime ──────────────────────────────────
    RUNTIME_BROADCAST    = "runtime.broadcast"
    HEALTH_PING          = "health.ping"
    HEALTH_PONG          = "health.pong"


# =========================================================
# DISTRIBUTED TRACE CONTEXT
# =========================================================

class TraceContext(BaseModel):
    """Propagated across every message hop for distributed tracing."""
    trace_id:       str = Field(default_factory=lambda: str(uuid4()))
    span_id:        str = Field(default_factory=lambda: str(uuid4()))
    parent_span_id: Optional[str] = None
    sampled:        bool = True

    def child(self) -> "TraceContext":
        """Create a child span that propagates the same trace."""
        return TraceContext(
            trace_id       = self.trace_id,
            parent_span_id = self.span_id,
        )

    def to_headers(self) -> Dict[str, str]:
        return {
            "x-trace-id":       self.trace_id,
            "x-span-id":        self.span_id,
            "x-parent-span-id": self.parent_span_id or "",
            "x-sampled":        "1" if self.sampled else "0",
        }

    @classmethod
    def from_headers(cls, headers: Dict[str, Any]) -> "TraceContext":
        return cls(
            trace_id       = headers.get("x-trace-id",       str(uuid4())),
            span_id        = headers.get("x-span-id",        str(uuid4())),
            parent_span_id = headers.get("x-parent-span-id") or None,
            sampled        = headers.get("x-sampled", "1") == "1",
        )


# =========================================================
# BASE MESSAGE ENVELOPE
# =========================================================

class RabbitMessage(BaseModel):
    """
    Universal message envelope.

    Every message in CortexPrime's bus is wrapped in this envelope
    regardless of its payload.  The TraceContext fields enable
    distributed tracing across all agent hops.
    """
    # Identity
    message_id:        str = Field(default_factory=lambda: str(uuid4()))
    message_type:      MessageType
    timestamp:         str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    # Correlation
    execution_id:      Optional[str] = None
    mission_id:        Optional[str] = None
    parent_message_id: Optional[str] = None

    # Reliability
    retry_count:       int = 0
    max_retries:       int = 3
    priority:          int = 5          # 1 (low) – 10 (high)

    # Distributed trace
    trace:             TraceContext = Field(default_factory=TraceContext)

    # Typed payload
    payload:           Dict[str, Any] = Field(default_factory=dict)

    def to_bytes(self) -> bytes:
        return self.model_dump_json().encode()

    @classmethod
    def from_bytes(cls, data: bytes) -> "RabbitMessage":
        return cls.model_validate_json(data)

    def child_message(self, message_type: MessageType, **kwargs) -> "RabbitMessage":
        """Create a causally-linked child message inheriting execution context."""
        return RabbitMessage(
            message_type      = message_type,
            execution_id      = self.execution_id,
            mission_id        = self.mission_id,
            parent_message_id = self.message_id,
            trace             = self.trace.child(),
            **kwargs,
        )

    def to_amqp_headers(self) -> Dict[str, str]:
        headers = {
            "message_type":  self.message_type.value,
            "execution_id":  self.execution_id or "",
            "mission_id":    self.mission_id   or "",
            "retry_count":   str(self.retry_count),
            "priority":      str(self.priority),
        }
        headers.update(self.trace.to_headers())
        return headers


# =========================================================
# TYPED MESSAGE FACTORIES
# =========================================================

# ── Orchestration ─────────────────────────────────────────

def mission_start_message(
    execution_id: str,
    objective:    str,
    agents:       List[str] = [],
    priority:     int = 5,
    mission_id:   Optional[str] = None,
) -> RabbitMessage:
    return RabbitMessage(
        message_type = MessageType.MISSION_START,
        execution_id = execution_id,
        mission_id   = mission_id,
        priority     = priority,
        payload      = {
            "objective": objective,
            "agents":    agents,
            "priority":  priority,
        },
    )


def mission_complete_message(
    execution_id: str,
    result:       Dict[str, Any],
    mission_id:   Optional[str] = None,
) -> RabbitMessage:
    return RabbitMessage(
        message_type = MessageType.MISSION_COMPLETE,
        execution_id = execution_id,
        mission_id   = mission_id,
        payload      = {"result": result},
    )


def mission_failed_message(
    execution_id: str,
    error:        str,
    stage:        str = "",
    mission_id:   Optional[str] = None,
) -> RabbitMessage:
    return RabbitMessage(
        message_type = MessageType.MISSION_FAILED,
        execution_id = execution_id,
        mission_id   = mission_id,
        payload      = {"error": error, "stage": stage},
    )


# ── Agent tasks ───────────────────────────────────────────

def agent_task_message(
    execution_id: str,
    agent_name:   str,
    task:         Dict[str, Any],
    priority:     int = 5,
    parent_msg:   Optional[RabbitMessage] = None,
) -> RabbitMessage:
    trace = parent_msg.trace.child() if parent_msg else TraceContext()
    return RabbitMessage(
        message_type      = MessageType.AGENT_TASK_DISPATCH,
        execution_id      = execution_id,
        parent_message_id = parent_msg.message_id if parent_msg else None,
        priority          = priority,
        trace             = trace,
        payload           = {
            "agent_name": agent_name,
            "task":       task,
            "priority":   priority,
        },
    )


def agent_result_message(
    execution_id:      str,
    agent_name:        str,
    result:            Dict[str, Any],
    parent_message_id: Optional[str] = None,
    trace:             Optional[TraceContext] = None,
) -> RabbitMessage:
    return RabbitMessage(
        message_type      = MessageType.AGENT_TASK_RESULT,
        execution_id      = execution_id,
        parent_message_id = parent_message_id,
        trace             = trace or TraceContext(),
        payload           = {
            "agent_name": agent_name,
            "result":     result,
        },
    )


def agent_to_agent_message(
    execution_id: str,
    from_agent:   str,
    to_agent:     str,
    content:      Dict[str, Any],
    parent_msg:   Optional[RabbitMessage] = None,
) -> RabbitMessage:
    """Direct agent-to-agent message routed via the agents exchange."""
    trace = parent_msg.trace.child() if parent_msg else TraceContext()
    return RabbitMessage(
        message_type      = MessageType.AGENT_MESSAGE,
        execution_id      = execution_id,
        parent_message_id = parent_msg.message_id if parent_msg else None,
        trace             = trace,
        payload           = {
            "from_agent": from_agent,
            "to_agent":   to_agent,
            "content":    content,
        },
    )


# ── Cognition / pipeline ──────────────────────────────────

def pipeline_stage_start_message(
    execution_id: str,
    stage:        str,
    agent:        str,
    task:         Dict[str, Any] = {},
    parent_msg:   Optional[RabbitMessage] = None,
) -> RabbitMessage:
    trace = parent_msg.trace.child() if parent_msg else TraceContext()
    return RabbitMessage(
        message_type      = MessageType.PIPELINE_STAGE_START,
        execution_id      = execution_id,
        parent_message_id = parent_msg.message_id if parent_msg else None,
        trace             = trace,
        payload           = {"stage": stage, "agent": agent, "task": task},
    )


def pipeline_stage_done_message(
    execution_id: str,
    stage:        str,
    agent:        str,
    output:       Dict[str, Any] = {},
    duration_ms:  Optional[float] = None,
    parent_msg:   Optional[RabbitMessage] = None,
) -> RabbitMessage:
    trace = parent_msg.trace.child() if parent_msg else TraceContext()
    return RabbitMessage(
        message_type      = MessageType.PIPELINE_STAGE_DONE,
        execution_id      = execution_id,
        parent_message_id = parent_msg.message_id if parent_msg else None,
        trace             = trace,
        payload           = {
            "stage":       stage,
            "agent":       agent,
            "output":      output,
            "duration_ms": duration_ms,
        },
    )


def cognition_event_message(
    execution_id: str,
    agent:        str,
    event_type:   str,
    status:       str,
    message:      str,
    phase:        str = "",
    payload:      Dict[str, Any] = {},
    parent_msg:   Optional[RabbitMessage] = None,
) -> RabbitMessage:
    trace = parent_msg.trace.child() if parent_msg else TraceContext()
    return RabbitMessage(
        message_type      = MessageType.COGNITION_EVENT,
        execution_id      = execution_id,
        parent_message_id = parent_msg.message_id if parent_msg else None,
        trace             = trace,
        payload           = {
            "agent":      agent,
            "event_type": event_type,
            "status":     status,
            "message":    message,
            "phase":      phase,
            "data":       payload,
        },
    )


def execution_event_message(
    execution_id: str,
    agent:        str,
    event_type:   str,
    status:       str,
    message:      str,
    payload:      Dict[str, Any] = {},
) -> RabbitMessage:
    return RabbitMessage(
        message_type = MessageType.EXECUTION_EVENT,
        execution_id = execution_id,
        payload      = {
            "agent":      agent,
            "event_type": event_type,
            "status":     status,
            "message":    message,
            "data":       payload,
        },
    )


# ── Memory ────────────────────────────────────────────────

def memory_store_message(
    execution_id: str,
    agent:        str,
    memory_type:  str,
    content:      str,
    embedding:    Optional[List[float]] = None,
    metadata:     Dict[str, Any] = {},
) -> RabbitMessage:
    return RabbitMessage(
        message_type = MessageType.MEMORY_STORE,
        execution_id = execution_id,
        payload      = {
            "agent":       agent,
            "memory_type": memory_type,
            "content":     content,
            "embedding":   embedding,
            "metadata":    metadata,
        },
    )


def memory_query_message(
    execution_id: str,
    agent:        str,
    query:        str,
    memory_types: List[str] = [],
    limit:        int = 10,
) -> RabbitMessage:
    return RabbitMessage(
        message_type = MessageType.MEMORY_QUERY,
        execution_id = execution_id,
        payload      = {
            "agent":        agent,
            "query":        query,
            "memory_types": memory_types,
            "limit":        limit,
        },
    )


# ── Reflection ────────────────────────────────────────────

def reflection_trigger_message(
    execution_id: str,
    agent:        str,
    context:      Dict[str, Any],
    mission_id:   Optional[str] = None,
) -> RabbitMessage:
    return RabbitMessage(
        message_type = MessageType.REFLECTION_TRIGGER,
        execution_id = execution_id,
        mission_id   = mission_id,
        payload      = {
            "agent":   agent,
            "context": context,
        },
    )


# =========================================================
# MESSAGE TYPES
# =========================================================

class MessageType(str, Enum):

    # Orchestration
    MISSION_START        = "mission.start"
    MISSION_COMPLETE     = "mission.complete"
    MISSION_FAILED       = "mission.failed"

    # Agent lifecycle
    AGENT_TASK_DISPATCH  = "agent.task.dispatch"
    AGENT_TASK_RESULT    = "agent.task.result"
    AGENT_STATUS_UPDATE  = "agent.status.update"

    # Cognition pipeline stages
    PIPELINE_STAGE_START  = "pipeline.stage.start"
    PIPELINE_STAGE_DONE   = "pipeline.stage.done"

    # Memory
    MEMORY_STORE          = "memory.store"
    MEMORY_RETRIEVED      = "memory.retrieved"

    # Reflection
    REFLECTION_TRIGGER    = "reflection.trigger"
    REFLECTION_COMPLETE   = "reflection.complete"

    # Execution events (forwarded to WebSocket)
    EXECUTION_EVENT       = "execution.event"


# =========================================================
# BASE MESSAGE
# =========================================================

class RabbitMessage(BaseModel):

    message_id:   str = str(uuid4())
    message_type: MessageType
    timestamp:    str = datetime.utcnow().isoformat()

    # Routing
    execution_id:      Optional[str] = None
    parent_message_id: Optional[str] = None
    retry_count:       int = 0

    # Payload
    payload: Dict[str, Any] = {}

    def to_bytes(self) -> bytes:
        return self.model_dump_json().encode()

    @classmethod
    def from_bytes(cls, data: bytes) -> "RabbitMessage":
        return cls.model_validate_json(data)


# =========================================================
# TYPED MESSAGE FACTORIES
# =========================================================

def mission_start_message(
    execution_id: str,
    objective: str,
    priority: int = 5,
) -> RabbitMessage:
    return RabbitMessage(
        message_type=MessageType.MISSION_START,
        execution_id=execution_id,
        payload={
            "objective": objective,
            "priority": priority,
        },
    )


def agent_task_message(
    execution_id: str,
    agent_name: str,
    task: Dict[str, Any],
    priority: int = 5,
) -> RabbitMessage:
    return RabbitMessage(
        message_type=MessageType.AGENT_TASK_DISPATCH,
        execution_id=execution_id,
        payload={
            "agent_name": agent_name,
            "task": task,
            "priority": priority,
        },
    )


def execution_event_message(
    execution_id: str,
    agent: str,
    event_type: str,
    status: str,
    message: str,
    payload: Dict[str, Any] = {},
) -> RabbitMessage:
    return RabbitMessage(
        message_type=MessageType.EXECUTION_EVENT,
        execution_id=execution_id,
        payload={
            "agent": agent,
            "event_type": event_type,
            "status": status,
            "message": message,
            "data": payload,
        },
    )

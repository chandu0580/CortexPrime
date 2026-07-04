"""
CortexPrime RabbitMQ Infrastructure
-------------------------------------
Async message bus for agent orchestration, cognition propagation,
distributed runtime workflows, and execution pipelines.

Public singletons
-----------------
  rabbitmq_connection  — async AMQP connection with reconnect loop
  channel_pool         — fixed-size channel pool for concurrent publishing
  rabbitmq_publisher   — typed message publisher (all event kinds)
  rabbitmq_consumer    — multi-queue consumer with retry + DLQ routing
  orchestration_bus    — high-level facade: missions, agents, cognition, memory
  message_tracer       — in-process distributed trace ring-buffer
  dlq_manager          — DLQ inspection and message replay
  default_retry_policy — exponential back-off retry policy

Schema types
------------
  RabbitMessage   — universal message envelope with TraceContext
  TraceContext    — distributed trace propagation (trace_id/span_id)
  MessageType     — all event kinds in the system
  Queues          — queue name constants
  Exchanges       — exchange name constants
  RoutingKeys     — routing key helpers
"""
from backend.infrastructure.rabbitmq.connection       import rabbitmq_connection    # noqa: F401
from backend.infrastructure.rabbitmq.channel_pool     import channel_pool           # noqa: F401
from backend.infrastructure.rabbitmq.publisher        import rabbitmq_publisher     # noqa: F401
from backend.infrastructure.rabbitmq.consumer         import rabbitmq_consumer      # noqa: F401
from backend.infrastructure.rabbitmq.orchestration_bus import orchestration_bus     # noqa: F401
from backend.infrastructure.rabbitmq.tracing          import message_tracer         # noqa: F401
from backend.infrastructure.rabbitmq.retry_policy     import dlq_manager, default_retry_policy  # noqa: F401
from backend.infrastructure.rabbitmq.schemas          import (                       # noqa: F401
    RabbitMessage,
    TraceContext,
    MessageType,
    Queues,
    Exchanges,
    RoutingKeys,
)

__all__ = [
    "rabbitmq_connection",
    "channel_pool",
    "rabbitmq_publisher",
    "rabbitmq_consumer",
    "orchestration_bus",
    "message_tracer",
    "dlq_manager",
    "default_retry_policy",
    "RabbitMessage",
    "TraceContext",
    "MessageType",
    "Queues",
    "Exchanges",
    "RoutingKeys",
]

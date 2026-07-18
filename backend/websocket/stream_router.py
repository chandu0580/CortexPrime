"""
Stream Router
=============
Maps topic names to Redis pub/sub channels and handles the bridge
between per-connection topic subscriptions and the Redis pub/sub layer.

When a client sends ``{"type": "subscribe_topic", "payload": {"topic": "cognition"}}``
the gateway calls ``stream_router.subscribe(conn_id, topic)`` which:
  1. Registers the topic on the ConnectionPool context.
  2. Registers a Redis pub/sub handler that forwards matching events to
     the pool's ``broadcast_to_topic()`` method.

This decouples the gateway from knowing which Redis channels carry
which kinds of events — the router owns that mapping.

Topic → Redis channel mapping
------------------------------
cognition      → cx:pub:broadcast  (all events — clients see everything)
orchestration  → cx:pub:broadcast  (filtered by event.type prefix)
execution      → cx:pub:broadcast  (filtered by event.type prefix)
metrics        → cx:pub:metrics
agent:{name}   → cx:pub:agent:{name}
ai_stream      → cx:pub:broadcast  (filtered by event.type = ai_response*)
system         → cx:pub:broadcast  (filtered by event.type = system*)
"""
from __future__ import annotations

import logging
from typing import Any, Dict, Optional, Set

log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Topic → channel mapping
# ---------------------------------------------------------------------------

# Special prefix sentinel: channels prefixed with "{agent}" are dynamic
AGENT_TOPIC_PREFIX = "agent:"

def _redis_channel_for_topic(topic: str) -> Optional[str]:
    """
    Map a topic name to its primary Redis pub/sub channel.
    Returns None for topics that use broadcast channel filtering.
    """
    from backend.infrastructure.redis.keys import RedisKeys

    if topic.startswith(AGENT_TOPIC_PREFIX):
        agent = topic[len(AGENT_TOPIC_PREFIX):]
        return RedisKeys.channel_agent(agent)
    if topic == "metrics":
        return RedisKeys.channel_metrics()
    # cognition, orchestration, execution, ai_stream, system → all come
    # through cx:pub:broadcast with event-type based routing
    return RedisKeys.channel_broadcast()


# Event type prefix routing for broadcast channel
_TOPIC_EVENT_PREFIXES: Dict[str, Set[str]] = {
    "cognition":     {"cognition_event", "cognition_flow", "cognition_state",
                      "execution_state_update", "pipeline_event",
                      "agent_status_update", "init", "snapshot"},
    "orchestration": {"orchestration_update", "mission_start", "mission_complete",
                      "mission_failed", "agent_task", "agent_result",
                      "pipeline_stage", "execution_state_update"},
    "execution":     {"execution_event", "execution_state_update", "pipeline_event",
                      "agent_execution_start", "agent_execution_done",
                      "execution_stream", "stage_started", "stage_completed"},
    "ai_stream":     {"ai_response", "ai_response_done", "stream_chunk"},
    "system":        {"system", "health_update", "rate_limited", "error"},
}


def event_matches_topic(event_type: str, topic: str) -> bool:
    """
    Return True if *event_type* should be forwarded to subscribers of *topic*.
    Used when both use the broadcast channel (no separate Redis channel per topic).
    """
    prefixes = _TOPIC_EVENT_PREFIXES.get(topic, set())
    if not prefixes:
        # Unknown topic — forward everything
        return True
    return any(event_type.startswith(p) for p in prefixes)


# ---------------------------------------------------------------------------
# Stream Router
# ---------------------------------------------------------------------------

class StreamRouter:
    """
    Manages topic subscription lifecycle, bridging the connection pool
    and Redis pub/sub.

    One instance per application (singleton ``stream_router``).
    """

    def __init__(self) -> None:
        # track which topics we have active Redis subscriptions for
        self._active_channels: Set[str] = set()

    async def subscribe(self, conn_id: str, topic: str) -> None:
        """
        Subscribe *conn_id* to *topic*.

        - Adds the topic to the connection's subscription set.
        - Ensures a Redis pub/sub handler is registered for the
          corresponding channel (idempotent).
        """
        from backend.websocket.connection_pool import connection_pool
        connection_pool.subscribe_topic(conn_id, topic)

        channel = _redis_channel_for_topic(topic)
        if channel and channel not in self._active_channels:
            await self._register_channel_handler(channel)
            self._active_channels.add(channel)
            log.debug("StreamRouter registered Redis channel %s", channel)

        log.debug("StreamRouter subscribe conn=%s topic=%s", conn_id, topic)

    async def unsubscribe(self, conn_id: str, topic: str) -> None:
        """Remove *topic* from *conn_id*'s subscription set."""
        from backend.websocket.connection_pool import connection_pool
        connection_pool.unsubscribe_topic(conn_id, topic)
        log.debug("StreamRouter unsubscribe conn=%s topic=%s", conn_id, topic)

    async def subscribe_defaults(self, conn_id: str) -> None:
        """
        Subscribe a new connection to the default topic set:
        cognition, orchestration, execution, system.
        """
        for topic in ("cognition", "orchestration", "execution", "system"):
            await self.subscribe(conn_id, topic)

    # ------------------------------------------------------------------
    # Redis channel handler registration
    # ------------------------------------------------------------------

    async def _register_channel_handler(self, channel: str) -> None:
        """
        Register a Redis pub/sub handler for *channel* that fans out
        incoming events to all pool connections subscribed to matching topics.
        """
        from backend.infrastructure.redis.pub_sub import pub_sub

        async def _handler(ch: str, payload: Dict[str, Any]) -> None:
            await self._route_event(ch, payload)

        pub_sub.subscribe(channel, _handler)

    async def _route_event(self, channel: str, payload: Dict[str, Any]) -> None:
        """
        Receive an event from Redis and fan it out to all connections
        whose topic subscriptions match the event type.
        """
        from backend.infrastructure.redis.keys import RedisKeys
        from backend.websocket.connection_pool import connection_pool

        event_type = payload.get("type", "")

        # Determine which topic(s) this event belongs to
        matching_topics: Set[str] = set()

        # Is this from a dedicated metrics channel?
        if channel == RedisKeys.channel_metrics():
            matching_topics.add("metrics")
        # Is this from an agent-specific channel?
        elif channel.startswith("cx:pub:agent:"):
            agent_name = channel[len("cx:pub:agent:"):]
            matching_topics.add(f"agent:{agent_name}")
        else:
            # Broadcast channel — route by event type prefix
            for topic, prefixes in _TOPIC_EVENT_PREFIXES.items():
                if any(event_type.startswith(p) for p in prefixes):
                    matching_topics.add(topic)
            # If no match, skip (don't flood unrelated subscribers)
            if not matching_topics:
                return

        # Fan out to each matching topic
        for topic in matching_topics:
            sent = await connection_pool.broadcast_to_topic(topic, payload)
            if sent:
                log.debug(
                    "StreamRouter routed event_type=%s topic=%s sent=%d",
                    event_type, topic, sent,
                )

    # ------------------------------------------------------------------
    # Direct broadcast helpers (used by MetricsBroadcaster etc.)
    # ------------------------------------------------------------------

    async def broadcast_to_topic(
        self, topic: str, payload: Dict[str, Any]
    ) -> int:
        """Directly broadcast *payload* to all connections subscribed to *topic*."""
        from backend.websocket.connection_pool import connection_pool
        return await connection_pool.broadcast_to_topic(topic, payload)

    async def broadcast_all(self, payload: Dict[str, Any]) -> int:
        """Broadcast *payload* to all connections regardless of topic."""
        from backend.websocket.connection_pool import connection_pool
        return await connection_pool.broadcast(payload)

    # ------------------------------------------------------------------
    # AI stream helpers
    # ------------------------------------------------------------------

    async def emit_ai_token(
        self,
        stream_id: str,
        token: str,
        seq: int = 0,
        done: bool = False,
    ) -> None:
        """
        Emit a single LLM token to all AI stream subscribers.
        Publishes via Redis pub/sub so other processes can emit too.
        """
        from backend.infrastructure.redis.pub_sub import pub_sub
        from backend.websocket.message_protocol import build_ai_response

        payload = build_ai_response(stream_id=stream_id, token=token, done=done, seq=seq)
        await pub_sub.broadcast(payload)

    async def emit_execution_chunk(
        self,
        execution_id: str,
        chunk: str,
        seq: int = 0,
        done: bool = False,
    ) -> None:
        """Emit an execution stream chunk to execution-topic subscribers."""
        from backend.infrastructure.redis.pub_sub import pub_sub
        from backend.websocket.message_protocol import build_execution_stream

        payload = build_execution_stream(
            execution_id=execution_id, chunk=chunk, done=done, seq=seq
        )
        await pub_sub.broadcast(payload)


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

stream_router = StreamRouter()

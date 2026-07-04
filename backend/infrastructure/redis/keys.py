"""
Centralized Redis key schema and TTL policy registry for CortexPrime.

All Redis key patterns and TTL constants live here — nothing is
hard-coded elsewhere.  Use the ``RedisKeys`` helpers to build keys
so that typos are caught at import time.

Key namespace prefix: ``cx:``
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


# ===========================================================================
# TTL POLICY
# Organised by data category; all values are in seconds.
# ===========================================================================

class TTL:
    # WebSocket sessions
    WS_SESSION          = 3600        # 1 h  — refreshed on each heartbeat
    WS_HEARTBEAT        = 60          # 60 s — connection keepalive ping

    # Cognition
    COGNITION_EVENT     = 3600        # 1 h
    COGNITION_STREAM    = 7200        # 2 h  — Redis Stream per execution
    COGNITION_CACHE     = 300         # 5 m  — latest-event snapshot per agent

    # Execution / pipeline
    EXECUTION_STATE     = 3600        # 1 h
    PIPELINE_CONTEXT    = 3600        # 1 h

    # Agent
    AGENT_STATE         = 300         # 5 m  — refreshed by heartbeat
    AGENT_HEARTBEAT     = 120         # 2 m
    AGENT_ACTIVITY      = 600         # 10 m
    AGENT_TRANSIENT_MEM = 900         # 15 m — working memory
    AGENT_THOUGHT_STACK = 600         # 10 m

    # Runtime
    RUNTIME_STATE       = 1800        # 30 m
    RUNTIME_METRICS     = 86400       # 24 h

    # Session context (user/mission scope)
    SESSION_CONTEXT     = 21600       # 6 h
    SESSION_MESSAGES    = 21600       # 6 h
    SESSION_OBJECTIVES  = 7200        # 2 h

    # Embedding cache
    EMBEDDING_CACHE     = 86400       # 24 h

    # Pub/sub channel TTL (Streams auto-trim)
    PUBSUB_STREAM       = 3600        # 1 h  — used for MAXLEN trim

    # Voice sessions
    VOICE_SESSION       = 604800      # 7 d  — full session JSON including transcript


# ===========================================================================
# KEY PATTERNS
# Conventions:
#   - ``cx:`` global namespace
#   - Colon-delimited hierarchy
#   - Curly braces mark substitution points
# ===========================================================================

class RedisKeys:
    """Build Redis keys from canonical patterns."""

    # -----------------------------------------------------------------------
    # WebSocket sessions
    # -----------------------------------------------------------------------
    @staticmethod
    def ws_session(conn_id: str) -> str:
        return f"cx:ws:session:{conn_id}"

    @staticmethod
    def ws_sessions_set() -> str:
        """Sorted set of all active WebSocket connection IDs (score = connected_at epoch)."""
        return "cx:ws:sessions"

    @staticmethod
    def ws_heartbeat(conn_id: str) -> str:
        return f"cx:ws:hb:{conn_id}"

    # -----------------------------------------------------------------------
    # Cognition
    # -----------------------------------------------------------------------
    @staticmethod
    def cognition_stream(execution_id: str) -> str:
        """Redis Stream for a specific execution's cognition events."""
        return f"cx:cog:stream:{execution_id}"

    @staticmethod
    def cognition_latest(agent: str) -> str:
        """Hash: latest cognition event fields per agent."""
        return f"cx:cog:latest:{agent}"

    @staticmethod
    def cognition_timeline(agent: str) -> str:
        """Sorted set: event IDs scored by timestamp for agent timeline."""
        return f"cx:cog:timeline:{agent}"

    @staticmethod
    def cognition_cache(execution_id: str) -> str:
        """List: recent raw JSON events for an execution."""
        return f"cx:cog:cache:{execution_id}"

    # -----------------------------------------------------------------------
    # Execution / pipeline
    # -----------------------------------------------------------------------
    @staticmethod
    def execution_state(execution_id: str) -> str:
        return f"cx:exec:state:{execution_id}"

    @staticmethod
    def active_executions() -> str:
        """Set of currently active execution IDs."""
        return "cx:exec:active"

    @staticmethod
    def pipeline_context(execution_id: str) -> str:
        return f"cx:pipe:ctx:{execution_id}"

    # -----------------------------------------------------------------------
    # Agent
    # -----------------------------------------------------------------------
    @staticmethod
    def agent_state(agent: str) -> str:
        return f"cx:agent:state:{agent}"

    @staticmethod
    def agent_heartbeat(agent: str) -> str:
        return f"cx:agent:hb:{agent}"

    @staticmethod
    def agent_activity(agent: str) -> str:
        """Hash: current activity detail for an agent."""
        return f"cx:agent:activity:{agent}"

    @staticmethod
    def agent_activity_timeline(agent: str) -> str:
        """Sorted set: activity event IDs scored by timestamp."""
        return f"cx:agent:timeline:{agent}"

    @staticmethod
    def active_agents() -> str:
        """Set of agents that have reported activity."""
        return "cx:agent:active"

    @staticmethod
    def agent_ops_counter(agent: str) -> str:
        """Integer counter: total operations for an agent."""
        return f"cx:agent:ops:{agent}"

    @staticmethod
    def agent_transient_mem(agent: str) -> str:
        """Hash: transient working memory fields for an agent."""
        return f"cx:mem:transient:{agent}"

    @staticmethod
    def agent_thought_stack(agent: str) -> str:
        """List: agent thought stack (LIFO, most recent thought at index 0)."""
        return f"cx:mem:thoughts:{agent}"

    # -----------------------------------------------------------------------
    # Runtime
    # -----------------------------------------------------------------------
    @staticmethod
    def runtime_state() -> str:
        return "cx:runtime:state"

    @staticmethod
    def runtime_metrics() -> str:
        return "cx:runtime:metrics"

    # -----------------------------------------------------------------------
    # Session context
    # -----------------------------------------------------------------------
    @staticmethod
    def session_context(session_id: str) -> str:
        return f"cx:sess:ctx:{session_id}"

    @staticmethod
    def session_messages(session_id: str) -> str:
        return f"cx:sess:msgs:{session_id}"

    @staticmethod
    def session_objectives(session_id: str) -> str:
        return f"cx:sess:obj:{session_id}"

    # -----------------------------------------------------------------------
    # Pub/sub channels  (not stored — used with PUBLISH/SUBSCRIBE)
    # -----------------------------------------------------------------------
    @staticmethod
    def channel_broadcast() -> str:
        """Global broadcast channel for all connected clients."""
        return "cx:pub:broadcast"

    @staticmethod
    def channel_session(session_id: str) -> str:
        """Per-session channel for targeted messages."""
        return f"cx:pub:session:{session_id}"

    @staticmethod
    def channel_agent(agent: str) -> str:
        """Per-agent event channel."""
        return f"cx:pub:agent:{agent}"

    @staticmethod
    def channel_metrics() -> str:
        """Dedicated channel for periodic runtime metrics snapshots."""
        return "cx:pub:metrics"

    @staticmethod
    def channel_orchestration() -> str:
        """Orchestration state update channel."""
        return "cx:pub:orchestration"

    # -----------------------------------------------------------------------
    # Auth — token blacklist & session tracking
    # -----------------------------------------------------------------------
    @staticmethod
    def auth_blacklist_jti(jti: str) -> str:
        """STRING: revocation marker for a single JTI; TTL = token remaining TTL."""
        return f"cx:auth:bl:jti:{jti}"

    @staticmethod
    def auth_user_revoke(user_id: str) -> str:
        """STRING: epoch of user-level global revocation event."""
        return f"cx:auth:bl:user:{user_id}"

    @staticmethod
    def auth_sessions(user_id: str) -> str:
        """ZSET: active session JTIs (score = expiry epoch) for a user."""
        return f"cx:auth:sess:{user_id}"

    # -----------------------------------------------------------------------
    # Embedding cache
    # -----------------------------------------------------------------------
    @staticmethod
    def embedding_cache(text_hash: str) -> str:
        return f"cx:embed:{text_hash}"

    # -----------------------------------------------------------------------
    # Voice sessions — multi-turn conversation persistence
    # -----------------------------------------------------------------------
    @staticmethod
    def voice_session(session_id: str) -> str:
        """STRING (JSON): full VoiceSession state + transcript_log."""
        return f"cx:voice:sess:{session_id}"

    @staticmethod
    def voice_session_index() -> str:
        """ZSET: active voice session IDs (score = created_at epoch)."""
        return "cx:voice:index"

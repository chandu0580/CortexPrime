"""
Redis Runtime Cache — backward-compatible facade.

All new code should import from the dedicated service modules:
  - runtime_state_manager.RuntimeStateManager  → execution / pipeline state
  - cognition_cache.CognitionCache             → cognition event streams
  - agent_activity_store.AgentActivityStore    → agent state + timeline

This module re-exports the ``RedisKeys`` constants and the ``redis_cache``
singleton (which now delegates to ``runtime_state``) so that existing
callers throughout the codebase continue to work without modification.
"""
from __future__ import annotations

import json
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

log = logging.getLogger(__name__)

# Delegate to the new services
from backend.infrastructure.redis.connection            import redis_connection
from backend.infrastructure.redis.runtime_state_manager import runtime_state
from backend.infrastructure.redis.cognition_cache       import cognition_cache
from backend.infrastructure.redis.keys                  import RedisKeys, TTL


# =========================================================
# BACKWARD-COMPAT KEY CONSTANTS  (legacy names)
# =========================================================

class _LegacyRedisKeys:
    """Aliases kept so that legacy import ``from .runtime_cache import RedisKeys`` works."""
    EXECUTION_STATE   = "cx:exec:state:{execution_id}"
    AGENT_STATE       = "cx:agent:state:{agent_name}"
    AGENT_HEARTBEAT   = "cx:agent:hb:{agent_name}"
    ACTIVE_EXECUTIONS = "cx:exec:active"
    PIPELINE_CONTEXT  = "cx:pipe:ctx:{execution_id}"
    TASK_PRIORITY_Q   = "cx:priority_queue"
    COGNITION_LOG     = "cx:cog:cache:{execution_id}"
    RUNTIME_METRICS   = "cx:runtime:metrics"


# Alias for legacy imports
RedisKeys = _LegacyRedisKeys  # type: ignore[assignment]


# =========================================================
# REDIS RUNTIME CACHE  (backward-compat wrapper)
# =========================================================

class RedisRuntimeCache:
    """
    Legacy runtime cache wrapper.

    All methods delegate to the new modular services.  This class is kept
    so that existing call sites (orchestration_tracer, lifecycle_manager,
    cognition_pipeline, execution_context) require zero changes.
    """

    # TTLs kept for reference
    EXECUTION_TTL = TTL.EXECUTION_STATE
    AGENT_TTL     = TTL.AGENT_STATE
    PIPELINE_TTL  = TTL.PIPELINE_CONTEXT
    METRICS_TTL   = TTL.RUNTIME_METRICS

    # In-memory fallback (also maintained inside delegate services)
    def __init__(self) -> None:
        self._executions: Dict[str, Any] = {}
        self._agents:     Dict[str, Any] = {}
        self._pipelines:  Dict[str, Any] = {}

    # ---------------------------------------------------------
    # EXECUTION STATE
    # ---------------------------------------------------------

    async def set_execution_state(
        self, execution_id: str, state: Dict[str, Any]
    ) -> None:
        await runtime_state.set_execution_state(execution_id, state)

    async def get_execution_state(
        self, execution_id: str
    ) -> Optional[Dict[str, Any]]:
        return await runtime_state.get_execution_state(execution_id)

    async def delete_execution_state(self, execution_id: str) -> None:
        await runtime_state.delete_execution_state(execution_id)

    async def list_active_executions(self) -> List[str]:
        return await runtime_state.list_active_executions()

    # ---------------------------------------------------------
    # AGENT STATE
    # ---------------------------------------------------------

    async def set_agent_state(
        self,
        agent_name: str,
        status:     str,
        metadata:   Dict[str, Any] = {},
    ) -> None:
        await runtime_state.update_agent_status(agent_name, status, metadata)

    async def get_agent_state(
        self, agent_name: str
    ) -> Optional[Dict[str, Any]]:
        from backend.infrastructure.redis.agent_activity_store import agent_activity_store
        return await agent_activity_store.get_state(agent_name)

    # ---------------------------------------------------------
    # PIPELINE CONTEXT
    # ---------------------------------------------------------

    async def set_pipeline_context(
        self, execution_id: str, context: Dict[str, Any]
    ) -> None:
        await runtime_state.set_pipeline_context(execution_id, context)

    async def get_pipeline_context(
        self, execution_id: str
    ) -> Optional[Dict[str, Any]]:
        return await runtime_state.get_pipeline_context(execution_id)

    # ---------------------------------------------------------
    # COGNITION LOG  (append-only list)
    # ---------------------------------------------------------

    async def append_cognition_log(
        self, execution_id: str, entry: Dict[str, Any]
    ) -> None:
        await cognition_cache.push_event(
            execution_id = execution_id,
            agent        = entry.get("agent",      "unknown"),
            event_type   = entry.get("event_type", "log"),
            message      = entry.get("message",    json.dumps(entry)),
            phase        = entry.get("phase"),
            payload      = entry.get("payload"),
        )

    async def get_cognition_log(
        self, execution_id: str
    ) -> List[Dict[str, Any]]:
        return await cognition_cache.get_recent(execution_id, limit=200)


# =========================================================
# SINGLETON
# =========================================================

redis_cache = RedisRuntimeCache()

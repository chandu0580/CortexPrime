from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional, Set
from uuid import uuid4

log = logging.getLogger(__name__)


# =========================================================
# AGENT LIFECYCLE STATES
# =========================================================

class AgentStatus:
    IDLE       = "idle"
    RUNNING    = "running"
    PAUSED     = "paused"
    STOPPING   = "stopping"
    STOPPED    = "stopped"
    FAILED     = "failed"


# =========================================================
# AGENT RECORD
# =========================================================

class AgentRecord:

    def __init__(
        self,
        agent_name: str,
        agent_type: str,
        capabilities: List[str] = [],
    ):
        self.agent_id     = str(uuid4())
        self.agent_name   = agent_name
        self.agent_type   = agent_type
        self.capabilities = capabilities
        self.status       = AgentStatus.IDLE
        self.created_at   = datetime.utcnow().isoformat()
        self.last_active  = self.created_at
        self.task_count   = 0
        self.error_count  = 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "agent_id":     self.agent_id,
            "agent_name":   self.agent_name,
            "agent_type":   self.agent_type,
            "capabilities": self.capabilities,
            "status":       self.status,
            "created_at":   self.created_at,
            "last_active":  self.last_active,
            "task_count":   self.task_count,
            "error_count":  self.error_count,
        }


# =========================================================
# AGENT LIFECYCLE MANAGER
# =========================================================

class AgentLifecycleManager:
    """
    Manages the full lifecycle of agents:
    - Registration / deregistration
    - Status transitions (idle → running → idle | failed)
    - Heartbeat monitoring
    - Redis-backed state persistence
    """

    def __init__(self):
        self._records:    Dict[str, AgentRecord] = {}
        self._active_set: Set[str] = set()

    # ---------------------------------------------------------
    # REGISTER
    # ---------------------------------------------------------

    def register(
        self,
        agent_name:   str,
        agent_type:   str = "cognitive",
        capabilities: List[str] = [],
    ) -> AgentRecord:
        record = AgentRecord(agent_name, agent_type, capabilities)
        self._records[agent_name] = record
        log.info("✅ Agent registered: %s (%s)", agent_name, agent_type)
        return record

    # ---------------------------------------------------------
    # DEREGISTER
    # ---------------------------------------------------------

    def deregister(self, agent_name: str) -> None:
        self._records.pop(agent_name, None)
        self._active_set.discard(agent_name)

    # ---------------------------------------------------------
    # STATUS TRANSITIONS
    # ---------------------------------------------------------

    async def activate(self, agent_name: str) -> None:
        record = self._records.get(agent_name)
        if record:
            record.status     = AgentStatus.RUNNING
            record.last_active = datetime.utcnow().isoformat()
            record.task_count += 1
            self._active_set.add(agent_name)
            await self._sync_redis(agent_name, AgentStatus.RUNNING)

    async def deactivate(self, agent_name: str) -> None:
        record = self._records.get(agent_name)
        if record:
            record.status = AgentStatus.IDLE
            self._active_set.discard(agent_name)
            await self._sync_redis(agent_name, AgentStatus.IDLE)

    async def fail(self, agent_name: str, error: str = "") -> None:
        record = self._records.get(agent_name)
        if record:
            record.status      = AgentStatus.FAILED
            record.error_count += 1
            self._active_set.discard(agent_name)
            await self._sync_redis(agent_name, AgentStatus.FAILED, {"error": error})

    # ---------------------------------------------------------
    # QUERY
    # ---------------------------------------------------------

    def get_record(self, agent_name: str) -> Optional[AgentRecord]:
        return self._records.get(agent_name)

    def list_all(self) -> List[Dict[str, Any]]:
        return [r.to_dict() for r in self._records.values()]

    def list_active(self) -> List[str]:
        return list(self._active_set)

    def is_active(self, agent_name: str) -> bool:
        return agent_name in self._active_set

    # ---------------------------------------------------------
    # SYNC STATE TO REDIS
    # ---------------------------------------------------------

    async def _sync_redis(
        self,
        agent_name: str,
        status:     str,
        extra:      Dict[str, Any] = {},
    ) -> None:
        try:
            from backend.infrastructure.redis.runtime_cache import redis_cache
            await redis_cache.set_agent_state(agent_name, status, extra)
        except Exception as exc:
            log.warning("Lifecycle manager Redis sync failed: %s", exc)

    # ---------------------------------------------------------
    # BOOTSTRAP — register all known agents
    # ---------------------------------------------------------

    def bootstrap(self) -> None:
        """Pre-register all CortexPrime cognitive agents."""
        agents = [
            ("orchestrator", "orchestrator",  ["route", "delegate", "coordinate"]),
            ("planner",      "planner",        ["decompose", "plan", "sequence"]),
            ("research",     "research",       ["search", "retrieve", "synthesize"]),
            ("critic",       "critic",         ["validate", "score", "hallucination_check"]),
            ("optimizer",    "optimizer",      ["optimize", "refine", "improve"]),
            ("reflection",   "reflection",     ["reflect", "learn", "consolidate"]),
            ("memory",       "memory",         ["store", "retrieve", "embed"]),
        ]
        for name, agent_type, caps in agents:
            if name not in self._records:
                self.register(name, agent_type, caps)


# =========================================================
# SINGLETON
# =========================================================

agent_lifecycle_manager = AgentLifecycleManager()

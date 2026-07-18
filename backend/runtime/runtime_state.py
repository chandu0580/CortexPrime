"""
Runtime State — READ-ONLY PROJECTION of the canonical Engineering Runtime Store.

This module is maintained for backward compatibility only.
ALL execution state now lives in the canonical RuntimeStore
(backend.services.enterprise_runtime_store).

Architecture:
  - start_execution() / complete_execution() write through to RuntimeStore.
  - update_agent_state() remains local (agent state != execution state).
  - get_state() reads from RuntimeStore and merges with local agent states.
"""
from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Dict

log = logging.getLogger(__name__)


class RuntimeState:

    def __init__(self):
        self._agent_states: Dict[str, Dict[str, str]] = {}

    # ==========================================
    # START EXECUTION  (write-through to RuntimeStore)
    # ==========================================

    def start_execution(
        self,
        execution_id: str,
        objective: str,
    ) -> None:
        from backend.services.enterprise_runtime_store import (
            EngineeringExecution,
            runtime_store,
        )
        execution = EngineeringExecution(
            execution_id=execution_id,
            status="running",
            objective=objective,
        )
        runtime_store.create_execution(execution)

    # ==========================================
    # COMPLETE EXECUTION  (write-through to RuntimeStore)
    # ==========================================

    def complete_execution(
        self,
        execution_id: str,
    ) -> None:
        from backend.services.enterprise_runtime_store import runtime_store
        runtime_store.update_execution(execution_id, status="completed")

    # ==========================================
    # UPDATE AGENT STATE  (local — not execution state)
    # ==========================================

    def update_agent_state(
        self,
        agent_name: str,
        status: str,
    ) -> None:
        self._agent_states[agent_name] = {
            "status": status,
            "updated_at": datetime.utcnow().isoformat(),
        }

    # ==========================================
    # GET FULL STATE  (RuntimeStore + local agent states)
    # ==========================================

    def get_state(self) -> Dict[str, Any]:
        from backend.services.enterprise_runtime_store import runtime_store
        all_execs = runtime_store.list_executions(limit=1000)
        active = {}
        history = []
        for e in all_execs:
            d = e.to_dict()
            if e.status in ("running", "pending"):
                active[e.execution_id] = d
            else:
                history.append(d)
        return {
            "active_executions": active,
            "agent_states": self._agent_states,
            "execution_history": history,
        }


# ==========================================
# GLOBAL RUNTIME STATE
# ==========================================

runtime_state = RuntimeState()

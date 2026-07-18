from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from backend.agents.base import AgentResult
from backend.orchestrator.runtime_resolver import get_cognitive_memory_service

log = logging.getLogger(__name__)


class CognitiveMemoryBridge:
    def __init__(self) -> None:
        self._local_cache: Dict[str, Dict[str, Any]] = {}

    def _mem(self) -> Any:
        return get_cognitive_memory_service()

    def ensure_context(self, mission_id: str, ctx_data: Dict[str, Any]) -> bool:
        mem = self._mem()
        if not mem:
            self._local_cache.setdefault(mission_id, {"reasoning_steps": [], "artifacts": [], "phases": {}})
            return True
        existing = self.get_context(mission_id)
        if existing:
            return True
        try:
            mem.create_context(
                mission_id=mission_id,
                user_id=ctx_data.get("user_id", ""),
                tenant_id=ctx_data.get("tenant_id", ""),
                trace_id=ctx_data.get("trace_id", ""),
                correlation_id=ctx_data.get("correlation_id", ""),
                initial_goal=ctx_data.get("goal", ""),
                mission_name=ctx_data.get("name", mission_id),
                objective=ctx_data.get("objective", ""),
                category=ctx_data.get("category", "multi_agent"),
            )
            return True
        except Exception as exc:
            log.debug("Failed to create cognitive memory context: %s", exc)
            self._local_cache.setdefault(mission_id, {"reasoning_steps": [], "artifacts": [], "phases": {}})
            return False

    def get_context(self, mission_id: str) -> Optional[Dict[str, Any]]:
        mem = self._mem()
        if mem:
            try:
                ctx = mem.get_context(mission_id)
                if ctx:
                    return self._to_dict(ctx)
            except Exception:
                pass
        return self._local_cache.get(mission_id)

    def add_reasoning_step(self, mission_id: str, agent_type: str,
                           description: str, decision: str = "",
                           confidence: float = 1.0, critical: bool = False) -> None:
        step = {
            "step_id": None,
            "agent": agent_type,
            "description": description,
            "decision": decision,
            "confidence": confidence,
            "critical": critical,
        }
        mem = self._mem()
        if mem:
            try:
                mem.add_reasoning_step(
                    mission_id, description=description, decision=decision,
                    confidence=confidence, critical=critical,
                )
                return
            except Exception as exc:
                log.debug("Failed to add reasoning step: %s", exc)
        cache = self._local_cache.setdefault(mission_id, {"reasoning_steps": [], "artifacts": [], "phases": {}})
        cache.setdefault("reasoning_steps", []).append(step)

    def add_artifact(self, mission_id: str, agent_type: str, name: str,
                     artifact_type: str, data: Any) -> None:
        mem = self._mem()
        if mem:
            try:
                mem.add_artifact(
                    mission_id, name=name, artifact_type=artifact_type,
                    data=data, source=f"agent.{agent_type}",
                )
                return
            except Exception as exc:
                log.debug("Failed to add artifact: %s", exc)
        cache = self._local_cache.setdefault(mission_id, {"reasoning_steps": [], "artifacts": [], "phases": {}})
        cache.setdefault("artifacts", []).append({
            "name": name, "type": artifact_type, "data": data, "source": f"agent.{agent_type}",
        })

    def update_phase(self, mission_id: str, phase: str, result: AgentResult) -> None:
        mem = self._mem()
        updates = {
            "current_phase": phase,
            "completed_steps": [phase],
        }
        if mem:
            try:
                mem.update_context(mission_id, updates)
                return
            except Exception:
                pass
        cache = self._local_cache.setdefault(mission_id, {"reasoning_steps": [], "artifacts": [], "phases": {}})
        cache.setdefault("phases", {})[phase] = {
            "agent": result.agent_type,
            "success": result.success,
            "error": result.error,
        }

    def get_reasoning_trace(self, mission_id: str) -> List[Dict[str, Any]]:
        ctx = self.get_context(mission_id)
        if ctx:
            steps = ctx.get("reasoning_steps") or ctx.get("reasoning_memory", {}).get("reasoning_chain", [])
            return [{
                "description": s.get("description", "") if isinstance(s, dict) else str(getattr(s, "description", "")),
                "decision": s.get("decision", "") if isinstance(s, dict) else str(getattr(s, "decision", "")),
                "confidence": s.get("confidence", 1.0) if isinstance(s, dict) else getattr(s, "confidence", 1.0),
                "critical": s.get("critical", False) if isinstance(s, dict) else getattr(s, "critical", False),
            } for s in (steps or [])]
        return []

    def _to_dict(self, ctx: Any) -> Dict[str, Any]:
        try:
            if hasattr(ctx, "model_dump"):
                return ctx.model_dump()
            if hasattr(ctx, "dict"):
                return ctx.dict()
            if hasattr(ctx, "__dict__"):
                return {k: v for k, v in ctx.__dict__.items() if not k.startswith("_")}
        except Exception:
            pass
        return {}


cognitive_memory_bridge = CognitiveMemoryBridge()

"""
Computer Agent V2  (CortexPrime Computer Agent V2)
====================================================
High-level orchestrator that exposes a single clean interface for
autonomous desktop task completion.

Unlike computer_agent.py (which executes explicit step lists),
ComputerAgentV2 accepts a *natural language goal* and drives the
full Observe → Analyze → Decide → Act → Verify → Recover loop via
TaskCompletionEngine.

Mission runtime (`mission_runtime.py`) calls `execute_autonomous_mission()`
when it detects a computer-task keyword in the user objective.
"""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import uuid4

from backend.computer.task_completion_engine import (
    TaskCompletionEngine,
    MissionResult,
    task_completion_engine,
)
from backend.computer.screen_observer import screen_observer

log = logging.getLogger(__name__)


# =========================================================
# COMPUTER AGENT V2
# =========================================================

class ComputerAgentV2:
    """
    Autonomous desktop agent.

    Entry points
    ------------
    execute_autonomous_mission(payload)   — called by mission_runtime
    capture_screen()                      — return current screenshot info
    list_monitors()                       — return monitor list
    list_active()                         — list running missions
    """

    # ----------------------------------------------------------
    # EXECUTE AUTONOMOUS MISSION
    # ----------------------------------------------------------

    async def execute_autonomous_mission(
        self,
        payload: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Main entry point.

        Expected payload keys
        ----------------------
        goal            : str   — natural-language task to complete
        execution_id    : str   — optional, generated if missing
        session_id      : str   — optional workflow session
        success_text    : str   — optional OCR text signalling success
        max_iterations  : int   — optional, default 30
        use_vision      : bool  — use GPT-4 vision, default True
        """
        goal           = payload.get("goal", "").strip()
        execution_id   = payload.get("execution_id", str(uuid4()))
        session_id     = payload.get("session_id")
        success_text   = payload.get("success_text")
        max_iterations = int(payload.get("max_iterations", 30))
        use_vision     = bool(payload.get("use_vision", True))

        if not goal:
            return {
                "success":      False,
                "error":        "goal is required",
                "execution_id": execution_id,
            }

        log.info("[ComputerAgentV2] Starting autonomous mission: %s", goal[:80])
        await self._emit(
            execution_id, "computer_mission_started", "started", "initialization",
            f"Autonomous mission started: {goal[:80]}",
            {"goal": goal}, session_id,
        )

        try:
            result: MissionResult = await task_completion_engine.execute(
                goal           = goal,
                execution_id   = execution_id,
                session_id     = session_id,
                success_text   = success_text,
                max_iterations = max_iterations,
                use_vision     = use_vision,
            )

            return {
                "success":      result.status == "completed",
                "execution_id": execution_id,
                "status":       result.status,
                "summary":      result.summary,
                "iterations":   result.iterations,
                "failures":     result.failures,
                "step_count":   len(result.steps),
                "screenshots":  result.screenshots,
                "steps":        [s.as_dict() for s in result.steps],
                "final_snapshot": result.final_snapshot,
                "started_at":   result.started_at,
                "completed_at": result.completed_at,
            }

        except Exception as exc:
            log.error("[ComputerAgentV2] Mission failed: %s", exc)
            await self._emit(
                execution_id, "computer_mission_error", "failed", "execution",
                f"Mission error: {exc}",
                {"error": str(exc)}, session_id,
            )
            return {
                "success":      False,
                "error":        str(exc),
                "execution_id": execution_id,
                "status":       "failed",
            }

    # ----------------------------------------------------------
    # SCREEN CAPTURE
    # ----------------------------------------------------------

    async def capture_screen(
        self,
        monitor:     int  = 0,
        run_ocr:     bool = True,
        detect_ui:   bool = True,
    ) -> Dict[str, Any]:
        """Capture the current screen and return metadata."""
        try:
            snapshot = await screen_observer.capture(
                monitor    = monitor,
                run_ocr    = run_ocr,
                detect_ui  = detect_ui,
            )
            return snapshot.as_dict()
        except Exception as exc:
            return {"error": str(exc)}

    # ----------------------------------------------------------
    # MONITOR LIST
    # ----------------------------------------------------------

    def list_monitors(self) -> List[Dict[str, Any]]:
        return screen_observer.list_monitors()

    # ----------------------------------------------------------
    # ACTIVE MISSIONS
    # ----------------------------------------------------------

    def list_active(self) -> List[Dict[str, Any]]:
        return task_completion_engine.list_active()

    # ----------------------------------------------------------
    # EMIT EVENT
    # ----------------------------------------------------------

    async def _emit(
        self,
        execution_id: str,
        event_type:   str,
        status:       str,
        phase:        str,
        message:      str,
        payload:      Optional[Dict[str, Any]] = None,
        session_id:   Optional[str]            = None,
    ) -> None:
        try:
            from backend.events.event_bus    import event_bus
            from backend.events.event_models import CognitionEvent
            await event_bus.publish(CognitionEvent(
                agent        = "computer_agent_v2",
                event_type   = event_type,
                status       = status,
                phase        = phase,
                execution_id = execution_id,
                message      = message,
                payload      = payload or {},
                session_id   = session_id,
            ))
        except Exception:
            pass


# =========================================================
# SINGLETON
# =========================================================

computer_agent_v2 = ComputerAgentV2()

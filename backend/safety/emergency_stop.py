"""
Emergency Stop System  (CortexPrime)
========================================
Provides a hard kill-switch that can:
- Stop any running mission
- Stop the Browser Agent
- Stop the Computer Agent
- Cancel pending approval requests
- Terminate active sessions

When activated, all running agents are signalled to abort and a
``emergency_stop_activated`` WebSocket event is broadcast globally.
"""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional, Set
from uuid import uuid4

log = logging.getLogger(__name__)


# =========================================================
# EMERGENCY STOP CONTROLLER
# =========================================================

class EmergencyStopController:
    """
    Global kill-switch registry.

    Usage
    -----
    # Check inside a long-running loop:
    if emergency_stop.is_stopped(execution_id):
        raise StopIteration("Emergency stop activated")

    # Activate the global stop:
    await emergency_stop.activate_global(reason="User initiated stop")
    """

    def __init__(self) -> None:
        self._stopped_executions: Set[str] = set()
        self._global_stop: bool            = False
        self._global_stop_reason: str      = ""
        self._stop_log: List[Dict[str, Any]] = []

    # ----------------------------------------------------------
    # GLOBAL STOP
    # ----------------------------------------------------------

    async def activate_global(
        self,
        reason:     str  = "Emergency stop activated",
        stopped_by: str  = "operator",
    ) -> Dict[str, Any]:
        """Activate the global emergency stop — affects ALL running agents."""
        self._global_stop        = True
        self._global_stop_reason = reason

        entry = {
            "stop_id":    str(uuid4()),
            "scope":      "global",
            "reason":     reason,
            "stopped_by": stopped_by,
            "timestamp":  datetime.utcnow().isoformat(),
        }
        self._stop_log.append(entry)

        log.warning("🛑 GLOBAL EMERGENCY STOP: %s by %s", reason, stopped_by)

        # Stop all browser sessions
        await self._stop_browser_agent()

        # Cancel all pending approvals
        await self._cancel_pending_approvals(reason)

        # Broadcast WebSocket event
        await self._broadcast_stop_event("emergency_stop_activated", entry)

        return entry

    async def deactivate_global(self, deactivated_by: str = "operator") -> Dict[str, Any]:
        """Lift the global emergency stop."""
        self._global_stop        = False
        self._global_stop_reason = ""

        entry = {
            "scope":           "global",
            "deactivated_by":  deactivated_by,
            "timestamp":       datetime.utcnow().isoformat(),
        }

        log.info("✅ Global emergency stop lifted by %s", deactivated_by)
        await self._broadcast_stop_event("emergency_stop_deactivated", entry)
        return entry

    @property
    def is_globally_stopped(self) -> bool:
        return self._global_stop

    # ----------------------------------------------------------
    # MISSION-SCOPED STOP
    # ----------------------------------------------------------

    async def stop_mission(
        self,
        execution_id: str,
        reason:       str = "Stopped by operator",
        stopped_by:   str = "operator",
    ) -> Dict[str, Any]:
        """Stop a specific mission execution."""
        self._stopped_executions.add(execution_id)

        entry = {
            "stop_id":      str(uuid4()),
            "scope":        "mission",
            "execution_id": execution_id,
            "reason":       reason,
            "stopped_by":   stopped_by,
            "timestamp":    datetime.utcnow().isoformat(),
        }
        self._stop_log.append(entry)

        log.warning("🛑 Mission stopped: %s | %s", execution_id[:8], reason)

        await self._broadcast_stop_event(
            "mission_stopped",
            entry,
            execution_id=execution_id,
        )

        # Close any browser session associated with this mission
        await self._stop_browser_session(execution_id)

        # Reject pending approvals for this execution
        await self._cancel_approvals_for_execution(execution_id, reason)

        return entry

    def resume_mission(self, execution_id: str) -> None:
        """Re-allow a previously stopped execution."""
        self._stopped_executions.discard(execution_id)
        log.info("▶️  Mission resumed: %s", execution_id[:8])

    def is_stopped(self, execution_id: str) -> bool:
        """Return True if this execution (or the whole system) is stopped."""
        return self._global_stop or execution_id in self._stopped_executions

    # ----------------------------------------------------------
    # BROWSER AGENT STOP
    # ----------------------------------------------------------

    async def stop_browser_agent(
        self,
        reason:     str = "Emergency stop",
        stopped_by: str = "operator",
    ) -> Dict[str, Any]:
        """Close all active browser sessions."""
        entry = {
            "stop_id":    str(uuid4()),
            "scope":      "browser_agent",
            "reason":     reason,
            "stopped_by": stopped_by,
            "timestamp":  datetime.utcnow().isoformat(),
        }
        self._stop_log.append(entry)

        sessions_closed = await self._stop_browser_agent()

        entry["sessions_closed"] = sessions_closed
        log.warning("🛑 Browser agent stopped: %d sessions closed", sessions_closed)

        await self._broadcast_stop_event("browser_agent_stopped", entry)
        return entry

    # ----------------------------------------------------------
    # COMPUTER AGENT STOP
    # ----------------------------------------------------------

    async def stop_computer_agent(
        self,
        reason:     str = "Emergency stop",
        stopped_by: str = "operator",
    ) -> Dict[str, Any]:
        """Terminate active computer-agent missions."""
        entry = {
            "stop_id":    str(uuid4()),
            "scope":      "computer_agent",
            "reason":     reason,
            "stopped_by": stopped_by,
            "timestamp":  datetime.utcnow().isoformat(),
        }
        self._stop_log.append(entry)

        missions_cancelled = await self._stop_computer_agent()
        entry["missions_cancelled"] = missions_cancelled

        log.warning("🛑 Computer agent stopped: %d missions cancelled", missions_cancelled)
        await self._broadcast_stop_event("computer_agent_stopped", entry)
        return entry

    # ----------------------------------------------------------
    # CANCEL WORKFLOWS
    # ----------------------------------------------------------

    async def cancel_workflow(
        self,
        workflow_id: str,
        reason:      str = "Cancelled",
        stopped_by:  str = "operator",
    ) -> Dict[str, Any]:
        """Cancel a specific workflow (execution ID)."""
        return await self.stop_mission(workflow_id, reason, stopped_by)

    # ----------------------------------------------------------
    # STATUS + LOG
    # ----------------------------------------------------------

    def get_status(self) -> Dict[str, Any]:
        return {
            "global_stop":          self._global_stop,
            "global_stop_reason":   self._global_stop_reason,
            "stopped_missions":     list(self._stopped_executions),
            "stop_log_count":       len(self._stop_log),
        }

    def get_stop_log(self, limit: int = 50) -> List[Dict[str, Any]]:
        return list(reversed(self._stop_log[-limit:]))

    # ----------------------------------------------------------
    # INTERNAL HELPERS
    # ----------------------------------------------------------

    async def _stop_browser_agent(self) -> int:
        """Close all open browser sessions. Returns session count."""
        try:
            from backend.tools.browser_agent import browser_agent
            sessions = browser_agent.list_sessions()
            for sid in sessions:
                await browser_agent.close_session(sid)
            return len(sessions)
        except Exception as exc:
            log.warning("Browser agent stop failed: %s", exc)
            return 0

    async def _stop_browser_session(self, session_id: str) -> None:
        try:
            from backend.tools.browser_agent import browser_agent
            await browser_agent.close_session(session_id)
        except Exception:
            pass

    async def _stop_computer_agent(self) -> int:
        """Cancel all active computer-agent missions. Returns mission count."""
        try:
            from backend.computer.computer_agent import computer_agent
            active = list(computer_agent.active_missions.keys())
            for mid in active:
                computer_agent.active_missions.pop(mid, None)
            return len(active)
        except Exception as exc:
            log.warning("Computer agent stop failed: %s", exc)
            return 0

    async def _cancel_pending_approvals(self, reason: str) -> None:
        try:
            from backend.safety.approval_queue import approval_queue
            pending = approval_queue.get_pending()
            for req in pending:
                approval_queue.reject(
                    req["request_id"],
                    rejected_by = "emergency_stop",
                    reason      = f"Emergency stop: {reason}",
                )
        except Exception as exc:
            log.warning("Approval cancellation failed: %s", exc)

    async def _cancel_approvals_for_execution(
        self, execution_id: str, reason: str
    ) -> None:
        try:
            from backend.safety.approval_queue import approval_queue
            for req in approval_queue.get_pending():
                if req.get("execution_id") == execution_id:
                    approval_queue.reject(
                        req["request_id"],
                        rejected_by = "emergency_stop",
                        reason      = reason,
                    )
        except Exception as exc:
            log.warning("Execution approval cancellation failed: %s", exc)

    async def _broadcast_stop_event(
        self,
        event_type:   str,
        payload:      Dict[str, Any],
        execution_id: Optional[str] = None,
    ) -> None:
        try:
            from backend.events.event_bus    import event_bus
            from backend.events.event_models import CognitionEvent
            await event_bus.publish(CognitionEvent(
                agent        = "governance",
                event_type   = event_type,
                status       = "critical",
                phase        = "emergency_stop",
                execution_id = execution_id or "global",
                message      = payload.get("reason", event_type),
                payload      = payload,
            ))
        except Exception as exc:
            log.warning("Emergency stop event broadcast failed: %s", exc)


# =========================================================
# SINGLETON
# =========================================================

emergency_stop = EmergencyStopController()

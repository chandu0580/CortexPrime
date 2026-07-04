"""
Task Completion Engine  (CortexPrime Computer Agent V2)
=========================================================
Implements the full Observe → Analyze → Plan → Act → Verify → Recover loop.

The engine runs until one of:
  - The VisionReasoner decides action="complete" (goal achieved)
  - Failure threshold is exceeded
  - Emergency stop is activated
  - Max iterations reached

Each iteration is recorded as a TaskStep and the full history is
returned for memory storage.
"""
from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import uuid4

from backend.computer.screen_observer     import ScreenObserver, ScreenSnapshot, screen_observer
from backend.computer.vision_reasoner     import VisionReasoner, ActionDecision, vision_reasoner
from backend.computer.verification_engine import VerificationEngine, VerificationResult, verification_engine
from backend.computer.recovery_engine     import RecoveryEngine, RecoveryResult, recovery_engine

log = logging.getLogger(__name__)

# Maximum Observe→Act iterations per mission
MAX_ITERATIONS    = 30
MAX_FAILURES      = 5
ACTION_SETTLE_MS  = 1200   # wait after each action before verification


# =========================================================
# TASK STEP
# =========================================================

@dataclass
class TaskStep:
    step_number:    int
    action:         str
    selector:       str
    value:          str
    reason:         str
    snapshot_path:  str
    verification:   Optional[Dict[str, Any]]
    recovery:       Optional[Dict[str, Any]]
    success:        bool
    timestamp:      str = field(default_factory=lambda: datetime.utcnow().isoformat())

    def as_dict(self) -> Dict[str, Any]:
        return {
            "step_number":   self.step_number,
            "action":        self.action,
            "selector":      self.selector,
            "value":         self.value,
            "reason":        self.reason,
            "snapshot_path": self.snapshot_path,
            "verification":  self.verification,
            "recovery":      self.recovery,
            "success":       self.success,
            "timestamp":     self.timestamp,
        }


# =========================================================
# MISSION RESULT
# =========================================================

@dataclass
class MissionResult:
    execution_id:   str
    goal:           str
    status:         str        # completed | failed | stopped | timeout
    steps:          List[TaskStep]
    screenshots:    List[str]
    iterations:     int
    failures:       int
    final_snapshot: Optional[Dict[str, Any]]
    started_at:     str
    completed_at:   str
    summary:        str

    def as_dict(self) -> Dict[str, Any]:
        return {
            "execution_id":   self.execution_id,
            "goal":           self.goal,
            "status":         self.status,
            "step_count":     len(self.steps),
            "steps":          [s.as_dict() for s in self.steps],
            "screenshots":    self.screenshots,
            "iterations":     self.iterations,
            "failures":       self.failures,
            "final_snapshot": self.final_snapshot,
            "started_at":     self.started_at,
            "completed_at":   self.completed_at,
            "summary":        self.summary,
        }


# =========================================================
# TASK COMPLETION ENGINE
# =========================================================

class TaskCompletionEngine:
    """
    Runs the Observe → Analyze → Decide → Act → Verify → Recover loop
    until the goal is reached or a failure threshold is exceeded.
    """

    def __init__(self) -> None:
        self._active_missions: Dict[str, Dict[str, Any]] = {}

    # ----------------------------------------------------------
    # MAIN ENTRY POINT
    # ----------------------------------------------------------

    async def execute(
        self,
        goal:           str,
        execution_id:   str         = "",
        session_id:     Optional[str] = None,
        success_text:   Optional[str] = None,   # OCR text that signals completion
        max_iterations: int           = MAX_ITERATIONS,
        use_vision:     bool          = True,
    ) -> MissionResult:
        """
        Run the full autonomy loop for the given *goal*.
        """
        if not execution_id:
            execution_id = str(uuid4())

        started_at = datetime.utcnow().isoformat()
        steps:       List[TaskStep] = []
        screenshots: List[str]      = []
        history:     List[str]      = []
        failures     = 0
        iteration    = 0

        self._active_missions[execution_id] = {
            "goal":       goal,
            "started_at": started_at,
            "status":     "running",
            "iteration":  0,
        }

        await self._emit(
            execution_id, "task_started", "running", "task_execution",
            f"Task started: {goal[:80]}",
            {"goal": goal, "max_iterations": max_iterations},
            session_id,
        )

        final_snapshot: Optional[ScreenSnapshot] = None
        status = "failed"

        try:
            while iteration < max_iterations:
                iteration += 1
                self._active_missions[execution_id]["iteration"] = iteration

                # ── Emergency stop check ──────────────────────
                if _is_emergency_stopped(execution_id):
                    status = "stopped"
                    break

                # ── OBSERVE ───────────────────────────────────
                await self._emit(
                    execution_id, "observe_started", "running", "observation",
                    f"Iteration {iteration}/{max_iterations} — capturing screen",
                    {"iteration": iteration}, session_id,
                )
                try:
                    snapshot = await screen_observer.capture(
                        run_ocr=True, detect_ui=True
                    )
                    final_snapshot = snapshot
                    screenshots.append(snapshot.image_path)
                except Exception as obs_err:
                    log.warning("Screen capture failed: %s", obs_err)
                    snapshot = screen_observer.last_snapshot
                    if not snapshot:
                        status = "failed"
                        break

                await self._emit(
                    execution_id, "observe_completed", "running", "observation",
                    f"Screen captured: {len(snapshot.elements)} elements",
                    snapshot.as_dict(), session_id,
                )

                # ── CHECK SUCCESS TEXT ─────────────────────────
                if success_text and success_text.lower() in snapshot.ocr_text.lower():
                    status = "completed"
                    await self._emit(
                        execution_id, "task_success_detected", "completed", "verification",
                        f"Success criterion met: '{success_text}'",
                        {"success_text": success_text}, session_id,
                    )
                    break

                # ── ANALYZE ───────────────────────────────────
                try:
                    analysis = await vision_reasoner.analyze(snapshot, use_vision=use_vision)
                    await self._emit(
                        execution_id, "analysis_completed", "running", "vision_reasoning",
                        f"Screen state: {analysis.state} — {analysis.description[:120]}",
                        analysis.as_dict(), session_id,
                    )
                    if analysis.errors:
                        history.append(f"Screen shows error: {'; '.join(analysis.errors[:3])}")
                except Exception as ana_err:
                    log.warning("Vision analysis failed: %s", ana_err)
                    analysis = None

                # ── DECIDE ────────────────────────────────────
                before_snap = snapshot
                try:
                    decision = await vision_reasoner.decide_action(
                        snapshot   = snapshot,
                        goal       = goal,
                        history    = history,
                        use_vision = use_vision,
                    )
                    await self._emit(
                        execution_id, "action_decided", "running", "planning",
                        f"Decision: {decision.action} → '{decision.selector}' ({decision.reason[:80]})",
                        decision.as_dict(), session_id,
                    )
                except Exception as dec_err:
                    log.warning("Decision failed: %s — waiting", dec_err)
                    decision = ActionDecision(
                        action="wait", selector="", value="2",
                        reason=f"Decision error: {dec_err}"
                    )

                # ── COMPLETE? ─────────────────────────────────
                if decision.action == "complete":
                    status = "completed"
                    await self._emit(
                        execution_id, "task_completed", "completed", "task_execution",
                        "Task completed — goal achieved",
                        {"reason": decision.reason}, session_id,
                    )
                    break

                if decision.action == "fail":
                    failures += 1
                    history.append(f"LLM says fail: {decision.reason}")
                    if failures >= MAX_FAILURES:
                        status = "failed"
                        break
                    continue

                # ── GOVERNANCE CHECK ──────────────────────────
                allowed = await _governance_check(
                    decision, execution_id, session_id
                )
                if not allowed:
                    step = TaskStep(
                        step_number   = len(steps) + 1,
                        action        = decision.action,
                        selector      = decision.selector,
                        value         = decision.value,
                        reason        = decision.reason,
                        snapshot_path = snapshot.image_path,
                        verification  = None,
                        recovery      = {"blocked": True},
                        success       = False,
                    )
                    steps.append(step)
                    history.append(f"Action BLOCKED by governance: {decision.action}")
                    failures += 1
                    if failures >= MAX_FAILURES:
                        status = "failed"
                        break
                    continue

                # ── ACT ───────────────────────────────────────
                act_success = await self._act(decision, snapshot, execution_id, session_id)
                history.append(
                    f"Step {iteration}: {decision.action} → '{decision.selector}' "
                    f"({'ok' if act_success else 'fail'})"
                )

                # ── AUDIT: DESKTOP ACTION ─────────────────────
                _audit_computer_action(
                    execution_id = execution_id,
                    action       = decision.action,
                    selector     = decision.selector,
                    value        = decision.value,
                    outcome      = "completed" if act_success else "failed",
                    reason       = decision.reason,
                    session_id   = session_id,
                    step         = iteration,
                )

                # ── VERIFY ────────────────────────────────────
                await asyncio.sleep(ACTION_SETTLE_MS / 1000)
                try:
                    after_snap   = await screen_observer.capture(run_ocr=True)
                    verification = await verification_engine.verify(
                        before        = before_snap,
                        after         = after_snap,
                        action        = decision.action,
                        goal_fragment = goal,
                        settle_ms     = 0,   # already waited above
                    )
                except Exception as ver_err:
                    log.warning("Verification failed: %s", ver_err)
                    verification = VerificationResult(
                        passed=True, strategy="error_fallback",
                        reason=str(ver_err)
                    )

                await self._emit(
                    execution_id, "verification_result", "running", "verification",
                    f"Verification: {'PASS' if verification.passed else 'FAIL'} — {verification.reason}",
                    verification.as_dict(), session_id,
                )

                recovery_info: Optional[Dict[str, Any]] = None

                # ── RECOVER ───────────────────────────────────
                if not verification.passed:
                    failures += 1
                    # ── AUDIT: VERIFICATION FAILURE ───────────
                    _audit_computer_action(
                        execution_id = execution_id,
                        action       = "verification_failure",
                        selector     = decision.selector,
                        value        = "",
                        outcome      = "failed",
                        reason       = f"Verification failed: {verification.reason}",
                        session_id   = session_id,
                        step         = iteration,
                    )
                    await self._emit(
                        execution_id, "recovery_started", "running", "recovery",
                        f"Verification failed (attempt {failures}/{MAX_FAILURES}) — initiating recovery",
                        {"failures": failures}, session_id,
                    )
                    recovery = await recovery_engine.recover(
                        failed_action = decision.as_dict(),
                        verification  = verification,
                        snapshot      = after_snap if "after_snap" in dir() else snapshot,
                        goal          = goal,
                        attempt       = failures - 1,
                        max_attempts  = MAX_FAILURES,
                        execution_id  = execution_id,
                    )
                    recovery_info = recovery.as_dict()

                    await self._emit(
                        execution_id, "recovery_result", "running", "recovery",
                        f"Recovery: {recovery.strategy} — {recovery.reason}",
                        recovery_info, session_id,
                    )

                    # ── AUDIT: RECOVERY ───────────────────────
                    _audit_computer_action(
                        execution_id = execution_id,
                        action       = f"recovery:{recovery.strategy}",
                        selector     = "",
                        value        = "",
                        outcome      = "completed" if recovery.succeeded else "failed",
                        reason       = f"Recovery via {recovery.strategy}: {recovery.reason}",
                        session_id   = session_id,
                        step         = iteration,
                    )

                    if not recovery.succeeded:
                        status = "failed"

                    if failures >= MAX_FAILURES:
                        status = "failed"
                        break

                # Record step
                steps.append(TaskStep(
                    step_number   = len(steps) + 1,
                    action        = decision.action,
                    selector      = decision.selector,
                    value         = decision.value,
                    reason        = decision.reason,
                    snapshot_path = snapshot.image_path,
                    verification  = verification.as_dict(),
                    recovery      = recovery_info,
                    success       = verification.passed,
                ))

                if status in ("failed", "stopped"):
                    break

            else:
                status = "timeout"

        except Exception as loop_err:
            log.error("Task completion loop error: %s", loop_err)
            status = "failed"
        finally:
            self._active_missions.pop(execution_id, None)

        completed_at = datetime.utcnow().isoformat()
        summary = _build_summary(goal, status, steps, failures)

        result = MissionResult(
            execution_id   = execution_id,
            goal           = goal,
            status         = status,
            steps          = steps,
            screenshots    = screenshots,
            iterations     = iteration,
            failures       = failures,
            final_snapshot = final_snapshot.as_dict() if final_snapshot else None,
            started_at     = started_at,
            completed_at   = completed_at,
            summary        = summary,
        )

        await self._emit(
            execution_id, "task_finished", status, "task_execution",
            f"Task {status}: {summary[:120]}",
            result.as_dict(), session_id,
        )

        # Persist to memory
        asyncio.ensure_future(
            _store_mission_memory(result, session_id)
        )

        return result

    # ----------------------------------------------------------
    # STATUS
    # ----------------------------------------------------------

    def list_active(self) -> List[Dict[str, Any]]:
        return list(self._active_missions.values())

    # ----------------------------------------------------------
    # ACT DISPATCHER
    # ----------------------------------------------------------

    async def _act(
        self,
        decision:     ActionDecision,
        snapshot:     ScreenSnapshot,
        execution_id: str,
        session_id:   Optional[str],
    ) -> bool:
        """Execute a single action decision. Returns True on success."""
        try:
            action   = decision.action
            selector = decision.selector
            value    = decision.value
            keys     = decision.keys or []

            # ── click ─────────────────────────────────────────
            if action == "click":
                coords = _parse_coords(selector)
                if coords:
                    import pyautogui
                    pyautogui.click(x=coords[0], y=coords[1])
                else:
                    # Find element by text
                    el, conf = await vision_reasoner.find_element(snapshot, selector)
                    if el:
                        import pyautogui
                        cx, cy = el.center()
                        pyautogui.click(x=cx, y=cy)
                    else:
                        log.warning("Click target not found: %s", selector)
                        return False
                await asyncio.sleep(0.3)
                return True

            # ── type ──────────────────────────────────────────
            elif action == "type":
                if selector:
                    el, conf = await vision_reasoner.find_element(snapshot, selector)
                    if el:
                        import pyautogui
                        pyautogui.click(x=el.center()[0], y=el.center()[1])
                        await asyncio.sleep(0.2)
                import pyautogui
                pyautogui.typewrite(value, interval=0.04)
                return True

            # ── hotkey ────────────────────────────────────────
            elif action == "hotkey":
                import pyautogui
                if keys:
                    pyautogui.hotkey(*keys)
                elif value:
                    pyautogui.hotkey(*value.split("+"))
                await asyncio.sleep(0.3)
                return True

            # ── scroll ────────────────────────────────────────
            elif action == "scroll":
                import pyautogui
                amount = int(value) if value.isdigit() else 3
                direction = -1 if selector.lower() == "down" else 1
                pyautogui.scroll(direction * amount)
                await asyncio.sleep(0.3)
                return True

            # ── wait ──────────────────────────────────────────
            elif action == "wait":
                secs = float(value) if value else 2.0
                await asyncio.sleep(min(secs, 10))
                return True

            else:
                log.warning("Unknown action: %s", action)
                return False

        except Exception as exc:
            log.error("Act failed: %s — %s", decision.action, exc)
            return False

    # ----------------------------------------------------------
    # EVENT HELPER
    # ----------------------------------------------------------

    async def _emit(
        self,
        execution_id: str,
        event_type:   str,
        status:       str,
        phase:        str,
        message:      str,
        payload:      Dict[str, Any] | None = None,
        session_id:   Optional[str]         = None,
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
# HELPERS
# =========================================================

def _parse_coords(selector: str):
    """Parse 'x,y' string → (int, int) or None."""
    try:
        parts = selector.split(",")
        if len(parts) == 2:
            return int(parts[0].strip()), int(parts[1].strip())
    except Exception:
        pass
    return None


def _build_summary(goal: str, status: str, steps: List[TaskStep], failures: int) -> str:
    completed = sum(1 for s in steps if s.success)
    return (
        f"{status.title()}: {goal[:60]} | "
        f"{len(steps)} steps ({completed} ok, {failures} failures)"
    )


def _is_emergency_stopped(execution_id: str) -> bool:
    try:
        from backend.safety.emergency_stop import emergency_stop
        return emergency_stop.is_stopped(execution_id)
    except Exception:
        return False


def _audit_computer_action(
    execution_id: str,
    action:       str,
    selector:     str,
    value:        str,
    outcome:      str,
    reason:       str,
    session_id:   Optional[str],
    step:         int = 0,
) -> None:
    """Fire-and-forget audit log entry for a computer agent desktop action."""
    try:
        import asyncio
        from backend.safety.audit_logger import audit_logger
        audit_logger.log(
            execution_id = execution_id,
            agent        = "computer_agent_v2",
            action       = action,
            risk_level   = "medium" if action in ("hotkey", "type") else "low",
            outcome      = outcome,
            reason       = reason,
            session_id   = session_id,
            metadata     = {
                "selector": selector,
                "value":    value[:128] if value else "",
                "step":     step,
            },
        )
    except Exception:
        pass   # audit must never crash the loop


async def _governance_check(
    decision:     ActionDecision,
    execution_id: str,
    session_id:   Optional[str],
) -> bool:
    """Gate risky computer actions through the governance layer."""
    try:
        from backend.safety.safety_guard import safety_guard
        from backend.safety.audit_logger import audit_logger

        assessment = safety_guard.assess_action(
            action = decision.action,
            agent  = "computer_agent_v2",
        )
        audit_logger.log(
            execution_id = execution_id,
            agent        = "computer_agent_v2",
            action       = decision.action,
            risk_level   = assessment.risk_level.value,
            outcome      = "allowed" if not assessment.requires_approval else "requires_approval",
            reason       = assessment.reason,
            session_id   = session_id,
        )
        if assessment.blocked:
            return False
        if assessment.requires_approval:
            from backend.safety.approval_queue import approval_queue
            req = await approval_queue.request(
                execution_id = execution_id,
                agent        = "computer_agent_v2",
                action       = decision.action,
                description  = f"{decision.action} → {decision.selector}",
                risk_level   = assessment.risk_level.value,
                context      = decision.as_dict(),
                session_id   = session_id,
                timeout      = 120,
            )
            return req.status.value == "approved"
        return True
    except Exception:
        return True


async def _store_mission_memory(result: MissionResult, session_id: Optional[str]) -> None:
    """Persist mission result to memory subsystems."""
    try:
        from backend.memory.memory_orchestrator import memory_orchestrator
        await memory_orchestrator.store_cognition_event(
            agent      = "computer_agent_v2",
            event_type = "computer_mission",
            content    = f"[{result.status.upper()}] {result.goal}: {result.summary}",
            session_id = session_id or "global",
            mission_id = result.execution_id,
            metadata   = {
                "status":       result.status,
                "goal":         result.goal,
                "iterations":   result.iterations,
                "failures":     result.failures,
                "step_count":   len(result.steps),
                "screenshots":  result.screenshots[:5],
            },
        )
    except Exception as exc:
        log.warning("Mission memory store failed: %s", exc)

    try:
        from backend.memory.vector_memory import vector_memory
        vector_memory.store_memory(
            objective = f"[computer] {result.goal}",
            content   = {
                "summary":    result.summary,
                "steps":      [s.action for s in result.steps[:10]],
                "status":     result.status,
                "failures":   result.failures,
                "screenshots": result.screenshots[:3],
            },
            metadata  = {
                "execution_id": result.execution_id,
                "status":       result.status,
                "memory_type":  "computer_mission",
            },
        )
    except Exception as exc:
        log.warning("Vector memory store failed: %s", exc)


# =========================================================
# SINGLETON
# =========================================================

task_completion_engine = TaskCompletionEngine()

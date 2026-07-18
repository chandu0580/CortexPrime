"""
Recovery Engine  (CortexPrime Computer Agent V2)
==================================================
When verification fails, the RecoveryEngine decides what to do:

Strategy priorities
-------------------
1. retry_action     — repeat the exact same action (transient glitch)
2. alternate_click  — find a different element matching the same description
3. escape_dialog    — press Escape if a dialog is blocking
4. scroll_and_retry — scroll the page and retry
5. replan           — ask the LLM for a completely new action plan
6. fail             — give up after max_failures

Each recovery attempt is logged so the TaskCompletionEngine can track
how many retries have been spent on a step.
"""
from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from backend.computer.screen_observer import ScreenSnapshot
from backend.computer.verification_engine import VerificationResult

log = logging.getLogger(__name__)


# =========================================================
# RECOVERY RESULT
# =========================================================

@dataclass
class RecoveryResult:
    strategy:     str
    succeeded:    bool
    reason:       str
    new_action:   Optional[Dict[str, Any]] = None

    def as_dict(self) -> Dict[str, Any]:
        return {
            "strategy":   self.strategy,
            "succeeded":  self.succeeded,
            "reason":     self.reason,
            "new_action": self.new_action,
        }


# =========================================================
# RECOVERY ENGINE
# =========================================================

class RecoveryEngine:
    """
    Decides how to recover from a failed verification or a stuck state.

    Usage
    -----
    recovery = await recovery_engine.recover(
        failed_action  = {"action": "click", "selector": "Save"},
        verification   = VerificationResult(passed=False, ...),
        snapshot       = current_snapshot,
        goal           = "save the file",
        attempt        = 2,
        max_attempts   = 3,
    )
    if recovery.new_action:
        # re-enqueue the new action
    elif not recovery.succeeded:
        # escalate to mission failure
    """

    # ----------------------------------------------------------
    # MAIN RECOVER
    # ----------------------------------------------------------

    async def recover(
        self,
        failed_action:  Dict[str, Any],
        verification:   VerificationResult,
        snapshot:       ScreenSnapshot,
        goal:           str,
        attempt:        int,
        max_attempts:   int = 3,
        execution_id:   str = "",
    ) -> RecoveryResult:
        """
        Choose and execute a recovery strategy.
        Returns a RecoveryResult; new_action (if set) should be re-queued.
        """
        if attempt >= max_attempts:
            return RecoveryResult(
                strategy  = "fail",
                succeeded = False,
                reason    = f"Max recovery attempts ({max_attempts}) exceeded",
            )

        action_name = failed_action.get("action", "")
        selector    = failed_action.get("selector", "")

        # ── Strategy 1: Dialog blocking? Escape and retry ─────
        if _dialog_detected(snapshot):
            result = await self._escape_dialog(execution_id)
            if result.succeeded:
                return result

        # ── Strategy 2: Simple retry for first attempt ────────
        if attempt == 0:
            return RecoveryResult(
                strategy  = "retry_action",
                succeeded = True,
                reason    = "Retrying the same action (first attempt)",
                new_action = failed_action,
            )

        # ── Strategy 3: Alternate element for click ───────────
        if action_name == "click" and selector:
            alt = await self._find_alternate_selector(snapshot, selector)
            if alt:
                return RecoveryResult(
                    strategy  = "alternate_click",
                    succeeded = True,
                    reason    = f"Using alternate element: '{alt}'",
                    new_action = {**failed_action, "selector": alt},
                )

        # ── Strategy 4: Scroll and retry ──────────────────────
        if attempt == 1:
            await self._scroll_down()
            return RecoveryResult(
                strategy  = "scroll_and_retry",
                succeeded = True,
                reason    = "Scrolled down and will retry",
                new_action = failed_action,
            )

        # ── Strategy 5: Replan via LLM ────────────────────────
        new_action = await self._replan(snapshot, goal, failed_action)
        if new_action:
            return RecoveryResult(
                strategy  = "replan",
                succeeded = True,
                reason    = f"Replanned: {new_action.get('reason', 'LLM suggested new action')}",
                new_action = new_action,
            )

        return RecoveryResult(
            strategy  = "fail",
            succeeded = False,
            reason    = "All recovery strategies exhausted",
        )

    # ----------------------------------------------------------
    # ESCAPE DIALOG
    # ----------------------------------------------------------

    async def _escape_dialog(self, execution_id: str) -> RecoveryResult:
        try:
            import pyautogui
            pyautogui.press("escape")
            await asyncio.sleep(0.5)
            return RecoveryResult(
                strategy  = "escape_dialog",
                succeeded = True,
                reason    = "Pressed Escape to dismiss blocking dialog",
            )
        except Exception as exc:
            return RecoveryResult(
                strategy  = "escape_dialog",
                succeeded = False,
                reason    = f"Escape failed: {exc}",
            )

    # ----------------------------------------------------------
    # ALTERNATE SELECTOR
    # ----------------------------------------------------------

    async def _find_alternate_selector(
        self,
        snapshot:  ScreenSnapshot,
        original:  str,
    ) -> Optional[str]:
        """
        Try to find an element near the original that could serve as an alternative.
        Uses simple keyword overlap on OCR elements.
        """
        original_lower = original.lower()
        candidates: List[str] = []
        for el in snapshot.elements:
            el_lower = el.text.lower()
            if el_lower == original_lower:
                continue
            # Share at least one keyword
            orig_words = set(original_lower.split())
            el_words   = set(el_lower.split())
            if orig_words & el_words:
                candidates.append(el.text)

        return candidates[0] if candidates else None

    # ----------------------------------------------------------
    # SCROLL DOWN
    # ----------------------------------------------------------

    async def _scroll_down(self) -> None:
        try:
            import pyautogui
            pyautogui.scroll(-3)
            await asyncio.sleep(0.5)
        except Exception as exc:
            log.warning("Scroll failed: %s", exc)

    # ----------------------------------------------------------
    # REPLAN VIA LLM
    # ----------------------------------------------------------

    async def _replan(
        self,
        snapshot:      ScreenSnapshot,
        goal:          str,
        failed_action: Dict[str, Any],
    ) -> Optional[Dict[str, Any]]:
        """Ask the LLM for a completely new action to achieve the goal."""
        try:
            from backend.computer.vision_reasoner import vision_reasoner

            history = [
                f"Failed: {failed_action.get('action')} → {failed_action.get('selector')} "
                f"(reason: {failed_action.get('reason', 'verification failed')})"
            ]
            decision = await vision_reasoner.decide_action(
                snapshot   = snapshot,
                goal       = goal,
                history    = history,
                use_vision = False,   # text only for replan — faster
            )
            return decision.as_dict()

        except Exception as exc:
            log.warning("Replan failed: %s", exc)
            return None


# =========================================================
# HELPERS
# =========================================================

def _dialog_detected(snapshot: ScreenSnapshot) -> bool:
    """Heuristic: detect if a modal dialog is open."""
    dialog_keywords = ["ok", "cancel", "yes", "no", "close", "dismiss", "error", "warning"]
    ocr_lower = snapshot.ocr_text.lower()
    hits = sum(1 for kw in dialog_keywords if kw in ocr_lower)
    return hits >= 2


# =========================================================
# SINGLETON
# =========================================================

recovery_engine = RecoveryEngine()

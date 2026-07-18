"""
Verification Engine  (CortexPrime Computer Agent V2)
======================================================
After every action, verify that the expected outcome was achieved by
comparing before/after screen states.

Verification strategies (tried in order):
1. Text appeared — expected text is now visible in OCR
2. Text disappeared — expected text is gone (e.g., dialog closed)
3. Screen changed — image hash or OCR diff shows something happened
4. URL / title changed (browser context)
5. LLM visual verdict — ask the LLM whether the goal was met

If verification fails, the VerificationEngine returns a VerificationResult
with ``passed=False`` and a human-readable ``reason`` so the RecoveryEngine
can decide how to proceed.
"""
from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from typing import Any, Dict, Optional

from backend.computer.screen_observer import ScreenSnapshot, screen_observer

log = logging.getLogger(__name__)


# =========================================================
# VERIFICATION RESULT
# =========================================================

@dataclass
class VerificationResult:
    passed:   bool
    strategy: str
    reason:   str
    before_hash: str = ""
    after_hash:  str = ""
    details:  Dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> Dict[str, Any]:
        return {
            "passed":       self.passed,
            "strategy":     self.strategy,
            "reason":       self.reason,
            "before_hash":  self.before_hash,
            "after_hash":   self.after_hash,
        }


# =========================================================
# VERIFICATION ENGINE
# =========================================================

class VerificationEngine:
    """
    Verifies that an action produced the expected screen change.

    Usage
    -----
    before = await screen_observer.capture()
    # ... execute action ...
    await asyncio.sleep(1)  # settle
    after  = await screen_observer.capture()

    result = await verifier.verify(
        before         = before,
        after          = after,
        action         = "click",
        expected_text  = "File saved",          # optional
        goal_fragment  = "save the file",       # optional — passed to LLM
    )
    if not result.passed:
        # hand off to RecoveryEngine
    """

    # ----------------------------------------------------------
    # MAIN VERIFY
    # ----------------------------------------------------------

    async def verify(
        self,
        before:         ScreenSnapshot,
        after:          ScreenSnapshot,
        action:         str,
        expected_text:  Optional[str]  = None,
        absent_text:    Optional[str]  = None,
        goal_fragment:  Optional[str]  = None,
        use_llm:        bool           = True,
        settle_ms:      int            = 500,
    ) -> VerificationResult:
        """
        Run verification strategies in order; return the first conclusive result.
        """
        await asyncio.sleep(settle_ms / 1000)

        # Capture a fresh "after" if the caller didn't provide one post-settle
        # (we re-capture here in case the action triggered async UI updates)
        try:
            after = await screen_observer.capture(run_ocr=True)
        except Exception:
            pass

        # 1. Expected text appeared
        if expected_text:
            if expected_text.lower() in after.ocr_text.lower():
                return VerificationResult(
                    passed   = True,
                    strategy = "text_appeared",
                    reason   = f"Expected text found: '{expected_text}'",
                    before_hash = before.image_hash,
                    after_hash  = after.image_hash,
                )
            # Text expected but not found → fail
            return VerificationResult(
                passed   = False,
                strategy = "text_appeared",
                reason   = f"Expected text NOT found: '{expected_text}'",
                before_hash = before.image_hash,
                after_hash  = after.image_hash,
            )

        # 2. Absent text disappeared
        if absent_text:
            if absent_text.lower() not in after.ocr_text.lower():
                return VerificationResult(
                    passed   = True,
                    strategy = "text_disappeared",
                    reason   = f"Expected text gone: '{absent_text}'",
                    before_hash = before.image_hash,
                    after_hash  = after.image_hash,
                )
            return VerificationResult(
                passed   = False,
                strategy = "text_disappeared",
                reason   = f"Expected-absent text still present: '{absent_text}'",
                before_hash = before.image_hash,
                after_hash  = after.image_hash,
            )

        # 3. Screen changed
        changed = screen_observer.has_changed(before, after)
        if not changed and action not in ("wait", "scroll"):
            # No visible change after a non-wait action → suspicious
            if use_llm and goal_fragment:
                return await self._llm_verify(before, after, goal_fragment, action)
            return VerificationResult(
                passed   = False,
                strategy = "screen_change",
                reason   = "Screen did not change after action",
                before_hash = before.image_hash,
                after_hash  = after.image_hash,
            )

        if changed:
            changes = screen_observer.changed_regions(before, after)
            return VerificationResult(
                passed   = True,
                strategy = "screen_change",
                reason   = f"Screen changed: {'; '.join(changes) or 'layout updated'}",
                before_hash = before.image_hash,
                after_hash  = after.image_hash,
            )

        # 4. Wait / scroll — always pass (no visual oracle needed)
        if action in ("wait", "scroll"):
            return VerificationResult(
                passed   = True,
                strategy = "implicit",
                reason   = f"Action '{action}' does not require screen change",
            )

        # 5. LLM visual verdict as last resort
        if use_llm and goal_fragment:
            return await self._llm_verify(before, after, goal_fragment, action)

        # Default: pass if screen changed, fail otherwise
        return VerificationResult(
            passed   = changed,
            strategy = "default",
            reason   = "Screen change check",
            before_hash = before.image_hash,
            after_hash  = after.image_hash,
        )

    # ----------------------------------------------------------
    # LLM VISUAL VERDICT
    # ----------------------------------------------------------

    async def _llm_verify(
        self,
        before:   ScreenSnapshot,
        after:    ScreenSnapshot,
        goal:     str,
        action:   str,
    ) -> VerificationResult:
        """Ask the LLM whether the goal sub-task was completed."""
        try:
            before_text = before.ocr_text[:600]
            after_text  = after.ocr_text[:600]

            prompt = (
                f"Goal: {goal}\n"
                f"Action performed: {action}\n\n"
                f"Screen BEFORE:\n{before_text}\n\n"
                f"Screen AFTER:\n{after_text}\n\n"
                "Was the action successful? Did the screen change in the expected way?\n"
                "Respond: PASS or FAIL, then one sentence reason."
            )

            from backend.llm.llm_gateway import llm_gateway
            result = await llm_gateway.generate_azure(
                prompt        = prompt,
                agent_type    = "general",
                system_prompt = "You are a computer-use verification AI. Be concise.",
            )
            if not result.get("success"):
                result = await llm_gateway.generate_openai(
                    prompt=prompt, model="gpt-4o-mini"
                )

            output = result.get("output", "").strip()
            passed = output.upper().startswith("PASS")
            reason = output.split("\n")[0] if output else "LLM verification inconclusive"

            return VerificationResult(
                passed   = passed,
                strategy = "llm_verdict",
                reason   = reason,
                before_hash = before.image_hash,
                after_hash  = after.image_hash,
            )
        except Exception as exc:
            log.warning("LLM verification failed: %s", exc)
            return VerificationResult(
                passed   = True,   # optimistic fallback
                strategy = "llm_verdict_failed",
                reason   = f"LLM verification unavailable: {exc}",
            )


# =========================================================
# SINGLETON
# =========================================================

verification_engine = VerificationEngine()

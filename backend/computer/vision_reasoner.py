"""
Vision Reasoner  (CortexPrime Computer Agent V2)
==================================================
Applies LLM-powered reasoning to a ScreenSnapshot to:
- Describe what is on screen
- Detect UI state (buttons, inputs, menus, dialogs, errors)
- Decide what the next action should be given a goal
- Find the best click target for a natural-language description

Uses OpenAI vision if an image is available; falls back to OCR text only.
"""
from __future__ import annotations

import base64
import logging
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from backend.computer.screen_observer import ScreenSnapshot, UIElement

log = logging.getLogger(__name__)


# =========================================================
# ANALYSIS RESULT
# =========================================================

@dataclass
class ScreenAnalysis:
    description:  str
    state:        str           # idle | loading | error | dialog | form | menu | success
    buttons:      List[str]
    inputs:       List[str]
    menus:        List[str]
    dialogs:      List[str]
    errors:       List[str]
    suggested_action: str       # natural-language next step
    raw_llm_output:   str       = ""

    def as_dict(self) -> Dict[str, Any]:
        return {
            "description":       self.description,
            "state":             self.state,
            "buttons":           self.buttons,
            "inputs":            self.inputs,
            "menus":             self.menus,
            "dialogs":           self.dialogs,
            "errors":            self.errors,
            "suggested_action":  self.suggested_action,
        }


@dataclass
class ActionDecision:
    action:      str           # click | type | hotkey | scroll | wait | complete | fail
    selector:    str           # text label or coordinates "x,y"
    value:       str           = ""
    keys:        List[str]     = None   # type: ignore[assignment]
    reason:      str           = ""
    confidence:  float         = 0.8

    def as_dict(self) -> Dict[str, Any]:
        return {
            "action":     self.action,
            "selector":   self.selector,
            "value":      self.value,
            "keys":       self.keys or [],
            "reason":     self.reason,
            "confidence": self.confidence,
        }


# =========================================================
# PROMPTS
# =========================================================

_ANALYZE_SYSTEM = """You are a computer vision AI analyzing a desktop screenshot.
Describe what you see concisely. Identify the current UI state and notable elements.
Respond in JSON with keys: description, state, buttons (list), inputs (list), menus (list), dialogs (list), errors (list), suggested_action.
State must be one of: idle, loading, error, dialog, form, menu, success."""

_DECIDE_SYSTEM = """You are an autonomous computer-use AI.
Given the current screen state and the goal, decide the single best next action.
Respond ONLY in JSON with keys: action, selector, value, keys (list), reason, confidence.
action must be one of: click, type, hotkey, scroll, wait, complete, fail.
- click: selector is the visible text of the element to click (or "x,y" coordinates).
- type: selector is the target field text; value is the text to type.
- hotkey: keys is a list of key names (e.g. ["ctrl","s"]).
- scroll: selector is direction ("up" or "down"); value is number of clicks.
- wait: value is seconds to wait as a string.
- complete: goal has been achieved.
- fail: goal cannot be achieved with the current screen."""

_FIND_ELEMENT_SYSTEM = """You are a UI element locator.
Given OCR-detected elements and a target description, identify the best matching element.
Return JSON: {index: <int>, text: <str>, confidence: <float 0-1>, reason: <str>}
If no match, return {index: -1, text: "", confidence: 0, reason: "not found"}."""


# =========================================================
# VISION REASONER
# =========================================================

class VisionReasoner:
    """
    LLM-powered screen analysis and action decision making.
    Supports both text-only (OCR) and vision (image+text) modes.
    """

    # ----------------------------------------------------------
    # ANALYZE SCREEN
    # ----------------------------------------------------------

    async def analyze(
        self,
        snapshot:      ScreenSnapshot,
        use_vision:    bool = True,
    ) -> ScreenAnalysis:
        """
        Analyze a snapshot and return a structured ScreenAnalysis.
        Tries GPT-4 vision if use_vision=True and image exists; falls back to text.
        """
        ocr_summary = _summarize_ocr(snapshot)

        if use_vision and Path(snapshot.image_path).exists():
            try:
                llm_out = await self._vision_analyze(snapshot.image_path, ocr_summary)
                analysis = _parse_analysis(llm_out)
                analysis.raw_llm_output = llm_out
                return analysis
            except Exception as exc:
                log.warning("Vision analysis failed: %s — falling back to text", exc)

        # Text-only fallback
        return await self._text_analyze(ocr_summary)

    # ----------------------------------------------------------
    # DECIDE NEXT ACTION
    # ----------------------------------------------------------

    async def decide_action(
        self,
        snapshot:      ScreenSnapshot,
        goal:          str,
        history:       List[str],
        use_vision:    bool = True,
    ) -> ActionDecision:
        """
        Given the current screen and goal, return the next best action to take.
        """
        ocr_summary  = _summarize_ocr(snapshot)
        history_text = "\n".join(f"- {h}" for h in history[-6:]) or "None"

        prompt = (
            f"Goal: {goal}\n\n"
            f"Actions taken so far:\n{history_text}\n\n"
            f"Current screen OCR text (truncated):\n{ocr_summary[:1200]}\n\n"
            f"Detected UI elements:\n"
            + "\n".join(
                f"  [{i}] '{el.text}' at ({el.center()[0]},{el.center()[1]})"
                for i, el in enumerate(snapshot.elements[:30])
            )
        )

        if use_vision and Path(snapshot.image_path).exists():
            try:
                raw = await self._vision_decide(snapshot.image_path, prompt)
                decision = _parse_decision(raw)
                decision.reason = decision.reason or "Vision-guided decision"
                return decision
            except Exception as exc:
                log.warning("Vision decision failed: %s — falling back to text", exc)

        return await self._text_decide(prompt)

    # ----------------------------------------------------------
    # FIND ELEMENT BY DESCRIPTION
    # ----------------------------------------------------------

    async def find_element(
        self,
        snapshot: ScreenSnapshot,
        target:   str,
    ) -> Tuple[Optional[UIElement], float]:
        """
        Find the UI element that best matches the natural-language target description.
        Returns (element, confidence) or (None, 0.0).
        """
        # Fast path: exact text match
        el = _exact_match(snapshot.elements, target)
        if el:
            return el, 1.0

        # Fuzzy match
        el = _fuzzy_match(snapshot.elements, target)
        if el:
            return el, 0.75

        # LLM match
        if not snapshot.elements:
            return None, 0.0

        elements_text = "\n".join(
            f"[{i}] text='{el.text}' center=({el.center()[0]},{el.center()[1]})"
            for i, el in enumerate(snapshot.elements[:40])
        )
        prompt = f"Target: {target}\n\nAvailable elements:\n{elements_text}"
        try:
            raw = await _llm_call_text(_FIND_ELEMENT_SYSTEM, prompt)
            parsed = _safe_json(raw)
            idx = parsed.get("index", -1)
            conf = float(parsed.get("confidence", 0))
            if 0 <= idx < len(snapshot.elements) and conf > 0.4:
                return snapshot.elements[idx], conf
        except Exception as exc:
            log.warning("LLM element find failed: %s", exc)

        return None, 0.0

    # ----------------------------------------------------------
    # VISION LLM CALLS
    # ----------------------------------------------------------

    async def _vision_analyze(self, image_path: str, ocr_hint: str) -> str:
        from backend.providers.openai_provider import openai_provider
        b64 = _encode_image(image_path)
        resp = await openai_provider.client.chat.completions.create(
            model    = openai_provider.deployment_name,
            messages = [
                {"role": "system", "content": _ANALYZE_SYSTEM},
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image_url",
                            "image_url": {"url": f"data:image/png;base64,{b64}"},
                        },
                        {
                            "type": "text",
                            "text": f"OCR hint:\n{ocr_hint[:600]}",
                        },
                    ],
                },
            ],
            timeout  = 30,
        )
        return resp.choices[0].message.content or ""

    async def _vision_decide(self, image_path: str, prompt: str) -> str:
        from backend.providers.openai_provider import openai_provider
        b64 = _encode_image(image_path)
        resp = await openai_provider.client.chat.completions.create(
            model    = openai_provider.deployment_name,
            messages = [
                {"role": "system", "content": _DECIDE_SYSTEM},
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image_url",
                            "image_url": {"url": f"data:image/png;base64,{b64}"},
                        },
                        {"type": "text", "text": prompt},
                    ],
                },
            ],
            timeout  = 30,
        )
        return resp.choices[0].message.content or ""

    # ----------------------------------------------------------
    # TEXT-ONLY LLM CALLS
    # ----------------------------------------------------------

    async def _text_analyze(self, ocr_text: str) -> ScreenAnalysis:
        raw = await _llm_call_text(
            _ANALYZE_SYSTEM,
            f"Screen text (OCR):\n{ocr_text[:1500]}",
        )
        analysis = _parse_analysis(raw)
        analysis.raw_llm_output = raw
        return analysis

    async def _text_decide(self, prompt: str) -> ActionDecision:
        raw = await _llm_call_text(_DECIDE_SYSTEM, prompt)
        return _parse_decision(raw)


# =========================================================
# HELPERS
# =========================================================

async def _llm_call_text(system: str, prompt: str) -> str:
    try:
        from backend.llm.llm_gateway import llm_gateway
        result = await llm_gateway.generate_azure(
            prompt        = prompt,
            agent_type    = "general",
            system_prompt = system,
        )
        if result.get("success") and result.get("output"):
            return result["output"]
        result2 = await llm_gateway.generate_openai(prompt=prompt, model="gpt-4o-mini")
        return result2.get("output", "")
    except Exception as exc:
        log.warning("LLM text call failed: %s", exc)
        return ""


def _encode_image(path: str) -> str:
    with open(path, "rb") as f:
        return base64.b64encode(f.read()).decode("utf-8")


def _summarize_ocr(snapshot: ScreenSnapshot) -> str:
    """Compact OCR summary for prompt injection."""
    text = snapshot.ocr_text.strip()
    if not text and snapshot.elements:
        text = " | ".join(el.text for el in snapshot.elements[:50])
    return text[:1500]


def _safe_json(raw: str) -> Dict[str, Any]:
    """Extract JSON from a raw LLM response."""
    import json
    # Try code fence first
    m = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", raw, re.DOTALL)
    if m:
        try:
            return json.loads(m.group(1))
        except Exception:
            pass
    # Try bare JSON
    m2 = re.search(r"\{.*\}", raw, re.DOTALL)
    if m2:
        try:
            return json.loads(m2.group(0))
        except Exception:
            pass
    return {}


def _parse_analysis(raw: str) -> ScreenAnalysis:
    d = _safe_json(raw)
    return ScreenAnalysis(
        description      = d.get("description", ""),
        state            = d.get("state", "idle"),
        buttons          = d.get("buttons", []),
        inputs           = d.get("inputs", []),
        menus            = d.get("menus", []),
        dialogs          = d.get("dialogs", []),
        errors           = d.get("errors", []),
        suggested_action = d.get("suggested_action", ""),
    )


def _parse_decision(raw: str) -> ActionDecision:
    d = _safe_json(raw)
    return ActionDecision(
        action     = d.get("action", "wait"),
        selector   = str(d.get("selector", "")),
        value      = str(d.get("value", "")),
        keys       = d.get("keys", []),
        reason     = d.get("reason", ""),
        confidence = float(d.get("confidence", 0.5)),
    )


def _exact_match(elements: List[UIElement], target: str) -> Optional[UIElement]:
    t = target.lower()
    for el in elements:
        if el.text.lower() == t:
            return el
    return None


def _fuzzy_match(elements: List[UIElement], target: str) -> Optional[UIElement]:
    t = target.lower()
    best: Optional[UIElement] = None
    best_score = 0
    for el in elements:
        et = el.text.lower()
        if t in et or et in t:
            score = len(set(t.split()) & set(et.split()))
            if score > best_score:
                best_score = score
                best = el
    return best


# =========================================================
# SINGLETON
# =========================================================

vision_reasoner = VisionReasoner()

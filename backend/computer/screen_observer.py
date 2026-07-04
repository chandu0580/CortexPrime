"""
Screen Observer  (CortexPrime Computer Agent V2)
==================================================
Handles all screen capture duties:
- full screen capture (all monitors)
- active window capture
- multi-monitor enumeration
- UI state snapshot (text + bounding boxes from OCR)
- image diff (detect what changed between two captures)

All captures are saved to generated_screens/ and the path is returned
so downstream layers (VisionReasoner, VerificationEngine) can read it.
"""
from __future__ import annotations

import asyncio
import hashlib
import logging
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from uuid import uuid4

log = logging.getLogger(__name__)

_SCREEN_DIR = Path("generated_screens")
_SCREEN_DIR.mkdir(exist_ok=True)


# =========================================================
# DATA CLASSES
# =========================================================

@dataclass
class UIElement:
    text:       str
    x:          int
    y:          int
    width:      int
    height:     int
    confidence: float

    def center(self) -> Tuple[int, int]:
        return self.x + self.width // 2, self.y + self.height // 2

    def as_dict(self) -> Dict[str, Any]:
        return {
            "text":       self.text,
            "x":          self.x,
            "y":          self.y,
            "width":      self.width,
            "height":     self.height,
            "confidence": self.confidence,
            "center_x":   self.center()[0],
            "center_y":   self.center()[1],
        }


@dataclass
class ScreenSnapshot:
    snapshot_id:  str
    image_path:   str
    width:        int
    height:       int
    monitor:      int
    timestamp:    str
    ocr_text:     str               = ""
    elements:     List[UIElement]   = field(default_factory=list)
    image_hash:   str               = ""

    def as_dict(self) -> Dict[str, Any]:
        return {
            "snapshot_id":  self.snapshot_id,
            "image_path":   self.image_path,
            "width":        self.width,
            "height":       self.height,
            "monitor":      self.monitor,
            "timestamp":    self.timestamp,
            "ocr_text":     self.ocr_text[:500],
            "element_count": len(self.elements),
            "image_hash":   self.image_hash,
        }


# =========================================================
# SCREEN OBSERVER
# =========================================================

class ScreenObserver:
    """
    Captures the screen and extracts a rich UI state.
    Uses mss for screen capture and pytesseract for OCR.
    Both are imported lazily so the module can be imported even
    when pyautogui / mss / tesseract are not installed.
    """

    def __init__(self) -> None:
        self._last_snapshot: Optional[ScreenSnapshot] = None

    # ----------------------------------------------------------
    # CAPTURE FULL SCREEN
    # ----------------------------------------------------------

    async def capture(
        self,
        monitor:     int  = 1,
        run_ocr:     bool = True,
        detect_ui:   bool = True,
    ) -> ScreenSnapshot:
        """
        Capture the specified monitor and return a ScreenSnapshot.
        monitor=0 captures ALL monitors merged; monitor=1..N captures one.
        """
        snapshot_id = str(uuid4())

        try:
            import mss
            import mss.tools

            with mss.mss() as sct:
                monitors = sct.monitors
                idx      = monitor if monitor < len(monitors) else 1
                mon_rect = monitors[idx]

                raw = sct.grab(mon_rect)
                path = _SCREEN_DIR / f"{snapshot_id}.png"
                mss.tools.to_png(raw.rgb, raw.size, output=str(path))

                w, h = raw.size

        except Exception as exc:
            log.warning("mss capture failed: %s — creating blank snapshot", exc)
            path = _SCREEN_DIR / f"{snapshot_id}.png"
            w, h = 1920, 1080
            # Create a minimal valid PNG
            try:
                from PIL import Image
                Image.new("RGB", (w, h), (30, 30, 30)).save(str(path))
            except Exception:
                pass

        img_hash  = _file_hash(str(path))
        ocr_text  = ""
        elements: List[UIElement] = []

        if run_ocr or detect_ui:
            ocr_text, elements = await self._run_ocr(str(path), detect_boxes=detect_ui)

        snapshot = ScreenSnapshot(
            snapshot_id = snapshot_id,
            image_path  = str(path),
            width       = w,
            height      = h,
            monitor     = monitor,
            timestamp   = datetime.utcnow().isoformat(),
            ocr_text    = ocr_text,
            elements    = elements,
            image_hash  = img_hash,
        )
        self._last_snapshot = snapshot

        await self._emit(
            snapshot_id,
            "screen_captured", "completed", "screen_observation",
            f"Screen captured: {w}x{h} | {len(elements)} UI elements",
            {"image_path": str(path), "monitor": monitor},
        )

        return snapshot

    # ----------------------------------------------------------
    # CAPTURE ACTIVE WINDOW
    # ----------------------------------------------------------

    async def capture_active_window(self) -> ScreenSnapshot:
        """Capture only the currently focused window."""
        try:
            import pygetwindow as gw
            win = gw.getActiveWindow()
            if win and win.width > 0 and win.height > 0:
                import mss
                import mss.tools
                snapshot_id = str(uuid4())
                rect = {
                    "left":   win.left,
                    "top":    win.top,
                    "width":  win.width,
                    "height": win.height,
                }
                with mss.mss() as sct:
                    raw  = sct.grab(rect)
                    path = _SCREEN_DIR / f"{snapshot_id}.png"
                    mss.tools.to_png(raw.rgb, raw.size, output=str(path))
                    w, h = raw.size

                img_hash             = _file_hash(str(path))
                ocr_text, elements   = await self._run_ocr(str(path), detect_boxes=True)

                snapshot = ScreenSnapshot(
                    snapshot_id = snapshot_id,
                    image_path  = str(path),
                    width       = w,
                    height      = h,
                    monitor     = 0,
                    timestamp   = datetime.utcnow().isoformat(),
                    ocr_text    = ocr_text,
                    elements    = elements,
                    image_hash  = img_hash,
                )
                self._last_snapshot = snapshot
                return snapshot

        except Exception as exc:
            log.warning("Active window capture failed: %s — falling back to full screen", exc)

        return await self.capture(monitor=1)

    # ----------------------------------------------------------
    # LIST MONITORS
    # ----------------------------------------------------------

    async def list_monitors(self) -> List[Dict[str, Any]]:
        try:
            import mss
            with mss.mss() as sct:
                return [
                    {
                        "index":  i,
                        "width":  m["width"],
                        "height": m["height"],
                        "left":   m["left"],
                        "top":    m["top"],
                    }
                    for i, m in enumerate(sct.monitors)
                ]
        except Exception as exc:
            log.warning("list_monitors failed: %s", exc)
            return [{"index": 1, "width": 1920, "height": 1080, "left": 0, "top": 0}]

    # ----------------------------------------------------------
    # SNAPSHOT DIFF  (detect changes)
    # ----------------------------------------------------------

    def has_changed(
        self,
        before: ScreenSnapshot,
        after:  ScreenSnapshot,
    ) -> bool:
        """Return True if the two snapshots differ (by hash or OCR)."""
        if before.image_hash and after.image_hash:
            return before.image_hash != after.image_hash
        return before.ocr_text.strip() != after.ocr_text.strip()

    def changed_regions(
        self,
        before: ScreenSnapshot,
        after:  ScreenSnapshot,
    ) -> List[str]:
        """Return a list of text tokens that appeared or disappeared."""
        before_tokens = set(before.ocr_text.split())
        after_tokens  = set(after.ocr_text.split())
        added   = after_tokens  - before_tokens
        removed = before_tokens - after_tokens
        out: List[str] = []
        if added:
            out.append(f"appeared: {', '.join(list(added)[:10])}")
        if removed:
            out.append(f"disappeared: {', '.join(list(removed)[:10])}")
        return out

    # ----------------------------------------------------------
    # FIND ELEMENT IN SNAPSHOT
    # ----------------------------------------------------------

    def find_element(
        self,
        snapshot: ScreenSnapshot,
        text:     str,
        min_confidence: float = 40.0,
    ) -> Optional[UIElement]:
        """Find a UI element whose text contains the given string."""
        text_lower = text.lower()
        for el in snapshot.elements:
            if el.confidence >= min_confidence and text_lower in el.text.lower():
                return el
        return None

    @property
    def last_snapshot(self) -> Optional[ScreenSnapshot]:
        return self._last_snapshot

    # ----------------------------------------------------------
    # OCR HELPER
    # ----------------------------------------------------------

    async def _run_ocr(
        self,
        image_path:   str,
        detect_boxes: bool = True,
    ) -> Tuple[str, List[UIElement]]:
        """Run pytesseract OCR; returns (full_text, [UIElement...])."""
        try:
            import pytesseract
            from PIL import Image

            pytesseract.pytesseract.tesseract_cmd = (
                r"C:\Program Files\Tesseract-OCR\tesseract.exe"
            )

            img  = Image.open(image_path)
            text = pytesseract.image_to_string(img)

            elements: List[UIElement] = []
            if detect_boxes:
                data = pytesseract.image_to_data(
                    img, output_type=pytesseract.Output.DICT
                )
                for i in range(len(data["text"])):
                    t    = data["text"][i].strip()
                    conf = float(data["conf"][i])
                    if t and conf > 30:
                        elements.append(UIElement(
                            text       = t,
                            x          = data["left"][i],
                            y          = data["top"][i],
                            width      = data["width"][i],
                            height     = data["height"][i],
                            confidence = conf,
                        ))

            return text, elements

        except Exception as exc:
            log.warning("OCR failed: %s", exc)
            return "", []

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
    ) -> None:
        try:
            from backend.events.event_bus    import event_bus
            from backend.events.event_models import CognitionEvent
            await event_bus.publish(CognitionEvent(
                agent        = "screen_observer",
                event_type   = event_type,
                status       = status,
                phase        = phase,
                execution_id = execution_id,
                message      = message,
                payload      = payload or {},
            ))
        except Exception:
            pass


# =========================================================
# UTILITY
# =========================================================

def _file_hash(path: str) -> str:
    try:
        with open(path, "rb") as f:
            return hashlib.md5(f.read()).hexdigest()
    except Exception:
        return ""


# =========================================================
# SINGLETON
# =========================================================

screen_observer = ScreenObserver()

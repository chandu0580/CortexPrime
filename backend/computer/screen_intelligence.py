from typing import Dict, Any
from uuid import uuid4
from datetime import datetime
from pathlib import Path
import asyncio

import mss
import mss.tools
from PIL import Image
import pytesseract

from backend.events.event_bus import (
    event_bus
)

from backend.events.event_models import (
    CognitionEvent
)

from backend.tools.tool_registry import (
    tool_registry
)


# ==========================================
# TESSERACT PATH
# ==========================================

pytesseract.pytesseract.tesseract_cmd = (
    r"C:\Program Files\Tesseract-OCR\tesseract.exe"
)


# ==========================================
# SCREEN INTELLIGENCE
# ==========================================

class ScreenIntelligence:

    def __init__(self):

        # ==========================================
        # SCREENSHOT DIRECTORY
        # ==========================================

        self.screenshot_dir = Path(
            "generated_screens"
        )

        self.screenshot_dir.mkdir(
            exist_ok=True
        )


    # ==========================================
    # EVENT HELPER
    # ==========================================

    async def publish_event(

        self,

        execution_id: str,

        event_type: str,

        status: str,

        phase: str,

        message: str,

        payload: Dict[str, Any] = {}
    ):

        await event_bus.publish(

            CognitionEvent(

                agent=
                    "screen_intelligence",

                event_type=
                    event_type,

                status=
                    status,

                phase=
                    phase,

                execution_id=
                    execution_id,

                message=
                    message,

                payload=
                    payload
            )
        )


    # ==========================================
    # CAPTURE SCREENSHOT
    # ==========================================

    async def capture_screen(

        self,

        payload: Dict[str, Any]

    ) -> Dict[str, Any]:

        execution_id = str(
            uuid4()
        )

        monitor_index = payload.get(
            "monitor",
            1
        )

        await self.publish_event(

            execution_id,

            "screen_capture_started",

            "running",

            "screen_capture",

            "Capturing desktop screenshot"
        )

        try:

            with mss.mss() as sct:

                monitor = (
                    sct.monitors[
                        monitor_index
                    ]
                )

                screenshot = (
                    sct.grab(monitor)
                )

                output_path = (

                    self.screenshot_dir /

                    f"{execution_id}.png"
                )

                mss.tools.to_png(

                    screenshot.rgb,

                    screenshot.size,

                    output=
                        str(output_path)
                )

            await asyncio.sleep(0.5)

            await self.publish_event(

                execution_id,

                "screen_capture_completed",

                "completed",

                "screen_capture",

                "Desktop screenshot captured",

                {

                    "image_path":
                        str(output_path)
                }
            )

            return {

                "success": True,

                "image_path":
                    str(output_path),

                "timestamp":
                    datetime.utcnow()
                    .isoformat()
            }

        except Exception as error:

            await self.publish_event(

                execution_id,

                "screen_capture_failed",

                "failed",

                "screen_capture",

                "Screen capture failed",

                {

                    "error":
                        str(error)
                }
            )

            return {

                "success": False,

                "error":
                    str(error)
            }


    # ==========================================
    # SCREEN OCR
    # ==========================================

    async def extract_screen_text(

        self,

        payload: Dict[str, Any]

    ) -> Dict[str, Any]:

        execution_id = str(
            uuid4()
        )

        capture_result = (

            await self.capture_screen({})
        )

        if not capture_result.get(
            "success"
        ):

            return capture_result

        image_path = (

            capture_result[
                "image_path"
            ]
        )

        await self.publish_event(

            execution_id,

            "screen_ocr_started",

            "running",

            "screen_ocr",

            "Performing OCR on screenshot"
        )

        try:

            image = Image.open(
                image_path
            )

            extracted_text = (

                pytesseract
                .image_to_string(
                    image
                )
            )

            await asyncio.sleep(0.5)

            await self.publish_event(

                execution_id,

                "screen_ocr_completed",

                "completed",

                "screen_ocr",

                "Screen OCR completed",

                {

                    "text_length":
                        len(extracted_text)
                }
            )

            return {

                "success": True,

                "image_path":
                    image_path,

                "extracted_text":
                    extracted_text,

                "text_length":
                    len(extracted_text)
            }

        except Exception as error:

            await self.publish_event(

                execution_id,

                "screen_ocr_failed",

                "failed",

                "screen_ocr",

                "Screen OCR failed",

                {

                    "error":
                        str(error)
                }
            )

            return {

                "success": False,

                "error":
                    str(error)
            }


    # ==========================================
    # GET MONITOR INFO
    # ==========================================

    async def get_monitors(

        self

    ) -> Dict[str, Any]:

        monitors = []

        with mss.mss() as sct:

            for index, monitor in enumerate(

                sct.monitors
            ):

                monitors.append({

                    "index":
                        index,

                    "width":
                        monitor["width"],

                    "height":
                        monitor["height"],

                    "left":
                        monitor["left"],

                    "top":
                        monitor["top"]
                })

        return {

            "success": True,

            "monitors":
                monitors
        }


    # ==========================================
    # CONTINUOUS SCREEN WATCH
    # ==========================================

    async def continuous_screen_watch(

        self,

        payload: Dict[str, Any]

    ) -> Dict[str, Any]:

        execution_id = str(
            uuid4()
        )

        cycles = payload.get(
            "cycles",
            3
        )

        interval = payload.get(
            "interval",
            5
        )

        captures = []

        await self.publish_event(

            execution_id,

            "continuous_screen_watch_started",

            "running",

            "screen_monitoring",

            "Continuous screen watch started",

            {

                "cycles":
                    cycles
            }
        )

        for _ in range(cycles):

            result = (

                await self.capture_screen({})
            )

            if result.get(
                "success"
            ):

                captures.append(

                    result[
                        "image_path"
                    ]
                )

            await asyncio.sleep(
                interval
            )

        await self.publish_event(

            execution_id,

            "continuous_screen_watch_completed",

            "completed",

            "screen_monitoring",

            "Continuous screen monitoring completed",

            {

                "captures":
                    len(captures)
            }
        )

        return {

            "success": True,

            "captures":
                captures
        }


# ==========================================
# SINGLETON
# ==========================================

screen_intelligence = (
    ScreenIntelligence()
)


# ==========================================
# REGISTER TOOLS
# ==========================================

tool_registry.register_tool(

    name="screen_capture",

    description=
        "Capture desktop screenshot",

    handler=
        screen_intelligence.capture_screen,

    tool_type=
        "computer"
)

tool_registry.register_tool(

    name="screen_extract_text",

    description=
        "OCR from desktop screenshot",

    handler=
        screen_intelligence.extract_screen_text,

    tool_type=
        "computer"
)

tool_registry.register_tool(

    name="screen_get_monitors",

    description=
        "Get monitor information",

    handler=
        screen_intelligence.get_monitors,

    tool_type=
        "computer"
)

tool_registry.register_tool(

    name="screen_watch",

    description=
        "Continuous screen monitoring",

    handler=
        screen_intelligence.continuous_screen_watch,

    tool_type=
        "computer"
)
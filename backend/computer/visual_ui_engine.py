from typing import Dict, Any, List
from uuid import uuid4
from pathlib import Path
import asyncio

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

from backend.computer.screen_intelligence import (
    screen_intelligence
)

from backend.computer.desktop_controller import (
    desktop_controller
)


# ==========================================
# TESSERACT CONFIG
# ==========================================

pytesseract.pytesseract.tesseract_cmd = (
    r"C:\Program Files\Tesseract-OCR\tesseract.exe"
)


# ==========================================
# VISUAL UI ENGINE
# ==========================================

class VisualUIEngine:

    def __init__(self):

        pass


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
                    "visual_ui_engine",

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
    # DETECT UI TEXT
    # ==========================================

    async def detect_ui_elements(

        self,

        payload: Dict[str, Any]

    ) -> Dict[str, Any]:

        execution_id = str(
            uuid4()
        )

        await self.publish_event(

            execution_id,

            "ui_detection_started",

            "running",

            "visual_reasoning",

            "Detecting visual UI elements"
        )

        # ==========================================
        # CAPTURE SCREEN
        # ==========================================

        capture_result = await (

            screen_intelligence
            .capture_screen({})
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

        try:

            image = Image.open(
                image_path
            )

            # ======================================
            # OCR DATA
            # ======================================

            data = (

                pytesseract
                .image_to_data(

                    image,

                    output_type=
                        pytesseract.Output.DICT
                )
            )

            detected_elements = []

            total_items = len(
                data["text"]
            )

            for index in range(
                total_items
            ):

                text = (
                    data["text"][index]
                    .strip()
                )

                confidence = int(

                    data["conf"][index]
                )

                if (

                    text

                    and

                    confidence > 40
                ):

                    x = data["left"][index]
                    y = data["top"][index]
                    width = data["width"][index]
                    height = data["height"][index]

                    detected_elements.append({

                        "text":
                            text,

                        "confidence":
                            confidence,

                        "x":
                            x,

                        "y":
                            y,

                        "width":
                            width,

                        "height":
                            height,

                        "center_x":
                            x + width // 2,

                        "center_y":
                            y + height // 2
                    })

            await asyncio.sleep(0.5)

            await self.publish_event(

                execution_id,

                "ui_detection_completed",

                "completed",

                "visual_reasoning",

                "UI element detection completed",

                {

                    "elements":
                        len(detected_elements)
                }
            )

            return {

                "success": True,

                "image_path":
                    image_path,

                "elements":
                    detected_elements,

                "count":
                    len(detected_elements)
            }

        except Exception as error:

            await self.publish_event(

                execution_id,

                "ui_detection_failed",

                "failed",

                "visual_reasoning",

                "UI detection failed",

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
    # FIND ELEMENT BY TEXT
    # ==========================================

    async def find_element_by_text(

        self,

        payload: Dict[str, Any]

    ) -> Dict[str, Any]:

        execution_id = str(
            uuid4()
        )

        target_text = payload.get(
            "text"
        )

        if not target_text:

            return {

                "success": False,

                "error":
                    "Missing target text"
            }

        detection_result = await (

            self.detect_ui_elements({})
        )

        if not detection_result.get(
            "success"
        ):

            return detection_result

        elements = detection_result[
            "elements"
        ]

        for element in elements:

            if (

                target_text.lower()

                in

                element[
                    "text"
                ].lower()
            ):

                await self.publish_event(

                    execution_id,

                    "ui_element_found",

                    "completed",

                    "visual_reasoning",

                    f"Found UI element: {target_text}"
                )

                return {

                    "success": True,

                    "element":
                        element
                }

        return {

            "success": False,

            "error":
                f"Element not found: {target_text}"
        }


    # ==========================================
    # CLICK ELEMENT BY TEXT
    # ==========================================

    async def click_element(

        self,

        payload: Dict[str, Any]

    ) -> Dict[str, Any]:

        execution_id = str(
            uuid4()
        )

        target_text = payload.get(
            "text"
        )

        if not target_text:

            return {

                "success": False,

                "error":
                    "Missing target text"
            }

        await self.publish_event(

            execution_id,

            "visual_click_started",

            "running",

            "computer_use",

            f"Searching visual element: {target_text}"
        )

        find_result = await (

            self.find_element_by_text({

                "text":
                    target_text
            })
        )

        if not find_result.get(
            "success"
        ):

            return find_result

        element = find_result[
            "element"
        ]

        x = element["center_x"]
        y = element["center_y"]

        # ==========================================
        # MOVE MOUSE
        # ==========================================

        await desktop_controller.move_mouse({

            "x": x,

            "y": y,

            "duration": 0.5
        })

        await asyncio.sleep(0.5)

        # ==========================================
        # CLICK
        # ==========================================

        await desktop_controller.click({

            "button":
                "left"
        })

        await self.publish_event(

            execution_id,

            "visual_click_completed",

            "completed",

            "computer_use",

            f"Clicked visual element: {target_text}",

            {

                "x":
                    x,

                "y":
                    y
            }
        )

        return {

            "success": True,

            "clicked_text":
                target_text,

            "coordinates": {

                "x": x,

                "y": y
            }
        }


    # ==========================================
    # SCREEN REASONING
    # ==========================================

    async def analyze_screen_state(

        self

    ) -> Dict[str, Any]:

        execution_id = str(
            uuid4()
        )

        detection_result = await (

            self.detect_ui_elements({})
        )

        if not detection_result.get(
            "success"
        ):

            return detection_result

        elements = detection_result[
            "elements"
        ]

        detected_text = [

            element["text"]

            for element in elements
        ]

        screen_summary = {

            "buttons_detected":
                len(elements),

            "visible_text":
                detected_text[:25],

            "screen_type":
                "interactive_desktop"
        }

        await self.publish_event(

            execution_id,

            "screen_analysis_completed",

            "completed",

            "screen_reasoning",

            "Visual screen reasoning completed"
        )

        return {

            "success": True,

            "summary":
                screen_summary
        }


# ==========================================
# SINGLETON
# ==========================================

visual_ui_engine = (
    VisualUIEngine()
)


# ==========================================
# REGISTER TOOLS
# ==========================================

tool_registry.register_tool(

    name="visual_detect_ui",

    description=
        "Detect visual UI elements",

    handler=
        visual_ui_engine.detect_ui_elements,

    tool_type=
        "computer_use"
)

tool_registry.register_tool(

    name="visual_find_element",

    description=
        "Find UI element by OCR text",

    handler=
        visual_ui_engine.find_element_by_text,

    tool_type=
        "computer_use"
)

tool_registry.register_tool(

    name="visual_click_element",

    description=
        "Click UI element by text",

    handler=
        visual_ui_engine.click_element,

    tool_type=
        "computer_use"
)

tool_registry.register_tool(

    name="visual_analyze_screen",

    description=
        "Analyze screen state",

    handler=
        visual_ui_engine.analyze_screen_state,

    tool_type=
        "computer_use"
)
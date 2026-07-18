from datetime import datetime
from pathlib import Path
from typing import Any, Dict
from uuid import uuid4

import pytesseract
from PIL import Image

from backend.events.event_bus import event_bus, publish_event
from backend.events.event_models import CognitionEvent
from backend.tools.tool_registry import tool_registry

pytesseract.pytesseract.tesseract_cmd = (
    r"C:\Program Files\Tesseract-OCR\tesseract.exe"
)



# ==========================================
# VISION ENGINE
# ==========================================

class VisionEngine:

    def __init__(self):

        # ==========================================
        # CONFIG
        # ==========================================

        self.supported_formats = [

            ".png",
            ".jpg",
            ".jpeg",
            ".webp"
        ]


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

        payload: Dict[str, Any] = None
    ):

        await publish_event("vision_engine", execution_id, event_type, status, phase, message, payload)


    # ==========================================
    # OCR EXTRACTION
    # ==========================================

    async def extract_text(

        self,

        payload: Dict[str, Any]

    ) -> Dict[str, Any]:

        execution_id = str(
            uuid4()
        )

        image_path = payload.get(
            "image_path"
        )

        if not image_path:

            return {

                "success": False,

                "error": "Missing image_path"
            }

        image_file = Path(image_path)

        if not image_file.exists():

            return {

                "success": False,

                "error": "Image file not found"
            }

        await self.publish_event(

            execution_id,

            "vision_ocr_started",

            "running",

            "ocr_extraction",

            f"Starting OCR extraction: {image_path}",

            {
                "image_path": image_path
            }
        )

        try:

            image = Image.open(
                image_path
            )

            extracted_text = (
                pytesseract.image_to_string(
                    image
                )
            )

            await self.publish_event(

                execution_id,

                "vision_ocr_completed",

                "completed",

                "ocr_extraction",

                "OCR extraction completed",

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
                    len(extracted_text),

                "timestamp":
                    datetime.utcnow()
                    .isoformat()
            }

        except Exception as error:

            await self.publish_event(

                execution_id,

                "vision_ocr_failed",

                "failed",

                "ocr_extraction",

                "OCR extraction failed",

                {
                    "error":
                        str(error)
                }
            )

            return {

                "success": False,

                "error": str(error)
            }


    # ==========================================
    # IMAGE METADATA
    # ==========================================

    async def analyze_image(

        self,

        payload: Dict[str, Any]

    ) -> Dict[str, Any]:

        execution_id = str(
            uuid4()
        )

        image_path = payload.get(
            "image_path"
        )

        if not image_path:

            return {

                "success": False,

                "error": "Missing image_path"
            }

        try:

            image = Image.open(
                image_path
            )

            width, height = image.size

            image_format = image.format

            mode = image.mode

            await self.publish_event(

                execution_id,

                "vision_analysis_completed",

                "completed",

                "image_analysis",

                "Image analysis completed",

                {
                    "width": width,
                    "height": height,
                    "format": image_format
                }
            )

            return {

                "success": True,

                "image_path":
                    image_path,

                "width":
                    width,

                "height":
                    height,

                "format":
                    image_format,

                "mode":
                    mode,

                "timestamp":
                    datetime.utcnow()
                    .isoformat()
            }

        except Exception as error:

            return {

                "success": False,

                "error":
                    str(error)
            }


    # ==========================================
    # VISUAL SUMMARY
    # ==========================================

    async def summarize_visual(

        self,

        payload: Dict[str, Any]

    ) -> Dict[str, Any]:

        execution_id = str(
            uuid4()
        )

        image_path = payload.get(
            "image_path"
        )

        if not image_path:

            return {

                "success": False,

                "error": "Missing image_path"
            }

        try:

            image = Image.open(
                image_path
            )

            width, height = image.size

            summary = (

                f"Image dimensions: "
                f"{width}x{height}. "
                f"Format: {image.format}. "
                f"Color mode: {image.mode}."
            )

            await self.publish_event(

                execution_id,

                "vision_summary_completed",

                "completed",

                "visual_reasoning",

                "Generated visual summary",

                {
                    "summary":
                        summary
                }
            )

            return {

                "success": True,

                "summary":
                    summary
            }

        except Exception as error:

            return {

                "success": False,

                "error":
                    str(error)
            }


# ==========================================
# SINGLETON
# ==========================================

vision_engine = VisionEngine()


# ==========================================
# REGISTER TOOLS
# ==========================================

tool_registry.register_tool(

    name="vision_extract_text",

    description=
        "Extract text from images using OCR",

    handler=
        vision_engine.extract_text,

    tool_type=
        "vision"
)

tool_registry.register_tool(

    name="vision_analyze_image",

    description=
        "Analyze image metadata",

    handler=
        vision_engine.analyze_image,

    tool_type=
        "vision"
)

tool_registry.register_tool(

    name="vision_visual_summary",

    description=
        "Generate visual image summary",

    handler=
        vision_engine.summarize_visual,

    tool_type=
        "vision"
)

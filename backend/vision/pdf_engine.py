from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List
from uuid import uuid4

import fitz
import pytesseract
from PIL import Image

from backend.events.event_bus import event_bus, publish_event
from backend.events.event_models import CognitionEvent
from backend.tools.tool_registry import tool_registry

# ==========================================
# TESSERACT CONFIG
# ==========================================

pytesseract.pytesseract.tesseract_cmd = (
    r"C:\Program Files\Tesseract-OCR\tesseract.exe"
)


# ==========================================
# PDF ENGINE
# ==========================================

class PDFEngine:

    def __init__(self):

        self.chunk_size = 1200


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

        await publish_event("pdf_engine", execution_id, event_type, status, phase, message, payload)


    # ==========================================
    # EXTRACT PDF TEXT
    # ==========================================

    async def extract_pdf_text(

        self,

        payload: Dict[str, Any]

    ) -> Dict[str, Any]:

        execution_id = str(
            uuid4()
        )

        pdf_path = payload.get(
            "pdf_path"
        )

        if not pdf_path:

            return {

                "success": False,

                "error": "Missing pdf_path"
            }

        pdf_file = Path(pdf_path)

        if not pdf_file.exists():

            return {

                "success": False,

                "error": "PDF file not found"
            }

        await self.publish_event(

            execution_id,

            "pdf_extraction_started",

            "running",

            "pdf_processing",

            f"Extracting PDF text: {pdf_path}",

            {
                "pdf_path": pdf_path
            }
        )

        try:

            document = fitz.open(
                pdf_path
            )

            extracted_pages = []

            combined_text = ""

            # ==========================================
            # PAGE LOOP
            # ==========================================

            for page_index in range(

                len(document)
            ):

                page = document[
                    page_index
                ]

                text = page.get_text()

                # ==========================================
                # OCR FALLBACK
                # ==========================================

                if not text.strip():

                    pix = page.get_pixmap()

                    image_path = (

                        f"temp_page_"
                        f"{page_index}.png"
                    )

                    pix.save(image_path)

                    image = Image.open(
                        image_path
                    )

                    text = (
                        pytesseract
                        .image_to_string(
                            image
                        )
                    )

                extracted_pages.append({

                    "page":
                        page_index + 1,

                    "text":
                        text
                })

                combined_text += (
                    text + "\n"
                )

            document.close()

            # ==========================================
            # CHUNKING
            # ==========================================

            chunks = self.chunk_text(
                combined_text
            )

            await self.publish_event(

                execution_id,

                "pdf_extraction_completed",

                "completed",

                "pdf_processing",

                "PDF extraction completed",

                {

                    "pages":
                        len(extracted_pages),

                    "chunks":
                        len(chunks)
                }
            )

            return {

                "success": True,

                "pdf_path":
                    pdf_path,

                "pages":
                    extracted_pages,

                "combined_text":
                    combined_text,

                "chunks":
                    chunks,

                "chunk_count":
                    len(chunks),

                "timestamp":
                    datetime.utcnow()
                    .isoformat()
            }

        except Exception as error:

            await self.publish_event(

                execution_id,

                "pdf_extraction_failed",

                "failed",

                "pdf_processing",

                "PDF extraction failed",

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
    # CHUNK TEXT
    # ==========================================

    def chunk_text(

        self,

        text: str

    ) -> List[str]:

        chunks = []

        start = 0

        while start < len(text):

            end = (
                start +
                self.chunk_size
            )

            chunk = text[start:end]

            chunks.append(
                chunk
            )

            start = end

        return chunks


    # ==========================================
    # DOCUMENT SUMMARY
    # ==========================================

    async def summarize_document(

        self,

        payload: Dict[str, Any]

    ) -> Dict[str, Any]:

        pdf_path = payload.get(
            "pdf_path"
        )

        extraction = await self.extract_pdf_text({

            "pdf_path":
                pdf_path
        })

        if not extraction.get(
            "success"
        ):

            return extraction

        combined_text = extraction.get(
            "combined_text",
            ""
        )

        summary = (

            combined_text[:1500]
        )

        return {

            "success": True,

            "summary":
                summary,

            "chunk_count":
                extraction.get(
                    "chunk_count"
                )
        }


# ==========================================
# SINGLETON
# ==========================================

pdf_engine = PDFEngine()


# ==========================================
# REGISTER TOOLS
# ==========================================

tool_registry.register_tool(

    name="pdf_extract_text",

    description=
        "Extract text from PDF documents",

    handler=
        pdf_engine.extract_pdf_text,

    tool_type=
        "document"
)

tool_registry.register_tool(

    name="pdf_document_summary",

    description=
        "Generate PDF summaries",

    handler=
        pdf_engine.summarize_document,

    tool_type=
        "document"
)

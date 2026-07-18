import logging

from pathlib import Path

import PyPDF2

log = logging.getLogger(__name__)


# ==========================================
# DOCUMENT TOOL
# ==========================================

class DocumentTool:

    def __init__(self):

        self.supported_extensions = [

            ".txt",
            ".md",
            ".pdf"
        ]

    # ==========================================
    # EXECUTE DOCUMENT TOOL
    # ==========================================

    def execute(
        self,
        tool_input: dict
    ):

        file_path = tool_input.get(
            "file_path"
        )

        if not file_path:

            raise Exception(
                "Missing file_path."
            )

        path = Path(file_path)

        if not path.exists():

            raise Exception(
                f"File not found: "
                f"{file_path}"
            )

        extension = (
            path.suffix.lower()
        )

        if (
            extension
            not in
            self.supported_extensions
        ):

            raise Exception(
                f"Unsupported file type: "
                f"{extension}"
            )

        log.info(
            "Reading Document: %s",
            file_path
        )

        # ==========================================
        # TXT / MD FILES
        # ==========================================

        if extension in [
            ".txt",
            ".md"
        ]:

            with open(
                path,
                "r",
                encoding="utf-8"
            ) as file:

                content = file.read()

            return {

                "file_path": file_path,

                "content": content
            }

        # ==========================================
        # PDF FILES
        # ==========================================

        if extension == ".pdf":

            content = ""

            with open(
                path,
                "rb"
            ) as file:

                reader = (
                    PyPDF2.PdfReader(file)
                )

                for page in reader.pages:

                    extracted = (
                        page.extract_text()
                    )

                    if extracted:

                        content += (
                            extracted + "\n"
                        )

            return {

                "file_path": file_path,

                "content": content
            }

        raise Exception(
            "Document processing failed."
        )

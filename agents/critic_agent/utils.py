import json
import logging
import re

log = logging.getLogger(__name__)


def safe_json_parse(content: str):

    try:

        # ==========================================
        # REMOVE MARKDOWN CODE BLOCKS
        # ==========================================

        cleaned = re.sub(
            r"```json|```",
            "",
            content
        ).strip()

        # ==========================================
        # PARSE JSON
        # ==========================================

        return json.loads(cleaned)

    except Exception as e:

        log.error(f"JSON Parse Error: {e}")

        return None

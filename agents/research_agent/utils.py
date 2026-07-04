import json
import re


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

        print(f"\n❌ JSON Parse Error: {e}\n")

        return None
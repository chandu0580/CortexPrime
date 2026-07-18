import logging

import requests

log = logging.getLogger(__name__)


# ==========================================
# API TOOL
# ==========================================

class APITool:

    def __init__(self):

        self.timeout = 20

    # ==========================================
    # EXECUTE API REQUEST
    # ==========================================

    def execute(
        self,
        tool_input: dict
    ):

        method = tool_input.get(
            "method",
            "GET"
        ).upper()

        url = tool_input.get(
            "url"
        )

        headers = tool_input.get(
            "headers",
            {}
        )

        params = tool_input.get(
            "params",
            {}
        )

        json_data = tool_input.get(
            "json",
            {}
        )

        if not url:

            raise Exception(
                "Missing API URL."
            )

        log.info(
            "Executing API Call: %s %s",
            method,
            url
        )

        # ==========================================
        # EXECUTE REQUEST
        # ==========================================

        response = requests.request(

            method=method,

            url=url,

            headers=headers,

            params=params,

            json=json_data,

            timeout=self.timeout
        )

        return {

            "status_code": (
                response.status_code
            ),

            "headers": dict(
                response.headers
            ),

            "body": self.safe_json(
                response
            )
        }

    # ==========================================
    # SAFE JSON PARSING
    # ==========================================

    def safe_json(
        self,
        response
    ):

        try:

            return response.json()

        except Exception:

            return response.text

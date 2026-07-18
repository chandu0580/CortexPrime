import logging
import os

from dotenv import load_dotenv

from openai import AzureOpenAI

log = logging.getLogger(__name__)


# ==========================================
# LOAD ENV
# ==========================================

load_dotenv()


# ==========================================
# AZURE OPENAI CLIENT
# ==========================================

client = AzureOpenAI(

    api_key=os.getenv(
        "AZURE_OPENAI_API_KEY"
    ),

    api_version=os.getenv(
        "AZURE_OPENAI_API_VERSION"
    ),

    azure_endpoint=os.getenv(
        "AZURE_OPENAI_ENDPOINT"
    ),

    timeout=180,

    max_retries=5
)


# ==========================================
# AUTONOMOUS REPAIR ENGINE
# ==========================================

class AutonomousRepairEngine:

    def __init__(self):

        pass

    # ==========================================
    # REPAIR CODE
    # ==========================================

    def repair_code(

        self,

        original_code: str,

        execution_error: str
    ):

        log.info(
            "Autonomous Repair "
            "Engine Activated..."
        )

        repair_prompt = f"""
You are an autonomous software repair AI.

Analyze the following Python code
and repair it.

ORIGINAL CODE:
{original_code}

EXECUTION ERROR:
{execution_error}

Return ONLY valid repaired Python code.
"""

        # ==========================================
        # LLM CALL
        # ==========================================

        response = client.chat.completions.create(

            model=os.getenv(
                "AZURE_OPENAI_CHAT_DEPLOYMENT"
            ),

            temperature=0.2,

            max_tokens=1500,

            messages=[

                {
                    "role": "system",

                    "content": (
                        "You are an expert "
                        "autonomous software "
                        "repair system."
                    )
                },

                {
                    "role": "user",

                    "content": repair_prompt
                }
            ]
        )

        repaired_code = (

            response.choices[0]
            .message
            .content
            .strip()
        )

        log.info(
            "Code Repair Generated."
        )

        return {

            "status": "success",

            "original_code": (
                original_code
            ),

            "execution_error": (
                execution_error
            ),

            "repaired_code": (
                repaired_code
            )
        }

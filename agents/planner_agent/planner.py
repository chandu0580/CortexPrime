import logging
import os

from dotenv import load_dotenv
from openai import AzureOpenAI

from agents.planner_agent.prompts import (
    PLANNER_AGENT_SYSTEM_PROMPT,
)
from agents.planner_agent.schemas import PlanningOutput
from agents.planner_agent.utils import safe_json_parse
from langgraph_system.state_management.cognitive_state import CognitiveState

log = logging.getLogger(__name__)


# ==========================================
# LOAD ENV VARIABLES
# ==========================================

load_dotenv()


# ==========================================
# AZURE OPENAI CLIENT
# ==========================================

client = AzureOpenAI(
    api_key=os.getenv("AZURE_OPENAI_API_KEY"),
    api_version=os.getenv("AZURE_OPENAI_API_VERSION"),
    azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT"),
    timeout=180,
    max_retries=5
)


# ==========================================
# PLANNER AGENT
# ==========================================

class PlannerAgent:

    def __init__(self):

        self.agent_name = "planner_agent"

    def execute(self, state: CognitiveState):

        log.info(
            "CortexPrime Planner Agent Activated..."
        )

        # ==========================================
        # USER PROMPT
        # ==========================================

        user_prompt = f"""
Analyze the following research intelligence and generate
a scalable strategic execution plan.

USER GOAL:
{state.user_goal}

RESEARCH SUMMARY:
{state.research_data.get("summary", "")}

Return ONLY valid JSON.

JSON FORMAT:

{{
    "execution_strategy": "",
    "execution_phases": [
        {{
            "phase": "",
            "objective": "",
            "priority": "",
            "deliverables": []
        }}
    ],
    "dependencies": [],
    "technical_requirements": [],
    "risks": [],
    "scalability_considerations": [],
    "estimated_complexity": "",
    "confidence": 0.0,
    "metadata": {{
        "estimated_timeline": "",
        "infrastructure_scale": "",
        "operational_risk": ""
    }}
}}
"""

        # ==========================================
        # LLM CALL
        # ==========================================

        response = client.chat.completions.create(
            model=os.getenv(
                "AZURE_OPENAI_CHAT_DEPLOYMENT"
            ),
            temperature=0.2,
            max_tokens=1200,
            response_format={
                "type": "json_object"
            },
            messages=[
                {
                    "role": "system",
                    "content": (
                        PLANNER_AGENT_SYSTEM_PROMPT
                    )
                },
                {
                    "role": "user",
                    "content": user_prompt
                }
            ]
        )

        # ==========================================
        # RAW RESPONSE
        # ==========================================

        raw_content = (
            response.choices[0]
            .message
            .content
        )

        # ==========================================
        # SAFE JSON PARSING
        # ==========================================

        parsed = safe_json_parse(
            raw_content
        )

        if not parsed:

            return {
                "agent": self.agent_name,
                "status": "failed",
                "error": (
                    "Invalid JSON returned from model"
                ),
                "raw_output": raw_content
            }

        # ==========================================
        # STRUCTURED OUTPUT
        # ==========================================

        structured_output = PlanningOutput(
            agent=self.agent_name,
            status="success",

            execution_strategy=parsed.get(
                "execution_strategy",
                ""
            ),

            execution_phases=parsed.get(
                "execution_phases",
                []
            ),

            dependencies=parsed.get(
                "dependencies",
                []
            ),

            technical_requirements=parsed.get(
                "technical_requirements",
                []
            ),

            risks=parsed.get(
                "risks",
                []
            ),

            scalability_considerations=parsed.get(
                "scalability_considerations",
                []
            ),

            estimated_complexity=parsed.get(
                "estimated_complexity",
                "unknown"
            ),

            confidence=parsed.get(
                "confidence",
                0.0
            ),

            metadata=parsed.get(
                "metadata",
                {}
            )
        )

        return structured_output.model_dump()

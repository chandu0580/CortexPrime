import logging
import os

from dotenv import load_dotenv
from openai import AzureOpenAI

from agents.critic_agent.prompts import (
    CRITIC_AGENT_SYSTEM_PROMPT,
)
from agents.critic_agent.schemas import CriticOutput
from agents.critic_agent.utils import safe_json_parse
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
# CRITIC AGENT
# ==========================================

class CriticAgent:

    def __init__(self):

        self.agent_name = "critic_agent"

    def execute(self, state: CognitiveState):

        log.info(
            "CortexPrime Critic Agent Activated..."
        )

        # ==========================================
        # USER PROMPT
        # ==========================================

        user_prompt = f"""
Analyze the following cognitive outputs critically.

USER GOAL:
{state.user_goal}

RESEARCH SUMMARY:
{state.research_data.get("summary", "")}

PLANNING STRATEGY:
{state.planning_data.get("execution_strategy", "")}

Return ONLY valid JSON.

JSON FORMAT:

{{
    "reasoning_validity": "",
    "hallucination_risk": "",
    "execution_feasibility": "",
    "contradictions_detected": [],
    "scalability_concerns": [],
    "security_risks": [],
    "compliance_issues": [],
    "operational_weaknesses": [],
    "recommendations": [],
    "confidence": 0.0,
    "metadata": {{
        "overall_risk_level": "",
        "architecture_stability": "",
        "deployment_readiness": ""
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
                        CRITIC_AGENT_SYSTEM_PROMPT
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

        structured_output = CriticOutput(
            agent=self.agent_name,
            status="success",

            reasoning_validity=parsed.get(
                "reasoning_validity",
                ""
            ),

            hallucination_risk=parsed.get(
                "hallucination_risk",
                ""
            ),

            execution_feasibility=parsed.get(
                "execution_feasibility",
                ""
            ),

            contradictions_detected=parsed.get(
                "contradictions_detected",
                []
            ),

            scalability_concerns=parsed.get(
                "scalability_concerns",
                []
            ),

            security_risks=parsed.get(
                "security_risks",
                []
            ),

            compliance_issues=parsed.get(
                "compliance_issues",
                []
            ),

            operational_weaknesses=parsed.get(
                "operational_weaknesses",
                []
            ),

            recommendations=parsed.get(
                "recommendations",
                []
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

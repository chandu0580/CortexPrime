import logging
import os

from dotenv import load_dotenv
from openai import AzureOpenAI

from agents.optimizer_agent.prompts import (
    OPTIMIZER_AGENT_SYSTEM_PROMPT,
)
from agents.optimizer_agent.schemas import OptimizerOutput
from agents.optimizer_agent.utils import safe_json_parse
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
# OPTIMIZER AGENT
# ==========================================

class OptimizerAgent:

    def __init__(self):

        self.agent_name = "optimizer_agent"

    def execute(self, state: CognitiveState):

        log.info(
            "CortexPrime Optimizer Agent Activated..."
        )

        # ==========================================
        # USER PROMPT
        # ==========================================

        user_prompt = f"""
Analyze and optimize the following cognitive outputs.

USER GOAL:
{state.user_goal}

RESEARCH SUMMARY:
{state.research_data.get("summary", "")}

PLANNING STRATEGY:
{state.planning_data.get("execution_strategy", "")}

CRITIC RECOMMENDATIONS:
{state.critique_data.get("recommendations", [])}

Return ONLY valid JSON.

JSON FORMAT:

{{
    "optimized_execution_strategy": "",
    "optimized_architecture_decisions": [],
    "scalability_improvements": [],
    "security_enhancements": [],
    "operational_optimizations": [],
    "hallucination_reduction_measures": [],
    "deployment_readiness_improvements": [],
    "refined_execution_phases": [
        {{
            "phase": "",
            "optimization": "",
            "impact": ""
        }}
    ],
    "confidence": 0.0,
    "metadata": {{
        "optimization_level": "",
        "architecture_maturity": "",
        "production_readiness": ""
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
                        OPTIMIZER_AGENT_SYSTEM_PROMPT
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

        structured_output = OptimizerOutput(
            agent=self.agent_name,
            status="success",

            optimized_execution_strategy=parsed.get(
                "optimized_execution_strategy",
                ""
            ),

            optimized_architecture_decisions=parsed.get(
                "optimized_architecture_decisions",
                []
            ),

            scalability_improvements=parsed.get(
                "scalability_improvements",
                []
            ),

            security_enhancements=parsed.get(
                "security_enhancements",
                []
            ),

            operational_optimizations=parsed.get(
                "operational_optimizations",
                []
            ),

            hallucination_reduction_measures=parsed.get(
                "hallucination_reduction_measures",
                []
            ),

            deployment_readiness_improvements=parsed.get(
                "deployment_readiness_improvements",
                []
            ),

            refined_execution_phases=parsed.get(
                "refined_execution_phases",
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

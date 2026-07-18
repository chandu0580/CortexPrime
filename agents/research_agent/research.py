import logging
import os

from dotenv import load_dotenv
from openai import AzureOpenAI

from agents.research_agent.prompts import (
    RESEARCH_AGENT_SYSTEM_PROMPT,
)
from agents.research_agent.schemas import ResearchOutput
from agents.research_agent.utils import safe_json_parse
from memory_system.semantic_memory_engine import SemanticMemoryEngine

log = logging.getLogger(__name__)


# ==========================================
# LOAD ENV VARIABLES
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
# NORMALIZE LIST OUTPUT
# ==========================================

def normalize_list_field(field):

    normalized = []

    for item in field:

        # ==========================================
        # STRING ITEM
        # ==========================================

        if isinstance(item, str):

            cleaned = item.strip()

            if cleaned:

                normalized.append(
                    cleaned
                )

        # ==========================================
        # DICT ITEM
        # ==========================================

        elif isinstance(item, dict):

            key = item.get(
                "key",
                ""
            ).strip()

            value = item.get(
                "value",
                ""
            ).strip()

            combined = (
                f"{key}: {value}"
            ).strip(": ").strip()

            if combined:

                normalized.append(
                    combined
                )

        # ==========================================
        # FALLBACK ITEM
        # ==========================================

        else:

            fallback = str(item).strip()

            if fallback:

                normalized.append(
                    fallback
                )

    # ==========================================
    # FINAL CLEANUP
    # ==========================================

    return [

        item

        for item in normalized

        if item.strip()
    ]


# ==========================================
# RESEARCH AGENT
# ==========================================

class ResearchAgent:

    def __init__(self):

        self.agent_name = (
            "research_agent"
        )

        self.semantic_memory = (
            SemanticMemoryEngine()
        )

    # ==========================================
    # EXECUTE
    # ==========================================

    def execute(
        self,
        user_goal: str
    ):

        log.info(
            "CortexPrime Research Agent Activated..."
        )

        # ==========================================
        # MEMORY RETRIEVAL
        # ==========================================

        retrieved_memories = (

            self.semantic_memory.search_memory(

                query=user_goal,

                top_k=3
            )
        )

        memory_context = "\n".join([

            memory.get(
                "memory_text",
                ""
            )

            for memory in retrieved_memories
        ])

        # ==========================================
        # USER PROMPT
        # ==========================================

        user_prompt = f"""
Analyze the following goal deeply
and generate structured intelligence.

USER GOAL:
{user_goal}

RELEVANT PAST MEMORIES:
{memory_context}

Return ONLY valid JSON.

JSON FORMAT:

{{
    "domain": "",
    "complexity": "low | medium | high",
    "confidence": 0.0,
    "summary": "",
    "insights": [],
    "risks": [],
    "opportunities": [],
    "reasoning_scope": [],
    "metadata": {{
        "urgency": "",
        "strategic_value": "",
        "execution_difficulty": ""
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

            temperature=0.3,

            max_tokens=1200,

            response_format={
                "type": "json_object"
            },

            messages=[

                {
                    "role": "system",

                    "content": (
                        RESEARCH_AGENT_SYSTEM_PROMPT
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
        # NORMALIZE STRUCTURED FIELDS
        # ==========================================

        insights = normalize_list_field(

            parsed.get(
                "insights",
                []
            )
        )

        risks = normalize_list_field(

            parsed.get(
                "risks",
                []
            )
        )

        opportunities = normalize_list_field(

            parsed.get(
                "opportunities",
                []
            )
        )

        reasoning_scope = normalize_list_field(

            parsed.get(
                "reasoning_scope",
                []
            )
        )

        # ==========================================
        # STRUCTURED OUTPUT
        # ==========================================

        structured_output = ResearchOutput(

            agent=self.agent_name,

            status="success",

            domain=parsed.get(
                "domain",
                "unknown"
            ),

            complexity=parsed.get(
                "complexity",
                "unknown"
            ),

            confidence=parsed.get(
                "confidence",
                0.0
            ),

            summary=parsed.get(
                "summary",
                ""
            ),

            insights=insights,

            risks=risks,

            opportunities=opportunities,

            reasoning_scope=reasoning_scope,

            metadata=parsed.get(
                "metadata",
                {}
            )
        )

        # ==========================================
        # STORE MEMORY
        # ==========================================

        memory_text = f"""

GOAL:
{user_goal}

SUMMARY:
{parsed.get("summary", "")}

INSIGHTS:
{insights}

OPPORTUNITIES:
{opportunities}
"""

        self.semantic_memory.store_memory(

            memory_text=memory_text,

            metadata={

                "agent": self.agent_name,

                "domain": parsed.get(
                    "domain",
                    "unknown"
                ),

                "complexity": parsed.get(
                    "complexity",
                    "unknown"
                )
            }
        )

        return structured_output.model_dump()

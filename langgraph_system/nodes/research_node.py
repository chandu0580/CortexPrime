from datetime import datetime

from agents.research_agent.tool_augmented_research import (
    ToolAugmentedResearchAgent
)

from execution_observability.telemetry_manager import (
    TelemetryManager
)

from resilience_engine.retry_manager import (
    RetryManager
)


# ==========================================
# INITIALIZE COMPONENTS
# ==========================================

research_agent = (
    ToolAugmentedResearchAgent()
)

telemetry_manager = (
    TelemetryManager()
)

retry_manager = (
    RetryManager()
)


# ==========================================
# RESEARCH NODE
# ==========================================

def research_node(state):

    print(
        "\n🧠 LangGraph Research Node Executing...\n"
    )

    started_at = datetime.utcnow()

    # ==========================================
    # EXECUTE WITH RETRIES
    # ==========================================

    result = (
        retry_manager.execute_with_retry(

            cognitive_state=state,

            node_name="research",

            execution_function=(
                research_agent.execute
            ),

            execution_args=(
                state.user_goal,
            )
        )
    )

    completed_at = datetime.utcnow()

    # ==========================================
    # STORE RESEARCH OUTPUT
    # ==========================================

    state.research_data = result

    state.research_confidence = (
        result.get(
            "confidence",
            0.0
        )
    )

    # ==========================================
    # LOG EXECUTION TRACE
    # ==========================================

    telemetry_manager.log_node_execution(
        state=state,
        node_name="research",
        started_at=started_at,
        completed_at=completed_at
    )

    return state
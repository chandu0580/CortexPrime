from datetime import datetime

from agents.critic_agent.critic import (
    CriticAgent
)

from execution_observability.telemetry_manager import (
    TelemetryManager
)

from resilience_engine.retry_manager import (
    RetryManager
)


critic_agent = CriticAgent()

telemetry_manager = (
    TelemetryManager()
)

retry_manager = (
    RetryManager()
)


def critic_node(state):

    print(
        "\n🧠 LangGraph Critic Node Executing...\n"
    )

    started_at = datetime.utcnow()

    # ==========================================
    # EXECUTE WITH RETRIES
    # ==========================================

    result = (
        retry_manager.execute_with_retry(

            cognitive_state=state,

            node_name="critic",

            execution_function=(
                critic_agent.execute
            ),

            execution_args=(state,)
        )
    )

    completed_at = datetime.utcnow()

    state.critique_data = result

    state.critique_confidence = (
        result.get(
            "confidence",
            0.0
        )
    )

    # ==========================================
    # LOG TRACE
    # ==========================================

    telemetry_manager.log_node_execution(
        state=state,
        node_name="critic",
        started_at=started_at,
        completed_at=completed_at
    )

    return state
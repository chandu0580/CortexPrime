from datetime import datetime

from agents.planner_agent.planner import (
    PlannerAgent
)

from execution_observability.telemetry_manager import (
    TelemetryManager
)

from resilience_engine.retry_manager import (
    RetryManager
)


planner_agent = PlannerAgent()

telemetry_manager = (
    TelemetryManager()
)

retry_manager = (
    RetryManager()
)


def planner_node(state):

    print(
        "\n🧠 LangGraph Planner Node Executing...\n"
    )

    started_at = datetime.utcnow()

    # ==========================================
    # TRACK REFLECTION COUNT
    # ==========================================

    if state.critique_data:

        state.reflection_count += 1

        print(
            f"\n🔄 Reflection Count: "
            f"{state.reflection_count}\n"
        )

    # ==========================================
    # EXECUTE WITH RETRIES
    # ==========================================

    result = (
        retry_manager.execute_with_retry(

            cognitive_state=state,

            node_name="planner",

            execution_function=(
                planner_agent.execute
            ),

            execution_args=(state,)
        )
    )

    completed_at = datetime.utcnow()

    state.planning_data = result

    state.planning_confidence = (
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
        node_name="planner",
        started_at=started_at,
        completed_at=completed_at
    )

    return state
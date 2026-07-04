from datetime import datetime

from agents.optimizer_agent.tool_augmented_optimizer import (
    ToolAugmentedOptimizerAgent
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

optimizer_agent = (
    ToolAugmentedOptimizerAgent()
)

telemetry_manager = (
    TelemetryManager()
)

retry_manager = (
    RetryManager()
)


# ==========================================
# OPTIMIZER NODE
# ==========================================

def optimizer_node(state):

    print(
        "\n🧠 LangGraph Optimizer Node Executing...\n"
    )

    started_at = datetime.utcnow()

    # ==========================================
    # EXECUTE WITH RETRIES
    # ==========================================

    result = (
        retry_manager.execute_with_retry(

            cognitive_state=state,

            node_name="optimizer",

            execution_function=(
                optimizer_agent.execute
            ),

            execution_args=(state,)
        )
    )

    completed_at = datetime.utcnow()

    # ==========================================
    # STORE OPTIMIZATION OUTPUT
    # ==========================================

    state.optimization_data = result

    state.optimization_confidence = (
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
        node_name="optimizer",
        started_at=started_at,
        completed_at=completed_at
    )

    return state
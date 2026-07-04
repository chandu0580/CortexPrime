from datetime import datetime
import asyncio

from backend.websocket.server import (
    websocket_manager
)

from langgraph_system.graphs.cognitive_graph import (
    cognitive_graph
)

from langgraph_system.state_management.cognitive_state import (
    CognitiveState
)

from langgraph_system.async_runtime.parallel_cognition_manager import (
    ParallelCognitionManager
)

from langgraph_system.checkpointing.checkpoint_manager import (
    CheckpointManager
)

from langgraph_system.nodes.research_node import (
    research_node
)

from langgraph_system.nodes.planner_node import (
    planner_node
)

from langgraph_system.nodes.critic_node import (
    critic_node
)


# ==========================================
# GRAPH EXECUTOR
# ==========================================

class GraphExecutor:

    def __init__(self):

        self.parallel_manager = (
            ParallelCognitionManager()
        )

        self.checkpoint_manager = (
            CheckpointManager()
        )

    # ==========================================
    # BROADCAST EVENT
    # ==========================================

    def broadcast_event(
        self,
        event_type: str,
        event_message: str
    ):

        try:

            asyncio.run(

                websocket_manager.broadcast({

                    "type": event_type,

                    "event": event_message,

                    "timestamp": (
                        datetime.utcnow()
                        .isoformat()
                    )
                })
            )

        except Exception as error:

            print(
                f"\n⚠️ WebSocket Broadcast "
                f"Failed: {error}\n"
            )

    # ==========================================
    # EXECUTE
    # ==========================================

    def execute(
        self,
        user_goal: str
    ):

        print(
            "\n🧠 CortexPrime Graph Runtime Initiated...\n"
        )

        # ==========================================
        # REALTIME EVENT
        # ==========================================

        self.broadcast_event(

            event_type="runtime_start",

            event_message=(
                "CortexPrime Runtime Started"
            )
        )

        # ==========================================
        # INITIALIZE STATE
        # ==========================================

        initial_state = CognitiveState(
            user_goal=user_goal
        )

        initial_state.workflow_status = (
            "running"
        )

        # ==========================================
        # SAVE INITIAL CHECKPOINT
        # ==========================================

        self.checkpoint_manager.save_checkpoint(
            initial_state
        )

        # ==========================================
        # TRACK START
        # ==========================================

        start_time = datetime.utcnow()

        # ==========================================
        # PARALLEL COGNITION
        # ==========================================

        self.broadcast_event(

            event_type="parallel_start",

            event_message=(
                "Parallel Cognition Started"
            )
        )

        parallel_results = (

            self.parallel_manager.run(

                cognitive_state=initial_state,

                research_function=(
                    research_node
                ),

                planner_function=(
                    planner_node
                ),

                critic_function=(
                    critic_node
                )
            )
        )

        # ==========================================
        # PARALLEL COMPLETE EVENT
        # ==========================================

        self.broadcast_event(

            event_type="parallel_complete",

            event_message=(
                "Parallel Cognition Completed"
            )
        )

        # ==========================================
        # UPDATE STATE
        # ==========================================

        research_state = (
            parallel_results.get(
                "research"
            )
        )

        planner_state = (
            parallel_results.get(
                "planner"
            )
        )

        critic_state = (
            parallel_results.get(
                "critic"
            )
        )

        if research_state:

            initial_state.research_data = (
                research_state.research_data
            )

            initial_state.research_confidence = (
                research_state.research_confidence
            )

        if planner_state:

            initial_state.planning_data = (
                planner_state.planning_data
            )

            initial_state.planning_confidence = (
                planner_state.planning_confidence
            )

        if critic_state:

            initial_state.critique_data = (
                critic_state.critique_data
            )

            initial_state.critique_confidence = (
                critic_state.critique_confidence
            )

        # ==========================================
        # SAVE POST-PARALLEL CHECKPOINT
        # ==========================================

        self.checkpoint_manager.save_checkpoint(
            initial_state
        )

        # ==========================================
        # GRAPH EXECUTION EVENT
        # ==========================================

        self.broadcast_event(

            event_type="graph_execution",

            event_message=(
                "Main Cognitive Graph Executing"
            )
        )

        # ==========================================
        # EXECUTE MAIN GRAPH
        # ==========================================

        final_state = (
            cognitive_graph.invoke(
                initial_state
            )
        )

        # ==========================================
        # FINALIZE WORKFLOW
        # ==========================================

        final_state["workflow_status"] = (
            "completed"
        )

        # ==========================================
        # FINAL OUTPUT
        # ==========================================

        optimization_data = (
            final_state.get(
                "optimization_data",
                {}
            )
        )

        planning_data = (
            final_state.get(
                "planning_data",
                {}
            )
        )

        final_state["final_output"] = (

            optimization_data.get(
                "optimized_execution_strategy"
            )

            or

            planning_data.get(
                "execution_strategy",
                ""
            )
        )

        # ==========================================
        # FINAL CONFIDENCE
        # ==========================================

        confidences = [

            final_state.get(
                "research_confidence",
                0.0
            ),

            final_state.get(
                "planning_confidence",
                0.0
            ),

            final_state.get(
                "critique_confidence",
                0.0
            ),

            final_state.get(
                "optimization_confidence",
                0.0
            )
        ]

        final_state["final_confidence"] = (
            max(confidences)
        )

        # ==========================================
        # RUNTIME METADATA
        # ==========================================

        final_state["runtime_metadata"] = {

            "started_at": (
                start_time.isoformat()
            ),

            "completed_at": (
                datetime.utcnow().isoformat()
            ),

            "reflection_cycles": (
                final_state.get(
                    "reflection_count",
                    0
                )
            ),

            "parallel_cognition_enabled": True,

            "checkpointing_enabled": True,

            "realtime_streaming_enabled": True
        }

        # ==========================================
        # SAVE FINAL CHECKPOINT
        # ==========================================

        final_state_model = CognitiveState(
            **final_state
        )

        self.checkpoint_manager.save_checkpoint(
            final_state_model
        )

        # ==========================================
        # FINAL REALTIME EVENT
        # ==========================================

        self.broadcast_event(

            event_type="runtime_complete",

            event_message=(
                "CortexPrime Execution Completed"
            )
        )

        print(
            "\n✅ Graph Execution Completed.\n"
        )

        return final_state
import logging
import time
from datetime import datetime

from agents.critic_agent.critic import CriticAgent
from agents.optimizer_agent.optimizer import OptimizerAgent
from agents.planner_agent.planner import PlannerAgent
from agents.research_agent.research import ResearchAgent
from langgraph_system.state_management.cognitive_state import CognitiveState
from memory_architecture.short_term_memory.memory_manager import ShortTermMemoryManager
from memory_architecture.short_term_memory.retriever import MemoryRetriever
from memory_architecture.vector_memory.semantic_retriever import SemanticRetriever
from reflection_engine.reflection_manager import ReflectionManager

log = logging.getLogger(__name__)


class CortexPrimeOrchestrator:

    def __init__(self):

        # ==========================================
        # INITIALIZE AGENTS
        # ==========================================

        self.research_agent = ResearchAgent()

        self.planner_agent = PlannerAgent()

        self.critic_agent = CriticAgent()

        self.optimizer_agent = OptimizerAgent()

        # ==========================================
        # MEMORY SYSTEMS
        # ==========================================

        self.memory_manager = (
            ShortTermMemoryManager()
        )

        self.memory_retriever = (
            MemoryRetriever()
        )

        self.semantic_retriever = (
            SemanticRetriever()
        )

        # ==========================================
        # REFLECTION ENGINE
        # ==========================================

        self.reflection_manager = (
            ReflectionManager()
        )

    # ==========================================
    # EXECUTION TRACE LOGGER
    # ==========================================

    def log_execution(
        self,
        state,
        agent_name,
        status,
        duration
    ):

        state.execution_trace.append({
            "agent": agent_name,
            "status": status,
            "duration_seconds": round(duration, 2),
            "timestamp": datetime.utcnow().isoformat()
        })

    # ==========================================
    # SAFE AGENT EXECUTION
    # ==========================================

    def safe_execute(
        self,
        state,
        agent_name,
        agent_function
    ):

        start_time = time.time()

        try:

            log.info(
                f"Executing {agent_name}..."
            )

            result = agent_function()

            if (
                isinstance(result, dict)
                and result.get("status") == "failed"
            ):

                raise Exception(
                    result.get(
                        "error",
                        "Unknown agent failure"
                    )
                )

            duration = (
                time.time() - start_time
            )

            self.log_execution(
                state,
                agent_name,
                "success",
                duration
            )

            state.agent_timings[
                agent_name
            ] = round(duration, 2)

            return result

        except Exception as e:

            duration = (
                time.time() - start_time
            )

            self.log_execution(
                state,
                agent_name,
                "failed",
                duration
            )

            error_message = (
                f"{agent_name} failed: {str(e)}"
            )

            state.errors.append(
                error_message
            )

            log.error(
                f"{error_message}"
            )

            return None

    # ==========================================
    # REFLECTION LOOP
    # ==========================================

    def run_reflection_loop(
        self,
        state
    ):

        log.info(
            "Reflection Loop Triggered..."
        )

        # ==========================================
        # RE-PLANNING
        # ==========================================

        state.active_agent = (
            "planner_agent_reflection"
        )

        improved_planning = (
            self.safe_execute(
                state,
                "planner_agent_reflection",
                lambda: self.planner_agent.execute(
                    state
                )
            )
        )

        if improved_planning:

            state.planning_data = (
                improved_planning
            )

            state.planning_confidence = (
                improved_planning.get(
                    "confidence",
                    0.0
                )
            )

        # ==========================================
        # RE-CRITIQUE
        # ==========================================

        state.active_agent = (
            "critic_agent_reflection"
        )

        improved_critique = (
            self.safe_execute(
                state,
                "critic_agent_reflection",
                lambda: self.critic_agent.execute(
                    state
                )
            )
        )

        if improved_critique:

            state.critique_data = (
                improved_critique
            )

            state.critique_confidence = (
                improved_critique.get(
                    "confidence",
                    0.0
                )
            )

        # ==========================================
        # RE-OPTIMIZATION
        # ==========================================

        state.active_agent = (
            "optimizer_agent_reflection"
        )

        improved_optimization = (
            self.safe_execute(
                state,
                "optimizer_agent_reflection",
                lambda: self.optimizer_agent.execute(
                    state
                )
            )
        )

        if improved_optimization:

            state.optimization_data = (
                improved_optimization
            )

            state.optimization_confidence = (
                improved_optimization.get(
                    "confidence",
                    0.0
                )
            )

    # ==========================================
    # MAIN WORKFLOW
    # ==========================================

    def execute(
        self,
        user_goal: str
    ):

        log.info(
            "CortexPrime Cognitive Orchestration Initiated..."
        )

        # ==========================================
        # INITIALIZE STATE
        # ==========================================

        state = CognitiveState(
            user_goal=user_goal
        )

        # ==========================================
        # RETRIEVE KEYWORD MEMORIES
        # ==========================================

        relevant_memories = (
            self.memory_retriever
            .retrieve_relevant_memories(
                current_goal=user_goal
            )
        )

        state.relevant_memories = (
            relevant_memories
        )

        # ==========================================
        # SEMANTIC VECTOR MEMORY RETRIEVAL
        # ==========================================

        semantic_memories = (
            self.semantic_retriever.retrieve(
                user_goal
            )
        )

        state.semantic_context = (
            semantic_memories
        )

        state.workflow_status = "running"

        # ==========================================
        # RESEARCH PHASE
        # ==========================================

        state.active_agent = (
            "research_agent"
        )

        research_result = (
            self.safe_execute(
                state,
                "research_agent",
                lambda: self.research_agent.execute(
                    state.user_goal
                )
            )
        )

        if not research_result:

            return self.fail_workflow(
                state,
                "Research phase failed"
            )

        state.research_data = (
            research_result
        )

        state.research_confidence = (
            research_result.get(
                "confidence",
                0.0
            )
        )

        # ==========================================
        # PLANNING PHASE
        # ==========================================

        state.active_agent = (
            "planner_agent"
        )

        planning_result = (
            self.safe_execute(
                state,
                "planner_agent",
                lambda: self.planner_agent.execute(
                    state
                )
            )
        )

        if not planning_result:

            return self.fail_workflow(
                state,
                "Planning phase failed"
            )

        state.planning_data = (
            planning_result
        )

        state.planning_confidence = (
            planning_result.get(
                "confidence",
                0.0
            )
        )

        # ==========================================
        # CRITIQUE PHASE
        # ==========================================

        state.active_agent = (
            "critic_agent"
        )

        critique_result = (
            self.safe_execute(
                state,
                "critic_agent",
                lambda: self.critic_agent.execute(
                    state
                )
            )
        )

        if not critique_result:

            return self.fail_workflow(
                state,
                "Critique phase failed"
            )

        state.critique_data = (
            critique_result
        )

        state.critique_confidence = (
            critique_result.get(
                "confidence",
                0.0
            )
        )

        # ==========================================
        # OPTIMIZATION PHASE
        # ==========================================

        state.active_agent = (
            "optimizer_agent"
        )

        optimization_result = (
            self.safe_execute(
                state,
                "optimizer_agent",
                lambda: self.optimizer_agent.execute(
                    state
                )
            )
        )

        if not optimization_result:

            return self.fail_workflow(
                state,
                "Optimization phase failed"
            )

        state.optimization_data = (
            optimization_result
        )

        state.optimization_confidence = (
            optimization_result.get(
                "confidence",
                0.0
            )
        )

        # ==========================================
        # REFLECTION CHECK
        # ==========================================

        reflection_triggered = (
            self.reflection_manager
            .should_trigger_reflection(
                state
            )
        )

        if reflection_triggered:

            self.run_reflection_loop(
                state
            )

        # ==========================================
        # FINAL OUTPUT
        # ==========================================

        state.final_output = (
            state.optimization_data.get(
                "optimized_execution_strategy"
            )
            or
            state.planning_data.get(
                "execution_strategy",
                ""
            )
        )

        state.final_confidence = max(
            state.research_confidence,
            state.planning_confidence,
            state.critique_confidence,
            state.optimization_confidence
        )

        # ==========================================
        # FINALIZE WORKFLOW
        # ==========================================

        state.workflow_status = (
            "completed"
        )

        state.active_agent = None

        log.info(
            "CortexPrime Cognitive Workflow Completed."
        )

        # ==========================================
        # STORE MEMORY
        # ==========================================

        self.memory_manager.store_execution(
            state
        )

        return state.model_dump()

    # ==========================================
    # FAILURE HANDLER
    # ==========================================

    def fail_workflow(
        self,
        state,
        message
    ):

        state.workflow_status = (
            "failed"
        )

        state.active_agent = None

        state.errors.append(
            message
        )

        return {
            "status": "failed",
            "errors": state.errors,
            "execution_trace": (
                state.execution_trace
            )
        }


# ==========================================
# GLOBAL ORCHESTRATOR
# ==========================================

orchestrator = CortexPrimeOrchestrator()

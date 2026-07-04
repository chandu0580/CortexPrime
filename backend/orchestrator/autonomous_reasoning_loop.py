from typing import Dict, Any, List

from uuid import uuid4

from datetime import datetime

import asyncio

import os


from backend.events.event_bus import (
    event_bus
)

from backend.events.event_models import (
    CognitionEvent
)

from backend.llm.llm_gateway import (
    llm_gateway
)

from backend.orchestrator.agent_router import (
    agent_router
)

from backend.orchestrator.reflection_engine import (
    reflection_engine
)

from backend.memory.episodic_memory_engine import (
    episodic_memory_engine
)


# =========================================================
# AUTONOMOUS REASONING LOOP
# =========================================================

class AutonomousReasoningLoop:

    def __init__(self):

        self.active_loops = {}

        self.loop_history = []


    # =====================================================
    # EVENT PUBLISHER
    # =====================================================

    async def publish_event(

        self,

        execution_id: str,

        event_type: str,

        status: str,

        phase: str,

        message: str,

        payload: Dict[str, Any] = {}
    ):

        await event_bus.publish(

            CognitionEvent(

                agent=
                    "autonomous_reasoning_loop",

                event_type=
                    event_type,

                status=
                    status,

                phase=
                    phase,

                execution_id=
                    execution_id,

                message=
                    message,

                payload=
                    payload
            )
        )


    # =====================================================
    # MEMORY CONTEXT
    # =====================================================

    async def retrieve_context(

        self,

        goal: str
    ) -> List[Dict[str, Any]]:

        try:

            memory_result = await (

                episodic_memory_engine
                .retrieve_memories({

                    "query":
                        goal,

                    "limit":
                        5
                })
            )

            return memory_result.get(
                "memories",
                []
            )

        except Exception:

            return []


    # =====================================================
    # THINK
    # =====================================================

    async def think(

        self,

        goal: str,

        observations: List[Dict[str, Any]],

        memory_context: List[Dict[str, Any]]
    ) -> Dict[str, Any]:

        prompt = f"""

You are CortexPrime autonomous cognition engine.

Goal:
{goal}

Memory Context:
{memory_context}

Observations:
{observations}

Analyze:
1. What is the user's intent?
2. What is the best response?
3. Is the task already solvable?
4. Generate concise reasoning.

DO NOT explain chain of thought.
DO NOT generate step-by-step planning.

Return only concise mission analysis.
"""

        return await (

            llm_gateway.generate({

                "provider":
                    "azure",

                "agent_type":
                    "planner",

                "prompt":
                    prompt
            })
        )


    # =====================================================
    # FINAL RESPONSE GENERATOR
    # =====================================================

    async def generate_final_response(

        self,

        goal: str,

        reasoning: Dict[str, Any]
    ) -> Dict[str, Any]:

        reasoning_output = reasoning.get(
            "output",
            ""
        )

        prompt = f"""

User Request:
{goal}

Internal Reasoning:
{reasoning_output}

Generate the FINAL USER RESPONSE.

Rules:
- concise
- direct
- helpful
- no internal reasoning
- no planning steps
- answer naturally

"""

        return await (

            llm_gateway.generate({

                "provider":
                    "azure",

                "agent_type":
                    "general",

                "prompt":
                    prompt
            })
        )


    # =====================================================
    # DETERMINE COMPLETION
    # =====================================================

    async def should_continue(

        self,

        iteration: int,

        max_iterations: int,

        final_response: Dict[str, Any]
    ) -> bool:

        if iteration >= (
            max_iterations - 1
        ):

            return False

        if final_response.get(
            "success",
            False
        ):

            output = final_response.get(
                "output",
                ""
            )

            if len(output.strip()) > 20:

                return False

        return True


    # =====================================================
    # OBSERVE
    # =====================================================

    async def observe(

        self,

        result: Dict[str, Any]
    ) -> Dict[str, Any]:

        return {

            "success":
                result.get(
                    "success",
                    False
                ),

            "timestamp":
                datetime.utcnow()
                .isoformat(),

            "summary":
                str(result)[:1000]
        }


    # =====================================================
    # REFLECT
    # =====================================================

    async def reflect(

        self,

        goal: str,

        result: Dict[str, Any]
    ) -> Dict[str, Any]:

        return await (

            reflection_engine
            .analyze_result({

                "goal":
                    goal,

                "result":
                    result
            })
        )


    # =====================================================
    # STORE MEMORY
    # =====================================================

    async def store_memory(

        self,

        goal: str,

        response: str
    ):

        try:

            await episodic_memory_engine.store_memory({

                "content":
                    f"Goal: {goal}\nResponse: {response}",

                "metadata": {

                    "type":
                        "autonomous_execution"
                }
            })

        except Exception:

            pass


    # =====================================================
    # MAIN EXECUTION
    # =====================================================

    async def execute_goal(

        self,

        payload: Dict[str, Any]
    ) -> Dict[str, Any]:

        execution_id = str(
            uuid4()
        )

        goal = payload.get(
            "goal"
        )

        max_iterations = payload.get(

            "max_iterations",

            int(

                os.getenv(

                    "MAX_AUTONOMOUS_ITERATIONS",

                    5
                )
            )
        )

        if not goal:

            return {

                "success": False,

                "error":
                    "Goal is required"
            }

        self.active_loops[
            execution_id
        ] = {

            "goal":
                goal,

            "status":
                "running",

            "started_at":
                datetime.utcnow()
                .isoformat()
        }

        await self.publish_event(

            execution_id,

            "autonomous_loop_started",

            "running",

            "autonomous_reasoning",

            f"Executing goal: {goal}"
        )

        observations = []

        iterations = []

        memory_context = await (

            self.retrieve_context(
                goal
            )
        )

        final_response = None

        # =================================================
        # LOOP
        # =================================================

        for iteration in range(
            max_iterations
        ):

            # =============================================
            # THINK
            # =============================================

            reasoning = await (

                self.think(

                    goal,

                    observations,

                    memory_context
                )
            )

            # =============================================
            # GENERATE FINAL RESPONSE
            # =============================================

            final_response = await (

                self.generate_final_response(

                    goal,

                    reasoning
                )
            )

            # =============================================
            # OBSERVE
            # =============================================

            observation = await (

                self.observe(
                    final_response
                )
            )

            observations.append(
                observation
            )

            # =============================================
            # REFLECT
            # =============================================

            reflection = await (

                self.reflect(

                    goal,

                    final_response
                )
            )

            iterations.append({

                "iteration":
                    iteration + 1,

                "reasoning":
                    reasoning,

                "response":
                    final_response,

                "reflection":
                    reflection
            })

            # =============================================
            # MEMORY
            # =============================================

            if final_response.get(
                "success"
            ):

                await self.store_memory(

                    goal,

                    final_response.get(
                        "output",
                        ""
                    )
                )

            # =============================================
            # SHOULD CONTINUE?
            # =============================================

            continue_loop = await (

                self.should_continue(

                    iteration,

                    max_iterations,

                    final_response
                )
            )

            if not continue_loop:

                break

            await asyncio.sleep(1)

        # =================================================
        # COMPLETE
        # =================================================

        self.active_loops[
            execution_id
        ]["status"] = "completed"

        completed_result = {

            "success": True,

            "execution_id":
                execution_id,

            "goal":
                goal,

            "final_response":
                final_response.get(
                    "output",
                    ""
                ),

            "iterations":
                iterations,

            "completed_at":
                datetime.utcnow()
                .isoformat()
        }

        self.loop_history.append(
            completed_result
        )

        await self.publish_event(

            execution_id,

            "autonomous_loop_completed",

            "completed",

            "autonomous_reasoning",

            f"Completed goal: {goal}"
        )

        return completed_result


    # =====================================================
    # ACTIVE LOOPS
    # =====================================================

    async def get_active_loops(

        self
    ) -> Dict[str, Any]:

        return {

            "success": True,

            "active_loops":
                self.active_loops
        }


    # =====================================================
    # LOOP HISTORY
    # =====================================================

    async def get_loop_history(

        self
    ) -> Dict[str, Any]:

        return {

            "success": True,

            "history":
                self.loop_history
        }


# =========================================================
# SINGLETON
# =========================================================

autonomous_reasoning_loop = (
    AutonomousReasoningLoop()
)

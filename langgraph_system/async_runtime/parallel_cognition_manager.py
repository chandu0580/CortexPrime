import asyncio

from langgraph_system.async_runtime.async_executor import (
    AsyncExecutor
)


# ==========================================
# PARALLEL COGNITION MANAGER
# ==========================================

class ParallelCognitionManager:

    def __init__(self):

        self.async_executor = (
            AsyncExecutor()
        )

    # ==========================================
    # EXECUTE PARALLEL COGNITION
    # ==========================================

    async def execute_parallel_cognition(

        self,

        cognitive_state,

        research_function=None,

        planner_function=None,

        critic_function=None
    ):

        print(
            "\n⚡ Executing Parallel Cognition...\n"
        )

        tasks = []

        # ==========================================
        # RESEARCH TASK
        # ==========================================

        if research_function:

            tasks.append({

                "name": "research",

                "function": research_function,

                "args": [
                    cognitive_state
                ]
            })

        # ==========================================
        # PLANNER TASK
        # ==========================================

        if planner_function:

            tasks.append({

                "name": "planner",

                "function": planner_function,

                "args": [
                    cognitive_state
                ]
            })

        # ==========================================
        # CRITIC TASK
        # ==========================================

        if critic_function:

            tasks.append({

                "name": "critic",

                "function": critic_function,

                "args": [
                    cognitive_state
                ]
            })

        # ==========================================
        # EXECUTE TASKS
        # ==========================================

        results = await (

            self.async_executor.run_parallel_tasks(
                tasks
            )
        )

        # ==========================================
        # MAP RESULTS
        # ==========================================

        mapped_results = {}

        for index, task in enumerate(tasks):

            mapped_results[
                task["name"]
            ] = results[index]

        print(
            "\n✅ Parallel Cognition Completed.\n"
        )

        return mapped_results

    # ==========================================
    # SYNCHRONOUS WRAPPER
    # ==========================================

    def run(

        self,

        cognitive_state,

        research_function=None,

        planner_function=None,

        critic_function=None
    ):

        return asyncio.run(

            self.execute_parallel_cognition(

                cognitive_state=cognitive_state,

                research_function=(
                    research_function
                ),

                planner_function=(
                    planner_function
                ),

                critic_function=(
                    critic_function
                )
            )
        )
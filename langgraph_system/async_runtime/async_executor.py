import asyncio


# ==========================================
# ASYNC EXECUTOR
# ==========================================

class AsyncExecutor:

    def __init__(self):

        pass

    # ==========================================
    # RUN TASK ASYNC
    # ==========================================

    async def run_task(

        self,

        task_function,

        *args,

        **kwargs
    ):

        return await asyncio.to_thread(

            task_function,

            *args,

            **kwargs
        )

    # ==========================================
    # RUN PARALLEL TASKS
    # ==========================================

    async def run_parallel_tasks(

        self,

        tasks: list
    ):

        async_tasks = [

            self.run_task(
                task["function"],
                *task.get(
                    "args",
                    []
                ),
                **task.get(
                    "kwargs",
                    {}
                )
            )

            for task in tasks
        ]

        results = await asyncio.gather(
            *async_tasks
        )

        return results
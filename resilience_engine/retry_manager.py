from resilience_engine.backoff_strategy import (
    BackoffStrategy
)

from resilience_engine.failure_handler import (
    FailureHandler
)


# ==========================================
# RETRY MANAGER
# ==========================================

class RetryManager:

    def __init__(self):

        self.max_retries = 3

        self.backoff_strategy = (
            BackoffStrategy()
        )

        self.failure_handler = (
            FailureHandler()
        )

    # ==========================================
    # EXECUTE WITH RETRIES
    # ==========================================

    def execute_with_retry(
        self,
        cognitive_state,
        node_name: str,
        execution_function,
        execution_args=None,
        execution_kwargs=None
    ):

        if execution_args is None:
            execution_args = ()

        if execution_kwargs is None:
            execution_kwargs = {}

        last_error = None

        for retry_attempt in range(
            self.max_retries
        ):

            try:

                print(
                    f"\n🚀 Attempt "
                    f"{retry_attempt + 1} "
                    f"for {node_name}\n"
                )

                result = execution_function(
                    *execution_args,
                    **execution_kwargs
                )

                return result

            except Exception as error:

                last_error = error

                print(
                    f"\n⚠️ Retry "
                    f"{retry_attempt + 1} "
                    f"failed for "
                    f"{node_name}\n"
                )

                # ==========================================
                # FINAL FAILURE
                # ==========================================

                if (
                    retry_attempt
                    ==
                    self.max_retries - 1
                ):

                    self.failure_handler.handle_failure(
                        state=cognitive_state,
                        node_name=node_name,
                        error=error
                    )

                    raise error

                # ==========================================
                # BACKOFF WAIT
                # ==========================================

                self.backoff_strategy.wait(
                    retry_attempt
                )

        raise last_error
from datetime import datetime


# ==========================================
# FAILURE HANDLER
# ==========================================

class FailureHandler:

    # ==========================================
    # HANDLE FAILURE
    # ==========================================

    def handle_failure(
        self,
        state,
        node_name: str,
        error: Exception
    ):

        error_message = (

            f"{node_name} failed: "
            f"{str(error)}"
        )

        print(
            f"\n❌ {error_message}\n"
        )

        # ==========================================
        # STORE ERROR
        # ==========================================

        state.errors.append({

            "node": node_name,

            "error": str(error),

            "timestamp": (
                datetime.utcnow()
                .isoformat()
            )
        })

        # ==========================================
        # UPDATE WORKFLOW STATUS
        # ==========================================

        state.workflow_status = (
            "degraded"
        )

        return state

    # ==========================================
    # BUILD FAILURE RESPONSE
    # ==========================================

    def build_failure_response(
        self,
        state
    ):

        return {

            "status": "failed",

            "workflow_status": (
                state.workflow_status
            ),

            "errors": (
                state.errors
            ),

            "execution_trace": (
                state.execution_trace
            ),

            "reflection_count": (
                state.reflection_count
            )
        }
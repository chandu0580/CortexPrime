from datetime import datetime


# ==========================================
# RUNTIME METRICS
# ==========================================

class RuntimeMetrics:

    def __init__(self):

        self.workflow_started_at = None

        self.workflow_completed_at = None

    # ==========================================
    # START TIMER
    # ==========================================

    def start_workflow_timer(self):

        self.workflow_started_at = (
            datetime.utcnow()
        )

    # ==========================================
    # STOP TIMER
    # ==========================================

    def stop_workflow_timer(self):

        self.workflow_completed_at = (
            datetime.utcnow()
        )

    # ==========================================
    # GET TOTAL DURATION
    # ==========================================

    def get_total_duration(self):

        if (
            not self.workflow_started_at
            or
            not self.workflow_completed_at
        ):

            return 0.0

        duration = (
            self.workflow_completed_at
            -
            self.workflow_started_at
        )

        return round(
            duration.total_seconds(),
            2
        )

    # ==========================================
    # BUILD METRICS OBJECT
    # ==========================================

    def generate_metrics(
        self,
        state
    ):

        return {

            "workflow_started_at": (
                self.workflow_started_at
                .isoformat()
            )
            if self.workflow_started_at
            else None,

            "workflow_completed_at": (
                self.workflow_completed_at
                .isoformat()
            )
            if self.workflow_completed_at
            else None,

            "total_execution_time_seconds": (
                self.get_total_duration()
            ),

            "reflection_cycles": (
                state.reflection_count
            ),

            "total_nodes_executed": (
                len(
                    state.execution_trace
                )
            ),

            "final_confidence": (
                state.final_confidence
            ),

            "workflow_status": (
                state.workflow_status
            )
        }
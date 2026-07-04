from execution_observability.trace_logger import (
    TraceLogger
)

from execution_observability.runtime_metrics import (
    RuntimeMetrics
)

from datetime import datetime


# ==========================================
# TELEMETRY MANAGER
# ==========================================

class TelemetryManager:

    def __init__(self):

        self.trace_logger = (
            TraceLogger()
        )

        self.runtime_metrics = (
            RuntimeMetrics()
        )

    # ==========================================
    # START WORKFLOW
    # ==========================================

    def start_workflow(self):

        self.runtime_metrics.start_workflow_timer()

    # ==========================================
    # STOP WORKFLOW
    # ==========================================

    def stop_workflow(self):

        self.runtime_metrics.stop_workflow_timer()

    # ==========================================
    # LOG NODE EXECUTION
    # ==========================================

    def log_node_execution(
        self,
        state,
        node_name: str,
        started_at,
        completed_at,
        status="completed"
    ):

        duration = (
            completed_at - started_at
        ).total_seconds()

        trace = (
            self.trace_logger.create_trace(
                node_name=node_name,
                status=status,
                started_at=(
                    started_at.isoformat()
                ),
                completed_at=(
                    completed_at.isoformat()
                ),
                duration_seconds=duration,
                reflection_count=(
                    state.reflection_count
                )
            )
        )

        state.execution_trace.append(
            trace
        )

    # ==========================================
    # GENERATE FINAL TELEMETRY
    # ==========================================

    def finalize_telemetry(
        self,
        state
    ):

        telemetry = (
            self.runtime_metrics
            .generate_metrics(
                state
            )
        )

        state.runtime_metrics = (
            telemetry
        )

        return state
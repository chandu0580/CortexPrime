from datetime import datetime


# ==========================================
# TRACE LOGGER
# ==========================================

class TraceLogger:

    def create_trace(
        self,
        node_name: str,
        status: str,
        started_at: str,
        completed_at: str,
        duration_seconds: float,
        reflection_count: int
    ):

        return {

            "node": node_name,

            "status": status,

            "started_at": started_at,

            "completed_at": completed_at,

            "duration_seconds": round(
                duration_seconds,
                2
            ),

            "reflection_count": (
                reflection_count
            ),

            "timestamp": (
                datetime.utcnow()
                .isoformat()
            )
        }
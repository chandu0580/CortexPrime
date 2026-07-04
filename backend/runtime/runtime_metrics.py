from typing import Dict, Any
from datetime import datetime


# ==========================================
# RUNTIME METRICS
# ==========================================

class RuntimeMetrics:

    def __init__(self):

        # ==========================================
        # EXECUTION
        # ==========================================

        self.total_executions = 0

        self.active_executions = 0

        self.failed_executions = 0

        self.completed_executions = 0

        # ==========================================
        # AGENTS
        # ==========================================

        self.active_agents = set()

        # ==========================================
        # TOKENS
        # ==========================================

        self.total_tokens = 0

        self.prompt_tokens = 0

        self.completion_tokens = 0

        # ==========================================
        # LATENCY
        # ==========================================

        self.total_latency_ms = 0

        self.average_latency_ms = 0

        # ==========================================
        # GOVERNANCE
        # ==========================================

        self.average_hallucination_score = 0

        self.average_confidence_score = 0

        # ==========================================
        # TIMESTAMPS
        # ==========================================

        self.runtime_started_at = (

            datetime.utcnow()
            .isoformat()
        )

        self.last_updated = (

            datetime.utcnow()
            .isoformat()
        )


    # ==========================================
    # REGISTER EXECUTION
    # ==========================================

    def register_execution_start(

        self,

        agent: str
    ):

        self.total_executions += 1

        self.active_executions += 1

        self.active_agents.add(
            agent
        )

        self.last_updated = (

            datetime.utcnow()
            .isoformat()
        )


    # ==========================================
    # REGISTER COMPLETION
    # ==========================================

    def register_execution_completed(

        self,

        latency_ms: float = 0
    ):

        self.active_executions = max(

            0,

            self.active_executions - 1
        )

        self.completed_executions += 1

        self.total_latency_ms += (
            latency_ms
        )

        # ==========================================
        # AVERAGE LATENCY
        # ==========================================

        if self.completed_executions > 0:

            self.average_latency_ms = (

                self.total_latency_ms /

                self.completed_executions
            )

        self.last_updated = (

            datetime.utcnow()
            .isoformat()
        )


    # ==========================================
    # REGISTER FAILURE
    # ==========================================

    def register_execution_failed(self):

        self.failed_executions += 1

        self.active_executions = max(

            0,

            self.active_executions - 1
        )

        self.last_updated = (

            datetime.utcnow()
            .isoformat()
        )


    # ==========================================
    # TOKEN USAGE
    # ==========================================

    def register_token_usage(

        self,

        prompt_tokens: int = 0,

        completion_tokens: int = 0
    ):

        self.prompt_tokens += (
            prompt_tokens
        )

        self.completion_tokens += (
            completion_tokens
        )

        self.total_tokens += (

            prompt_tokens +

            completion_tokens
        )

        self.last_updated = (

            datetime.utcnow()
            .isoformat()
        )


    # ==========================================
    # GOVERNANCE SCORES
    # ==========================================

    def register_governance_scores(

        self,

        hallucination_score: float,

        confidence_score: float
    ):

        self.average_hallucination_score = (
            hallucination_score
        )

        self.average_confidence_score = (
            confidence_score
        )

        self.last_updated = (

            datetime.utcnow()
            .isoformat()
        )


    # ==========================================
    # EXPORT METRICS
    # ==========================================

    def export_metrics(

        self

    ) -> Dict[str, Any]:

        return {

            "runtime_started_at":
                self.runtime_started_at,

            "last_updated":
                self.last_updated,

            "total_executions":
                self.total_executions,

            "active_executions":
                self.active_executions,

            "completed_executions":
                self.completed_executions,

            "failed_executions":
                self.failed_executions,

            "active_agents":
                list(
                    self.active_agents
                ),

            "active_agent_count":
                len(
                    self.active_agents
                ),

            "total_tokens":
                self.total_tokens,

            "prompt_tokens":
                self.prompt_tokens,

            "completion_tokens":
                self.completion_tokens,

            "average_latency_ms":
                round(
                    self.average_latency_ms,
                    2
                ),

            "average_hallucination_score":
                self.average_hallucination_score,

            "average_confidence_score":
                self.average_confidence_score
        }


# ==========================================
# SINGLETON
# ==========================================

runtime_metrics = RuntimeMetrics()
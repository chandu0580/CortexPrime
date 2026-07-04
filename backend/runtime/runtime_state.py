from typing import Dict, Any
from datetime import datetime


# ==========================================
# RUNTIME STATE
# ==========================================

class RuntimeState:

    def __init__(self):

        # ==========================================
        # ACTIVE EXECUTIONS
        # ==========================================

        self.active_executions = {}

        # ==========================================
        # AGENT STATES
        # ==========================================

        self.agent_states = {}

        # ==========================================
        # EXECUTION HISTORY
        # ==========================================

        self.execution_history = []

    # ==========================================
    # START EXECUTION
    # ==========================================

    def start_execution(

        self,

        execution_id: str,

        objective: str

    ):

        execution = {

            "execution_id":
                execution_id,

            "objective":
                objective,

            "status":
                "running",

            "started_at":
                datetime.utcnow()
                .isoformat()
        }

        self.active_executions[
            execution_id
        ] = execution

        self.execution_history.append(
            execution
        )

    # ==========================================
    # COMPLETE EXECUTION
    # ==========================================

    def complete_execution(

        self,

        execution_id: str

    ):

        if (

            execution_id

            in self.active_executions
        ):

            self.active_executions[
                execution_id
            ][
                "status"
            ] = "completed"

            self.active_executions[
                execution_id
            ][
                "completed_at"
            ] = (

                datetime.utcnow()
                .isoformat()
            )

    # ==========================================
    # UPDATE AGENT STATE
    # ==========================================

    def update_agent_state(

        self,

        agent_name: str,

        status: str

    ):

        self.agent_states[
            agent_name
        ] = {

            "status":
                status,

            "updated_at":
                datetime.utcnow()
                .isoformat()
        }

    # ==========================================
    # GET FULL STATE
    # ==========================================

    def get_state(self):

        return {

            "active_executions":
                self.active_executions,

            "agent_states":
                self.agent_states,

            "execution_history":
                self.execution_history
        }


# ==========================================
# GLOBAL RUNTIME STATE
# ==========================================

runtime_state = RuntimeState()
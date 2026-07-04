from typing import Dict, Any, List
from datetime import datetime

from backend.runtime.base_agent import BaseAgent

from backend.events.event_bus import (
    event_bus
)

from backend.events.event_models import (
    CognitionEvent,
    EventTypes
)

from backend.runtime.runtime_state import (
    runtime_state
)


# ==========================================
# MEMORY AGENT
# ==========================================

class MemoryAgent(BaseAgent):

    def __init__(self):

        super().__init__(
            agent_name="memory"
        )

        # ==========================================
        # MEMORY STORES
        # ==========================================

        self.working_memory: List[
            Dict[str, Any]
        ] = []

        self.episodic_memory: List[
            Dict[str, Any]
        ] = []

    # ==========================================
    # EXECUTE
    # ==========================================

    async def execute(

        self,

        task: Dict[str, Any]

    ) -> Dict[str, Any]:

        self.set_status(
            "running"
        )

        # ==========================================
        # UPDATE RUNTIME STATE
        # ==========================================

        runtime_state.update_agent_state(

            self.agent_name,

            "running"
        )

        self.log_event(
            "Memory processing started"
        )

        content = task.get(
            "content",
            "No content provided"
        )

        timestamp = (
            datetime.utcnow()
            .isoformat()
        )

        memory_entry = {

            "content":
                content,

            "timestamp":
                timestamp
        }

        # ==========================================
        # EVENT :: MEMORY STORE START
        # ==========================================

        await event_bus.publish(

            CognitionEvent(

                agent=self.agent_name,

                event_type=(
                    EventTypes
                    .MEMORY_STORED
                ),

                status="running",

                message=(
                    "Memory storage started"
                ),

                payload={

                    "memory_entry":
                        memory_entry
                }
            )
        )

        # ==========================================
        # STORE IN WORKING MEMORY
        # ==========================================

        self.working_memory.append(
            memory_entry
        )

        # ==========================================
        # STORE IN EPISODIC MEMORY
        # ==========================================

        self.episodic_memory.append(
            memory_entry
        )

        self.log_event(
            "Memory stored successfully"
        )

        # ==========================================
        # RESPONSE
        # ==========================================

        response = {

            "status":
                "success",

            "agent":
                self.agent_name,

            "timestamp":
                timestamp,

            "working_memory_size":
                len(
                    self.working_memory
                ),

            "episodic_memory_size":
                len(
                    self.episodic_memory
                ),

            "stored_memory":
                memory_entry,

            "metadata": {

                "memory_engine":
                    "cortexprime-memory-runtime",

                "runtime_state":
                    "completed",

                "memory_persistence":
                    "enabled"
            }
        }

        # ==========================================
        # EVENT :: MEMORY COMPLETE
        # ==========================================

        await event_bus.publish(

            CognitionEvent(

                agent=self.agent_name,

                event_type=(
                    EventTypes
                    .MEMORY_RETRIEVED
                ),

                status="completed",

                message=(
                    "Memory stored successfully"
                ),

                payload={

                    "working_memory_size":
                        len(
                            self.working_memory
                        ),

                    "episodic_memory_size":
                        len(
                            self.episodic_memory
                        )
                }
            )
        )

        # ==========================================
        # UPDATE RUNTIME STATE
        # ==========================================

        runtime_state.update_agent_state(

            self.agent_name,

            "completed"
        )

        self.set_status(
            "idle"
        )

        return response

    # ==========================================
    # RETRIEVE MEMORY
    # ==========================================

    def retrieve_memory(self):

        return {

            "working_memory":
                self.working_memory,

            "episodic_memory":
                self.episodic_memory,

            "metadata": {

                "working_memory_entries":
                    len(
                        self.working_memory
                    ),

                "episodic_memory_entries":
                    len(
                        self.episodic_memory
                    )
            }
        }

    # ==========================================
    # CLEAR WORKING MEMORY
    # ==========================================

    def clear_working_memory(self):

        self.working_memory.clear()

        self.log_event(
            "Working memory cleared"
        )

        runtime_state.update_agent_state(

            self.agent_name,

            "memory_cleared"
        )
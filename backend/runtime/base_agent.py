import uuid
from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any, Dict

# ==========================================
# BASE AGENT
# ==========================================

class BaseAgent(ABC):

    def __init__(

        self,

        agent_name: str

    ):

        self.agent_id = str(
            uuid.uuid4()
        )

        self.agent_name = (
            agent_name
        )

        self.status = "idle"

        self.created_at = (
            datetime.utcnow()
        )

    # ==========================================
    # EXECUTE
    # ==========================================

    @abstractmethod
    async def execute(

        self,

        task: Dict[str, Any]

    ) -> Dict[str, Any]:

        """
        Main execution method
        """

        pass

    # ==========================================
    # SET STATUS
    # ==========================================

    def set_status(

        self,

        status: str

    ):

        self.status = status

    # ==========================================
    # GET METADATA
    # ==========================================

    def metadata(self):

        return {

            "agent_id":
                self.agent_id,

            "agent_name":
                self.agent_name,

            "status":
                self.status,

            "created_at":
                self.created_at.isoformat()
        }

    # ==========================================
    # LOG EVENT
    # ==========================================

    def log_event(

        self,

        event: str

    ):

        timestamp = (
            datetime.utcnow()
            .isoformat()
        )

        print(

            f"[{timestamp}] "

            f"[{self.agent_name}] "

            f"{event}"
        )

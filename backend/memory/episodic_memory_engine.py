from typing import Dict, Any, List
from uuid import uuid4
from datetime import datetime


from backend.events.event_bus import (
    event_bus
)

from backend.events.event_models import (
    CognitionEvent
)

from backend.tools.tool_registry import (
    tool_registry
)


# ==========================================
# EPISODIC MEMORY ENGINE
# ==========================================

class EpisodicMemoryEngine:

    def __init__(self):

        # ==========================================
        # MEMORY STORE
        # ==========================================

        self.memories: List[
            Dict[str, Any]
        ] = []

        self.max_memories = 1000


    # ==========================================
    # EVENT HELPER
    # ==========================================

    async def publish_event(

        self,

        execution_id: str,

        event_type: str,

        status: str,

        phase: str,

        message: str,

        payload: Dict[str, Any] = {}
    ):

        await event_bus.publish(

            CognitionEvent(

                agent=
                    "episodic_memory_engine",

                event_type=
                    event_type,

                status=
                    status,

                phase=
                    phase,

                execution_id=
                    execution_id,

                message=
                    message,

                payload=
                    payload
            )
        )


    # ==========================================
    # STORE MEMORY
    # ==========================================

    async def store_memory(

        self,

        payload: Dict[str, Any]

    ) -> Dict[str, Any]:

        execution_id = str(
            uuid4()
        )

        memory_content = payload.get(
            "content"
        )

        memory_type = payload.get(
            "memory_type",
            "general"
        )

        if not memory_content:

            return {

                "success": False,

                "error":
                    "Missing memory content"
            }

        # ==========================================
        # IMPORTANCE SCORE
        # ==========================================

        importance_score = (
            self.calculate_importance(
                memory_content
            )
        )

        memory = {

            "memory_id":
                str(uuid4()),

            "content":
                memory_content,

            "memory_type":
                memory_type,

            "importance_score":
                importance_score,

            "timestamp":
                datetime.utcnow()
                .isoformat()
        }

        # ==========================================
        # MEMORY LIMIT
        # ==========================================

        if len(self.memories) >= (

            self.max_memories
        ):

            self.memories = sorted(

                self.memories,

                key=lambda item:
                item[
                    "importance_score"
                ],

                reverse=True
            )[: self.max_memories - 1]

        self.memories.append(
            memory
        )

        # ==========================================
        # EVENT
        # ==========================================

        await self.publish_event(

            execution_id,

            "episodic_memory_stored",

            "completed",

            "memory_storage",

            "Stored episodic memory",

            {

                "memory_id":
                    memory["memory_id"],

                "importance_score":
                    importance_score,

                "memory_type":
                    memory_type
            }
        )

        return {

            "success": True,

            "memory":
                memory
        }


    # ==========================================
    # RECALL MEMORIES
    # ==========================================

    async def recall_memories(

        self,

        payload: Dict[str, Any]

    ) -> Dict[str, Any]:

        execution_id = str(
            uuid4()
        )

        query = payload.get(
            "query",
            ""
        )

        limit = payload.get(
            "limit",
            5
        )

        # ==========================================
        # SIMPLE SEMANTIC MATCH
        # ==========================================

        matched_memories = []

        query_lower = query.lower()

        for memory in self.memories:

            content_lower = (

                memory[
                    "content"
                ].lower()
            )

            if query_lower in content_lower:

                matched_memories.append(
                    memory
                )

        # ==========================================
        # SORT BY IMPORTANCE
        # ==========================================

        matched_memories = sorted(

            matched_memories,

            key=lambda item:
            item[
                "importance_score"
            ],

            reverse=True
        )[:limit]

        # ==========================================
        # EVENT
        # ==========================================

        await self.publish_event(

            execution_id,

            "episodic_memory_recalled",

            "completed",

            "memory_recall",

            "Recalled episodic memories",

            {

                "query":
                    query,

                "memory_count":
                    len(
                        matched_memories
                    )
            }
        )

        return {

            "success": True,

            "query":
                query,

            "memories":
                matched_memories
        }


    # ==========================================
    # MEMORY TIMELINE
    # ==========================================

    async def memory_timeline(

        self

    ) -> Dict[str, Any]:

        sorted_memories = sorted(

            self.memories,

            key=lambda item:
            item["timestamp"],

            reverse=True
        )

        return {

            "success": True,

            "timeline":
                sorted_memories
        }


    # ==========================================
    # MEMORY REFLECTION
    # ==========================================

    async def reflect_on_memories(

        self

    ) -> Dict[str, Any]:

        execution_id = str(
            uuid4()
        )

        high_value_memories = [

            memory

            for memory in self.memories

            if memory[
                "importance_score"
            ] > 0.7
        ]

        reflection = (

            f"Detected "
            f"{len(high_value_memories)} "
            f"high-value memories."
        )

        await self.publish_event(

            execution_id,

            "memory_reflection_completed",

            "completed",

            "memory_reflection",

            reflection,

            {

                "high_value_memory_count":
                    len(
                        high_value_memories
                    )
            }
        )

        return {

            "success": True,

            "reflection":
                reflection,

            "high_value_memories":
                high_value_memories
        }


    # ==========================================
    # IMPORTANCE SCORING
    # ==========================================

    def calculate_importance(

        self,

        content: str

    ) -> float:

        content_lower = (
            content.lower()
        )

        keywords = [

            "critical",
            "important",
            "urgent",
            "failure",
            "success",
            "research",
            "strategy",
            "mission"
        ]

        score = 0.2

        for keyword in keywords:

            if keyword in content_lower:

                score += 0.1

        return min(score, 1.0)


    # ==========================================
    # MEMORY COUNT
    # ==========================================

    def memory_count(self) -> int:

        return len(
            self.memories
        )


# ==========================================
# SINGLETON
# ==========================================

episodic_memory_engine = (
    EpisodicMemoryEngine()
)


# ==========================================
# REGISTER TOOLS
# ==========================================

tool_registry.register_tool(

    name="episodic_store_memory",

    description=
        "Store episodic memories",

    handler=
        episodic_memory_engine.store_memory,

    tool_type=
        "memory"
)

tool_registry.register_tool(

    name="episodic_recall_memory",

    description=
        "Recall episodic memories",

    handler=
        episodic_memory_engine.recall_memories,

    tool_type=
        "memory"
)

tool_registry.register_tool(

    name="episodic_memory_reflection",

    description=
        "Reflect on stored memories",

    handler=
        episodic_memory_engine.reflect_on_memories,

    tool_type=
        "memory"
)
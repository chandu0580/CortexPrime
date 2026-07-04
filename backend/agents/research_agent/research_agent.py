from typing import Dict, Any
from datetime import datetime
from uuid import uuid4

from backend.runtime.base_agent import BaseAgent

from backend.providers.openai_provider import (
    openai_provider
)

from backend.providers.tavily_provider import (
    tavily_provider
)

from backend.events.event_bus import (
    event_bus
)

from backend.events.event_models import (

    CognitionEvent,

    EventTypes
)

from backend.research.live_research_pipeline import (
    live_research_pipeline,
)

from backend.research.tavily_client import tavily_client


# ==========================================
# RESEARCH AGENT
# ==========================================

class ResearchAgent(BaseAgent):

    def __init__(self):

        super().__init__(

            agent_name="research"
        )


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

        query = task.get(

            "query",

            "No query provided"
        )

        mission_id   = task.get("mission_id")
        execution_id = str(uuid4())

        self.log_event(
            f"Researching: {query}"
        )


        # ==========================================
        # EVENT :: START
        # ==========================================

        await event_bus.publish(

            CognitionEvent(

                agent=self.agent_name,

                event_type=(
                    EventTypes
                    .RESEARCH_STARTED
                ),

                status="running",

                phase="initializing_research",

                execution_id=
                    execution_id,

                message=(
                    f"Research started for: "
                    f"{query}"
                ),

                payload={

                    "query":       query,
                    "live_search": tavily_client.is_configured(),
                }
            )
        )


        # ==========================================
        # PHASE :: LIVE SEARCH
        # ==========================================

        await event_bus.publish(

            CognitionEvent(

                agent=self.agent_name,

                event_type=(
                    EventTypes
                    .PHASE_RESEARCHING
                ),

                status="running",

                phase="researching_sources",

                execution_id=
                    execution_id,

                message=(
                    "ResearchAgent is querying "
                    "live web intelligence sources via Tavily"
                ),

                payload={

                    "query": query
                }
            )
        )


        # ==========================================
        # LIVE RESEARCH PIPELINE
        # ==========================================

        research_result = await live_research_pipeline.run(
            query      = query,
            mission_id = mission_id,
            agent      = self.agent_name,
            force_live = True,
        )

        sources    = research_result.sources
        citations  = research_result.citations


        # ==========================================
        # PHASE :: ANALYZING
        # ==========================================

        await event_bus.publish(

            CognitionEvent(

                agent=self.agent_name,

                event_type=(
                    EventTypes
                    .PHASE_ANALYZING
                ),

                status="running",

                phase="analyzing_findings",

                execution_id=
                    execution_id,

                message=(
                    "ResearchAgent is analyzing "
                    "retrieved knowledge"
                ),

                payload={

                    "sources_found": len(sources),
                    "citations":     len(citations),
                }
            )
        )


        # ==========================================
        # STREAM SYNTHESISED RESPONSE
        # ==========================================

        await event_bus.publish(

            CognitionEvent(

                agent=self.agent_name,

                event_type=(
                    EventTypes
                    .STREAM_STARTED
                ),

                status="running",

                phase="streaming_response",

                execution_id=
                    execution_id,

                stream=True,

                message=(
                    "Streaming research synthesis"
                ),

                payload={

                    "sources_found": len(sources)
                }
            )
        )


        # Stream the already-synthesised response token by token so the
        # frontend receives real-time updates.
        full_response = research_result.annotated
        chunk_size    = 8

        for i in range(0, len(full_response), chunk_size):

            token = full_response[i : i + chunk_size]

            await event_bus.publish(

                CognitionEvent(

                    agent=self.agent_name,

                    event_type=(
                        EventTypes
                        .TOKEN_STREAM
                    ),

                    status="running",

                    phase="generating_tokens",

                    execution_id=
                        execution_id,

                    stream=True,

                    stream_chunk=
                        token,

                    message=token
                )
            )


        # ==========================================
        # STREAM COMPLETE
        # ==========================================

        await event_bus.publish(

            CognitionEvent(

                agent=self.agent_name,

                event_type=(
                    EventTypes
                    .STREAM_COMPLETED
                ),

                status="completed",

                phase="stream_completed",

                execution_id=
                    execution_id,

                stream=True,

                stream_completed=True,

                message=(
                    "Streaming completed"
                )
            )
        )


        # ==========================================
        # RESPONSE PAYLOAD
        # ==========================================

        response = {

            "status":
                "success",

            "agent":
                self.agent_name,

            "query":
                query,

            "execution_id":
                execution_id,

            "timestamp":
                datetime.utcnow()
                .isoformat(),

            "research":
                full_response,

            "synthesis":
                research_result.synthesis,

            "sources":
                sources,

            "citations":
                citations,

            "answer":
                research_result.answer,

            "source_count":
                len(sources),

            "latency_ms":
                research_result.latency_ms,

            "live_search":
                tavily_client.is_configured(),
        }


        # ==========================================
        # EVENT :: COMPLETE
        # ==========================================

        await event_bus.publish(

            CognitionEvent(

                agent=self.agent_name,

                event_type=(
                    EventTypes
                    .RESEARCH_COMPLETED
                ),

                status="completed",

                phase="research_completed",

                execution_id=
                    execution_id,

                message=(
                    f"Research completed for: "
                    f"{query}"
                ),

                payload={

                    "query":        query,
                    "result":       full_response,
                    "sources":      sources,
                    "citations":    citations,
                    "source_count": len(sources),
                }
            )
        )


        self.log_event(
            "Research completed"
        )

        self.set_status(
            "idle"
        )

        return response


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

        query = task.get(

            "query",

            "No query provided"
        )

        execution_id = str(
            uuid4()
        )

        self.log_event(
            f"Researching: {query}"
        )


        # ==========================================
        # EVENT :: START
        # ==========================================

        await event_bus.publish(

            CognitionEvent(

                agent=self.agent_name,

                event_type=(
                    EventTypes
                    .RESEARCH_STARTED
                ),

                status="running",

                phase="initializing_research",

                execution_id=
                    execution_id,

                message=(
                    f"Research started for: "
                    f"{query}"
                ),

                payload={

                    "query":
                        query
                }
            )
        )


        # ==========================================
        # PHASE :: RESEARCHING
        # ==========================================

        await event_bus.publish(

            CognitionEvent(

                agent=self.agent_name,

                event_type=(
                    EventTypes
                    .PHASE_RESEARCHING
                ),

                status="running",

                phase="researching_sources",

                execution_id=
                    execution_id,

                message=(
                    "ResearchAgent is retrieving "
                    "external intelligence sources"
                ),

                payload={

                    "query":
                        query
                }
            )
        )


        # ==========================================
        # TAVILY SEARCH
        # ==========================================

        tavily_results = await (

            tavily_provider.search(
                query=query
            )
        )

        sources = tavily_results.get(
            "results",
            []
        )


        # ==========================================
        # PHASE :: ANALYZING
        # ==========================================

        await event_bus.publish(

            CognitionEvent(

                agent=self.agent_name,

                event_type=(
                    EventTypes
                    .PHASE_ANALYZING
                ),

                status="running",

                phase="analyzing_findings",

                execution_id=
                    execution_id,

                message=(
                    "ResearchAgent is analyzing "
                    "retrieved knowledge"
                ),

                payload={

                    "sources_found":
                        len(sources)
                }
            )
        )


        # ==========================================
        # STREAM START
        # ==========================================

        await event_bus.publish(

            CognitionEvent(

                agent=self.agent_name,

                event_type=(
                    EventTypes
                    .STREAM_STARTED
                ),

                status="running",

                phase="streaming_response",

                execution_id=
                    execution_id,

                stream=True,

                message=(
                    "Streaming cognitive analysis"
                ),

                payload={

                    "sources_found":
                        len(sources)
                }
            )
        )


        # ==========================================
        # STREAMING RESPONSE
        # ==========================================

        full_response = ""

        async for token in (

            openai_provider
            .stream_response(

                prompt=f"""

                You are CortexPrime,
                an enterprise AI
                research engine.

                Use the following
                web intelligence
                sources to perform
                deep analysis.

                USER QUERY:
                {query}

                WEB SOURCES:
                {sources}

                Return:
                - Key insights
                - Technical analysis
                - Strategic observations
                - Enterprise implications
                - Future predictions

                Think step-by-step.
                """
            )
        ):

            full_response += token

            # ==========================================
            # TOKEN STREAM EVENT
            # ==========================================

            await event_bus.publish(

                CognitionEvent(

                    agent=self.agent_name,

                    event_type=(
                        EventTypes
                        .TOKEN_STREAM
                    ),

                    status="running",

                    phase="generating_tokens",

                    execution_id=
                        execution_id,

                    stream=True,

                    stream_chunk=
                        token,

                    message=token
                )
            )


        # ==========================================
        # PHASE :: SYNTHESIS
        # ==========================================

        await event_bus.publish(

            CognitionEvent(

                agent=self.agent_name,

                event_type=(
                    EventTypes
                    .PHASE_STREAMING
                ),

                status="running",

                phase="synthesizing_response",

                execution_id=
                    execution_id,

                message=(
                    "ResearchAgent is synthesizing "
                    "final intelligence response"
                )
            )
        )


        # ==========================================
        # STREAM COMPLETE
        # ==========================================

        await event_bus.publish(

            CognitionEvent(

                agent=self.agent_name,

                event_type=(
                    EventTypes
                    .STREAM_COMPLETED
                ),

                status="completed",

                phase="stream_completed",

                execution_id=
                    execution_id,

                stream=True,

                stream_completed=True,

                message=(
                    "Streaming completed"
                )
            )
        )


        # ==========================================
        # RESPONSE PAYLOAD
        # ==========================================

        response = {

            "status":
                "success",

            "agent":
                self.agent_name,

            "query":
                query,

            "execution_id":
                execution_id,

            "timestamp":
                datetime.utcnow()
                .isoformat(),

            "research":
                full_response,

            "sources":
                sources
        }


        # ==========================================
        # EVENT :: COMPLETE
        # ==========================================

        await event_bus.publish(

            CognitionEvent(

                agent=self.agent_name,

                event_type=(
                    EventTypes
                    .RESEARCH_COMPLETED
                ),

                status="completed",

                phase="research_completed",

                execution_id=
                    execution_id,

                message=(
                    f"Research completed for: "
                    f"{query}"
                ),

                payload={

                    "query":
                        query,

                    "result":
                        full_response,

                    "sources":
                        sources
                }
            )
        )


        self.log_event(
            "Research completed"
        )

        self.set_status(
            "idle"
        )

        return response
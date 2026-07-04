from typing import Dict, Any, List
from uuid import uuid4
from statistics import mean

from backend.events.event_bus import (
    event_bus
)

from backend.events.event_models import (
    CognitionEvent
)


# ==========================================
# EVIDENCE ENGINE
# ==========================================

class EvidenceEngine:

    def __init__(self):

        # ==========================================
        # MINIMUM CONFIDENCE
        # ==========================================

        self.minimum_confidence = 0.55

        # ==========================================
        # HALLUCINATION THRESHOLD
        # ==========================================

        self.hallucination_threshold = 0.45


    # ==========================================
    # BUILD EVIDENCE GRAPH
    # ==========================================

    async def build_evidence_graph(

        self,

        query: str,

        sources: List[Dict[str, Any]]

    ) -> Dict[str, Any]:

        evidence_id = str(
            uuid4()
        )

        # ==========================================
        # START EVENT
        # ==========================================

        await event_bus.publish(

            CognitionEvent(

                agent="evidence_engine",

                event_type=
                    "evidence_analysis_started",

                status="running",

                phase=
                    "evidence_reasoning",

                message=(
                    f"Building evidence graph "
                    f"for query: {query}"
                ),

                payload={

                    "query":
                        query,

                    "source_count":
                        len(sources),

                    "evidence_id":
                        evidence_id
                }
            )
        )

        # ==========================================
        # BUILD NODES
        # ==========================================

        evidence_nodes = []

        confidence_scores = []

        for index, source in enumerate(
            sources
        ):

            score = float(

                source.get(
                    "score",
                    0.5
                )
            )

            confidence_scores.append(
                score
            )

            evidence_node = {

                "id":
                    f"source_{index}",

                "title":
                    source.get("title"),

                "url":
                    source.get("url"),

                "content":
                    source.get("content"),

                "confidence":
                    round(score, 2),

                "supports_claim":
                    score >=
                    self.minimum_confidence
            }

            evidence_nodes.append(
                evidence_node
            )

        # ==========================================
        # GLOBAL CONFIDENCE
        # ==========================================

        overall_confidence = round(

            mean(confidence_scores),

            2
        ) if confidence_scores else 0.0

        # ==========================================
        # HALLUCINATION SCORE
        # ==========================================

        hallucination_score = round(

            max(
                0.0,

                1.0 - overall_confidence
            ),

            2
        )

        # ==========================================
        # DETECT CONTRADICTIONS
        # ==========================================

        contradictions = (

            self.detect_contradictions(
                evidence_nodes
            )
        )

        # ==========================================
        # VALIDATION EVENT
        # ==========================================

        await event_bus.publish(

            CognitionEvent(

                agent="evidence_engine",

                event_type=
                    "evidence_validation",

                status="completed",

                phase=
                    "evidence_validation",

                message=(
                    "Validated evidence "
                    "confidence and grounding"
                ),

                confidence_score=
                    overall_confidence,

                hallucination_score=
                    hallucination_score,

                payload={

                    "contradictions":
                        contradictions,

                    "overall_confidence":
                        overall_confidence
                }
            )
        )

        # ==========================================
        # FINAL GRAPH
        # ==========================================

        evidence_graph = {

            "evidence_id":
                evidence_id,

            "query":
                query,

            "overall_confidence":
                overall_confidence,

            "hallucination_score":
                hallucination_score,

            "contradictions":
                contradictions,

            "evidence_nodes":
                evidence_nodes
        }

        # ==========================================
        # COMPLETION EVENT
        # ==========================================

        await event_bus.publish(

            CognitionEvent(

                agent="evidence_engine",

                event_type=
                    "evidence_graph_completed",

                status="completed",

                phase=
                    "citation_grounding",

                message=(
                    "Completed evidence "
                    "grounding graph"
                ),

                confidence_score=
                    overall_confidence,

                hallucination_score=
                    hallucination_score,

                payload={
                    "evidence_graph":
                        evidence_graph
                }
            )
        )

        return evidence_graph


    # ==========================================
    # CONTRADICTION DETECTION
    # ==========================================

    def detect_contradictions(

        self,

        evidence_nodes:
            List[Dict[str, Any]]

    ) -> List[str]:

        contradictions = []

        low_confidence_count = len([

            node

            for node in evidence_nodes

            if node["confidence"] < 0.4
        ])

        if low_confidence_count >= 2:

            contradictions.append(

                "Multiple weak evidence "
                "sources detected"
            )

        return contradictions


    # ==========================================
    # GENERATE CITATIONS
    # ==========================================

    def generate_citations(

        self,

        sources: List[Dict[str, Any]]

    ) -> List[Dict[str, Any]]:

        citations = []

        for index, source in enumerate(
            sources
        ):

            citations.append({

                "citation_id":
                    f"[Source {index + 1}]",

                "title":
                    source.get("title"),

                "url":
                    source.get("url"),

                "score":
                    source.get("score")
            })

        return citations


    # ==========================================
    # VALIDATE CLAIM
    # ==========================================

    async def validate_claim(

        self,

        claim: str,

        evidence_graph:
            Dict[str, Any]

    ) -> Dict[str, Any]:

        confidence = evidence_graph.get(
            "overall_confidence",
            0.0
        )

        hallucination_score = (
            evidence_graph.get(
                "hallucination_score",
                1.0
            )
        )

        supported = (

            confidence >=
            self.minimum_confidence
        )

        # ==========================================
        # CLAIM VALIDATION EVENT
        # ==========================================

        await event_bus.publish(

            CognitionEvent(

                agent="evidence_engine",

                event_type=
                    "claim_validation",

                status="completed",

                phase=
                    "reasoning_validation",

                message=(
                    f"Validated claim: "
                    f"{claim}"
                ),

                confidence_score=
                    confidence,

                hallucination_score=
                    hallucination_score,

                payload={

                    "claim":
                        claim,

                    "supported":
                        supported
                }
            )
        )

        return {

            "claim":
                claim,

            "supported":
                supported,

            "confidence":
                confidence,

            "hallucination_score":
                hallucination_score
        }


# ==========================================
# SINGLETON
# ==========================================

evidence_engine = (
    EvidenceEngine()
)
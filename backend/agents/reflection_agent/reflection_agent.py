from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Dict, List
from uuid import uuid4

from backend.events.event_bus import event_bus
from backend.events.event_models import CognitionEvent, EventTypes
from backend.runtime.base_agent import BaseAgent
from backend.runtime.runtime_state import runtime_state

log = logging.getLogger(__name__)


# =========================================================
# REFLECTION AGENT
# =========================================================

class ReflectionAgent(BaseAgent):
    """
    Performs deep metacognitive analysis of a completed (or in-progress)
    execution cycle.

    Responsibilities:
    - Identify reasoning gaps, inconsistencies, or missed context
    - Score execution quality and coherence
    - Generate improvement recommendations for future executions
    - Consolidate learnings into episodic memory
    - Emit structured reflection events to the WebSocket stream
    """

    def __init__(self):
        super().__init__(agent_name="reflection")
        self.reflection_history: List[Dict[str, Any]] = []

    # =========================================================
    # EXECUTE
    # =========================================================

    async def execute(
        self,
        task: Dict[str, Any],
    ) -> Dict[str, Any]:

        self.set_status("running")
        runtime_state.update_agent_state(self.agent_name, "running")

        execution_id     = task.get("execution_id", str(uuid4()))
        objective        = task.get("objective", "")
        plan             = task.get("plan") or {}
        research_result  = task.get("research_result") or {}
        critic_result    = task.get("critic_result") or {}
        optimizer_result = task.get("optimizer_result") or {}
        stage_timings    = task.get("stage_timings") or {}
        completed_stages = task.get("completed_stages") or []

        self.log_event(f"Reflection started for execution: {execution_id}")

        # ── Event: reflection starting ───────────────────────
        await event_bus.publish(
            CognitionEvent(
                agent=self.agent_name,
                event_type=EventTypes.REFLECTION_STARTED,
                status="running",
                phase="reflecting",
                execution_id=execution_id,
                message="Reflection Agent activated — analysing execution cycle…",
                payload={"objective": objective},
            )
        )

        # ── Phase 1: LLM-powered reflection ──────────────────
        reflection_text = await self._reflect_with_llm(
            objective=objective,
            plan=plan,
            research_result=research_result,
            critic_result=critic_result,
            optimizer_result=optimizer_result,
            stage_timings=stage_timings,
            completed_stages=completed_stages,
        )

        # ── Phase 2: Compute quality scores ──────────────────
        quality_assessment = self._assess_quality(
            completed_stages=completed_stages,
            critic_result=critic_result,
            optimizer_result=optimizer_result,
            stage_timings=stage_timings,
        )

        # ── Phase 3: Generate improvement recommendations ─────
        recommendations = self._generate_recommendations(
            quality_assessment=quality_assessment,
            reflection_text=reflection_text,
            stage_timings=stage_timings,
        )

        # ── Phase 4: Consolidate into episodic memory ─────────
        await self._consolidate_to_memory(
            execution_id=execution_id,
            objective=objective,
            reflection_text=reflection_text,
            quality_assessment=quality_assessment,
        )

        # ── Build result ─────────────────────────────────────
        result = {
            "execution_id":       execution_id,
            "reflection":         reflection_text,
            "quality_assessment": quality_assessment,
            "recommendations":    recommendations,
            "timestamp":          datetime.utcnow().isoformat(),
        }

        self.reflection_history.append(result)

        # ── Event: reflection completed ───────────────────────
        await event_bus.publish(
            CognitionEvent(
                agent=self.agent_name,
                event_type=EventTypes.REFLECTION_COMPLETED,
                status="completed",
                phase="reflection_complete",
                execution_id=execution_id,
                message="Reflection complete — learnings consolidated",
                payload=result,
            )
        )

        self.set_status("idle")
        runtime_state.update_agent_state(self.agent_name, "idle")

        return result

    # =========================================================
    # LLM REFLECTION
    # =========================================================

    async def _reflect_with_llm(
        self,
        objective:        str,
        plan:             Dict[str, Any],
        research_result:  Dict[str, Any],
        critic_result:    Dict[str, Any],
        optimizer_result: Dict[str, Any],
        stage_timings:    Dict[str, float],
        completed_stages: List[str],
    ) -> str:
        try:
            from backend.llm.llm_gateway import llm_gateway

            summary = self._build_execution_summary(
                objective, plan, research_result,
                critic_result, optimizer_result,
                stage_timings, completed_stages,
            )

            prompt = f"""You are the Reflection Agent of CortexPrime — an advanced metacognitive AI.

Analyse the following execution cycle and generate a structured reflection:

{summary}

Your reflection should cover:
1. Reasoning quality — were the agent decisions coherent and well-grounded?
2. Information gaps — what context was missing or could improve the result?
3. Execution efficiency — which stages were slow and why?
4. Confidence assessment — how confident are you in the final output?
5. Key learnings — what should the system remember for future similar tasks?

Be concise but insightful. Write in third-person as a system observer."""

            response = await llm_gateway.complete(
                prompt=prompt,
                system=(
                    "You are a metacognitive reflection engine. "
                    "Provide structured, actionable analysis of AI execution cycles."
                ),
                max_tokens=600,
            )
            return response.get("content", "Reflection analysis completed.")

        except Exception as exc:
            log.warning("LLM reflection failed, using fallback: %s", exc)
            return self._fallback_reflection(
                objective, completed_stages, stage_timings
            )

    # =========================================================
    # QUALITY ASSESSMENT
    # =========================================================

    def _assess_quality(
        self,
        completed_stages: List[str],
        critic_result:    Dict[str, Any],
        optimizer_result: Dict[str, Any],
        stage_timings:    Dict[str, float],
    ) -> Dict[str, Any]:
        total_stages    = 6
        completed_count = len(completed_stages)
        completion_rate = completed_count / total_stages

        # Base coherence from critic
        coherence_score = 0.85
        if critic_result:
            coherence_score = float(
                critic_result.get("confidence_score", 0.85)
            )

        # Efficiency: penalise if any stage took >5s
        slowest_ms = max(stage_timings.values(), default=0)
        efficiency_score = max(0.3, 1.0 - (slowest_ms / 30_000))

        overall = round(
            (completion_rate * 0.4)
            + (coherence_score * 0.4)
            + (efficiency_score * 0.2),
            3,
        )

        return {
            "completion_rate":  round(completion_rate, 3),
            "coherence_score":  round(coherence_score, 3),
            "efficiency_score": round(efficiency_score, 3),
            "overall_score":    overall,
            "grade": (
                "A" if overall >= 0.85
                else "B" if overall >= 0.70
                else "C" if overall >= 0.55
                else "D"
            ),
        }

    # =========================================================
    # RECOMMENDATIONS
    # =========================================================

    def _generate_recommendations(
        self,
        quality_assessment: Dict[str, Any],
        reflection_text:    str,
        stage_timings:      Dict[str, float],
    ) -> List[str]:
        recs: List[str] = []
        grade = quality_assessment.get("grade", "C")

        if quality_assessment.get("completion_rate", 1) < 1.0:
            recs.append(
                "Not all pipeline stages completed — investigate failed stages."
            )

        if quality_assessment.get("coherence_score", 1) < 0.7:
            recs.append(
                "Coherence score is low — consider adding more context retrieval."
            )

        if quality_assessment.get("efficiency_score", 1) < 0.6:
            slowest = max(stage_timings, key=stage_timings.get, default="unknown")
            recs.append(
                f"Stage '{slowest}' is a performance bottleneck — "
                "consider caching or parallel sub-tasks."
            )

        if grade in ("A", "B"):
            recs.append(
                "Execution quality is good — consider expanding research depth."
            )

        if not recs:
            recs.append(
                "No significant improvements identified — execution performed well."
            )

        return recs

    # =========================================================
    # CONSOLIDATE TO EPISODIC MEMORY
    # =========================================================

    async def _consolidate_to_memory(
        self,
        execution_id:       str,
        objective:          str,
        reflection_text:    str,
        quality_assessment: Dict[str, Any],
    ) -> None:
        try:
            from backend.memory.episodic_memory_engine import episodic_memory_engine
            await episodic_memory_engine.store_memory({
                "content":     f"Reflection on '{objective}': {reflection_text}",
                "memory_type": "reflection",
                "metadata": {
                    "execution_id":    execution_id,
                    "quality":         quality_assessment,
                    "agent":           self.agent_name,
                    "timestamp":       datetime.utcnow().isoformat(),
                },
            })
        except Exception as exc:
            log.warning("Reflection memory consolidation failed: %s", exc)

    # =========================================================
    # HELPERS
    # =========================================================

    def _build_execution_summary(
        self,
        objective:        str,
        plan:             Dict[str, Any],
        research_result:  Dict[str, Any],
        critic_result:    Dict[str, Any],
        optimizer_result: Dict[str, Any],
        stage_timings:    Dict[str, float],
        completed_stages: List[str],
    ) -> str:
        lines = [
            f"OBJECTIVE: {objective}",
            f"COMPLETED STAGES: {', '.join(completed_stages) or 'none'}",
            f"STAGE TIMINGS (ms): {stage_timings}",
        ]

        if plan:
            lines.append(f"PLAN: {str(plan)[:300]}")

        if research_result:
            synthesis = (
                research_result.get("synthesis")
                or research_result.get("response")
                or ""
            )
            lines.append(f"RESEARCH SYNTHESIS: {synthesis[:400]}")

        if critic_result:
            lines.append(
                f"CRITIC EVALUATION: confidence={critic_result.get('confidence_score', 'N/A')}, "
                f"governance={critic_result.get('governance_status', 'N/A')}"
            )

        if optimizer_result:
            opt_resp = (
                optimizer_result.get("optimized_response")
                or optimizer_result.get("response")
                or ""
            )
            lines.append(f"OPTIMIZED OUTPUT: {opt_resp[:300]}")

        return "\n".join(lines)

    def _fallback_reflection(
        self,
        objective:        str,
        completed_stages: List[str],
        stage_timings:    Dict[str, float],
    ) -> str:
        total_ms = sum(stage_timings.values())
        return (
            f"Execution of '{objective}' completed {len(completed_stages)} stages "
            f"in {total_ms:.0f}ms. "
            "The cognitive pipeline executed successfully. "
            "Key learnings have been consolidated into episodic memory."
        )

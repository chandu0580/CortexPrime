"""
Memory Context Service
======================
Single entry-point for the mission pipeline to interact with the full
memory system.  Handles:

  1. Pre-execution retrieval   — episodic + semantic + reflection recall
  2. Context building          — formats retrieved memories for prompt injection
  3. Semantic fact extraction  — extracts user-stated facts from queries and
                                 stores them as semantic knowledge so CortexPrime
                                 "remembers" them across conversations
  4. Post-execution storage    — stores mission result to episodic memory
  5. Reflection generation     — generates and stores a post-mission reflection

All operations are non-fatal.  If the full memory stack (PostgreSQL /
pgvector) is unavailable we fall back to ChromaDB or return empty context.

WebSocket events emitted:
  memory_retrieval_started  — before search
  memory_retrieved          — ranked results ready
  memory_ranked             — ranking complete with scores
  reflection_loaded         — past reflections found
  context_built             — formatted context ready for agents
"""
from __future__ import annotations

import asyncio
import logging
import re
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Lazy imports — memory subsystems may be unavailable in minimal deployments
# ---------------------------------------------------------------------------

def _get_orchestrator():
    from backend.memory.memory_orchestrator import memory_orchestrator
    return memory_orchestrator

def _get_vector_memory():
    from backend.memory.vector_memory import vector_memory
    return vector_memory

def _get_event_bus():
    from backend.events.event_bus import event_bus
    from backend.events.event_models import CognitionEvent
    return event_bus, CognitionEvent


# ---------------------------------------------------------------------------
# Context formatting constants
# ---------------------------------------------------------------------------

MAX_EPISODIC_CHARS  = 1200
MAX_SEMANTIC_CHARS  = 800
MAX_REFLECTION_CHARS = 600


# =========================================================================
# CONTEXT BUILDER
# =========================================================================

class MemoryContextService:
    """
    Orchestrates memory retrieval and context assembly for mission execution.
    """

    # ─────────────────────────────────────────────────────────────────────
    # 1.  PRE-EXECUTION RETRIEVAL
    # ─────────────────────────────────────────────────────────────────────

    async def retrieve_for_mission(
        self,
        objective:   str,
        session_id:  str,
        execution_id: str,
        ws_session_id: Optional[str] = None,
    ) -> "MissionMemoryContext":
        """
        Retrieve and rank all relevant memories for a mission.
        Returns a MissionMemoryContext with formatted strings ready to inject
        into agent prompts.
        """
        await self._emit("memory_retrieval_started", execution_id,
                         "Searching memory stores for relevant context",
                         {"objective": objective[:100]}, ws_session_id)

        episodic_snippets:  List[str] = []
        semantic_snippets:  List[str] = []
        reflection_snippets: List[str] = []
        retrieval_stats: Dict[str, int] = {}

        # ── Full orchestrator retrieval (pgvector) ────────────────────────
        try:
            orch = _get_orchestrator()

            # Initialize session if new
            asyncio.ensure_future(
                orch.init_session(session_id, objective=objective,
                                  agents=["planner","research","critic","orchestrator"])
            )

            # Parallel retrieval
            ctx, memories = await asyncio.gather(
                orch.retrieve_context(session_id, query=objective),
                orch.search_memories(objective, n=8),
                return_exceptions=True,
            )

            if not isinstance(ctx, Exception) and ctx is not None:
                # Format episodic entries
                for ep in ctx.episodic[:5]:
                    snippet = f"[{ep.agent}] {ep.content[:300]}"
                    if ep.relevance:
                        snippet += f"  (relevance: {ep.relevance:.2f})"
                    episodic_snippets.append(snippet)
                retrieval_stats["episodic"] = len(ctx.episodic)

                # Format semantic entries
                for sm in ctx.semantic[:4]:
                    snippet = f"{sm.concept}: {sm.content[:250]}"
                    if sm.confidence < 1.0:
                        snippet += f"  (confidence: {sm.confidence:.0%})"
                    semantic_snippets.append(snippet)
                retrieval_stats["semantic"] = len(ctx.semantic)

                # Format reflections
                for rf in ctx.reflections[:3]:
                    snippet = f"[{rf.agent}] {rf.reflection[:200]}"
                    if rf.score:
                        snippet += f"  (score: {rf.score:.2f})"
                    reflection_snippets.append(snippet)
                retrieval_stats["reflections"] = len(ctx.reflections)

        except Exception as err:
            log.warning("MemoryOrchestrator retrieval failed: %s", err)

        # ── ChromaDB fallback if pgvector returned nothing ────────────────
        if not episodic_snippets:
            try:
                vm = _get_vector_memory()
                coll_size = vm.get_memory_count()
                if coll_size > 0:
                    limit = max(1, min(4, coll_size))
                    raw = vm.search_memories(query=objective, limit=limit)
                    if isinstance(raw, dict):
                        docs = raw.get("documents", [[]])
                        docs = docs[0] if docs and isinstance(docs[0], list) else docs
                        for d in docs[:3]:
                            episodic_snippets.append(f"[vector_memory] {str(d)[:300]}")
                        retrieval_stats["chroma"] = len(docs)
            except Exception as err:
                log.warning("ChromaDB fallback failed: %s", err)

        total = sum(retrieval_stats.values())

        await self._emit("memory_retrieved", execution_id,
                         f"Retrieved {total} memory items across all stores",
                         {"stats": retrieval_stats, "total": total}, ws_session_id)

        # ── Ranking notification ──────────────────────────────────────────
        await self._emit("memory_ranked", execution_id,
                         "Memories ranked by relevance and recency",
                         {"episodic": len(episodic_snippets),
                          "semantic": len(semantic_snippets),
                          "reflections": len(reflection_snippets)}, ws_session_id)

        if reflection_snippets:
            await self._emit("reflection_loaded", execution_id,
                             f"{len(reflection_snippets)} reflections loaded — applying lessons learned",
                             {"count": len(reflection_snippets)}, ws_session_id)

        # ── Build formatted context ───────────────────────────────────────
        context = MissionMemoryContext(
            episodic    = episodic_snippets,
            semantic    = semantic_snippets,
            reflections = reflection_snippets,
            stats       = retrieval_stats,
        )

        await self._emit("context_built", execution_id,
                         "Memory context assembled and ready for agents",
                         {"context_tokens_approx": len(context.full_context) // 4}, ws_session_id)

        return context

    # ─────────────────────────────────────────────────────────────────────
    # 2.  SEMANTIC FACT EXTRACTION
    # ─────────────────────────────────────────────────────────────────────

    async def extract_and_store_facts(
        self,
        text:       str,
        session_id: str,
        source:     str = "user_query",
    ) -> List[str]:
        """
        Extract user-stated facts from a query and store them as semantic knowledge.
        E.g. "My project is CortexPrime" → stores concept="user_project" content="CortexPrime"

        Returns list of stored memory IDs.
        """
        facts = _extract_facts(text)
        if not facts:
            return []

        stored_ids: List[str] = []
        try:
            orch = _get_orchestrator()
            for concept, content in facts:
                mem_id = await orch.store_semantic_knowledge(
                    concept    = concept,
                    content    = content,
                    agent      = "system",
                    source     = source,
                    confidence = 0.9,
                    metadata   = {"session_id": session_id, "extracted_at": datetime.now(timezone.utc).isoformat()},
                )
                stored_ids.append(mem_id)
                log.info("Semantic fact stored: %s → %s  (id=%s)", concept, content[:60], mem_id[:8])
        except Exception as err:
            log.warning("Semantic fact extraction storage failed: %s", err)

        return stored_ids

    # ─────────────────────────────────────────────────────────────────────
    # 3.  POST-EXECUTION STORAGE
    # ─────────────────────────────────────────────────────────────────────

    async def store_mission_result(
        self,
        objective:    str,
        response:     str,
        execution_id: str,
        session_id:   str,
        confidence:   float,
        plan_text:    str = "",
        research_text: str = "",
    ) -> Optional[str]:
        """
        Store the completed mission as an episodic memory AND extract semantic facts.
        Returns the memory ID.
        """
        try:
            orch = _get_orchestrator()
            mem_id = await orch.store_cognition_event(
                agent       = "orchestrator",
                event_type  = "mission_completed",
                content     = response[:1000],
                session_id  = session_id,
                mission_id  = execution_id,
                metadata    = {
                    "objective":  objective[:200],
                    "confidence": confidence,
                    "plan":       plan_text[:300],
                    "research":   research_text[:300],
                },
            )

            # Extract and store semantic facts from the objective itself
            asyncio.ensure_future(
                self.extract_and_store_facts(objective, session_id, source="mission_objective")
            )

            # Store key insights from the response as semantic knowledge
            asyncio.ensure_future(
                self._store_response_knowledge(objective, response, session_id, execution_id)
            )

            return mem_id
        except Exception as err:
            log.warning("Mission result storage failed (non-fatal): %s", err)
            return None

    async def _store_response_knowledge(
        self,
        objective:    str,
        response:     str,
        session_id:   str,
        execution_id: str,
    ) -> None:
        """Store a condensed semantic summary of the mission Q&A pair."""
        try:
            if len(response) < 50:
                return
            orch = _get_orchestrator()
            await orch.store_semantic_knowledge(
                concept    = f"mission_knowledge_{execution_id[:8]}",
                content    = f"Q: {objective[:150]}\nA: {response[:400]}",
                agent      = "orchestrator",
                source     = f"execution:{execution_id}",
                confidence = 0.85,
                metadata   = {"session_id": session_id, "execution_id": execution_id},
            )
        except Exception as err:
            log.debug("Response knowledge storage failed: %s", err)

    # ─────────────────────────────────────────────────────────────────────
    # 4.  REFLECTION GENERATION
    # ─────────────────────────────────────────────────────────────────────

    async def generate_and_store_reflection(
        self,
        objective:    str,
        response:     str,
        plan_text:    str,
        research_text: str,
        confidence:   float,
        execution_id: str,
        session_id:   str,
        ws_session_id: Optional[str] = None,
    ) -> Optional[str]:
        """
        Generate a structured reflection on the completed mission and store it.
        The reflection captures lessons learned, confidence analysis, and
        optimization hints for future similar missions.
        """
        try:
            from backend.llm.llm_gateway import llm_gateway

            reflection_prompt = (
                f"Mission objective: {objective}\n\n"
                f"Confidence score: {confidence:.2f}\n\n"
                f"Plan summary: {plan_text[:300]}\n\n"
                f"Research summary: {research_text[:300]}\n\n"
                "Generate a concise structured reflection (max 200 words) covering:\n"
                "1. What went well in this mission\n"
                "2. What could be improved\n"
                "3. Key lessons learned for similar future missions\n"
                "4. A one-line optimization hint\n\n"
                "Format: Plain text, no markdown headers."
            )

            result = await llm_gateway.generate_azure(
                prompt        = reflection_prompt,
                agent_type    = "runtime",
                system_prompt = "You are a metacognitive reflection agent. Be concise and specific.",
            )
            reflection_text = result.get("output", "") if result.get("success") else ""

            if not reflection_text:
                # Simple fallback reflection
                reflection_text = (
                    f"Mission '{objective[:80]}' completed with {confidence:.0%} confidence. "
                    f"Plan had {len(plan_text.split(chr(10)))} steps. "
                    f"Research produced {len(research_text.split())} words of context. "
                    f"{'High confidence suggests good retrieval.' if confidence > 0.8 else 'Lower confidence — may benefit from more research.'}"
                )

            orch = _get_orchestrator()
            mem_id = await orch.store_reflection(
                agent      = "orchestrator",
                reflection = reflection_text,
                mission_id = execution_id,
                score      = confidence,
                metadata   = {
                    "objective":   objective[:200],
                    "session_id":  session_id,
                    "ws_session":  ws_session_id or "global",
                },
            )

            await self._emit("REFLECTION_STORED", execution_id,
                             "Mission reflection generated and stored",
                             {"memory_id": mem_id, "score": confidence}, ws_session_id)

            log.info("Reflection stored: id=%s score=%.2f", mem_id[:8], confidence)
            return mem_id

        except Exception as err:
            log.warning("Reflection generation failed (non-fatal): %s", err)
            return None

    # ─────────────────────────────────────────────────────────────────────
    # INTERNAL HELPERS
    # ─────────────────────────────────────────────────────────────────────

    async def _emit(
        self,
        event_type:   str,
        execution_id: str,
        message:      str,
        payload:      Dict[str, Any] | None = None,
        session_id:   str | None = None,
    ) -> None:
        try:
            event_bus, CognitionEvent = _get_event_bus()
            await event_bus.publish(CognitionEvent(
                agent        = "memory",
                event_type   = event_type,
                status       = "running",
                phase        = event_type,
                execution_id = execution_id,
                message      = message,
                payload      = payload or {},
                session_id   = session_id,
            ))
        except Exception as err:
            log.debug("Memory event emit failed: %s", err)


# =========================================================================
# MISSION MEMORY CONTEXT  (result object)
# =========================================================================

class MissionMemoryContext:
    """
    Holds retrieved memory snippets formatted for agent prompt injection.
    """

    def __init__(
        self,
        episodic:    List[str],
        semantic:    List[str],
        reflections: List[str],
        stats:       Dict[str, int],
    ):
        self.episodic    = episodic
        self.semantic    = semantic
        self.reflections = reflections
        self.stats       = stats

    @property
    def has_context(self) -> bool:
        return bool(self.episodic or self.semantic or self.reflections)

    @property
    def episodic_context(self) -> str:
        """Formatted episodic memory block for prompt injection."""
        if not self.episodic:
            return "No previous interactions found."
        text = "\n".join(f"• {s}" for s in self.episodic)
        return text[:MAX_EPISODIC_CHARS]

    @property
    def semantic_context(self) -> str:
        """Formatted semantic knowledge block for prompt injection."""
        if not self.semantic:
            return "No stored knowledge available."
        text = "\n".join(f"• {s}" for s in self.semantic)
        return text[:MAX_SEMANTIC_CHARS]

    @property
    def reflection_context(self) -> str:
        """Formatted reflection hints for prompt injection."""
        if not self.reflections:
            return "No prior reflections for this topic."
        text = "\n".join(f"• {s}" for s in self.reflections)
        return text[:MAX_REFLECTION_CHARS]

    @property
    def full_context(self) -> str:
        """
        Complete context block injected into agent system prompts.
        Used for planner + researcher + critic.
        """
        if not self.has_context:
            return "No prior memory context available."

        parts: List[str] = []
        if self.episodic:
            parts.append(f"PREVIOUS INTERACTIONS:\n{self.episodic_context}")
        if self.semantic:
            parts.append(f"KNOWN FACTS:\n{self.semantic_context}")
        if self.reflections:
            parts.append(f"LESSONS LEARNED:\n{self.reflection_context}")

        return "\n\n".join(parts)

    @property
    def planner_injection(self) -> str:
        """Compact context for the planner — focus on previous plans and facts."""
        sections: List[str] = []
        if self.semantic:
            sections.append(f"Known facts:\n{self.semantic_context}")
        if self.reflections:
            sections.append(f"Past lessons:\n{self.reflection_context}")
        if self.episodic:
            # Just the most recent episodic entry for the planner
            sections.append(f"Recent context:\n• {self.episodic[0]}")
        return "\n\n".join(sections) if sections else ""

    @property
    def researcher_injection(self) -> str:
        """Context for the researcher — emphasize episodic + semantic."""
        return self.full_context

    @property
    def critic_injection(self) -> str:
        """Context for the critic — focus on reflections and confidence patterns."""
        if self.reflections:
            return f"Relevant reflections and lessons:\n{self.reflection_context}"
        return ""

    def summary_line(self) -> str:
        total = sum(self.stats.values())
        return f"{total} memories ({self.stats})"


# =========================================================================
# FACT EXTRACTION
# =========================================================================

# Patterns for extracting user-stated facts
_FACT_PATTERNS: List[Tuple[re.Pattern, str, int]] = [
    # "my project is X"
    (re.compile(r"my project (?:is|:|=)\s*(.+)", re.I), "user_project", 1),
    # "I'm working on X" / "I am working on X"
    (re.compile(r"i(?:'m| am) working on\s+(.+)", re.I), "user_current_work", 1),
    # "my name is X"
    (re.compile(r"my name is\s+(.+)", re.I), "user_name", 1),
    # "I prefer X" / "I like X"
    (re.compile(r"i (?:prefer|like|use|want)\s+(.+)", re.I), "user_preference", 1),
    # "use X for Y"
    (re.compile(r"use\s+(\w[\w\s]{0,30})\s+for\s+(.+)", re.I), "technology_choice", 1),
    # "my team is X" / "our team is X"
    (re.compile(r"(?:my|our) team (?:is|uses|prefers)\s+(.+)", re.I), "team_context", 1),
    # "the project is called X"
    (re.compile(r"(?:the project|it) is called\s+(.+)", re.I), "project_name", 1),
    # "I'm building X"
    (re.compile(r"i(?:'m| am) building\s+(.+)", re.I), "user_building", 1),
    # "remember that X"
    (re.compile(r"remember that\s+(.+)", re.I), "user_reminder", 1),
]


def _extract_facts(text: str) -> List[Tuple[str, str]]:
    """
    Extract (concept, value) pairs from user text.
    Returns a list of tuples suitable for storage in semantic memory.
    """
    facts: List[Tuple[str, str]] = []
    text_clean = text.strip()

    for pattern, concept, group in _FACT_PATTERNS:
        m = pattern.search(text_clean)
        if m:
            value = m.group(group).strip().rstrip(".,!?;:")
            if 2 <= len(value) <= 200:
                facts.append((concept, value))

    return facts


# =========================================================================
# SINGLETON
# =========================================================================

memory_context_service = MemoryContextService()

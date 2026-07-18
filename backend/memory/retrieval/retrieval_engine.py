"""
Multi-source Memory Retrieval Engine.

Combines episodic, semantic, reflection, and runtime context stores
into a single ranked AssembledContext.  All sub-retrievals run
concurrently; individual failures are caught and degraded gracefully.
"""
from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from backend.memory.models import (
    AssembledContext,
    EpisodicEntry,
)
from backend.memory.retrieval.ranking_engine import ranking_engine
from backend.memory.stores.context_store import context_store
from backend.memory.stores.episodic_store import episodic_store
from backend.memory.stores.reflection_store import reflection_store
from backend.memory.stores.semantic_store import semantic_store

logger = logging.getLogger(__name__)


@dataclass
class RetrievalConfig:
    n_episodic:     int   = 10
    n_semantic:     int   = 10
    n_reflections:  int   = 5
    min_relevance:  float = 0.3
    current_agent:  str   = ""
    half_life_h:    float = 24.0


class RetrievalEngine:
    """
    Executes parallel retrieval across all memory stores, deduplicates,
    ranks, and assembles a structured context object.
    """

    async def retrieve(
        self,
        query:      str,
        session_id: str,
        config:     Optional[RetrievalConfig] = None,
    ) -> AssembledContext:
        cfg = config or RetrievalConfig()

        # ---- Fire all retrievals concurrently ----
        (
            similar_episodic,
            session_episodic,
            semantic_results,
            reflections,
            runtime_ctx,
        ) = await asyncio.gather(
            episodic_store.search_similar(query, cfg.n_episodic),
            episodic_store.get_session(session_id, 15),
            semantic_store.search(query, cfg.n_semantic, cfg.min_relevance),
            reflection_store.get_recent(cfg.n_reflections),
            context_store.get_runtime_context(session_id),
            return_exceptions=True,
        )

        # ---- Merge episodic (recent session + similar), dedup by id ----
        seen: set[str] = set()
        merged_episodic: List[EpisodicEntry] = []

        for entry in [
            *(session_episodic  if not isinstance(session_episodic,  Exception) else []),
            *(similar_episodic  if not isinstance(similar_episodic,  Exception) else []),
        ]:
            if entry.id not in seen:
                seen.add(entry.id)
                merged_episodic.append(entry)

        # ---- Rank episodic by composite relevance ----
        merged_episodic = ranking_engine.rank(
            merged_episodic,
            current_agent=cfg.current_agent,
            top_k=cfg.n_episodic,
            half_life_h=cfg.half_life_h,
        )

        return AssembledContext(
            session_id  = session_id,
            query       = query,
            episodic    = merged_episodic,
            semantic    = semantic_results if not isinstance(semantic_results, Exception) else [],
            reflections = reflections      if not isinstance(reflections,      Exception) else [],
            active_context = (
                runtime_ctx.model_dump()
                if not isinstance(runtime_ctx, Exception)
                else {}
            ),
        )

    async def quick_search(
        self,
        query: str,
        n:     int = 5,
    ) -> List[Dict[str, Any]]:
        """
        Fast combined semantic + episodic search.
        Returns a flat list of dicts sorted by descending relevance.
        """
        sem_task = semantic_store.search(query, n)
        epi_task = episodic_store.search_similar(query, n)

        sem_r, epi_r = await asyncio.gather(
            sem_task, epi_task, return_exceptions=True
        )

        results: List[Dict[str, Any]] = []

        for e in (sem_r if not isinstance(sem_r, Exception) else []):
            results.append({
                "type":      "semantic",
                "concept":   e.concept,
                "content":   e.content,
                "relevance": e.relevance or 0.0,
            })

        for e in (epi_r if not isinstance(epi_r, Exception) else []):
            results.append({
                "type":      "episodic",
                "agent":     e.agent,
                "content":   e.content,
                "relevance": e.relevance or 0.0,
            })

        results.sort(key=lambda x: x["relevance"], reverse=True)
        return results[:n]


retrieval_engine = RetrievalEngine()

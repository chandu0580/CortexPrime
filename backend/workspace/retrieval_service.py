"""
Retrieval Service — orchestrates semantic search + citation generation.

Usage:
    context = await retrieval_service.retrieve(workspace_id, query, n_chunks=6)
    # context.chunks     — ranked RetrievedChunk list
    # context.formatted  — ready-to-inject text block
    # context.citation_map — citation_id → Citation
"""
from __future__ import annotations

import logging
from typing import List, Optional

from backend.memory.embedding_pipeline import embedding_pipeline
from backend.workspace.models import (
    Citation,
    RetrievedChunk,
    WorkspaceContext,
)
from backend.workspace.workspace_store import workspace_store

logger = logging.getLogger(__name__)


class RetrievalService:
    """Semantic + keyword search over document chunks with citation assembly."""

    async def retrieve(
        self,
        workspace_id:   str,
        query:          str,
        n_chunks:       int = 6,
        min_score:      float = 0.0,
    ) -> WorkspaceContext:
        """
        Embed the query → cosine search → fall back to keyword → build context.
        Returns WorkspaceContext (empty if nothing found).
        """
        ws = await workspace_store.get_workspace(workspace_id)
        ws_name = ws.name if ws else workspace_id

        chunks: List[RetrievedChunk] = []

        # 1. Vector search
        query_emb = await embedding_pipeline.embed(query, use_cache=True)
        if query_emb:
            chunks = await workspace_store.search(workspace_id, query_emb, n=n_chunks)
            logger.debug(f"Vector search returned {len(chunks)} chunks for '{query[:60]}'")

        # 2. Keyword fallback if vector search returned nothing
        if not chunks:
            logger.info(f"Vector search returned 0 chunks — falling back to keyword search")
            chunks = await workspace_store.keyword_search(workspace_id, query, n=n_chunks)

        # 3. Filter by minimum score
        if min_score > 0:
            chunks = [c for c in chunks if c.score >= min_score]

        # 4. Build citations and formatted block
        citations = self._build_citations(chunks)
        citation_map = {c.citation_id: c for c in citations}
        formatted = self._format_context(chunks, citations)

        return WorkspaceContext(
            workspace_id   = workspace_id,
            workspace_name = ws_name,
            chunks         = chunks,
            formatted      = formatted,
            citation_map   = citation_map,
        )

    # ── Private ─────────────────────────────────────────────────────

    def _build_citations(self, chunks: List[RetrievedChunk]) -> List[Citation]:
        citations = []
        used_docs: dict = {}  # doc_id+page → citation index
        idx = 1
        for chunk in chunks:
            key = f"{chunk.document_id}:{chunk.page_number}"
            if key not in used_docs:
                used_docs[key] = idx
                idx += 1
            cit_id = f"[{used_docs[key]}]"
            citations.append(Citation(
                citation_id = cit_id,
                filename    = chunk.filename,
                page_number = chunk.page_number,
                chunk_index = chunk.chunk_index,
                excerpt     = chunk.content[:200],
                score       = round(chunk.score, 4),
                document_id = chunk.document_id,
            ))
        return citations

    def _format_context(
        self,
        chunks:    List[RetrievedChunk],
        citations: List[Citation],
    ) -> str:
        if not chunks:
            return ""

        lines = ["WORKSPACE DOCUMENT CONTEXT:", "─" * 60]
        for chunk, cit in zip(chunks, citations):
            page_ref = f" (page {chunk.page_number})" if chunk.page_number else ""
            lines.append(
                f"\n{cit.citation_id} Source: {chunk.filename}{page_ref} "
                f"| relevance: {chunk.score:.2f}\n"
                f"{chunk.content}\n"
                f"{'─' * 40}"
            )
        return "\n".join(lines)


# =========================================================
# SINGLETON
# =========================================================

retrieval_service = RetrievalService()

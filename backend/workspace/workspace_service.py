"""
Workspace Service — main orchestration layer.

Coordinates:
  upload      → extract → chunk → embed → store
  chat        → retrieve → inject → generate → cite
  management  → CRUD on workspaces + documents
"""
from __future__ import annotations

import logging
import os
from typing import Any, Dict, List, Optional

from backend.memory.embedding_pipeline import embedding_pipeline
from backend.workspace.chunking_engine import chunk_pages
from backend.workspace.document_processor import document_processor
from backend.workspace.models import (
    Workspace,
    WorkspaceChatRequest,
    WorkspaceChatResponse,
    WorkspaceDocument,
)
from backend.workspace.retrieval_service import retrieval_service
from backend.workspace.workspace_store import workspace_store

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────────────────────
# LLM HELPER  (reuse mission_runtime's pattern)
# ─────────────────────────────────────────────────────────────────────────────

async def _llm_call(prompt: str, system: str, model: Optional[str] = None) -> str:
    """Single LLM call returning the full response text."""
    try:
        import openai

        api_key  = os.getenv("AZURE_OPENAI_API_KEY") or os.getenv("OPENAI_API_KEY")
        base_url = os.getenv("AZURE_OPENAI_ENDPOINT")
        api_ver  = os.getenv("AZURE_OPENAI_API_VERSION", "2025-01-01-preview")

        if base_url and os.getenv("AZURE_OPENAI_API_KEY"):
            client = openai.AsyncAzureOpenAI(
                api_key        = api_key,
                azure_endpoint = base_url,
                api_version    = api_ver,
            )
            chat_model = model or os.getenv("AZURE_OPENAI_DEPLOYMENT", "gpt-5")
        else:
            client     = openai.AsyncOpenAI(api_key=api_key)
            chat_model = model or "gpt-4o-mini"

        resp = await client.chat.completions.create(
            model    = chat_model,
            messages = [
                {"role": "system", "content": system},
                {"role": "user",   "content": prompt},
            ],
            max_tokens   = 2000,
            temperature  = 0.3,
        )
        return resp.choices[0].message.content or ""
    except Exception as exc:
        logger.error(f"Workspace LLM call failed: {exc}")
        raise


# ─────────────────────────────────────────────────────────────────────────────
# WORKSPACE SERVICE
# ─────────────────────────────────────────────────────────────────────────────

class WorkspaceService:

    # ── Workspace CRUD ──────────────────────────────────────────────

    async def create_workspace(self, name: str, description: str = "") -> Workspace:
        ws = Workspace(name=name, description=description)
        return await workspace_store.create_workspace(ws)

    async def list_workspaces(self) -> List[Workspace]:
        return await workspace_store.list_workspaces()

    async def get_workspace(self, ws_id: str) -> Optional[Workspace]:
        return await workspace_store.get_workspace(ws_id)

    async def delete_workspace(self, ws_id: str) -> None:
        await workspace_store.delete_workspace(ws_id)

    # ── Document Upload Pipeline ────────────────────────────────────

    async def ingest_document(
        self,
        workspace_id: str,
        filename:     str,
        data:         bytes,
    ) -> WorkspaceDocument:
        """
        Full ingestion pipeline:
          1. Extract pages from file
          2. Chunk pages
          3. Generate embeddings (batch)
          4. Store document + chunks
        """
        ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else "bin"
        logger.info(f"Ingesting '{filename}' ({len(data)} bytes) into workspace {workspace_id}")

        # 1. Extract
        pages, content_hash = document_processor.process_bytes(data, filename)
        total_pages = len(pages)
        logger.info(f"  Extracted {total_pages} pages from '{filename}'")

        # 2. Create document record
        doc = WorkspaceDocument(
            workspace_id = workspace_id,
            filename     = filename,
            file_type    = ext,
            content_hash = content_hash,
            file_size    = len(data),
            total_pages  = total_pages,
        )
        await workspace_store.save_document(doc)

        # 3. Chunk
        chunks = chunk_pages(pages, doc.id, workspace_id)
        logger.info(f"  Created {len(chunks)} chunks from '{filename}'")

        # 4. Embed (batch, with semaphore to avoid overloading API)
        texts      = [c.content for c in chunks]
        embeddings = await embedding_pipeline.embed_batch(texts, use_cache=False)
        embedded   = sum(1 for e in embeddings if e is not None)
        logger.info(f"  Generated {embedded}/{len(chunks)} embeddings for '{filename}'")

        # 5. Persist chunks
        await workspace_store.save_chunks(chunks, embeddings)

        # 6. Update doc totals
        doc.total_chunks = len(chunks)
        await workspace_store.update_document_chunk_count(doc.id, len(chunks), total_pages)

        logger.info(f"Ingestion complete: '{filename}' — {len(chunks)} chunks, {embedded} embedded")
        return doc

    # ── Document Management ─────────────────────────────────────────

    async def list_documents(self, ws_id: str) -> List[WorkspaceDocument]:
        return await workspace_store.list_documents(ws_id)

    async def delete_document(self, doc_id: str) -> None:
        await workspace_store.delete_document(doc_id)

    async def get_document_chunks(self, doc_id: str) -> List[dict]:
        return await workspace_store.get_chunks_for_document(doc_id)

    # ── Workspace Chat (RAG) ────────────────────────────────────────

    async def chat(self, req: WorkspaceChatRequest) -> WorkspaceChatResponse:
        """
        Retrieval-Augmented Generation over workspace documents.

        1. Retrieve relevant chunks
        2. Build grounded prompt with citations
        3. Call LLM
        4. Return answer + citation list
        """
        ws = await workspace_store.get_workspace(req.workspace_id)
        if not ws:
            raise ValueError(f"Workspace {req.workspace_id} not found")

        # 1. Retrieve
        ctx = await retrieval_service.retrieve(
            workspace_id = req.workspace_id,
            query        = req.query,
            n_chunks     = req.n_chunks,
        )

        if not ctx.has_context:
            # No documents indexed — still answer but note the lack of context
            answer = await _llm_call(
                prompt = req.query,
                system = (
                    "You are a helpful assistant. "
                    "The workspace has no indexed documents yet. "
                    "Answer based on general knowledge and inform the user "
                    "that no documents were found in the workspace."
                ),
                model = req.model,
            )
            return WorkspaceChatResponse(
                answer      = answer,
                citations   = [],
                chunks_used = 0,
                model_used  = req.model or "default",
            )

        # 2. Build grounded prompt
        system = (
            "You are a precise, grounded AI assistant. "
            "You MUST answer ONLY using the provided document context. "
            "When you use information from a source, include the citation marker (e.g. [1]) inline. "
            "Do NOT fabricate information. If the context does not contain the answer, say so explicitly. "
            "Be thorough and structured."
        )

        prompt = (
            f"{ctx.formatted}\n\n"
            f"{'─' * 60}\n"
            f"USER QUESTION: {req.query}\n\n"
            f"Instructions:\n"
            f"- Answer using ONLY the document context above.\n"
            f"- Include inline citations using the [N] markers shown in the context.\n"
            f"- If the answer spans multiple sources, cite each one.\n"
            f"- If the context does not fully answer the question, state what is missing."
        )

        # 3. Generate
        answer = await _llm_call(prompt=prompt, system=system, model=req.model)

        # 4. Filter citations to only those actually referenced in the answer
        used_citations = [
            c for c in ctx.citation_map.values()
            if c.citation_id in answer
        ]
        # If LLM didn't explicitly cite, include top-ranked sources anyway
        if not used_citations:
            used_citations = list(ctx.citation_map.values())[:3]

        model_used = (
            req.model
            or os.getenv("AZURE_OPENAI_DEPLOYMENT", "")
            or "gpt-4o-mini"
        )

        return WorkspaceChatResponse(
            answer      = answer,
            citations   = used_citations,
            chunks_used = len(ctx.chunks),
            model_used  = model_used,
        )

    # ── Search ──────────────────────────────────────────────────────

    async def search(
        self,
        workspace_id: str,
        query:        str,
        n_chunks:     int = 8,
    ) -> Dict[str, Any]:
        ctx = await retrieval_service.retrieve(workspace_id, query, n_chunks)
        return {
            "chunks":    [c.model_dump() for c in ctx.chunks],
            "citations": [c.model_dump() for c in ctx.citation_map.values()],
            "count":     len(ctx.chunks),
        }


# =========================================================
# SINGLETON
# =========================================================

workspace_service = WorkspaceService()

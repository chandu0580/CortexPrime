"""
Workspace Store — PostgreSQL persistence for workspaces, documents, chunks.

Tables auto-created on first use. Falls back to an in-memory store when
PostgreSQL is unavailable (development / CI).

Schema
──────
workspaces (id, name, description, created_at, metadata)
workspace_documents (id, workspace_id, filename, file_type, content_hash,
                     total_chunks, total_pages, file_size, created_at, metadata)
document_chunks (id, document_id, workspace_id, chunk_index, content,
                 page_number, char_start, char_end, embedding::vector(1536),
                 metadata, created_at)
"""
from __future__ import annotations

import json
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import uuid4

from backend.memory.db.postgres_client import postgres_client
from backend.memory.embedding_pipeline import embedding_pipeline, pgvector_str
from backend.workspace.models import (
    Workspace,
    WorkspaceDocument,
    DocumentChunk,
    RetrievedChunk,
)

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────────────────────
# DDL
# ─────────────────────────────────────────────────────────────────────────────

_DDL = [
    """
    CREATE TABLE IF NOT EXISTS workspaces (
        id          TEXT PRIMARY KEY,
        name        TEXT NOT NULL,
        description TEXT DEFAULT '',
        created_at  TIMESTAMPTZ DEFAULT NOW(),
        metadata    JSONB DEFAULT '{}'
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS workspace_documents (
        id           TEXT PRIMARY KEY,
        workspace_id TEXT NOT NULL,
        filename     TEXT NOT NULL,
        file_type    TEXT NOT NULL,
        content_hash TEXT DEFAULT '',
        total_chunks INT  DEFAULT 0,
        total_pages  INT  DEFAULT 0,
        file_size    INT  DEFAULT 0,
        created_at   TIMESTAMPTZ DEFAULT NOW(),
        metadata     JSONB DEFAULT '{}'
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS document_chunks (
        id           TEXT PRIMARY KEY,
        document_id  TEXT NOT NULL,
        workspace_id TEXT NOT NULL,
        chunk_index  INT  NOT NULL,
        content      TEXT NOT NULL,
        page_number  INT,
        char_start   INT  DEFAULT 0,
        char_end     INT  DEFAULT 0,
        embedding    vector(1536),
        metadata     JSONB DEFAULT '{}',
        created_at   TIMESTAMPTZ DEFAULT NOW()
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_doc_chunks_workspace ON document_chunks(workspace_id)",
    "CREATE INDEX IF NOT EXISTS idx_doc_chunks_document ON document_chunks(document_id)",
    "CREATE INDEX IF NOT EXISTS idx_workspace_docs_ws   ON workspace_documents(workspace_id)",
]

_VECTOR_INDEX_DDL = """
    CREATE INDEX IF NOT EXISTS idx_doc_chunks_embedding
    ON document_chunks USING ivfflat (embedding vector_cosine_ops) WITH (lists = 50)
"""


# ─────────────────────────────────────────────────────────────────────────────
# IN-MEMORY FALLBACK (no PostgreSQL)
# ─────────────────────────────────────────────────────────────────────────────

class _InMemoryFallback:
    def __init__(self):
        self._workspaces:  Dict[str, dict] = {}
        self._documents:   Dict[str, dict] = {}
        self._chunks:      List[dict]      = []

    async def create_workspace(self, ws: Workspace) -> None:
        self._workspaces[ws.id] = ws.model_dump()

    async def list_workspaces(self) -> List[dict]:
        return list(self._workspaces.values())

    async def get_workspace(self, ws_id: str) -> Optional[dict]:
        return self._workspaces.get(ws_id)

    async def delete_workspace(self, ws_id: str) -> None:
        self._workspaces.pop(ws_id, None)
        self._documents = {k: v for k, v in self._documents.items()
                           if v["workspace_id"] != ws_id}
        self._chunks    = [c for c in self._chunks if c["workspace_id"] != ws_id]

    async def save_document(self, doc: WorkspaceDocument) -> None:
        self._documents[doc.id] = doc.model_dump()

    async def list_documents(self, ws_id: str) -> List[dict]:
        return [d for d in self._documents.values() if d["workspace_id"] == ws_id]

    async def get_document(self, doc_id: str) -> Optional[dict]:
        return self._documents.get(doc_id)

    async def delete_document(self, doc_id: str) -> None:
        doc = self._documents.pop(doc_id, None)
        if doc:
            self._chunks = [c for c in self._chunks if c["document_id"] != doc_id]

    async def save_chunks(self, chunks: List[DocumentChunk], embeddings: List) -> None:
        for chunk, emb in zip(chunks, embeddings):
            d = chunk.model_dump()
            d["embedding"] = emb
            self._chunks.append(d)

    async def search(
        self, workspace_id: str, query_emb: List[float], n: int
    ) -> List[RetrievedChunk]:
        import numpy as np
        results = []
        for c in self._chunks:
            if c["workspace_id"] != workspace_id:
                continue
            emb = c.get("embedding")
            if emb is None:
                continue
            a = np.array(query_emb)
            b = np.array(emb)
            norm = np.linalg.norm(a) * np.linalg.norm(b)
            score = float(np.dot(a, b) / norm) if norm > 0 else 0.0
            results.append((score, c))
        results.sort(key=lambda x: x[0], reverse=True)
        out = []
        for score, c in results[:n]:
            doc = self._documents.get(c["document_id"], {})
            out.append(RetrievedChunk(
                chunk_id     = c["id"],
                document_id  = c["document_id"],
                workspace_id = c["workspace_id"],
                filename     = doc.get("filename", "unknown"),
                page_number  = c.get("page_number"),
                content      = c["content"],
                score        = score,
                chunk_index  = c["chunk_index"],
            ))
        return out

    async def get_chunks_for_document(self, doc_id: str) -> List[dict]:
        return [c for c in self._chunks if c["document_id"] == doc_id]


# ─────────────────────────────────────────────────────────────────────────────
# MAIN STORE
# ─────────────────────────────────────────────────────────────────────────────

class WorkspaceStore:
    """Persistent workspace + document + chunk store backed by PostgreSQL."""

    def __init__(self):
        self._initialised = False
        self._fallback    = _InMemoryFallback()
        self._pg_ok       = False

    # ── Init ────────────────────────────────────────────────────────

    async def _ensure_init(self) -> None:
        if self._initialised:
            return
        self._initialised = True
        pool = await postgres_client.pool()
        if pool is None:
            logger.warning("WorkspaceStore: PostgreSQL unavailable — using in-memory fallback")
            return

        # Ensure pgvector extension
        try:
            async with pool.acquire() as conn:
                await conn.execute("CREATE EXTENSION IF NOT EXISTS vector")
        except Exception as exc:
            logger.warning(f"pgvector extension: {exc}")

        for ddl in _DDL:
            try:
                await postgres_client.execute(ddl)
            except Exception as exc:
                logger.warning(f"DDL error: {exc}")

        # Best-effort vector index (needs enough data first)
        try:
            await postgres_client.execute(_VECTOR_INDEX_DDL)
        except Exception:
            pass  # fine if table is empty

        self._pg_ok = True
        logger.info("WorkspaceStore: PostgreSQL ready")

    # ── Workspaces ──────────────────────────────────────────────────

    async def create_workspace(self, ws: Workspace) -> Workspace:
        await self._ensure_init()
        if self._pg_ok:
            await postgres_client.execute(
                """INSERT INTO workspaces (id, name, description, created_at, metadata)
                   VALUES ($1, $2, $3, $4, $5::jsonb)""",
                ws.id, ws.name, ws.description,
                ws.created_at, json.dumps(ws.metadata),
            )
        else:
            await self._fallback.create_workspace(ws)
        return ws

    async def list_workspaces(self) -> List[Workspace]:
        await self._ensure_init()
        if self._pg_ok:
            rows = await postgres_client.fetch(
                "SELECT id, name, description, created_at, metadata FROM workspaces ORDER BY created_at DESC"
            )
            result = []
            for r in rows:
                doc_count = await postgres_client.fetchval(
                    "SELECT COUNT(*) FROM workspace_documents WHERE workspace_id = $1", r["id"]
                ) or 0
                result.append(Workspace(
                    id          = r["id"],
                    name        = r["name"],
                    description = r["description"] or "",
                    created_at  = r["created_at"],
                    metadata    = json.loads(r["metadata"] or "{}"),
                    doc_count   = int(doc_count),
                ))
            return result
        else:
            return [Workspace(**d) for d in await self._fallback.list_workspaces()]

    async def get_workspace(self, ws_id: str) -> Optional[Workspace]:
        await self._ensure_init()
        if self._pg_ok:
            row = await postgres_client.fetchrow(
                "SELECT id, name, description, created_at, metadata FROM workspaces WHERE id = $1",
                ws_id,
            )
            if not row:
                return None
            return Workspace(
                id          = row["id"],
                name        = row["name"],
                description = row["description"] or "",
                created_at  = row["created_at"],
                metadata    = json.loads(row["metadata"] or "{}"),
            )
        else:
            d = await self._fallback.get_workspace(ws_id)
            return Workspace(**d) if d else None

    async def delete_workspace(self, ws_id: str) -> None:
        await self._ensure_init()
        if self._pg_ok:
            await postgres_client.execute(
                "DELETE FROM document_chunks   WHERE workspace_id = $1", ws_id
            )
            await postgres_client.execute(
                "DELETE FROM workspace_documents WHERE workspace_id = $1", ws_id
            )
            await postgres_client.execute(
                "DELETE FROM workspaces WHERE id = $1", ws_id
            )
        else:
            await self._fallback.delete_workspace(ws_id)

    # ── Documents ───────────────────────────────────────────────────

    async def save_document(self, doc: WorkspaceDocument) -> WorkspaceDocument:
        await self._ensure_init()
        if self._pg_ok:
            await postgres_client.execute(
                """INSERT INTO workspace_documents
                   (id, workspace_id, filename, file_type, content_hash,
                    total_chunks, total_pages, file_size, created_at, metadata)
                   VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10::jsonb)""",
                doc.id, doc.workspace_id, doc.filename, doc.file_type,
                doc.content_hash, doc.total_chunks, doc.total_pages,
                doc.file_size, doc.created_at, json.dumps(doc.metadata),
            )
        else:
            await self._fallback.save_document(doc)
        return doc

    async def update_document_chunk_count(
        self, doc_id: str, total_chunks: int, total_pages: int
    ) -> None:
        await self._ensure_init()
        if self._pg_ok:
            await postgres_client.execute(
                "UPDATE workspace_documents SET total_chunks=$2, total_pages=$3 WHERE id=$1",
                doc_id, total_chunks, total_pages,
            )

    async def list_documents(self, ws_id: str) -> List[WorkspaceDocument]:
        await self._ensure_init()
        if self._pg_ok:
            rows = await postgres_client.fetch(
                """SELECT id, workspace_id, filename, file_type, content_hash,
                          total_chunks, total_pages, file_size, created_at, metadata
                   FROM workspace_documents WHERE workspace_id=$1 ORDER BY created_at DESC""",
                ws_id,
            )
            return [
                WorkspaceDocument(
                    id           = r["id"],
                    workspace_id = r["workspace_id"],
                    filename     = r["filename"],
                    file_type    = r["file_type"],
                    content_hash = r["content_hash"] or "",
                    total_chunks = r["total_chunks"] or 0,
                    total_pages  = r["total_pages"] or 0,
                    file_size    = r["file_size"] or 0,
                    created_at   = r["created_at"],
                    metadata     = json.loads(r["metadata"] or "{}"),
                )
                for r in rows
            ]
        else:
            return [WorkspaceDocument(**d) for d in await self._fallback.list_documents(ws_id)]

    async def get_document(self, doc_id: str) -> Optional[WorkspaceDocument]:
        await self._ensure_init()
        if self._pg_ok:
            row = await postgres_client.fetchrow(
                """SELECT id, workspace_id, filename, file_type, content_hash,
                          total_chunks, total_pages, file_size, created_at, metadata
                   FROM workspace_documents WHERE id=$1""",
                doc_id,
            )
            if not row:
                return None
            return WorkspaceDocument(
                id           = row["id"],
                workspace_id = row["workspace_id"],
                filename     = row["filename"],
                file_type    = row["file_type"],
                content_hash = row["content_hash"] or "",
                total_chunks = row["total_chunks"] or 0,
                total_pages  = row["total_pages"] or 0,
                file_size    = row["file_size"] or 0,
                created_at   = row["created_at"],
                metadata     = json.loads(row["metadata"] or "{}"),
            )
        else:
            d = await self._fallback.get_document(doc_id)
            return WorkspaceDocument(**d) if d else None

    async def delete_document(self, doc_id: str) -> None:
        await self._ensure_init()
        if self._pg_ok:
            await postgres_client.execute(
                "DELETE FROM document_chunks WHERE document_id = $1", doc_id
            )
            await postgres_client.execute(
                "DELETE FROM workspace_documents WHERE id = $1", doc_id
            )
        else:
            await self._fallback.delete_document(doc_id)

    # ── Chunks ──────────────────────────────────────────────────────

    async def save_chunks(
        self,
        chunks:     List[DocumentChunk],
        embeddings: List,
    ) -> None:
        """Batch-insert chunks + their embeddings."""
        await self._ensure_init()
        if self._pg_ok:
            for chunk, emb in zip(chunks, embeddings):
                vec = pgvector_str(emb) if emb else None
                if vec:
                    await postgres_client.execute(
                        """INSERT INTO document_chunks
                           (id, document_id, workspace_id, chunk_index, content,
                            page_number, char_start, char_end, embedding, metadata, created_at)
                           VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9::vector,$10::jsonb,$11)""",
                        chunk.id, chunk.document_id, chunk.workspace_id,
                        chunk.chunk_index, chunk.content, chunk.page_number,
                        chunk.char_start, chunk.char_end, vec,
                        json.dumps(chunk.metadata), chunk.created_at,
                    )
                else:
                    await postgres_client.execute(
                        """INSERT INTO document_chunks
                           (id, document_id, workspace_id, chunk_index, content,
                            page_number, char_start, char_end, metadata, created_at)
                           VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9::jsonb,$10)""",
                        chunk.id, chunk.document_id, chunk.workspace_id,
                        chunk.chunk_index, chunk.content, chunk.page_number,
                        chunk.char_start, chunk.char_end,
                        json.dumps(chunk.metadata), chunk.created_at,
                    )
        else:
            await self._fallback.save_chunks(chunks, embeddings)

    async def search(
        self,
        workspace_id: str,
        query_emb:    List[float],
        n:            int = 6,
    ) -> List[RetrievedChunk]:
        """Cosine-similarity search over embedded chunks in a workspace."""
        await self._ensure_init()
        if self._pg_ok and query_emb:
            vec = pgvector_str(query_emb)
            if vec:
                rows = await postgres_client.fetch(
                    """
                    SELECT
                        dc.id,
                        dc.document_id,
                        dc.workspace_id,
                        dc.chunk_index,
                        dc.content,
                        dc.page_number,
                        1 - (dc.embedding <=> $2::vector) AS score,
                        wd.filename
                    FROM document_chunks dc
                    JOIN workspace_documents wd ON wd.id = dc.document_id
                    WHERE dc.workspace_id = $1
                      AND dc.embedding IS NOT NULL
                    ORDER BY dc.embedding <=> $2::vector
                    LIMIT $3
                    """,
                    workspace_id, vec, n,
                )
                return [
                    RetrievedChunk(
                        chunk_id     = r["id"],
                        document_id  = r["document_id"],
                        workspace_id = r["workspace_id"],
                        filename     = r["filename"],
                        page_number  = r["page_number"],
                        content      = r["content"],
                        score        = float(r["score"] or 0),
                        chunk_index  = r["chunk_index"],
                    )
                    for r in rows
                ]
        # Fallback: in-memory cosine search
        return await self._fallback.search(workspace_id, query_emb, n)

    async def keyword_search(
        self,
        workspace_id: str,
        query:        str,
        n:            int = 6,
    ) -> List[RetrievedChunk]:
        """Full-text search fallback when embeddings are unavailable."""
        await self._ensure_init()
        if self._pg_ok:
            rows = await postgres_client.fetch(
                """
                SELECT
                    dc.id, dc.document_id, dc.workspace_id, dc.chunk_index,
                    dc.content, dc.page_number,
                    ts_rank(to_tsvector('english', dc.content),
                            plainto_tsquery('english', $2)) AS score,
                    wd.filename
                FROM document_chunks dc
                JOIN workspace_documents wd ON wd.id = dc.document_id
                WHERE dc.workspace_id = $1
                  AND to_tsvector('english', dc.content) @@ plainto_tsquery('english', $2)
                ORDER BY score DESC
                LIMIT $3
                """,
                workspace_id, query, n,
            )
            return [
                RetrievedChunk(
                    chunk_id     = r["id"],
                    document_id  = r["document_id"],
                    workspace_id = r["workspace_id"],
                    filename     = r["filename"],
                    page_number  = r["page_number"],
                    content      = r["content"],
                    score        = float(r["score"] or 0),
                    chunk_index  = r["chunk_index"],
                )
                for r in rows
            ]
        return []

    async def get_chunks_for_document(self, doc_id: str) -> List[dict]:
        await self._ensure_init()
        if self._pg_ok:
            rows = await postgres_client.fetch(
                """SELECT id, chunk_index, content, page_number, char_start, char_end, metadata
                   FROM document_chunks WHERE document_id=$1 ORDER BY chunk_index""",
                doc_id,
            )
            return [dict(r) for r in rows]
        else:
            return await self._fallback.get_chunks_for_document(doc_id)


# =========================================================
# SINGLETON
# =========================================================

workspace_store = WorkspaceStore()

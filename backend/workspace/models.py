"""
Workspace Intelligence — Pydantic models and data classes.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import uuid4

from pydantic import BaseModel, Field


# =========================================================
# CORE DOMAIN MODELS
# =========================================================

class Workspace(BaseModel):
    id:          str = Field(default_factory=lambda: str(uuid4()))
    name:        str
    description: str = ""
    created_at:  datetime = Field(default_factory=datetime.utcnow)
    metadata:    Dict[str, Any] = Field(default_factory=dict)
    doc_count:   int = 0


class WorkspaceDocument(BaseModel):
    id:           str = Field(default_factory=lambda: str(uuid4()))
    workspace_id: str
    filename:     str
    file_type:    str           # pdf | docx | txt | md | pptx | image
    content_hash: str = ""
    total_chunks: int = 0
    total_pages:  int = 0
    file_size:    int = 0       # bytes
    created_at:   datetime = Field(default_factory=datetime.utcnow)
    metadata:     Dict[str, Any] = Field(default_factory=dict)


class DocumentChunk(BaseModel):
    id:           str = Field(default_factory=lambda: str(uuid4()))
    document_id:  str
    workspace_id: str
    chunk_index:  int
    content:      str
    page_number:  Optional[int] = None
    char_start:   int = 0
    char_end:     int = 0
    metadata:     Dict[str, Any] = Field(default_factory=dict)
    created_at:   datetime = Field(default_factory=datetime.utcnow)


class RetrievedChunk(BaseModel):
    """A chunk returned from semantic search with citation metadata."""
    chunk_id:     str
    document_id:  str
    workspace_id: str
    filename:     str
    page_number:  Optional[int]
    content:      str
    score:        float          # cosine similarity [0, 1]
    chunk_index:  int


class Citation(BaseModel):
    """Source reference for a generated response."""
    citation_id: str = Field(default_factory=lambda: f"[{uuid4().hex[:4].upper()}]")
    filename:    str
    page_number: Optional[int]
    chunk_index: int
    excerpt:     str            # first 200 chars of the chunk
    score:       float
    document_id: str


class WorkspaceChatRequest(BaseModel):
    query:        str = Field(..., min_length=1, max_length=4000)
    workspace_id: str
    session_id:   Optional[str] = None
    n_chunks:     int = Field(default=6, ge=1, le=20)
    model:        Optional[str] = None


class WorkspaceChatResponse(BaseModel):
    answer:     str
    citations:  List[Citation]
    chunks_used: int
    model_used: str


class WorkspaceContext(BaseModel):
    """Context assembled from retrieved chunks — injected into agents."""
    workspace_id:   str
    workspace_name: str
    chunks:         List[RetrievedChunk]
    formatted:      str          # ready-to-inject text block
    citation_map:   Dict[str, Citation]  # citation_id → Citation

    @property
    def has_context(self) -> bool:
        return len(self.chunks) > 0

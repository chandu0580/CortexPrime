"""
Workspace API Routes — /api/workspace/*

Endpoints
─────────
POST   /api/workspace/                          Create workspace
GET    /api/workspace/                          List workspaces
GET    /api/workspace/{ws_id}                   Get workspace
DELETE /api/workspace/{ws_id}                   Delete workspace

POST   /api/workspace/{ws_id}/upload            Upload + ingest document
GET    /api/workspace/{ws_id}/documents         List documents
DELETE /api/workspace/{ws_id}/documents/{doc_id} Delete document
GET    /api/workspace/{ws_id}/documents/{doc_id}/chunks  View chunks

POST   /api/workspace/{ws_id}/search            Semantic search
POST   /api/workspace/{ws_id}/chat              RAG chat
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from pydantic import BaseModel, Field

from backend.auth.dependencies import require_user
from backend.workspace.models import WorkspaceChatRequest
from backend.workspace.workspace_service import workspace_service

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/workspace",
    tags=["Workspace"],
    dependencies=[Depends(require_user)],
)


# =========================================================
# REQUEST / RESPONSE SCHEMAS
# =========================================================

class CreateWorkspaceRequest(BaseModel):
    name:        str = Field(..., min_length=1, max_length=200)
    description: str = Field(default="", max_length=1000)


class SearchRequest(BaseModel):
    query:    str = Field(..., min_length=1)
    n_chunks: int = Field(default=8, ge=1, le=20)


# =========================================================
# WORKSPACE CRUD
# =========================================================

@router.post("/", response_model=Dict[str, Any], status_code=201)
async def create_workspace(req: CreateWorkspaceRequest):
    ws = await workspace_service.create_workspace(req.name, req.description)
    return ws.model_dump()


@router.get("/", response_model=List[Dict[str, Any]])
async def list_workspaces():
    workspaces = await workspace_service.list_workspaces()
    return [w.model_dump() for w in workspaces]


@router.get("/{ws_id}", response_model=Dict[str, Any])
async def get_workspace(ws_id: str):
    ws = await workspace_service.get_workspace(ws_id)
    if not ws:
        raise HTTPException(status_code=404, detail="Workspace not found")
    return ws.model_dump()


@router.delete("/{ws_id}", status_code=204)
async def delete_workspace(ws_id: str):
    ws = await workspace_service.get_workspace(ws_id)
    if not ws:
        raise HTTPException(status_code=404, detail="Workspace not found")
    await workspace_service.delete_workspace(ws_id)


# =========================================================
# DOCUMENT UPLOAD + MANAGEMENT
# =========================================================

_ALLOWED_EXTENSIONS = {
    "pdf", "docx", "txt", "md", "pptx",
    "png", "jpg", "jpeg", "gif", "webp", "bmp", "tiff",
}
_MAX_FILE_SIZE = 50 * 1024 * 1024  # 50 MB


@router.post("/{ws_id}/upload", response_model=Dict[str, Any], status_code=201)
async def upload_document(ws_id: str, file: UploadFile = File(...)):
    """Upload and ingest a document into the workspace."""
    ws = await workspace_service.get_workspace(ws_id)
    if not ws:
        raise HTTPException(status_code=404, detail="Workspace not found")

    # Validate extension
    filename = file.filename or "upload.txt"
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    if ext not in _ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type '.{ext}'. Allowed: {sorted(_ALLOWED_EXTENSIONS)}",
        )

    # Read bytes
    data = await file.read()
    if len(data) > _MAX_FILE_SIZE:
        raise HTTPException(status_code=413, detail="File exceeds 50 MB limit")
    if not data:
        raise HTTPException(status_code=400, detail="Empty file")

    try:
        doc = await workspace_service.ingest_document(ws_id, filename, data)
        return {
            **doc.model_dump(),
            "message": f"Ingested {doc.total_chunks} chunks from {doc.total_pages} pages",
        }
    except Exception as exc:
        logger.error(f"Ingestion failed for {filename}: {exc}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Ingestion failed: {exc}")


@router.get("/{ws_id}/documents", response_model=List[Dict[str, Any]])
async def list_documents(ws_id: str):
    docs = await workspace_service.list_documents(ws_id)
    return [d.model_dump() for d in docs]


@router.delete("/{ws_id}/documents/{doc_id}", status_code=204)
async def delete_document(ws_id: str, doc_id: str):
    await workspace_service.delete_document(doc_id)


@router.get("/{ws_id}/documents/{doc_id}/chunks", response_model=List[Dict[str, Any]])
async def get_document_chunks(ws_id: str, doc_id: str):
    return await workspace_service.get_document_chunks(doc_id)


# =========================================================
# SEMANTIC SEARCH
# =========================================================

@router.post("/{ws_id}/search", response_model=Dict[str, Any])
async def search_workspace(ws_id: str, req: SearchRequest):
    ws = await workspace_service.get_workspace(ws_id)
    if not ws:
        raise HTTPException(status_code=404, detail="Workspace not found")
    return await workspace_service.search(ws_id, req.query, req.n_chunks)


# =========================================================
# WORKSPACE CHAT (RAG)
# =========================================================

@router.post("/{ws_id}/chat", response_model=Dict[str, Any])
async def workspace_chat(ws_id: str, req: WorkspaceChatRequest):
    ws = await workspace_service.get_workspace(ws_id)
    if not ws:
        raise HTTPException(status_code=404, detail="Workspace not found")

    # Ensure workspace_id is set from path
    req = WorkspaceChatRequest(
        query        = req.query,
        workspace_id = ws_id,
        session_id   = req.session_id,
        n_chunks     = req.n_chunks,
        model        = req.model,
    )

    try:
        response = await workspace_service.chat(req)
        return response.model_dump()
    except Exception as exc:
        logger.error(f"Workspace chat failed: {exc}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Chat failed: {exc}")

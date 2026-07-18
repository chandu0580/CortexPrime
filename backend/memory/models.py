"""
CortexPrime Memory Layer — Pydantic data models.
"""
from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional
from uuid import uuid4

from pydantic import BaseModel, Field

# =========================================================
# MEMORY TYPE ENUM
# =========================================================

class MemoryType(str, Enum):
    EPISODIC   = "episodic"
    SEMANTIC   = "semantic"
    REFLECTION = "reflection"
    CONTEXT    = "context"


# =========================================================
# CORE ENTRY MODELS
# =========================================================

class EpisodicEntry(BaseModel):
    id:         str              = Field(default_factory=lambda: str(uuid4()))
    session_id: str
    agent:      str
    event_type: str
    content:    str
    metadata:   Dict[str, Any]   = Field(default_factory=dict)
    relevance:  Optional[float]  = None
    created_at: datetime         = Field(default_factory=datetime.utcnow)


class SemanticEntry(BaseModel):
    id:         str              = Field(default_factory=lambda: str(uuid4()))
    concept:    str
    content:    str
    source:     Optional[str]    = None
    confidence: float            = 1.0
    metadata:   Dict[str, Any]   = Field(default_factory=dict)
    relevance:  Optional[float]  = None
    created_at: datetime         = Field(default_factory=datetime.utcnow)


class ReflectionEntry(BaseModel):
    id:         str              = Field(default_factory=lambda: str(uuid4()))
    mission_id: Optional[str]   = None
    agent:      str
    reflection: str
    score:      Optional[float]  = None
    metadata:   Dict[str, Any]   = Field(default_factory=dict)
    created_at: datetime         = Field(default_factory=datetime.utcnow)


class RuntimeContext(BaseModel):
    session_id:        str
    messages:          List[Dict[str, Any]] = Field(default_factory=list)
    active_agents:     List[str]            = Field(default_factory=list)
    current_objective: Optional[str]        = None
    metadata:          Dict[str, Any]       = Field(default_factory=dict)
    updated_at:        datetime             = Field(default_factory=datetime.utcnow)


class AssembledContext(BaseModel):
    session_id:          str
    query:               Optional[str]         = None
    episodic:            List[EpisodicEntry]   = Field(default_factory=list)
    semantic:            List[SemanticEntry]   = Field(default_factory=list)
    reflections:         List[ReflectionEntry] = Field(default_factory=list)
    active_context:      Dict[str, Any]        = Field(default_factory=dict)
    compression_applied: bool                  = False
    assembled_at:        datetime              = Field(default_factory=datetime.utcnow)


# =========================================================
# REQUEST / RESPONSE MODELS (used by API routes)
# =========================================================

class StoreMemoryRequest(BaseModel):
    type:       MemoryType
    agent:      str
    content:    str
    session_id: Optional[str]   = None
    mission_id: Optional[str]   = None
    event_type: str              = "memory"
    concept:    Optional[str]   = None
    metadata:   Dict[str, Any]  = Field(default_factory=dict)


class SearchRequest(BaseModel):
    query:            str
    n_results:        int           = 10
    session_id:       Optional[str] = None
    include_episodic: bool          = True
    include_semantic: bool          = True
    min_relevance:    float         = 0.0


class ReflectRequest(BaseModel):
    agent:      str
    reflection: str
    mission_id: Optional[str]   = None
    score:      Optional[float] = None
    metadata:   Dict[str, Any]  = Field(default_factory=dict)


class MemoryStatusResponse(BaseModel):
    postgres:   bool
    redis:      bool
    neo4j:      bool
    embeddings: str
    total_events_tracked: int

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional


class RelationshipType(str, Enum):
    DEPENDS_ON = "depends_on"
    RELATED_TO = "related_to"
    OWNS = "owns"
    PRODUCED_BY = "produced_by"
    REFERENCES = "references"
    CONNECTED_TO = "connected_to"
    CAUSED_BY = "caused_by"
    DERIVED_FROM = "derived_from"


class KnowledgeCategory(str, Enum):
    DOCUMENT = "document"
    MISSION = "mission"
    EXECUTION = "execution"
    POLICY = "policy"
    CONNECTOR = "connector"
    INFRASTRUCTURE = "infrastructure"
    ARTIFACT = "artifact"


@dataclass
class KnowledgeDocument:
    id: str = ""
    title: str = ""
    content: str = ""
    summary: str = ""
    category: str = "document"
    tags: list[str] = field(default_factory=list)
    source: str = ""
    source_url: str = ""
    confidence: float = 1.0
    metadata: dict[str, Any] = field(default_factory=dict)
    embedding: Optional[list[float]] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


@dataclass
class KnowledgeRelationship:
    id: str = ""
    source_id: str = ""
    target_id: str = ""
    relationship_type: str = "related_to"
    strength: float = 1.0
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: Optional[str] = None


@dataclass
class KnowledgeQuery:
    query: str = ""
    category: Optional[str] = None
    tags: Optional[list[str]] = None
    source: Optional[str] = None
    confidence_min: Optional[float] = None
    confidence_max: Optional[float] = None
    metadata_filter: Optional[dict[str, Any]] = None
    relationship_type: Optional[str] = None
    relationship_source_id: Optional[str] = None
    relationship_target_id: Optional[str] = None
    sort_by: str = "created_at"
    sort_order: str = "desc"
    limit: int = 20
    offset: int = 0
    include_relationships: bool = False


@dataclass
class KnowledgeSearchResult:
    entries: list[KnowledgeDocument] = field(default_factory=list)
    total: int = 0
    query: str = ""
    limit: int = 20
    offset: int = 0
    relationships: Optional[list[KnowledgeRelationship]] = None


@dataclass
class KnowledgeContext:
    mission_id: Optional[str] = None
    execution_id: Optional[str] = None
    user_id: Optional[str] = None
    session_id: Optional[str] = None
    additional: dict[str, Any] = field(default_factory=dict)


@dataclass
class IndexRequest:
    title: str
    content: str
    summary: str = ""
    category: str = "document"
    tags: list[str] = field(default_factory=list)
    source: str = ""
    source_url: str = ""
    confidence: float = 1.0
    metadata: dict[str, Any] = field(default_factory=dict)


KNOWLEDGE_EVENT_TYPES: dict[str, str] = {
    "knowledge.created": "Knowledge entry was created",
    "knowledge.updated": "Knowledge entry was updated",
    "knowledge.deleted": "Knowledge entry was deleted",
    "knowledge.indexed": "Knowledge was indexed from a runtime",
    "knowledge.related": "Knowledge relationship was created",
}

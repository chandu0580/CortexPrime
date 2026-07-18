from __future__ import annotations

import logging
import uuid
from typing import Any, Optional

try:
    from backend.database.repositories.factory import RepositoryFactory
    from backend.database.repositories.factory import repo_factory as _repo_factory
except ImportError:
    _repo_factory = None
from backend.knowledge.events import KnowledgeEvent, KnowledgeEventPublisher, knowledge_event_publisher
from backend.knowledge.models import (
    IndexRequest,
    KnowledgeDocument,
    KnowledgeRelationship,
)

log = logging.getLogger(__name__)


class KnowledgeManager:
    def __init__(
        self,
        events: Optional[KnowledgeEventPublisher] = None,
        repo_factory: Optional[RepositoryFactory] = None,
    ) -> None:
        self._events = events or knowledge_event_publisher
        self._repo_factory = repo_factory or _repo_factory or RepositoryFactory()

    async def create_entry(self, request: IndexRequest) -> Optional[KnowledgeDocument]:
        repo = await self._repo_factory.knowledge_entry_repo()
        from backend.database.repositories.knowledge import KnowledgeEntryModel

        model = KnowledgeEntryModel(
            id=uuid.uuid4(),
            title=request.title,
            content=request.content,
            summary=request.summary or request.content[:200],
            category=request.category,
            tags=request.tags,
            source=request.source,
            source_url=request.source_url,
            confidence=request.confidence,
            metadata_=request.metadata,
        )
        model = await repo.create(model)

        doc = KnowledgeDocument(
            id=str(model.id),
            title=model.title,
            content=model.content,
            summary=model.summary or "",
            category=model.category,
            tags=model.tags or [],
            source=model.source or "",
            source_url=model.source_url or "",
            confidence=model.confidence,
            metadata=model.metadata_ or {},
            created_at=model.created_at.isoformat() if model.created_at else None,
            updated_at=model.updated_at.isoformat() if model.updated_at else None,
        )

        await self._publish_event("knowledge.created", doc.id, doc.title, doc.category, doc.source)
        return doc

    async def update_entry(
        self,
        entry_id: str,
        updates: dict[str, Any],
    ) -> Optional[KnowledgeDocument]:
        repo = await self._repo_factory.knowledge_entry_repo()
        try:
            model = await repo.get(uuid.UUID(entry_id))
        except (ValueError, Exception):
            return None
        if not model:
            return None

        for key, value in updates.items():
            col = "metadata_" if key == "metadata" else key
            if hasattr(model, col) and key not in ("id", "created_at", "embedding"):
                setattr(model, col, value)

        model = await repo.update(model)

        doc = KnowledgeDocument(
            id=str(model.id),
            title=model.title,
            content=model.content,
            summary=model.summary or "",
            category=model.category,
            tags=model.tags or [],
            source=model.source or "",
            source_url=model.source_url or "",
            confidence=model.confidence,
            metadata=model.metadata_ or {},
            created_at=model.created_at.isoformat() if model.created_at else None,
            updated_at=model.updated_at.isoformat() if model.updated_at else None,
        )

        await self._publish_event("knowledge.updated", doc.id, doc.title, doc.category, doc.source)
        return doc

    async def delete_entry(self, entry_id: str) -> bool:
        repo = await self._repo_factory.knowledge_entry_repo()
        await self._repo_factory.knowledge_rel_repo()
        try:
            pk = uuid.UUID(entry_id)
        except ValueError:
            return False
        model = await repo.get(pk)
        if not model:
            return False

        await repo.delete(pk)
        await self._publish_event("knowledge.deleted", entry_id, model.title, model.category, model.source)
        return True

    async def get_entry(self, entry_id: str) -> Optional[KnowledgeDocument]:
        repo = await self._repo_factory.knowledge_entry_repo()
        try:
            model = await repo.get(uuid.UUID(entry_id))
        except (ValueError, Exception):
            return None
        if not model:
            return None
        return KnowledgeDocument(
            id=str(model.id),
            title=model.title,
            content=model.content,
            summary=model.summary or "",
            category=model.category,
            tags=model.tags or [],
            source=model.source or "",
            source_url=model.source_url or "",
            confidence=model.confidence,
            metadata=model.metadata_ or {},
            created_at=model.created_at.isoformat() if model.created_at else None,
            updated_at=model.updated_at.isoformat() if model.updated_at else None,
        )

    async def list_entries(
        self,
        category: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[KnowledgeDocument]:
        repo = await self._repo_factory.knowledge_entry_repo()
        if category:
            models = await repo.list_by_category(category)
        else:
            models = await repo.list(limit=limit, offset=offset)
        return [
            KnowledgeDocument(
                id=str(m.id),
                title=m.title,
                content=m.content,
                summary=m.summary or "",
                category=m.category,
                tags=m.tags or [],
                source=m.source or "",
                source_url=m.source_url or "",
                confidence=m.confidence,
                metadata=m.metadata_ or {},
                created_at=m.created_at.isoformat() if m.created_at else None,
                updated_at=m.updated_at.isoformat() if m.updated_at else None,
            )
            for m in models
        ]

    async def create_relationship(
        self,
        source_id: str,
        target_id: str,
        relationship_type: str = "related_to",
        strength: float = 1.0,
        metadata: Optional[dict[str, Any]] = None,
    ) -> Optional[KnowledgeRelationship]:
        rel_repo = await self._repo_factory.knowledge_rel_repo()
        from backend.database.repositories.knowledge import KnowledgeRelationshipModel

        model = KnowledgeRelationshipModel(
            id=uuid.uuid4(),
            source_id=source_id,
            target_id=target_id,
            relationship_type=relationship_type,
            strength=strength,
            metadata_=metadata or {},
        )
        model = await rel_repo.create(model)

        rel = KnowledgeRelationship(
            id=str(model.id),
            source_id=model.source_id,
            target_id=model.target_id,
            relationship_type=model.relationship_type,
            strength=model.strength,
            metadata=model.metadata_ or {},
            created_at=model.created_at.isoformat() if model.created_at else None,
        )

        await self._events.publish(KnowledgeEvent(
            event_type="knowledge.related",
            knowledge_id=source_id,
            title=f"{relationship_type}: {source_id} -> {target_id}",
            category="relationship",
            relationship_type=relationship_type,
            source_id=source_id,
            target_id=target_id,
            message=f"Relationship {relationship_type} created between {source_id} and {target_id}",
        ))
        return rel

    async def delete_relationship(self, relationship_id: str) -> bool:
        rel_repo = await self._repo_factory.knowledge_rel_repo()
        try:
            return await rel_repo.delete(uuid.UUID(relationship_id))
        except (ValueError, Exception):
            return False

    async def get_entry_relationships(self, entry_id: str) -> list[KnowledgeRelationship]:
        rel_repo = await self._repo_factory.knowledge_rel_repo()
        items = await rel_repo.list_for_source(entry_id)
        return [
            KnowledgeRelationship(
                id=str(item.id),
                source_id=item.source_id,
                target_id=item.target_id,
                relationship_type=item.relationship_type,
                strength=item.strength,
                metadata=item.metadata_ or {},
                created_at=item.created_at.isoformat() if item.created_at else None,
            )
            for item in items
        ]

    async def _publish_event(
        self,
        event_type: str,
        knowledge_id: str,
        title: str,
        category: str,
        source: str,
    ) -> None:
        await self._events.publish(KnowledgeEvent(
            event_type=event_type,
            knowledge_id=knowledge_id,
            title=title,
            category=category,
            source=source,
            message=f"{event_type}: {title}",
        ))

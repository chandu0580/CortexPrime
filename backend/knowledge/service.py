from __future__ import annotations

import logging
from typing import Any, Optional

try:
    from backend.database.repositories.factory import RepositoryFactory
    from backend.database.repositories.factory import repo_factory as _repo_factory
except ImportError:
    _repo_factory = None
from backend.knowledge.events import KnowledgeEventPublisher, knowledge_event_publisher
from backend.knowledge.indexer import KnowledgeIndexer
from backend.knowledge.manager import KnowledgeManager
from backend.knowledge.models import (
    IndexRequest,
    KnowledgeDocument,
    KnowledgeQuery,
    KnowledgeRelationship,
    KnowledgeSearchResult,
)
from backend.knowledge.search import KnowledgeSearch

log = logging.getLogger(__name__)


class KnowledgeService:
    def __init__(
        self,
        search: Optional[KnowledgeSearch] = None,
        manager: Optional[KnowledgeManager] = None,
        indexer: Optional[KnowledgeIndexer] = None,
        events: Optional[KnowledgeEventPublisher] = None,
        repo_factory: Optional[RepositoryFactory] = None,
    ) -> None:
        self._search = search or KnowledgeSearch(repo_factory=repo_factory)
        self._manager = manager or KnowledgeManager(events=events, repo_factory=repo_factory)
        self._indexer = indexer or KnowledgeIndexer(
            manager=self._manager, events=events, repo_factory=repo_factory,
        )
        self._events = events or knowledge_event_publisher
        self._repo_factory = repo_factory or _repo_factory or RepositoryFactory()

    # ------------------------------------------------------------------
    # CRUD
    # ------------------------------------------------------------------

    async def create_entry(self, request: IndexRequest) -> Optional[KnowledgeDocument]:
        return await self._manager.create_entry(request)

    async def get_entry(self, entry_id: str) -> Optional[KnowledgeDocument]:
        return await self._manager.get_entry(entry_id)

    async def update_entry(self, entry_id: str, updates: dict[str, Any]) -> Optional[KnowledgeDocument]:
        return await self._manager.update_entry(entry_id, updates)

    async def delete_entry(self, entry_id: str) -> bool:
        return await self._manager.delete_entry(entry_id)

    async def list_entries(
        self,
        category: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[KnowledgeDocument]:
        return await self._manager.list_entries(category=category, limit=limit, offset=offset)

    # ------------------------------------------------------------------
    # Search
    # ------------------------------------------------------------------

    async def search(self, kq: KnowledgeQuery) -> KnowledgeSearchResult:
        return await self._search.search(kq)

    async def search_relationships(
        self,
        relationship_type: Optional[str] = None,
        source_id: Optional[str] = None,
        target_id: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[KnowledgeRelationship]:
        return await self._search.search_relationships(
            relationship_type=relationship_type,
            source_id=source_id,
            target_id=target_id,
            limit=limit,
            offset=offset,
        )

    # ------------------------------------------------------------------
    # Relationships
    # ------------------------------------------------------------------

    async def create_relationship(
        self,
        source_id: str,
        target_id: str,
        relationship_type: str = "related_to",
        strength: float = 1.0,
        metadata: Optional[dict[str, Any]] = None,
    ) -> Optional[KnowledgeRelationship]:
        return await self._manager.create_relationship(
            source_id=source_id,
            target_id=target_id,
            relationship_type=relationship_type,
            strength=strength,
            metadata=metadata,
        )

    async def delete_relationship(self, relationship_id: str) -> bool:
        return await self._manager.delete_relationship(relationship_id)

    async def get_entry_relationships(self, entry_id: str) -> list[KnowledgeRelationship]:
        return await self._manager.get_entry_relationships(entry_id)

    # ------------------------------------------------------------------
    # Indexing
    # ------------------------------------------------------------------

    async def index_mission(self, mission_id: str, title: str, objective: str,
                             status: str, owner: str, result: Optional[str] = None,
                             metadata: Optional[dict[str, Any]] = None) -> Optional[KnowledgeDocument]:
        return await self._indexer.index_mission(
            mission_id=mission_id, title=title, objective=objective,
            status=status, owner=owner, result=result, metadata=metadata,
        )

    async def index_execution(self, execution_id: str, mission_id: Optional[str],
                               agent: str, status: str, trigger: str,
                               result_data: Optional[dict[str, Any]] = None,
                               error: Optional[str] = None) -> Optional[KnowledgeDocument]:
        return await self._indexer.index_execution(
            execution_id=execution_id, mission_id=mission_id,
            agent=agent, status=status, trigger=trigger,
            result_data=result_data, error=error,
        )

    async def index_governance_decision(self, decision_id: str, policy_name: str,
                                         decision: str, resource_type: str,
                                         resource_id: str, action: str,
                                         reason: str) -> Optional[KnowledgeDocument]:
        return await self._indexer.index_governance_decision(
            decision_id=decision_id, policy_name=policy_name,
            decision=decision, resource_type=resource_type,
            resource_id=resource_id, action=action, reason=reason,
        )

    async def index_connector(self, connector_id: str, name: str,
                               connector_type: str, status: str,
                               metadata: Optional[dict[str, Any]] = None) -> Optional[KnowledgeDocument]:
        return await self._indexer.index_connector(
            connector_id=connector_id, name=name,
            connector_type=connector_type, status=status, metadata=metadata,
        )

    async def index_artifact(self, name: str, description: str,
                              source: str, tags: Optional[list[str]] = None,
                              metadata: Optional[dict[str, Any]] = None) -> Optional[KnowledgeDocument]:
        return await self._indexer.index_artifact(
            name=name, description=description, source=source,
            tags=tags, metadata=metadata,
        )

    # ------------------------------------------------------------------
    # Metadata / categories
    # ------------------------------------------------------------------

    async def list_categories(self) -> list[str]:
        return await self._search.list_categories()

    async def count_by_category(self) -> dict[str, int]:
        return await self._search.count_by_category()

    # ------------------------------------------------------------------
    # Health
    # ------------------------------------------------------------------

    async def health(self) -> dict[str, Any]:
        try:
            counts = await self._search.count_by_category()
            return {
                "status": "healthy",
                "total_entries": sum(counts.values()),
                "categories": counts,
                "service": "knowledge_runtime",
            }
        except Exception as exc:
            return {
                "status": "degraded",
                "error": str(exc),
                "service": "knowledge_runtime",
            }

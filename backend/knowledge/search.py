from __future__ import annotations

import logging
from typing import Any, Optional

try:
    from backend.database.repositories.factory import RepositoryFactory
    from backend.database.repositories.factory import repo_factory as _repo_factory
except ImportError:
    _repo_factory = None
from backend.knowledge.models import (
    KnowledgeDocument,
    KnowledgeQuery,
    KnowledgeRelationship,
    KnowledgeSearchResult,
)

log = logging.getLogger(__name__)


class KnowledgeSearch:
    def __init__(
        self,
        repo_factory: Optional[RepositoryFactory] = None,
    ) -> None:
        self._repo_factory = repo_factory or _repo_factory or RepositoryFactory()

    async def search(self, kq: KnowledgeQuery) -> KnowledgeSearchResult:
        repo = await self._repo_factory.knowledge_entry_repo()
        rel_repo = await self._repo_factory.knowledge_rel_repo()

        raw = await repo.search(
            query=kq.query,
            category=kq.category,
            limit=kq.limit,
            offset=kq.offset,
        )

        total = len(raw)
        entries = [self._model_to_doc(m) for m in raw]

        if kq.tags:
            entries = [e for e in entries if e.tags and any(t in e.tags for t in kq.tags)]
            total = len(entries)

        if kq.source:
            entries = [e for e in entries if e.source == kq.source]
            total = len(entries)

        entries = self._filter_by_confidence(entries, kq.confidence_min, kq.confidence_max)
        total = len(entries)

        if kq.metadata_filter:
            entries = self._filter_by_metadata(entries, kq.metadata_filter)
            total = len(entries)

        entries = self._sort(entries, kq.sort_by, kq.sort_order)

        entries = entries[kq.offset:kq.offset + kq.limit]

        result = KnowledgeSearchResult(
            entries=entries,
            total=total,
            query=kq.query,
            limit=kq.limit,
            offset=kq.offset,
        )

        if kq.include_relationships:
            rels: list[KnowledgeRelationship] = []
            seen = set()
            for entry in entries:
                for item in await rel_repo.list_for_source(entry.id):
                    if item.id not in seen:
                        seen.add(item.id)
                        rels.append(KnowledgeRelationship(
                            id=str(item.id),
                            source_id=item.source_id,
                            target_id=item.target_id,
                            relationship_type=item.relationship_type,
                            strength=item.strength,
                            metadata=item.metadata_ or {},
                            created_at=item.created_at.isoformat() if item.created_at else None,
                        ))
                for item in await rel_repo.list_for_source(entry.id):
                    if item.id not in seen:
                        seen.add(item.id)
                        rels.append(KnowledgeRelationship(
                            id=str(item.id),
                            source_id=item.source_id,
                            target_id=item.target_id,
                            relationship_type=item.relationship_type,
                            strength=item.strength,
                            metadata=item.metadata_ or {},
                            created_at=item.created_at.isoformat() if item.created_at else None,
                        ))
            result.relationships = rels

        return result

    async def search_relationships(
        self,
        relationship_type: Optional[str] = None,
        source_id: Optional[str] = None,
        target_id: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[KnowledgeRelationship]:
        rel_repo = await self._repo_factory.knowledge_rel_repo()
        all_rels = await rel_repo.list()
        result = []
        for item in all_rels:
            if relationship_type and item.relationship_type != relationship_type:
                continue
            if source_id and item.source_id != source_id:
                continue
            if target_id and item.target_id != target_id:
                continue
            result.append(KnowledgeRelationship(
                id=str(item.id),
                source_id=item.source_id,
                target_id=item.target_id,
                relationship_type=item.relationship_type,
                strength=item.strength,
                metadata=item.metadata_ or {},
                created_at=item.created_at.isoformat() if item.created_at else None,
            ))
        result.sort(key=lambda r: r.strength, reverse=True)
        return result[offset:offset + limit]

    async def list_categories(self) -> list[str]:
        repo = await self._repo_factory.knowledge_entry_repo()
        counts = await repo.count_by_category()
        return list(counts.keys())

    async def count_by_category(self) -> dict[str, int]:
        repo = await self._repo_factory.knowledge_entry_repo()
        return await repo.count_by_category()

    def _model_to_doc(self, model: Any) -> KnowledgeDocument:
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
            embedding=None,
            created_at=model.created_at.isoformat() if model.created_at else None,
            updated_at=model.updated_at.isoformat() if model.updated_at else None,
        )

    def _filter_by_confidence(
        self,
        entries: list[KnowledgeDocument],
        min_val: Optional[float],
        max_val: Optional[float],
    ) -> list[KnowledgeDocument]:
        result = entries
        if min_val is not None:
            result = [e for e in result if e.confidence >= min_val]
        if max_val is not None:
            result = [e for e in result if e.confidence <= max_val]
        return result

    def _filter_by_metadata(
        self,
        entries: list[KnowledgeDocument],
        filters: dict[str, Any],
    ) -> list[KnowledgeDocument]:
        result = entries
        for key, value in filters.items():
            result = [e for e in result if e.metadata.get(key) == value]
        return result

    def _sort(
        self,
        entries: list[KnowledgeDocument],
        sort_by: str,
        sort_order: str,
    ) -> list[KnowledgeDocument]:
        reverse = sort_order.lower() == "desc"
        if sort_by == "title":
            entries.sort(key=lambda e: e.title.lower(), reverse=reverse)
        elif sort_by == "confidence":
            entries.sort(key=lambda e: e.confidence, reverse=reverse)
        elif sort_by == "category":
            entries.sort(key=lambda e: e.category, reverse=reverse)
        else:
            entries.sort(key=lambda e: e.created_at or "", reverse=reverse)
        return entries

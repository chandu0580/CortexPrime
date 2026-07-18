from __future__ import annotations

import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest

from backend.knowledge.models import KnowledgeDocument, KnowledgeQuery, KnowledgeSearchResult
from backend.knowledge.search import KnowledgeSearch


@pytest.fixture
def mock_entry_repo():
    repo = AsyncMock()
    repo.search = AsyncMock(return_value=[])
    repo.count_by_category = AsyncMock(return_value={})
    repo.list_by_category = AsyncMock(return_value=[])
    return repo


@pytest.fixture
def mock_rel_repo():
    repo = AsyncMock()
    repo.list_for_source = AsyncMock(return_value=[])
    repo.list = AsyncMock(return_value=[])
    return repo


@pytest.fixture
def mock_repo_factory(mock_entry_repo, mock_rel_repo):
    factory = MagicMock()
    factory.knowledge_entry_repo = AsyncMock(return_value=mock_entry_repo)
    factory.knowledge_rel_repo = AsyncMock(return_value=mock_rel_repo)
    return factory


@pytest.fixture
def search(mock_repo_factory):
    return KnowledgeSearch(repo_factory=mock_repo_factory)


def _make_doc(**kwargs) -> KnowledgeDocument:
    return KnowledgeDocument(
        id=kwargs.get("id", str(uuid.uuid4())),
        title=kwargs.get("title", "doc"),
        content=kwargs.get("content", "content"),
        summary=kwargs.get("summary", ""),
        category=kwargs.get("category", "document"),
        tags=kwargs.get("tags", []),
        source=kwargs.get("source", ""),
        source_url=kwargs.get("source_url", ""),
        confidence=kwargs.get("confidence", 1.0),
        metadata=kwargs.get("metadata", {}),
        created_at=kwargs.get("created_at", datetime.now(timezone.utc).isoformat()),
        updated_at=kwargs.get("updated_at", datetime.now(timezone.utc).isoformat()),
    )


def _make_model(**kwargs):
    model = MagicMock()
    model.id = kwargs.get("id", uuid.uuid4())
    model.title = kwargs.get("title", "doc")
    model.content = kwargs.get("content", "content")
    model.summary = kwargs.get("summary", "")
    model.category = kwargs.get("category", "document")
    model.tags = kwargs.get("tags", [])
    model.source = kwargs.get("source", "")
    model.source_url = kwargs.get("source_url", "")
    model.confidence = kwargs.get("confidence", 1.0)
    model.metadata_ = kwargs.get("metadata_", {})
    model.created_at = kwargs.get("created_at", datetime.now(timezone.utc))
    model.updated_at = kwargs.get("updated_at", datetime.now(timezone.utc))
    return model


def _make_rel_model(**kwargs):
    model = MagicMock()
    model.id = kwargs.get("id", uuid.uuid4())
    model.source_id = kwargs.get("source_id", "src-1")
    model.target_id = kwargs.get("target_id", "tgt-1")
    model.relationship_type = kwargs.get("relationship_type", "related_to")
    model.strength = kwargs.get("strength", 1.0)
    model.metadata_ = kwargs.get("metadata_", {})
    model.created_at = kwargs.get("created_at", datetime.now(timezone.utc))
    return model


@pytest.mark.asyncio
async def test_search_no_results(search, mock_entry_repo):
    mock_entry_repo.search.return_value = []
    kq = KnowledgeQuery(query="nothing")
    result = await search.search(kq)
    assert len(result.entries) == 0
    assert result.total == 0


@pytest.mark.asyncio
async def test_search_with_results(search, mock_entry_repo):
    mock_entry_repo.search.return_value = [_make_model(title="found it")]
    kq = KnowledgeQuery(query="found")
    result = await search.search(kq)
    assert len(result.entries) == 1
    assert result.entries[0].title == "found it"


@pytest.mark.asyncio
async def test_search_pagination(search, mock_entry_repo):
    mock_entry_repo.search.return_value = []
    kq = KnowledgeQuery(query="test", limit=5, offset=10)
    await search.search(kq)
    mock_entry_repo.search.assert_called_with(query="test", category=None, limit=5, offset=10)


@pytest.mark.asyncio
async def test_search_confidence_filter(search, mock_entry_repo):
    mock_entry_repo.search.return_value = [
        _make_model(title="high", confidence=0.9),
        _make_model(title="low", confidence=0.3),
    ]
    kq = KnowledgeQuery(query="test", confidence_min=0.5)
    result = await search.search(kq)
    assert len(result.entries) == 1
    assert result.entries[0].title == "high"


@pytest.mark.asyncio
async def test_search_confidence_range(search, mock_entry_repo):
    mock_entry_repo.search.return_value = [
        _make_model(title="a", confidence=0.2),
        _make_model(title="b", confidence=0.5),
        _make_model(title="c", confidence=0.9),
    ]
    kq = KnowledgeQuery(query="test", confidence_min=0.4, confidence_max=0.8)
    result = await search.search(kq)
    assert len(result.entries) == 1
    assert result.entries[0].title == "b"


@pytest.mark.asyncio
async def test_search_source_filter(search, mock_entry_repo):
    mock_entry_repo.search.return_value = [
        _make_model(title="from api", source="api"),
        _make_model(title="from cli", source="cli"),
    ]
    kq = KnowledgeQuery(query="test", source="api")
    result = await search.search(kq)
    assert len(result.entries) == 1
    assert result.entries[0].source == "api"


@pytest.mark.asyncio
async def test_search_tags_filter(search, mock_entry_repo):
    mock_entry_repo.search.return_value = [
        _make_model(title="tagged", tags=["alpha", "beta"]),
        _make_model(title="plain", tags=[]),
    ]
    kq = KnowledgeQuery(query="test", tags=["alpha"])
    result = await search.search(kq)
    assert len(result.entries) == 1


@pytest.mark.asyncio
async def test_search_metadata_filter(search, mock_entry_repo):
    mock_entry_repo.search.return_value = [
        _make_model(title="prod", metadata_={"env": "production"}),
        _make_model(title="staging", metadata_={"env": "staging"}),
    ]
    kq = KnowledgeQuery(query="test", metadata_filter={"env": "production"})
    result = await search.search(kq)
    assert len(result.entries) == 1
    assert result.entries[0].title == "prod"


@pytest.mark.asyncio
async def test_search_sort_by_title(search, mock_entry_repo):
    mock_entry_repo.search.return_value = [
        _make_model(title="zeta"),
        _make_model(title="alpha"),
    ]
    kq = KnowledgeQuery(query="test", sort_by="title", sort_order="asc")
    result = await search.search(kq)
    assert result.entries[0].title == "alpha"
    assert result.entries[1].title == "zeta"


@pytest.mark.asyncio
async def test_search_sort_by_confidence(search, mock_entry_repo):
    mock_entry_repo.search.return_value = [
        _make_model(title="low", confidence=0.3),
        _make_model(title="high", confidence=0.9),
    ]
    kq = KnowledgeQuery(query="test", sort_by="confidence", sort_order="desc")
    result = await search.search(kq)
    assert result.entries[0].title == "high"


@pytest.mark.asyncio
async def test_search_include_relationships(search, mock_entry_repo, mock_rel_repo):
    eid = uuid.uuid4()
    mock_entry_repo.search.return_value = [_make_model(id=eid)]
    mock_rel_repo.list_for_source.return_value = [
        _make_rel_model(source_id=str(eid), target_id="tgt-1"),
    ]
    kq = KnowledgeQuery(query="test", include_relationships=True)
    result = await search.search(kq)
    assert result.relationships is not None
    assert len(result.relationships) == 1


@pytest.mark.asyncio
async def test_search_relationship_by_type(search, mock_rel_repo):
    mock_rel_repo.list.return_value = [
        _make_rel_model(source_id="a", target_id="b", relationship_type="depends_on"),
        _make_rel_model(source_id="c", target_id="d", relationship_type="related_to"),
    ]
    rels = await search.search_relationships(relationship_type="depends_on")
    assert len(rels) == 1
    assert rels[0].relationship_type == "depends_on"


@pytest.mark.asyncio
async def test_search_relationship_by_source(search, mock_rel_repo):
    mock_rel_repo.list.return_value = [
        _make_rel_model(source_id="src-1", target_id="tgt-1"),
        _make_rel_model(source_id="src-2", target_id="tgt-2"),
    ]
    rels = await search.search_relationships(source_id="src-1")
    assert len(rels) == 1


@pytest.mark.asyncio
async def test_search_relationship_pagination(search, mock_rel_repo):
    mock_rel_repo.list.return_value = [
        _make_rel_model(source_id="a", target_id="b"),
        _make_rel_model(source_id="c", target_id="d"),
        _make_rel_model(source_id="e", target_id="f"),
    ]
    rels = await search.search_relationships(limit=1, offset=1)
    assert len(rels) == 1


@pytest.mark.asyncio
async def test_list_categories(search, mock_entry_repo):
    mock_entry_repo.count_by_category.return_value = {"doc": 3, "mission": 1}
    cats = await search.list_categories()
    assert sorted(cats) == ["doc", "mission"]


@pytest.mark.asyncio
async def test_count_by_category(search, mock_entry_repo):
    mock_entry_repo.count_by_category.return_value = {"doc": 5}
    counts = await search.count_by_category()
    assert counts["doc"] == 5

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest

from backend.knowledge.models import (
    IndexRequest,
    KnowledgeDocument,
    KnowledgeQuery,
    KnowledgeSearchResult,
    RelationshipType,
)
from backend.knowledge.service import KnowledgeService


@pytest.fixture
def mock_entry_repo():
    repo = AsyncMock()
    repo.list = AsyncMock(return_value=[])
    repo.list_by_category = AsyncMock(return_value=[])
    repo.get = AsyncMock(return_value=None)
    repo.create = AsyncMock()
    repo.update = AsyncMock()
    repo.delete = AsyncMock(return_value=True)
    repo.search = AsyncMock(return_value=[])
    repo.count_by_category = AsyncMock(return_value={})
    return repo


@pytest.fixture
def mock_rel_repo():
    repo = AsyncMock()
    repo.create = AsyncMock()
    repo.list = AsyncMock(return_value=[])
    repo.list_for_source = AsyncMock(return_value=[])
    repo.delete = AsyncMock(return_value=True)
    return repo


@pytest.fixture
def mock_repo_factory(mock_entry_repo, mock_rel_repo):
    factory = MagicMock()
    factory.knowledge_entry_repo = AsyncMock(return_value=mock_entry_repo)
    factory.knowledge_rel_repo = AsyncMock(return_value=mock_rel_repo)
    return factory


@pytest.fixture
def service(mock_repo_factory):
    return KnowledgeService(repo_factory=mock_repo_factory)


def _make_model(**kwargs):
    model = MagicMock()
    model.id = kwargs.get("id", uuid.uuid4())
    model.title = kwargs.get("title", "test-entry")
    model.content = kwargs.get("content", "test content")
    model.summary = kwargs.get("summary", "")
    model.category = kwargs.get("category", "document")
    model.tags = kwargs.get("tags", [])
    model.source = kwargs.get("source", "")
    model.source_url = kwargs.get("source_url", "")
    model.confidence = kwargs.get("confidence", 1.0)
    model.metadata_ = kwargs.get("metadata_", {})
    model.embedding = kwargs.get("embedding")
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


# ---------------------------------------------------------------------------
# CRUD
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_create_entry(service, mock_entry_repo):
    eid = uuid.uuid4()
    mock_entry_repo.create.return_value = _make_model(id=eid, title="new-entry")
    request = IndexRequest(title="new-entry", content="content", category="document")
    doc = await service.create_entry(request)
    assert doc is not None
    assert doc.title == "new-entry"
    assert doc.category == "document"
    assert doc.id == str(eid)


@pytest.mark.asyncio
async def test_get_entry_found(service, mock_entry_repo):
    eid = uuid.uuid4()
    mock_entry_repo.get.return_value = _make_model(id=eid, title="found")
    doc = await service.get_entry(str(eid))
    assert doc is not None
    assert doc.title == "found"


@pytest.mark.asyncio
async def test_get_entry_not_found(service, mock_entry_repo):
    mock_entry_repo.get.return_value = None
    doc = await service.get_entry(str(uuid.uuid4()))
    assert doc is None


@pytest.mark.asyncio
async def test_update_entry(service, mock_entry_repo):
    eid = uuid.uuid4()
    mock_entry_repo.get.return_value = _make_model(id=eid, title="old")
    mock_entry_repo.update.return_value = _make_model(id=eid, title="updated")
    doc = await service.update_entry(str(eid), {"title": "updated"})
    assert doc is not None
    assert doc.title == "updated"


@pytest.mark.asyncio
async def test_update_entry_not_found(service, mock_entry_repo):
    mock_entry_repo.get.return_value = None
    doc = await service.update_entry(str(uuid.uuid4()), {"title": "x"})
    assert doc is None


@pytest.mark.asyncio
async def test_delete_entry(service, mock_entry_repo):
    eid = uuid.uuid4()
    mock_entry_repo.get.return_value = _make_model(id=eid)
    result = await service.delete_entry(str(eid))
    assert result is True


@pytest.mark.asyncio
async def test_delete_entry_not_found(service, mock_entry_repo):
    mock_entry_repo.get.return_value = None
    result = await service.delete_entry(str(uuid.uuid4()))
    assert result is False


@pytest.mark.asyncio
async def test_list_entries(service, mock_entry_repo):
    mock_entry_repo.list.return_value = [_make_model(title="a"), _make_model(title="b")]
    entries = await service.list_entries()
    assert len(entries) == 2


@pytest.mark.asyncio
async def test_list_entries_by_category(service, mock_entry_repo):
    mock_entry_repo.list_by_category.return_value = [_make_model(title="c", category="mission")]
    entries = await service.list_entries(category="mission")
    assert len(entries) == 1
    assert entries[0].category == "mission"


# ---------------------------------------------------------------------------
# Relationships
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_create_relationship(service, mock_rel_repo):
    mock_rel_repo.create.return_value = _make_rel_model(
        source_id="src-1", target_id="tgt-1", relationship_type="depends_on",
    )
    rel = await service.create_relationship(
        source_id="src-1", target_id="tgt-1", relationship_type="depends_on",
    )
    assert rel is not None
    assert rel.source_id == "src-1"
    assert rel.target_id == "tgt-1"
    assert rel.relationship_type == "depends_on"


@pytest.mark.asyncio
async def test_get_entry_relationships(service, mock_rel_repo):
    mock_rel_repo.list_for_source.return_value = [
        _make_rel_model(source_id="src-1", target_id="tgt-a"),
        _make_rel_model(source_id="src-1", target_id="tgt-b"),
    ]
    rels = await service.get_entry_relationships("src-1")
    assert len(rels) == 2


@pytest.mark.asyncio
async def test_delete_relationship(service, mock_rel_repo):
    result = await service.delete_relationship(str(uuid.uuid4()))
    assert result is True


# ---------------------------------------------------------------------------
# Search
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_search_keyword(service, mock_entry_repo):
    mock_entry_repo.search.return_value = [_make_model(title="found")]
    kq = KnowledgeQuery(query="test", limit=10)
    result = await service.search(kq)
    assert len(result.entries) == 1
    assert result.entries[0].title == "found"


@pytest.mark.asyncio
async def test_search_empty(service, mock_entry_repo):
    mock_entry_repo.search.return_value = []
    kq = KnowledgeQuery(query="nonexistent")
    result = await service.search(kq)
    assert len(result.entries) == 0
    assert result.total == 0


@pytest.mark.asyncio
async def test_search_with_category(service, mock_entry_repo):
    mock_entry_repo.search.return_value = [_make_model(title="m", category="mission")]
    kq = KnowledgeQuery(query="test", category="mission")
    result = await service.search(kq)
    assert len(result.entries) == 1
    mock_entry_repo.search.assert_called_with(query="test", category="mission", limit=20, offset=0)


@pytest.mark.asyncio
async def test_search_with_pagination(service, mock_entry_repo):
    mock_entry_repo.search.return_value = []
    kq = KnowledgeQuery(query="test", limit=5, offset=10)
    await service.search(kq)
    mock_entry_repo.search.assert_called_with(query="test", category=None, limit=5, offset=10)


@pytest.mark.asyncio
async def test_search_relationships(service, mock_rel_repo):
    mock_rel_repo.list.return_value = [
        _make_rel_model(source_id="src-1", target_id="tgt-1", relationship_type="depends_on"),
        _make_rel_model(source_id="src-2", target_id="tgt-2", relationship_type="related_to"),
    ]
    rels = await service.search_relationships(relationship_type="depends_on")
    assert len(rels) == 1
    assert rels[0].relationship_type == "depends_on"


@pytest.mark.asyncio
async def test_search_relationships_by_source(service, mock_rel_repo):
    mock_rel_repo.list.return_value = [
        _make_rel_model(source_id="src-1", target_id="tgt-1"),
        _make_rel_model(source_id="src-2", target_id="tgt-2"),
    ]
    rels = await service.search_relationships(source_id="src-1")
    assert len(rels) == 1


# ---------------------------------------------------------------------------
# Indexing
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_index_mission(service, mock_entry_repo):
    eid = uuid.uuid4()
    mock_entry_repo.create.return_value = _make_model(id=eid, title="Mission: test", category="mission")
    doc = await service.index_mission(
        mission_id="mis-1", title="test", objective="do something",
        status="completed", owner="tester",
    )
    assert doc is not None
    assert doc.category == "mission"


@pytest.mark.asyncio
async def test_index_execution(service, mock_entry_repo, mock_rel_repo):
    eid = uuid.uuid4()
    mock_entry_repo.create.return_value = _make_model(id=eid, title="Execution: exec-1", category="execution")
    mock_rel_repo.create.return_value = _make_rel_model()
    doc = await service.index_execution(
        execution_id="exec-1", mission_id="mis-1", agent="agent1",
        status="completed", trigger="manual",
    )
    assert doc is not None


@pytest.mark.asyncio
async def test_index_governance_decision(service, mock_entry_repo):
    eid = uuid.uuid4()
    mock_entry_repo.create.return_value = _make_model(id=eid, title="Governance: test-policy", category="policy")
    doc = await service.index_governance_decision(
        decision_id="dec-1", policy_name="test-policy",
        decision="DENY", resource_type="mission", resource_id="res-1",
        action="execute", reason="policy denied",
    )
    assert doc is not None
    assert doc.category == "policy"


@pytest.mark.asyncio
async def test_index_connector(service, mock_entry_repo):
    eid = uuid.uuid4()
    mock_entry_repo.create.return_value = _make_model(id=eid, title="Connector: my-conn", category="connector")
    doc = await service.index_connector(
        connector_id="conn-1", name="my-conn", connector_type="github", status="active",
    )
    assert doc is not None
    assert doc.category == "connector"


@pytest.mark.asyncio
async def test_index_artifact(service, mock_entry_repo):
    eid = uuid.uuid4()
    mock_entry_repo.create.return_value = _make_model(id=eid, title="Artifact: build.zip", category="artifact")
    doc = await service.index_artifact(
        name="build.zip", description="release build", source="ci_pipeline",
        tags=["release", "v1.0"],
    )
    assert doc is not None
    assert doc.category == "artifact"


# ---------------------------------------------------------------------------
# Categories
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_list_categories(service, mock_entry_repo):
    mock_entry_repo.count_by_category.return_value = {"document": 3, "mission": 1}
    cats = await service.list_categories()
    assert sorted(cats) == ["document", "mission"]


@pytest.mark.asyncio
async def test_count_by_category(service, mock_entry_repo):
    mock_entry_repo.count_by_category.return_value = {"document": 3}
    counts = await service.count_by_category()
    assert counts["document"] == 3


# ---------------------------------------------------------------------------
# Health
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_health(service, mock_entry_repo):
    mock_entry_repo.count_by_category.return_value = {"document": 5}
    result = await service.health()
    assert result["status"] == "healthy"
    assert result["total_entries"] == 5

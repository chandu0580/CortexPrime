"""
Live Research Runtime Tests.

Tests every layer of the research pipeline:
  1. TavilyClient — configured check, response shape, live-trigger detection
  2. SourceRanker — scoring, top-k limit, min_score filter
  3. CitationEngine — build, format_for_prompt, annotate_response
  4. LiveResearchPipeline — full run (mocked Tavily + mocked LLM)
  5. /health/research endpoint — shape + status values
  6. /api/research/search endpoint — full pipeline via HTTP

Tests that require TAVILY_API_KEY are skipped when it's not set.
No mocks are used for the live integration tests so they serve as real smoke tests.
"""
from __future__ import annotations

import os
from typing import Any, Dict, List
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from backend.auth.jwt_handler import create_access_token


@pytest.fixture(autouse=True)
def _no_blacklist():
    mock_redis = AsyncMock()
    mock_redis.get = AsyncMock(return_value=None)
    with patch(
        "backend.auth.token_blacklist.TokenBlacklist._get_redis",
        new_callable=AsyncMock,
        return_value=mock_redis,
    ):
        yield


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _tavily_configured() -> bool:
    return bool(os.getenv("TAVILY_API_KEY", ""))


SKIP_LIVE = pytest.mark.skipif(
    not _tavily_configured(),
    reason="TAVILY_API_KEY not set — skipping live Tavily integration tests",
)


def _fake_sources(n: int = 3) -> List[Any]:
    """Build fake TavilySource objects for unit tests."""
    from backend.research.tavily_client import TavilySource
    return [
        TavilySource(
            title     = f"Source {i}",
            url       = f"https://example{i}.com/article",
            snippet   = f"This is snippet content for source {i}.",
            score     = 0.9 - i * 0.1,
            published = "2025-06-01",
        )
        for i in range(n)
    ]


def _fake_tavily_response(query: str = "test query", n: int = 3):
    from backend.research.tavily_client import TavilyResponse
    return TavilyResponse(
        query        = query,
        sources      = _fake_sources(n),
        answer       = "A direct answer.",
        latency_ms   = 120.0,
        search_type  = "general",
    )


# ===========================================================================
# 1. TavilyClient unit tests
# ===========================================================================

def test_tavily_configured_when_api_key_set(monkeypatch):
    monkeypatch.setenv("TAVILY_API_KEY", "tvly-test-key")
    from backend.research.tavily_client import TavilyClient
    client = TavilyClient()
    assert client.is_configured() is True


def test_tavily_not_configured_when_no_key(monkeypatch):
    monkeypatch.delenv("TAVILY_API_KEY", raising=False)
    from backend.research.tavily_client import TavilyClient
    client = TavilyClient()
    assert client.is_configured() is False


@pytest.mark.parametrize("query,expected", [
    ("latest AI news",           True),   # 'latest' trigger
    ("what is machine learning", False),  # no live triggers
    ("today's top stories",      True),   # "today" substring in "today's"
    ("compare GPT-5 and Claude", True),   # 'compare' is a trigger
    ("current OpenAI models",    True),   # 'current' trigger
    ("Python tutorial",          False),  # no live triggers
])
def test_live_trigger_detection(query, expected):
    from backend.research.tavily_client import TavilyClient
    assert TavilyClient.needs_live_search(query) == expected


@pytest.mark.asyncio
async def test_tavily_returns_empty_on_missing_key(monkeypatch):
    """No API key → returns empty TavilyResponse without raising."""
    monkeypatch.delenv("TAVILY_API_KEY", raising=False)
    from backend.research.tavily_client import TavilyClient
    client = TavilyClient()
    result = await client.search("AI news")
    assert result.sources == []
    assert result.source_count == 0
    assert result.answer is None


def test_tavily_source_domain_parsing():
    from backend.research.tavily_client import TavilySource
    src = TavilySource(
        title="Test", url="https://www.arxiv.org/abs/1234",
        snippet="content", score=0.8,
    )
    assert src.domain == "arxiv.org"


def test_tavily_response_to_dict_shape():
    resp = _fake_tavily_response()
    d    = resp.to_dict()
    assert "query"        in d
    assert "sources"      in d
    assert "source_count" in d
    assert "latency_ms"   in d
    assert d["source_count"] == 3


# ===========================================================================
# 2. SourceRanker unit tests
# ===========================================================================

def test_source_ranker_returns_top_k():
    from backend.research.source_ranker import SourceRanker
    sources = _fake_sources(10)
    ranked  = SourceRanker().rank(sources, top_k=3)
    assert len(ranked) == 3


def test_source_ranker_descending_order():
    from backend.research.source_ranker import SourceRanker
    sources = _fake_sources(5)
    ranked  = SourceRanker().rank(sources)
    scores  = [r["final_score"] for r in ranked]
    assert scores == sorted(scores, reverse=True)


def test_source_ranker_score_fields():
    from backend.research.source_ranker import SourceRanker
    sources = _fake_sources(2)
    ranked  = SourceRanker().rank(sources)
    for r in ranked:
        assert "relevance_score"  in r
        assert "recency_score"    in r
        assert "authority_score"  in r
        assert "final_score"      in r
        assert 0.0 <= r["final_score"] <= 1.0


def test_source_ranker_high_authority():
    from backend.research.tavily_client import TavilySource
    from backend.research.source_ranker import SourceRanker, _AUTHORITY_SCORE
    src = TavilySource(
        title="Paper", url="https://arxiv.org/abs/9999",
        snippet="Abstract", score=0.7,
    )
    ranked = SourceRanker().rank([src])
    assert ranked[0]["authority_score"] >= _AUTHORITY_SCORE["high"] * 0.9


def test_source_ranker_min_score_filter():
    from backend.research.source_ranker import SourceRanker
    sources = _fake_sources(5)
    ranked  = SourceRanker().rank(sources, min_score=0.99)
    assert ranked == []  # no source should score 0.99


def test_source_ranker_recency_no_date():
    from backend.research.tavily_client import TavilySource
    from backend.research.source_ranker import SourceRanker
    src = TavilySource(title="X", url="https://x.com", snippet="x", score=0.8)
    assert src.published is None
    ranked = SourceRanker().rank([src])
    # recency should default to 0.5 — score must be non-zero
    assert ranked[0]["recency_score"] == 0.5


# ===========================================================================
# 3. CitationEngine unit tests
# ===========================================================================

def test_citation_engine_builds_correct_count():
    from backend.research.source_ranker  import SourceRanker
    from backend.research.citation_engine import CitationEngine
    sources   = _fake_sources(4)
    ranked    = SourceRanker().rank(sources)
    citations = CitationEngine().build(ranked)
    assert len(citations) == len(ranked)


def test_citation_indices_are_1_based():
    from backend.research.source_ranker  import SourceRanker
    from backend.research.citation_engine import CitationEngine
    sources   = _fake_sources(3)
    ranked    = SourceRanker().rank(sources)
    citations = CitationEngine().build(ranked)
    assert [c.index for c in citations] == list(range(1, len(citations) + 1))


def test_citation_markers():
    from backend.research.source_ranker  import SourceRanker
    from backend.research.citation_engine import CitationEngine
    sources   = _fake_sources(2)
    ranked    = SourceRanker().rank(sources)
    citations = CitationEngine().build(ranked)
    assert citations[0].marker == "[1]"
    assert citations[1].marker == "[2]"


def test_format_for_prompt_no_sources():
    from backend.research.citation_engine import CitationEngine
    text = CitationEngine().format_for_prompt([])
    assert "No external sources" in text


def test_format_for_prompt_includes_urls():
    from backend.research.source_ranker  import SourceRanker
    from backend.research.citation_engine import CitationEngine
    sources   = _fake_sources(2)
    ranked    = SourceRanker().rank(sources)
    citations = CitationEngine().build(ranked)
    prompt    = CitationEngine().format_for_prompt(citations)
    for c in citations:
        assert c.url in prompt


def test_annotate_response_appends_references():
    from backend.research.source_ranker  import SourceRanker
    from backend.research.citation_engine import CitationEngine
    sources   = _fake_sources(2)
    ranked    = SourceRanker().rank(sources)
    citations = CitationEngine().build(ranked)
    result    = CitationEngine().annotate_response("This is the response [1].", citations)
    assert "Sources:" in result
    assert citations[0].url in result


def test_citation_to_dict_shape():
    from backend.research.source_ranker  import SourceRanker
    from backend.research.citation_engine import CitationEngine
    sources   = _fake_sources(1)
    ranked    = SourceRanker().rank(sources)
    citations = CitationEngine().build(ranked)
    d         = citations[0].to_dict()
    for key in ("index", "marker", "title", "url", "domain", "snippet", "score"):
        assert key in d


# ===========================================================================
# 4. LiveResearchPipeline unit tests (mocked Tavily + LLM)
# ===========================================================================

@pytest.mark.asyncio
async def test_pipeline_run_returns_result():
    """Full pipeline run with mocked Tavily + LLM."""
    from backend.research.live_research_pipeline import LiveResearchPipeline

    pipeline     = LiveResearchPipeline()
    fake_resp    = _fake_tavily_response("latest AI news", n=4)
    fake_synth   = "GPT-5 was released in 2025 [1]. Claude 3 followed [2]."

    # "latest AI news" hits _NEWS_TRIGGERS (contains 'news'), so the pipeline
    # routes to search_news — patch that method instead of search.
    # Also patch is_configured() so the pipeline doesn't skip Tavily in CI.
    with patch(
        "backend.research.live_research_pipeline.tavily_client.is_configured",
        return_value=True,
    ), patch(
        "backend.research.live_research_pipeline.tavily_client.search_news",
        new_callable=AsyncMock, return_value=fake_resp,
    ), patch(
        "backend.research.live_research_pipeline.LiveResearchPipeline._synthesize",
        new_callable=AsyncMock, return_value=fake_synth,
    ), patch(
        "backend.research.live_research_pipeline.LiveResearchPipeline._store_memory",
        new_callable=AsyncMock,
    ), patch(
        "backend.research.live_research_pipeline.LiveResearchPipeline._audit",
        new_callable=AsyncMock,
    ):
        result = await pipeline.run(query="latest AI news", force_live=True)

    assert result.success
    assert len(result.sources) > 0
    assert result.synthesis == fake_synth
    assert "[1]" in result.annotated or "Sources:" in result.annotated
    assert isinstance(result.citations, list)
    assert result.citations[0]["index"] == 1


@pytest.mark.asyncio
async def test_pipeline_run_no_sources():
    """Pipeline handles zero Tavily sources gracefully."""
    from backend.research.tavily_client          import TavilyResponse
    from backend.research.live_research_pipeline import LiveResearchPipeline

    pipeline  = LiveResearchPipeline()
    empty_resp = TavilyResponse(
        query="obscure query", sources=[], answer=None,
        latency_ms=50.0, search_type="general",
    )

    with patch(
        "backend.research.live_research_pipeline.tavily_client.search",
        new_callable=AsyncMock, return_value=empty_resp,
    ), patch(
        "backend.research.live_research_pipeline.LiveResearchPipeline._synthesize",
        new_callable=AsyncMock, return_value="No sources found.",
    ), patch(
        "backend.research.live_research_pipeline.LiveResearchPipeline._store_memory",
        new_callable=AsyncMock,
    ), patch(
        "backend.research.live_research_pipeline.LiveResearchPipeline._audit",
        new_callable=AsyncMock,
    ):
        result = await pipeline.run(query="obscure query", force_live=True)

    assert result.sources    == []
    assert result.citations  == []
    assert result.success    is False   # no sources → not a successful search


@pytest.mark.asyncio
async def test_pipeline_records_telemetry():
    """Telemetry must be updated after a pipeline run."""
    from backend.research.live_research_pipeline import LiveResearchPipeline
    from backend.research.research_telemetry     import ResearchTelemetry

    pipeline  = LiveResearchPipeline()
    telemetry = ResearchTelemetry()
    fake_resp = _fake_tavily_response("test", n=3)

    with patch(
        "backend.research.live_research_pipeline.tavily_client.is_configured",
        return_value=True,
    ), patch(
        "backend.research.live_research_pipeline.tavily_client.search",
        new_callable=AsyncMock, return_value=fake_resp,
    ), patch(
        "backend.research.live_research_pipeline.LiveResearchPipeline._synthesize",
        new_callable=AsyncMock, return_value="synthesised text",
    ), patch(
        "backend.research.live_research_pipeline.LiveResearchPipeline._store_memory",
        new_callable=AsyncMock,
    ), patch(
        "backend.research.live_research_pipeline.LiveResearchPipeline._audit",
        new_callable=AsyncMock,
    ), patch(
        "backend.research.live_research_pipeline.research_telemetry",
        telemetry,
    ):
        await pipeline.run(query="test", force_live=True)

    assert telemetry._total_searches == 1
    assert telemetry._total_sources  == 3


# ===========================================================================
# 5. /health/research endpoint
# ===========================================================================

@pytest.mark.asyncio
async def test_health_research_shape():
    from httpx import AsyncClient, ASGITransport
    from backend.main import app

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.get("/health/research")

    assert resp.status_code == 200
    body = resp.json()

    required = {
        "status", "provider", "configured",
        "total_searches", "success_rate",
        "avg_latency_ms", "avg_source_count", "recent_searches",
    }
    missing = required - set(body.keys())
    assert not missing, f"/health/research missing keys: {missing}"
    assert body["provider"] == "tavily"
    assert body["status"] in ("healthy", "degraded", "unavailable")


@pytest.mark.asyncio
async def test_health_research_unavailable_when_no_key(monkeypatch):
    monkeypatch.delenv("TAVILY_API_KEY", raising=False)
    from httpx import AsyncClient, ASGITransport
    from backend.main import app
    from backend.research.tavily_client import tavily_client

    # Reset the singleton's api_key to reflect monkeypatch
    original = tavily_client.api_key
    tavily_client.api_key = ""
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.get("/health/research")
        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "unavailable"
        assert body["warning"] is not None
    finally:
        tavily_client.api_key = original


# ===========================================================================
# 6. /api/research/search endpoint (mocked)
# ===========================================================================

@pytest.mark.asyncio
async def test_search_endpoint_returns_required_fields():
    from httpx import AsyncClient, ASGITransport
    from backend.main import app
    from backend.research.live_research_pipeline import ResearchResult

    fake_result = ResearchResult(
        query        = "latest AI news",
        execution_id = "exec-001",
        search_type  = "general",
        sources      = [{"title": "T", "url": "https://x.com", "final_score": 0.8, "snippet": "x", "domain": "x.com", "relevance_score": 0.8, "recency_score": 0.7, "authority_score": 0.6, "score": 0.8, "published": None}],
        citations    = [{"index": 1, "marker": "[1]", "title": "T", "url": "https://x.com", "domain": "x.com", "snippet": "x", "published": None, "score": 0.8}],
        answer       = "Direct answer",
        synthesis    = "This is a synthesised response [1].",
        annotated    = "This is a synthesised response [1].\n\n---\n**Sources:**\n[1] [T](https://x.com)",
        latency_ms   = 240.0,
        success      = True,
    )

    headers = {
        "Authorization": f"Bearer {create_access_token(user_id='research-user', role='user')}"
    }

    with patch(
        "backend.research.live_research_pipeline.live_research_pipeline.run",
        new_callable=AsyncMock,
        return_value=fake_result,
    ):
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.post(
                "/api/research/search",
                json={"query": "latest AI news", "force_live": True},
                headers=headers,
            )

    assert resp.status_code == 200
    body = resp.json()
    required = {"query", "sources", "citations", "response", "source_count", "success"}
    missing  = required - set(body.keys())
    assert not missing, f"/api/research/search missing keys: {missing}"
    assert body["success"] is True
    assert body["source_count"] == 1


# ===========================================================================
# 7. Live integration tests (only when TAVILY_API_KEY is set)
# ===========================================================================

@SKIP_LIVE
@pytest.mark.asyncio
async def test_live_search_returns_real_sources():
    """Real Tavily call — requires TAVILY_API_KEY."""
    from backend.research.tavily_client import TavilyClient
    client = TavilyClient()
    result = await client.search("OpenAI GPT-5 release date", max_results=3)
    assert result.source_count >= 1
    for src in result.sources:
        assert src.url.startswith("http")
        assert src.title


@SKIP_LIVE
@pytest.mark.asyncio
async def test_live_news_search():
    """Real Tavily news call — requires TAVILY_API_KEY."""
    from backend.research.tavily_client import TavilyClient
    client = TavilyClient()
    result = await client.search_news("AI latest news", days=3, max_results=3)
    assert result.source_count >= 1
    assert result.search_type == "news"


@SKIP_LIVE
@pytest.mark.asyncio
async def test_live_pipeline_end_to_end():
    """
    Full pipeline with real Tavily + real LLM.
    Proves: live search → ranking → citations → synthesis → annotated response.
    """
    from backend.research.live_research_pipeline import LiveResearchPipeline
    pipeline = LiveResearchPipeline()
    result   = await pipeline.run(
        query      = "latest developments in large language models 2025",
        force_live = True,
    )
    assert result.success
    assert len(result.sources) >= 1
    assert result.synthesis
    assert len(result.citations) >= 1
    assert "Sources:" in result.annotated or result.annotated
    # Verify citation indices are in annotated text
    for c in result.citations:
        assert c["marker"] in result.annotated or c["url"] in result.annotated

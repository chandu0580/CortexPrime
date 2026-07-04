"""
Category 08 — Research Test
==============================
Validates the live research pipeline:

  Live Tavily search → Citation generation → Memory storage → Telemetry

Tests include both unit-level (no network) and live integration tests.
Live tests are skipped when TAVILY_API_KEY is not set.
"""
from __future__ import annotations

import os
import time
from pathlib import Path
from typing import Any, Dict, List

from tests.production_validation import (
    CategoryResult, CheckResult, CheckStatus,
    http_get, http_post,
    pass_, fail_, skip_, warn_, check,
    backend_is_up, BASE_URL, MISSION_TIMEOUT,
)


def _load_env():
    """Load .env into os.environ if not already set."""
    env_path = Path("backend/.env")
    if env_path.exists():
        for line in env_path.read_text().splitlines():
            if "=" in line and not line.strip().startswith("#"):
                k, _, v = line.partition("=")
                os.environ.setdefault(k.strip(), v.strip())


_load_env()


# ---------------------------------------------------------------------------
# Tavily client checks
# ---------------------------------------------------------------------------

def _check_tavily_client_importable() -> CheckResult:
    try:
        from backend.research.tavily_client import TavilyClient, tavily_client
        configured = tavily_client.is_configured()
        return pass_("tavily_client_importable",
                     f"TavilyClient importable — configured: {configured}")
    except ImportError as exc:
        return fail_("tavily_client_importable", f"Import failed: {exc}")
    except Exception as exc:
        return warn_("tavily_client_importable", f"Warning: {exc}")


def _check_tavily_key_configured() -> CheckResult:
    key = os.getenv("TAVILY_API_KEY", "")
    if key and len(key) > 10:
        masked = key[:8] + "..." + key[-4:]
        return pass_("tavily_key_configured", f"TAVILY_API_KEY configured: {masked}")
    return fail_("tavily_key_configured",
                 "TAVILY_API_KEY not set — live research unavailable")


def _check_live_trigger_detection() -> CheckResult:
    """needs_live_search() detects research-triggering queries."""
    try:
        from backend.research.tavily_client import tavily_client
        live_queries = [
            "latest AI news 2025",
            "current status of OpenAI",
            "today's top stories in tech",
            "compare GPT-4 vs Claude",
        ]
        non_live = [
            "what is Python",
            "explain machine learning",
        ]
        triggered = [q for q in live_queries if tavily_client.needs_live_search(q)]
        skipped   = [q for q in non_live   if not tavily_client.needs_live_search(q)]

        if len(triggered) == len(live_queries) and len(skipped) == len(non_live):
            return pass_("live_trigger_detection",
                         f"Live trigger detection correct ({len(triggered)} triggered, {len(skipped)} skipped)")
        issues = []
        if len(triggered) < len(live_queries):
            missed = [q for q in live_queries if not tavily_client.needs_live_search(q)]
            issues.append(f"Missed triggers: {missed}")
        if len(skipped) < len(non_live):
            false_pos = [q for q in non_live if tavily_client.needs_live_search(q)]
            issues.append(f"False positives: {false_pos}")
        return warn_("live_trigger_detection",
                     f"Trigger detection issues: {'; '.join(issues)}")
    except Exception as exc:
        return fail_("live_trigger_detection", f"Check failed: {exc}")


def _check_source_ranker() -> CheckResult:
    """SourceRanker correctly scores and orders sources (returns dicts)."""
    try:
        from backend.research.source_ranker import source_ranker
        from backend.research.tavily_client import TavilySource

        sources = [
            TavilySource(title="OpenAI Blog",  url="https://openai.com/blog/gpt4",  snippet="GPT-4", score=0.9),
            TavilySource(title="Random Blog",  url="http://randomblog.io/post",      snippet="AI",   score=0.3),
            TavilySource(title="ArXiv Paper",  url="https://arxiv.org/abs/2301.01",  snippet="Research", score=0.8),
        ]
        ranked = source_ranker.rank(sources, top_k=3)  # returns List[Dict]

        has_final_score   = all("final_score" in d for d in ranked)
        is_descending     = all(ranked[i]["final_score"] >= ranked[i+1]["final_score"] for i in range(len(ranked)-1))
        top_url           = ranked[0]["url"] if ranked else ""
        authority_rewarded = top_url in ("https://openai.com/blog/gpt4", "https://arxiv.org/abs/2301.01")

        if has_final_score and is_descending and authority_rewarded:
            return pass_("source_ranker",
                         f"SourceRanker: {len(ranked)} sources ranked correctly")
        issues = []
        if not has_final_score:    issues.append("final_score missing")
        if not is_descending:      issues.append("not descending order")
        if not authority_rewarded: issues.append(f"authority not rewarded (top={top_url[:40]})")
        return warn_("source_ranker", f"Ranker issues: {', '.join(issues)}")
    except Exception as exc:
        return fail_("source_ranker", f"Ranker check failed: {exc}")


def _check_citation_engine() -> CheckResult:
    """CitationEngine produces correct [N] markers from ranked source dicts."""
    try:
        from backend.research.citation_engine import citation_engine

        # citation_engine.build() takes List[Dict], not objects
        sources = [
            {"title": f"Source {i}", "url": f"https://example{i}.com",
             "snippet": f"Snippet {i}", "domain": f"example{i}.com",
             "final_score": 0.8, "published": None}
            for i in range(3)
        ]
        citations = citation_engine.build(sources)

        expected_markers = {"[1]", "[2]", "[3]"}
        got_markers      = {c.marker for c in citations}

        if expected_markers == got_markers:
            return pass_("citation_engine",
                         f"CitationEngine generated {len(citations)} citations with correct markers")
        return fail_("citation_engine",
                     f"Markers mismatch: expected {expected_markers}, got {got_markers}")
    except Exception as exc:
        return fail_("citation_engine", f"CitationEngine check failed: {exc}")


def _check_research_telemetry() -> CheckResult:
    """ResearchTelemetry snapshot has correct structure."""
    try:
        from backend.research.research_telemetry import ResearchTelemetry
        tel  = ResearchTelemetry()
        snap = tel.snapshot()
        # Actual keys from the implementation
        required = {"total_searches", "total_successes", "success_rate"}
        missing  = required - set(snap.keys())
        if not missing:
            return pass_("research_telemetry", "ResearchTelemetry snapshot structure correct",
                         keys=list(snap.keys()))
        return fail_("research_telemetry",
                     f"Snapshot missing keys: {missing}")
    except Exception as exc:
        return fail_("research_telemetry", f"Telemetry check failed: {exc}")


def _check_research_health_route() -> CheckResult:
    code, body = http_get("/health/research", timeout=10.0)
    if code == 200 and isinstance(body, dict):
        configured = body.get("configured", "?")
        return pass_("research_health_route",
                     f"/health/research — configured: {configured}")
    return fail_("research_health_route", f"/health/research HTTP {code}")


def _check_research_history_route() -> CheckResult:
    code, body = http_get("/api/research/history", timeout=5.0)
    if code == 200:
        return pass_("research_history_route", "/api/research/history accessible")
    return warn_("research_history_route", f"/api/research/history HTTP {code}")


def _check_live_tavily_search() -> CheckResult:
    """
    Real Tavily search for a live-trigger query.
    Skipped if TAVILY_API_KEY is not configured.
    """
    key = os.getenv("TAVILY_API_KEY", "")
    if not key or len(key) < 10:
        return skip_("live_tavily_search", "TAVILY_API_KEY not configured")

    try:
        import asyncio
        from backend.research.tavily_client import TavilyClient
        client = TavilyClient()

        async def _run():
            return await client.search("latest Python 3.13 features 2025", max_results=3)

        t0       = time.perf_counter()
        response = asyncio.run(_run())
        latency  = time.perf_counter() - t0

        # TavilyResponse has no .success field — check sources length
        sources  = response.sources if response.sources is not None else []
        if len(sources) > 0:
            return pass_("live_tavily_search",
                         f"Live Tavily: {len(sources)} sources in {latency:.2f}s",
                         query=response.query, latency_ms=response.latency_ms)
        return fail_("live_tavily_search",
                     f"Live Tavily returned 0 sources (answer={bool(response.answer)})",
                     answer=response.answer)
    except Exception as exc:
        return fail_("live_tavily_search", f"Live search failed: {exc}")


def _check_live_research_pipeline() -> CheckResult:
    """
    Full live pipeline: Tavily → rank → cite → (LLM synthesis mock) → result.
    """
    key = os.getenv("TAVILY_API_KEY", "")
    if not key or len(key) < 10:
        return skip_("live_research_pipeline", "TAVILY_API_KEY not configured")

    try:
        import asyncio
        from unittest.mock import AsyncMock, patch
        from backend.research.live_research_pipeline import LiveResearchPipeline

        pipeline = LiveResearchPipeline()

        async def _run():
            with patch.object(pipeline, "_synthesize", new_callable=AsyncMock, return_value="Synthesized answer."):
                with patch.object(pipeline, "_store_memory", new_callable=AsyncMock):
                    with patch.object(pipeline, "_audit", new_callable=AsyncMock):
                        return await pipeline.run(
                            query      = "latest advances in large language models 2025",
                            mission_id = "validation",
                            agent      = "validator",
                            force_live = True,
                        )

        t0     = time.perf_counter()
        result = asyncio.run(_run())
        lat    = time.perf_counter() - t0

        if result.success and len(result.sources) > 0:
            return pass_("live_research_pipeline",
                         f"Pipeline: {len(result.sources)} sources, {len(result.citations)} citations in {lat:.2f}s",
                         source_count=len(result.sources), citation_count=len(result.citations))
        if result.sources:
            return warn_("live_research_pipeline",
                         f"Pipeline ran with {len(result.sources)} sources (success={result.success})")
        return fail_("live_research_pipeline",
                     f"Pipeline produced 0 sources (error: {result.error})")
    except Exception as exc:
        return fail_("live_research_pipeline", f"Pipeline failed: {exc}")


def _check_research_mission_via_http() -> CheckResult:
    """POST /api/research/search with a live query."""
    key = os.getenv("TAVILY_API_KEY", "")
    if not key or len(key) < 10:
        return skip_("research_http_search", "TAVILY_API_KEY not configured")

    code, body = http_post(
        "/api/research/search",
        {"query": "Python asyncio best practices 2025", "force_live": True, "top_k": 3},
        timeout=30.0,
    )
    if code == 200 and isinstance(body, dict):
        sources = body.get("sources", [])
        success = body.get("success", False)
        return pass_("research_http_search",
                     f"HTTP research search: {len(sources)} sources, success={success}")
    return warn_("research_http_search", f"/api/research/search HTTP {code}")


# ---------------------------------------------------------------------------
# Category runner
# ---------------------------------------------------------------------------

def run() -> CategoryResult:
    cat = CategoryResult("08 — Research")

    # Pure-Python checks
    for fn in [
        _check_tavily_client_importable,
        _check_tavily_key_configured,
        _check_live_trigger_detection,
        _check_source_ranker,
        _check_citation_engine,
        _check_research_telemetry,
        _check_live_tavily_search,
        _check_live_research_pipeline,
    ]:
        cat.checks.append(check(fn.__name__.lstrip("_"), fn))

    # HTTP checks
    if backend_is_up():
        for fn in [
            _check_research_health_route,
            _check_research_history_route,
            _check_research_mission_via_http,
        ]:
            cat.checks.append(check(fn.__name__.lstrip("_"), fn))
    else:
        cat.checks.append(skip_("research_http", "Backend not reachable"))

    return cat

"""
Regression test for a real bug: llm_router.py's internal provider keys
("claude", "azure", "gemini") don't match cost_engine.py's _COST_TABLE
keys ("anthropic", "azure_openai", "google") — only "openai" happened to
line up, so every real Claude/Azure/Gemini call silently estimated to
$0.00 before the alias fix.
"""
from __future__ import annotations

from backend.analytics.cost_engine import estimate_cost


class TestProviderAlias:
    def test_claude_maps_to_anthropic_cost_table(self):
        assert estimate_cost("claude", "claude-3-5-sonnet", 1000, 1000) > 0.0

    def test_azure_maps_to_azure_openai_cost_table(self):
        assert estimate_cost("azure", "gpt-4o", 1000, 1000) > 0.0

    def test_gemini_maps_to_google_cost_table(self):
        assert estimate_cost("gemini", "gemini-1.5-flash", 1000, 1000) > 0.0

    def test_openai_unaffected_by_alias_map(self):
        assert estimate_cost("openai", "gpt-4o", 1000, 1000) > 0.0

    def test_aliased_and_native_name_produce_identical_estimate(self):
        assert estimate_cost("claude", "claude-3-5-sonnet", 500, 500) == estimate_cost("anthropic", "claude-3-5-sonnet", 500, 500)
        assert estimate_cost("azure", "gpt-4o", 500, 500) == estimate_cost("azure_openai", "gpt-4o", 500, 500)
        assert estimate_cost("gemini", "gemini-1.5-flash", 500, 500) == estimate_cost("google", "gemini-1.5-flash", 500, 500)

    def test_unknown_provider_still_returns_zero(self):
        assert estimate_cost("not-a-real-provider", "some-model", 1000, 1000) == 0.0

"""Phase 11.3 (ADR-123 D-17): the model sees the budgeted context, and a local
provider refuses a prompt it would silently truncate.

Measured on the live cluster: the investigation prompt was
``json.dumps(context.to_dict())``, which carries every section -- including the
ones the budget had excluded, with all of their content (the excluded world
evidence was about three quarters of each prompt) -- and Ollama cut prompts of
8,948 and 18,914 tokens down to 4,098, dropping the system instructions from the
front and saying so only in its own server log."""
from __future__ import annotations

import asyncio
import json
from datetime import datetime, timezone
from types import SimpleNamespace

import pytest

from backend.harness.llm_boundary import InvalidModelOutput
from backend.intelligence.application.context import AssembledContext, ContextBudget, ContextSection
from backend.intelligence.application.model_boundary import GovernedModelProposalPort
from backend.llm_provider.models import LLMRequest
from backend.llm_provider.providers.ollama_adapter import OllamaAdapter

NOW = datetime(2026, 9, 11, 5, 0, tzinfo=timezone.utc)
EXCLUDED_EVIDENCE = "EXCLUDED-WORLD-EVIDENCE-" + "x" * 400


def _section(kind: str, order: int, content, *, included: bool = True) -> ContextSection:
    return ContextSection(
        section_type=kind, order=order, content=content, provenance="test",
        inclusion_reason="test", token_estimate=len(json.dumps(content)) // 4, digest="d" * 16,
        included=included, exclusion_reason=None if included else "context token budget exceeded")


def _context() -> AssembledContext:
    return AssembledContext(
        investigation_ref="winv_test", tenant_id="tenant-a", assembled_at=NOW,
        harness_version="h/1", policy_ref="pol/1",
        sections=(
            _section("incident", 0, {"incident_ref": "kubernetes:pod:prod/api"}),
            _section("hypotheses", 1, [{"hypothesis_ref": "h-configuration", "status": "open"}]),
            _section("world_evidence", 2, [EXCLUDED_EVIDENCE], included=False),
            _section("available_tools", 3, ["k8s.pod_logs"], included=False),
        ),
        context_digest="c" * 64, total_tokens=20, budget=ContextBudget(max_context_tokens=50))


class TestPromptView:
    def test_it_carries_included_content_and_only_names_the_excluded(self):
        view = _context().prompt_view()
        assert EXCLUDED_EVIDENCE not in json.dumps(view)
        assert [s["section_type"] for s in view["sections"]] == ["incident", "hypotheses"]
        assert all(s["included"] is True for s in view["sections"])
        assert view["excluded_sections"] == [
            {"section_type": "world_evidence", "reason": "context token budget exceeded"},
            {"section_type": "available_tools", "reason": "context token budget exceeded"},
        ]
        assert view["context_digest"] == "c" * 64

    def test_the_recorded_context_still_carries_everything(self):
        """The audit record is unchanged; only what the model is shown changed."""
        assert EXCLUDED_EVIDENCE in json.dumps(_context().to_dict())


class _CapturingBoundary:
    def __init__(self):
        self.prompts: list = []

    async def propose(self, *, prompt, **_kwargs):
        self.prompts.append(prompt)
        raise InvalidModelOutput("stopped by the test", "")


class TestProposalPort:
    def test_it_sends_the_budgeted_view_not_the_recorded_context(self):
        boundary = _CapturingBoundary()
        port = GovernedModelProposalPort(boundary=boundary, provider_label="test")
        investigation = SimpleNamespace(steps_taken=0, investigation_ref="winv_test", seq=3)
        with pytest.raises(Exception):
            port.propose(context=_context(), investigation=investigation, now=NOW)
        assert boundary.prompts, "the boundary was never asked"
        sent = json.loads(boundary.prompts[0])
        assert EXCLUDED_EVIDENCE not in boundary.prompts[0]
        assert [s["section_type"] for s in sent["sections"]] == ["incident", "hypotheses"]


class _FakeResponse:
    status_code = 200
    text = ""

    @staticmethod
    def json():
        return {"response": "{}", "prompt_eval_count": 10, "eval_count": 2, "done_reason": "stop"}


class _FakeClient:
    def __init__(self):
        self.posts: list = []

    async def post(self, path, json=None, timeout=None):  # noqa: A002 - mirrors httpx
        self.posts.append((path, json))
        return _FakeResponse()


def _adapter(monkeypatch) -> OllamaAdapter:
    monkeypatch.setenv("OLLAMA_NUM_CTX", "8192")
    adapter = OllamaAdapter()
    adapter._http_client = _FakeClient()
    return adapter


class TestOllamaWindow:
    def test_a_prompt_it_would_silently_truncate_is_refused_before_any_call(self, monkeypatch):
        adapter = _adapter(monkeypatch)
        request = LLMRequest(model="llama3.2", messages=[{"role": "user", "content": "x" * 30000}],
                             max_tokens=900)
        response = asyncio.run(adapter.generate(request))
        assert response.error and "context window" in response.error
        assert adapter._http_client.posts == [], "nothing may reach the provider"

    def test_a_prompt_that_fits_is_still_sent_with_the_stated_window(self, monkeypatch):
        adapter = _adapter(monkeypatch)
        request = LLMRequest(model="llama3.2", messages=[{"role": "user", "content": "x" * 6000}],
                             max_tokens=900)
        response = asyncio.run(adapter.generate(request))
        assert not response.error
        assert len(adapter._http_client.posts) == 1
        assert adapter._http_client.posts[0][1]["options"]["num_ctx"] == 8192

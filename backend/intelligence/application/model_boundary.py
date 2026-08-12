"""The live governed model boundary for investigation proposals.

This is the seam Phase 8.2 deferred: the InvestigationEngine's ``ModelProposalPort``
implemented over the existing ``harness.GovernedModelBoundary`` — schema-validated,
trace-recorded-before-return, provider/model stamped from platform configuration.
No second model gateway, no second tracer, no provider SDK here.

The strict proposal schema is the model-output firewall: the model may propose an
interpretation, hypotheses, and one discriminating test — and nothing else.
``extra='forbid'`` rejects any smuggled field (success/verified/autonomy/provider/
model/url/command/arguments/...); the boundary raises ``InvalidModelOutput`` and
the engine classifies the step, never advancing on malformed output.

The engine depends only on the ``ModelProposalPort``; this module (not the engine)
is where the governed boundary is invoked. The real provider is composed behind the
boundary's ``ModelPort`` (BLOCKED while credentials are placeholders); a scripted
``ModelPort`` is provided for deterministic verification, honestly labeled
``provider='scripted'``.
"""

from __future__ import annotations

import asyncio
import json
from datetime import datetime
from typing import Any, Awaitable, Callable, Optional

from pydantic import BaseModel, ConfigDict

from backend.contracts.tenant import TenantRef  # noqa: F401  (documentation of scope)
from backend.platform.hashing import compute_digest
from backend.intelligence.application.proposal import (
    InvestigationProposal,
    ModelProviderUnavailable,
    ModelSchemaRejected,
    ModelTraceUnavailable,
    ProposedHypothesis,
    ProposedTest,
)

__all__ = [
    "InvestigationProposalSchema",
    "HypothesisProposalSchema",
    "TestProposalSchema",
    "GovernedModelProposalPort",
    "ScriptedModelPort",
    "INVESTIGATION_SYSTEM_PROMPT",
]

INVESTIGATION_SYSTEM_PROMPT = (
    "You are a DevOps incident investigator. Propose ONLY: an interpretation, "
    "candidate hypotheses, and at most one discriminating test that names a tool "
    "from the available-tools list and a subject/predicate reference. You may NOT "
    "declare truth, resolve the investigation, verify anything, execute, change "
    "autonomy, or name a URL/shell/provider. Output strictly the JSON schema; any "
    "extra field is rejected."
)


class HypothesisProposalSchema(BaseModel):
    """A proposed differential candidate. Strict — no status/authority fields."""

    model_config = ConfigDict(extra="forbid")

    ref: str
    proposition: str
    subject_ref: str
    temporal_fit: str = "unknown"


class TestProposalSchema(BaseModel):
    """A proposed discriminating test. Names a TOOL (a key) and references only —
    no url/shell/provider/command/arguments (all rejected as extra)."""

    model_config = ConfigDict(extra="forbid")

    discriminates: str
    tool: str
    subject_ref: str
    predicate: str
    evidence_expected: str
    supports_if: str
    contradicts_if: str
    residual_uncertainty: str
    supports_value: Optional[Any] = None
    contradicts_value: Optional[Any] = None


class InvestigationProposalSchema(BaseModel):
    """The ONLY shape the model may propose. Any authoritative field
    (success/verified/status/autonomy/outcome/provider/model/url/command) is an
    extra field and is rejected — that is the model-output firewall."""

    model_config = ConfigDict(extra="forbid")

    interpretation: str = ""
    hypotheses: list[HypothesisProposalSchema] = []
    test: Optional[TestProposalSchema] = None


def _run(coro: Awaitable[Any]) -> Any:
    """Run one boundary coroutine from the (sync) investigation loop."""
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(coro)
    # Already inside a loop (unusual for the sync engine) — use a fresh loop.
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


class GovernedModelProposalPort:
    """``ModelProposalPort`` over ``harness.GovernedModelBoundary``.

    Builds the prompt from the assembled context (deterministic), invokes the
    governed boundary with the strict schema, and maps the validated schema to the
    engine's ``InvestigationProposal`` — stamping provider/model from PLATFORM
    configuration (the span), never from the model's output."""

    def __init__(self, *, boundary, provider_label: str = "scripted") -> None:
        # ``boundary`` is a harness.GovernedModelBoundary composed by the caller.
        self._boundary = boundary
        self._provider_label = provider_label

    def propose(self, *, context, investigation, now: datetime) -> InvestigationProposal:
        from backend.harness.llm_boundary import InvalidModelOutput, TraceEvidenceMissing

        prompt = json.dumps(context.to_dict(), sort_keys=True, default=str)
        step = investigation.steps_taken
        corr = compute_digest({"inv": investigation.investigation_ref, "step": step}).value[:16]
        try:
            proposal_schema, span = _run(self._boundary.propose(
                schema=InvestigationProposalSchema,
                system_prompt=INVESTIGATION_SYSTEM_PROMPT, prompt=prompt,
                mission_id=investigation.investigation_ref, iteration=step,
                step_id=f"step-{investigation.seq}", correlation_id=corr,
                trace_id=corr, trace_span_id=f"{corr}-{step}",
                context_recipe={"context_digest": context.context_digest},
                tools_available=list(_available_tools(context)),
            ))
        except InvalidModelOutput as exc:
            raise ModelSchemaRejected(exc.reason) from exc
        except TraceEvidenceMissing as exc:
            raise ModelTraceUnavailable(exc.reason) from exc
        except Exception as exc:  # provider errors, timeouts, auth failures
            raise ModelProviderUnavailable(type(exc).__name__) from exc

        # Platform-controlled identity: provider/model come from the span, never
        # from the model's JSON (which cannot even carry them — extra fields fail).
        provider = getattr(span, "model_provider", None) or self._provider_label
        digest = compute_digest(proposal_schema.model_dump()).value[:16]
        return InvestigationProposal(
            provider=provider, proposal_digest=digest,
            interpretation=proposal_schema.interpretation,
            proposed_hypotheses=tuple(
                ProposedHypothesis(hypothesis_ref=h.ref, proposition=h.proposition,
                                   subject_ref=h.subject_ref, temporal_fit=h.temporal_fit)
                for h in proposal_schema.hypotheses),
            proposed_test=(ProposedTest(
                discriminates_hypothesis=proposal_schema.test.discriminates,
                tool=proposal_schema.test.tool, subject_ref=proposal_schema.test.subject_ref,
                predicate=proposal_schema.test.predicate,
                evidence_expected=proposal_schema.test.evidence_expected,
                supports_if=proposal_schema.test.supports_if,
                contradicts_if=proposal_schema.test.contradicts_if,
                residual_uncertainty=proposal_schema.test.residual_uncertainty,
                supports_value=proposal_schema.test.supports_value,
                contradicts_value=proposal_schema.test.contradicts_value)
                if proposal_schema.test is not None else None),
            suggested_conclusion=None)


def _available_tools(context) -> tuple[str, ...]:
    for s in context.sections:
        if s.section_type == "available_tools":
            return tuple(s.content)
    return ()


class ScriptedModelPort:
    """A deterministic ``ModelPort`` (provider='scripted') for verification. It
    returns JSON content produced by ``responder(prompt)`` — the responder reads
    the assembled-context prompt and emits a schema-valid proposal. It holds NO
    credentials and calls NO external provider; the real provider is a different
    ModelPort composed only when credentials exist."""

    def __init__(self, responder: Callable[[str], str], *,
                 model: str = "scripted/investigator/1") -> None:
        self._responder = responder
        self._model = model

    async def generate(self, *, system_prompt: str, prompt: str):
        from backend.harness.llm_boundary import ModelInvocation
        content = self._responder(prompt)
        return ModelInvocation(content=content, provider="scripted", model=self._model,
                               latency_ms=0.0, usage=None, config={"scripted": True})

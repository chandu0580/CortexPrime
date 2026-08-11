"""The single model chokepoint (Parts D + E): validate, scrub, normalize, record.

Rules this module makes structural:

* **The model produces an untrusted proposal.** Its output is parsed strictly
  and validated against a declared Pydantic schema before anything interprets
  it. There is no regex extraction, no ``getattr`` dispatch, no "probably
  JSON". A deterministic markdown-fence unwrap is the only preprocessing —
  it either finds a complete fenced block or leaves the text alone.
* **Invalid output is an explicit harness failure** (:class:`InvalidModelOutput`),
  recorded on the trace with the scrubbed raw output. It never executes, and
  it never silently degrades to a template.
* **Prompts are scrubbed before they leave the process** — deterministic code,
  never model judgment — and again on the trace write path (both directions of
  the credential rule).
* **Token usage is normalized** across providers (``prompt_tokens`` /
  ``input_tokens`` vocabulary differences) so the loop can enforce a budget.
  A provider that reports no usage yields ``None``, and the loop treats an
  unknown spend as unbudgetable rather than free.

The default model port wraps ``backend.llm_provider.LLMService`` — the stack
that preserves usage and latency. The port is injectable: tests and offline
runs supply a scripted port, and the trace records which port produced every
span, so scripted evidence can never masquerade as a real model run.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Mapping, Optional, Protocol, Type, TypeVar

from pydantic import BaseModel, ValidationError

from backend.harness.trace import (
    SCRUB_MAX_CHARS,
    HarnessSpan,
    TraceRecorder,
    build_model_span,
)
from backend.harness.version import HarnessVersion
from backend.platform.credentials.redaction import scrub_text

__all__ = [
    "InvalidModelOutput",
    "TokenUsage",
    "ModelInvocation",
    "ModelPort",
    "LLMServiceModelPort",
    "GovernedModelBoundary",
]

ProposalT = TypeVar("ProposalT", bound=BaseModel)


class InvalidModelOutput(RuntimeError):
    """Model output failed strict parsing or schema validation.

    An explicit harness failure: the proposal never existed as far as
    governance is concerned. Carries the *scrubbed* raw excerpt for the trace,
    never the raw text.
    """

    def __init__(self, reason: str, scrubbed_excerpt: str) -> None:
        super().__init__(reason)
        self.reason = reason
        self.scrubbed_excerpt = scrubbed_excerpt


@dataclass(frozen=True)
class TokenUsage:
    """Provider-neutral token accounting."""

    prompt_tokens: int
    completion_tokens: int

    @property
    def total_tokens(self) -> int:
        return self.prompt_tokens + self.completion_tokens

    @classmethod
    def from_provider_usage(cls, usage: Optional[Mapping[str, Any]]) -> Optional["TokenUsage"]:
        """Normalize OpenAI-shaped (``prompt_tokens``/``completion_tokens``)
        and Anthropic-shaped (``input_tokens``/``output_tokens``) usage dicts.
        Unknown shapes yield ``None`` — an unmeasured spend is unmeasured,
        not zero."""
        if not usage:
            return None
        prompt = usage.get("prompt_tokens", usage.get("input_tokens"))
        completion = usage.get("completion_tokens", usage.get("output_tokens"))
        if not isinstance(prompt, int) or not isinstance(completion, int):
            return None
        return cls(prompt_tokens=prompt, completion_tokens=completion)

    def as_mapping(self) -> dict[str, int]:
        return {
            "prompt_tokens": self.prompt_tokens,
            "completion_tokens": self.completion_tokens,
            "total_tokens": self.total_tokens,
        }


@dataclass(frozen=True)
class ModelInvocation:
    """What one model call returned, before any interpretation."""

    content: str
    provider: str
    model: str
    latency_ms: Optional[float]
    usage: Optional[TokenUsage]
    config: Optional[Mapping[str, Any]] = None


class ModelPort(Protocol):
    """The one seam through which the harness reaches a model."""

    async def generate(self, *, system_prompt: str, prompt: str) -> ModelInvocation: ...


class LLMServiceModelPort:
    """Default port over ``backend.llm_provider.LLMService`` (lazy import so
    the harness package itself never drags provider SDK initialization in)."""

    def __init__(self, model: Optional[str] = None) -> None:
        self._model = model
        self._service = None

    async def _service_instance(self):
        if self._service is None:
            from backend.llm_provider.service import LLMService

            service = LLMService()
            initialize = getattr(service, "initialize", None)
            if initialize is not None:
                maybe = initialize()
                if hasattr(maybe, "__await__"):
                    await maybe
            self._service = service
        return self._service

    async def generate(self, *, system_prompt: str, prompt: str) -> ModelInvocation:
        from backend.llm_provider.models import LLMRequest

        service = await self._service_instance()
        request = LLMRequest(
            model=self._model or "",
            messages=[{"role": "user", "content": prompt}],
            system_prompt=system_prompt,
            response_format={"type": "json_object"},
        )
        response = await service.generate(request)
        if getattr(response, "error", None):
            raise RuntimeError(f"model call failed: {response.error}")
        return ModelInvocation(
            content=response.content or "",
            provider=getattr(response, "provider", "") or "",
            model=getattr(response, "model", "") or "",
            latency_ms=getattr(response, "latency_ms", None),
            usage=TokenUsage.from_provider_usage(getattr(response, "usage", None)),
            config={"response_format": "json_object"},
        )


def _strip_markdown_fence(text: str) -> str:
    """Deterministic unwrap of one complete fenced block, or the text unchanged.

    Not extraction: either the whole (stripped) content is a single fenced
    block and the fence comes off, or nothing happens. A stray brace in prose
    stays a stray brace and fails parsing loudly.
    """
    stripped = text.strip()
    if not stripped.startswith("```"):
        return stripped
    lines = stripped.splitlines()
    if len(lines) >= 2 and lines[-1].strip() == "```":
        return "\n".join(lines[1:-1]).strip()
    return stripped


class GovernedModelBoundary:
    """Every governed model invocation flows through :meth:`propose`."""

    def __init__(
        self,
        *,
        model_port: ModelPort,
        recorder: TraceRecorder,
        harness_version: HarnessVersion,
    ) -> None:
        self._port = model_port
        self._recorder = recorder
        self._version = harness_version

    async def propose(
        self,
        *,
        schema: Type[ProposalT],
        system_prompt: str,
        prompt: str,
        mission_id: str,
        iteration: int,
        step_id: str,
        correlation_id: str,
        trace_id: str,
        trace_span_id: str,
        context_recipe: Optional[Mapping[str, Any]] = None,
    ) -> tuple[ProposalT, HarnessSpan]:
        """One validated proposal, or :class:`InvalidModelOutput`. Always a span."""
        started_at = datetime.now(timezone.utc).isoformat()
        safe_system = scrub_text(system_prompt, max_length=SCRUB_MAX_CHARS)
        safe_prompt = scrub_text(prompt, max_length=SCRUB_MAX_CHARS)

        invocation = await self._port.generate(
            system_prompt=safe_system, prompt=safe_prompt
        )

        failure: Optional[str] = None
        proposal: Optional[ProposalT] = None
        try:
            payload = json.loads(_strip_markdown_fence(invocation.content))
            proposal = schema.model_validate(payload)
        except json.JSONDecodeError as exc:
            failure = f"model output is not valid JSON: {exc.msg} at pos {exc.pos}"
        except ValidationError as exc:
            failure = (
                f"model output failed schema {schema.__name__}: "
                f"{exc.error_count()} error(s): "
                + "; ".join(
                    f"{'.'.join(str(p) for p in e['loc'])}: {e['type']}"
                    for e in exc.errors()[:5]
                )
            )

        span = build_model_span(
            mission_id=mission_id,
            iteration=iteration,
            step_id=step_id,
            harness_version=self._version.identity,
            correlation_id=correlation_id,
            trace_id=trace_id,
            trace_span_id=trace_span_id,
            started_at=started_at,
            model_provider=invocation.provider,
            model_id=invocation.model,
            model_config=invocation.config,
            prompt=f"[system]\n{safe_system}\n[user]\n{safe_prompt}",
            context_recipe=context_recipe,
            # Scrubbing is lossy; the persisted prompt is evidence, not a
            # byte-exact replay input. Claiming otherwise would be false.
            context_reconstructable=False,
            output=invocation.content,
            token_usage=invocation.usage.as_mapping() if invocation.usage else None,
            latency_ms=invocation.latency_ms,
            stop_or_failure_reason=failure,
        )
        self._recorder.record(span)

        if failure is not None:
            raise InvalidModelOutput(
                failure, scrub_text(invocation.content[:2000], max_length=2000)
            )
        assert proposal is not None
        return proposal, span

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
import logging
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

_log = logging.getLogger(__name__)

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


class TraceEvidenceMissing(RuntimeError):
    """The model-proposal span could not be persisted (Part E, L14).

    Fail-closed: the constitution states a step without its evidence record is
    a failed step. The model proposal's span is the *only* record of what the
    model saw and proposed; if it cannot be written, the proposal must not
    reach a governed action, because acting on it would produce an
    unattributable side effect. Distinct from best-effort *post-action* spans,
    whose authoritative outcome already lives in the fenced audit chain.
    """

    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


def schema_identity(schema: Type[BaseModel]) -> str:
    """A deterministic identity for a proposal schema: name + a digest of its
    JSON schema. A field added, a constraint changed, an enum widened — any of
    which changes what the model may propose — changes this string, so a trace
    records exactly which input contract validated the output (Part J)."""
    from backend.platform.hashing import compute_digest

    body = compute_digest(schema.model_json_schema()).value[:12]
    return f"{schema.__name__}+{body}"


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

    def __init__(self, model: Optional[str] = None, *, provider: Optional[str] = None,
                 timeout_seconds: float = 60.0, max_tokens: Optional[int] = None) -> None:
        self._model = model
        self._provider = provider or ""
        self._timeout = timeout_seconds
        self._max_tokens = max_tokens
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
        service = await self._service_instance()
        response = await service.generate(
            prompt,
            model=self._model or "",
            provider=self._provider,
            system_prompt=system_prompt,
            response_format={"type": "json_object"},
            timeout_seconds=self._timeout,
            max_tokens=self._max_tokens,
            temperature=0.0,
        )
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
        tools_available: Optional[Any] = None,
    ) -> tuple[ProposalT, HarnessSpan]:
        """One validated proposal, or :class:`InvalidModelOutput`. Always a span.

        The span is persisted **before** the proposal is returned; a persistence
        failure raises :class:`TraceEvidenceMissing` and no proposal is handed
        back (Part E fail-closed rule for pre-action evidence).
        """
        started_at = datetime.now(timezone.utc).isoformat()
        safe_system = scrub_text(system_prompt, max_length=SCRUB_MAX_CHARS)
        safe_prompt = scrub_text(prompt, max_length=SCRUB_MAX_CHARS)
        # Deterministic context identity: the same mission/iteration/step under
        # the same harness version names the same assembled context (Part J).
        from backend.platform.hashing import compute_digest as _digest

        context_id = _digest(
            {
                "mission_id": mission_id,
                "iteration": iteration,
                "step_id": step_id,
                "harness_version": self._version.identity,
            }
        ).value[:16]

        try:
            invocation = await self._port.generate(
                system_prompt=safe_system, prompt=safe_prompt
            )
        except Exception as exc:
            # Phase 11.4 run 9 (F-10): a provider failure raised before any
            # span was built, so "Always a span" held only for calls that
            # answered -- an unavailable model left no durable trace of the
            # attempt or its cause. The span records the scrubbed cause and
            # no output; the error still propagates, so a failed call can
            # never become a proposal.
            failure_span = build_model_span(
                mission_id=mission_id,
                iteration=iteration,
                step_id=step_id,
                harness_version=self._version.identity,
                correlation_id=correlation_id,
                trace_id=trace_id,
                trace_span_id=trace_span_id,
                started_at=started_at,
                model_provider=str(getattr(self._port, "_provider", "") or "unavailable"),
                model_id=str(getattr(self._port, "_model", "") or ""),
                model_config=None,
                prompt=f"[system]\n{safe_system}\n[user]\n{safe_prompt}",
                context_recipe=context_recipe,
                context_reconstructable=False,
                output=None,
                token_usage=None,
                latency_ms=None,
                context_id=context_id,
                schema_id=schema_identity(schema),
                tools_available=tuple(tools_available) if tools_available is not None else None,
                stop_or_failure_reason=scrub_text(
                    f"provider call failed: {type(exc).__name__}: {exc}", max_length=400),
            )
            try:
                self._recorder.record(failure_span)
            except Exception:  # noqa: BLE001 - the provider error is the one to surface
                _log.error("recording a failed model-call span failed", exc_info=False)
            raise

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
            context_id=context_id,
            schema_id=schema_identity(schema),
            tools_available=tuple(tools_available) if tools_available is not None else None,
            stop_or_failure_reason=failure,
        )
        # Fail-closed: if the pre-action evidence cannot be persisted, the
        # proposal never reaches a governed action (Part E, L14). The audit
        # chain records authorized actions; this records what the model saw and
        # proposed, and without it that action is unattributable.
        try:
            self._recorder.record(span)
        except Exception as exc:
            raise TraceEvidenceMissing(
                f"model-proposal span could not be persisted: {type(exc).__name__}"
            ) from exc

        if failure is not None:
            raise InvalidModelOutput(
                failure, scrub_text(invocation.content[:2000], max_length=2000)
            )
        assert proposal is not None
        return proposal, span

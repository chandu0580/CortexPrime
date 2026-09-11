"""An OpenAI-compatible chat-completions provider, configured entirely by environment.

Phase 11.3 (ADR-123 D-18). The governed investigator's hosted model is whatever
OpenAI-compatible endpoint the operator names:

    LLM_API_KEY    the bearer credential
    LLM_BASE_URL   the endpoint, e.g. ``https://host/v1/``
    LLM_MODEL      the model to declare and call, e.g. ``glm-5.2``

Declaring ``LLM_MODEL`` is what lets the router find this provider when a caller
names that model: the router matches declared model names only. The provider
sorts LAST by priority (1000 unless ``LLM_PROVIDER_PRIORITY`` says otherwise; a
lower number wins), so it answers a caller that names its model and is chosen
for an unnamed request only when no other provider is available.

The one rule here that is not a convenience: a plain ``http://`` URL to a host
that is not loopback sends the key and every prompt across the network
unencrypted. That is refused unless ``LLM_ALLOW_PLAINTEXT_HTTP=1`` accepts it in
the operator's own configuration, and when it is accepted the provider says so
in the log at initialisation. Nothing in this module logs or returns the key.
"""
from __future__ import annotations

import logging
import os
import time
from typing import Any, AsyncGenerator, Optional
from urllib.parse import urlparse

from openai import AsyncOpenAI

from backend.llm_provider.interface import LLMProvider
from backend.llm_provider.models import (
    EmbeddingRequest,
    EmbeddingResult,
    FinishReason,
    LLMModelInfo,
    LLMProviderInfo,
    LLMRequest,
    LLMResponse,
    ModelCapability,
    ProviderHealth,
    StreamChunk,
)

log = logging.getLogger(__name__)

PROVIDER_NAME = "openai-compatible"
_LOOPBACK_HOSTS = frozenset({"localhost", "127.0.0.1", "::1"})


def _int_env(name: str, default: int) -> int:
    raw = (os.getenv(name) or "").strip()
    try:
        return int(raw) if raw else default
    except ValueError:
        return default


def _float_env(name: str, default: float) -> float:
    raw = (os.getenv(name) or "").strip()
    try:
        return float(raw) if raw else default
    except ValueError:
        return default


def _is_loopback(host: str) -> bool:
    host = (host or "").lower()
    return host in _LOOPBACK_HOSTS or host.endswith(".localhost")


class OpenAICompatibleAdapter(LLMProvider):
    """Chat completions against ``LLM_BASE_URL`` through the OpenAI SDK."""

    def __init__(self) -> None:
        self._client: Optional[Any] = None
        self._initialized = False
        self._base_url = (os.getenv("LLM_BASE_URL") or "").strip()
        self._default_model = (os.getenv("LLM_MODEL") or "").strip()

        models: list[LLMModelInfo] = []
        if self._default_model:
            models.append(LLMModelInfo(
                name=self._default_model, provider=PROVIDER_NAME,
                capabilities={ModelCapability.CHAT, ModelCapability.STRUCTURED_OUTPUT},
                context_window=_int_env("LLM_CONTEXT_WINDOW", 128000),
                max_output_tokens=_int_env("LLM_MAX_OUTPUT_TOKENS", 8192),
                # Unpriced unless the operator states a price: the cost surface
                # then reports zero USD and says the provider is unpriced.
                cost_per_1k_input=_float_env("LLM_COST_PER_1K_INPUT", 0.0),
                cost_per_1k_output=_float_env("LLM_COST_PER_1K_OUTPUT", 0.0),
                version=self._default_model, is_default=True,
            ))

        self._info = LLMProviderInfo(
            name=PROVIDER_NAME,
            display_name="OpenAI-compatible endpoint (LLM_BASE_URL)",
            version="1.0",
            models=models,
            priority=_int_env("LLM_PROVIDER_PRIORITY", 1000),
        )

    @property
    def name(self) -> str:
        return PROVIDER_NAME

    @property
    def provider_info(self) -> LLMProviderInfo:
        return self._info

    @staticmethod
    def plaintext_refusal(base_url: str) -> Optional[str]:
        """Why ``base_url`` may not be used, or ``None`` if it may."""
        parsed = urlparse(base_url or "")
        if parsed.scheme == "https":
            return None
        if parsed.scheme != "http":
            return f"LLM_BASE_URL must be an http(s) URL, not {parsed.scheme or 'no scheme'!r}"
        if _is_loopback(parsed.hostname or ""):
            return None
        if (os.getenv("LLM_ALLOW_PLAINTEXT_HTTP") or "").strip() == "1":
            return None
        return ("LLM_BASE_URL is plain http to a non-loopback host: the API key and every prompt "
                "would cross the network unencrypted. Use https, or set LLM_ALLOW_PLAINTEXT_HTTP=1 "
                "to accept that explicitly.")

    async def initialize(self) -> bool:
        if self._initialized:
            return True
        api_key = (os.getenv("LLM_API_KEY") or "").strip()
        if not (api_key and self._base_url and self._default_model):
            log.info("openai-compatible provider not configured: LLM_API_KEY, LLM_BASE_URL and "
                     "LLM_MODEL are all required")
            return False
        refusal = self.plaintext_refusal(self._base_url)
        if refusal:
            log.warning("openai-compatible provider refused: %s", refusal)
            return False
        parsed = urlparse(self._base_url)
        if parsed.scheme == "http" and not _is_loopback(parsed.hostname or ""):
            log.warning("openai-compatible provider uses plain HTTP to %s, accepted by "
                        "LLM_ALLOW_PLAINTEXT_HTTP=1: the key and prompts are not encrypted in transit",
                        parsed.hostname)
        try:
            self._client = AsyncOpenAI(api_key=api_key, base_url=self._base_url)
        except Exception as exc:  # noqa: BLE001 - an SDK that cannot build a client is unavailable
            log.warning("openai-compatible provider initialization failed: %s", type(exc).__name__)
            return False
        self._initialized = True
        log.info("openai-compatible provider initialized for model %s", self._default_model)
        return True

    async def health_check(self) -> ProviderHealth:
        start = time.monotonic()
        available = self._client is not None
        latency = (time.monotonic() - start) * 1000
        self._info.latency_ms = latency
        self._info.is_available = available
        return ProviderHealth(
            provider=self.name, is_available=available, latency_ms=latency,
            models_available=[m.name for m in self._info.models],
        )

    async def generate(self, request: LLMRequest) -> LLMResponse:
        start = time.monotonic()
        if not self._client:
            return LLMResponse(
                content="", model=request.model or "", provider=self.name,
                error="openai-compatible client not configured",
                finish_reason=FinishReason.ERROR,
                latency_ms=(time.monotonic() - start) * 1000, request_id=request.request_id,
            )
        model = request.model or self._default_model
        try:
            kwargs: dict[str, Any] = dict(
                model=model, messages=self._build_messages(request),
                temperature=request.temperature, timeout=request.timeout_seconds,
            )
            if request.max_tokens:
                kwargs["max_tokens"] = request.max_tokens
            if request.stop:
                kwargs["stop"] = request.stop
            if request.response_format:
                kwargs["response_format"] = request.response_format
            response = await self._client.chat.completions.create(**kwargs)
            choice = response.choices[0]
            usage = response.usage.model_dump() if hasattr(response.usage, "model_dump") else None
            return LLMResponse(
                content=choice.message.content or "",
                model=model, provider=self.name, usage=usage,
                finish_reason=self._map_finish_reason(choice.finish_reason),
                latency_ms=(time.monotonic() - start) * 1000, request_id=request.request_id,
            )
        except Exception as exc:  # noqa: BLE001 - surfaced to the caller as a provider error
            return LLMResponse(
                content="", model=model, provider=self.name,
                error=self._redact(f"{type(exc).__name__}: {exc}"),
                finish_reason=FinishReason.ERROR,
                latency_ms=(time.monotonic() - start) * 1000, request_id=request.request_id,
            )

    async def stream(self, request: LLMRequest) -> AsyncGenerator[StreamChunk, None]:
        if not self._client:
            yield StreamChunk(done=True, error="openai-compatible client not configured")
            return
        model = request.model or self._default_model
        try:
            stream = await self._client.chat.completions.create(
                model=model, messages=self._build_messages(request),
                temperature=request.temperature, stream=True, timeout=request.timeout_seconds,
            )
            index = 0
            async for chunk in stream:
                if not chunk.choices:
                    continue
                reason = chunk.choices[0].finish_reason
                finish = self._map_finish_reason(reason) if reason else None
                yield StreamChunk(
                    content=chunk.choices[0].delta.content or "", index=index,
                    finish_reason=finish, done=finish is not None,
                    request_id=request.request_id, model=model, provider=self.name,
                )
                index += 1
                if finish is not None:
                    break
        except Exception as exc:  # noqa: BLE001
            yield StreamChunk(
                finish_reason=FinishReason.ERROR, done=True,
                error=self._redact(f"{type(exc).__name__}: {exc}"),
                request_id=request.request_id, model=model, provider=self.name,
            )

    async def embed(self, request: EmbeddingRequest) -> EmbeddingResult:
        return EmbeddingResult(
            error="the openai-compatible provider is configured for chat completions only",
            request_id=request.request_id, provider=self.name,
        )

    async def function_call(self, request: LLMRequest) -> LLMResponse:
        return LLMResponse(
            content="", model=request.model or self._default_model, provider=self.name,
            error="the openai-compatible provider does not offer function calling here",
            finish_reason=FinishReason.ERROR, request_id=request.request_id,
        )

    async def shutdown(self) -> None:
        client, self._client = self._client, None
        self._initialized = False
        close = getattr(client, "close", None)
        if close is not None:
            try:
                maybe = close()
                if hasattr(maybe, "__await__"):
                    await maybe
            except Exception:  # noqa: BLE001 - shutdown never raises
                log.debug("openai-compatible client close failed", exc_info=True)

    @staticmethod
    def _redact(text: str) -> str:
        key = (os.getenv("LLM_API_KEY") or "").strip()
        if key and key in text:
            text = text.replace(key, "[redacted]")
        return text[:500]

    @staticmethod
    def _build_messages(request: LLMRequest) -> list[dict[str, str]]:
        messages: list[dict[str, str]] = []
        if request.system_prompt:
            messages.append({"role": "system", "content": request.system_prompt})
        messages.extend(request.messages)
        return messages

    @staticmethod
    def _map_finish_reason(reason: Optional[str]) -> Optional[FinishReason]:
        if not reason:
            return None
        return {
            "stop": FinishReason.STOP,
            "length": FinishReason.LENGTH,
            "content_filter": FinishReason.CONTENT_FILTER,
            "function_call": FinishReason.FUNCTION_CALL,
            "tool_calls": FinishReason.TOOL_CALL,
        }.get(reason, FinishReason.STOP)

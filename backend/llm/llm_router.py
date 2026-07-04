"""
CortexPrime Multi-LLM Router
=============================
Routing layer on top of all configured LLM providers.
Does NOT replace the existing LLMGateway — it wraps and extends it.

Routing rules
-------------
  CODING      → Azure OpenAI (GPT-5)        fallback: OpenAI → Claude → Gemini
  REASONING   → Claude                       fallback: OpenAI → Azure  → Gemini
  RESEARCH    → Gemini                       fallback: Claude → OpenAI → Azure
  OFFLINE     → Ollama                       fallback: Azure  → OpenAI
  GENERAL     → Azure OpenAI (GPT-5)        fallback: OpenAI → Claude → Gemini

Failover
--------
  Each provider is tried in order until one succeeds.
  A provider is temporarily skipped for CIRCUIT_OPEN_SECS seconds
  after CIRCUIT_FAIL_THRESHOLD consecutive failures.

Telemetry
---------
  Per-provider: call_count, fail_count, total_latency_ms, last_error, last_used_at
  Accessible via llm_router.telemetry() and persisted to Redis when available.

Health
------
  llm_router.health() → dict consumed by GET /health/llm
"""
from __future__ import annotations

import asyncio
import logging
import os
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Sequence

try:
    from backend.core.logging import get_logger as _get_logger
    log = _get_logger(__name__)
except ImportError:
    log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

CIRCUIT_FAIL_THRESHOLD = 3          # consecutive failures before opening circuit
CIRCUIT_OPEN_SECS      = 60         # seconds to wait before retrying a tripped provider
CALL_TIMEOUT_SECS      = 60         # per-provider timeout


def _get_request_id_safe() -> str:
    """Return current request_id without failing if the core module isn't available."""
    try:
        from backend.core.logging import get_request_id
        return get_request_id()
    except Exception:
        return "no-request-id"

# ---------------------------------------------------------------------------
# Task types
# ---------------------------------------------------------------------------

class TaskType(str, Enum):
    CODING    = "coding"
    REASONING = "reasoning"
    RESEARCH  = "research"
    OFFLINE   = "offline"
    GENERAL   = "general"


# Keywords that identify each non-general task type
_CODING_KWS: Sequence[str] = [
    "write code", "implement", "code this", "debug", "refactor", "unit test",
    "function ", "class ", "def ", "algorithm", "programming", "script",
    "fix the bug", "add feature", "build a", "create a module",
]
_REASONING_KWS: Sequence[str] = [
    "reason through", "think step by step", "chain of thought",
    "explain why", "analyze", "deep analysis", "long reasoning",
    "compare and contrast", "philosophical", "evaluate the pros",
    "what are the implications", "moral", "ethical", "decision framework",
]
_RESEARCH_KWS: Sequence[str] = [
    "research", "find information", "latest news", "current events",
    "who is", "what is the latest", "recent developments",
    "search for", "look up", "summarize the", "literature review",
    "state of the art", "survey of", "market analysis",
]
_OFFLINE_KWS: Sequence[str] = [
    "offline", "local model", "use ollama", "run locally",
    "no internet", "private", "on-device",
]


def detect_task_type(prompt: str) -> TaskType:
    """Classify a prompt into a TaskType using keyword matching."""
    lower = prompt.lower()
    if any(kw in lower for kw in _OFFLINE_KWS):
        return TaskType.OFFLINE
    if any(kw in lower for kw in _CODING_KWS):
        return TaskType.CODING
    if any(kw in lower for kw in _RESEARCH_KWS):
        return TaskType.RESEARCH
    if any(kw in lower for kw in _REASONING_KWS):
        return TaskType.REASONING
    return TaskType.GENERAL


# ---------------------------------------------------------------------------
# Routing table  (task_type → ordered list of provider names to try)
# ---------------------------------------------------------------------------

_ROUTING: Dict[TaskType, List[str]] = {
    TaskType.CODING:    ["azure",  "openai", "claude",  "gemini"],
    TaskType.REASONING: ["claude", "openai", "azure",   "gemini"],
    TaskType.RESEARCH:  ["gemini", "claude", "openai",  "azure"],
    TaskType.OFFLINE:   ["ollama", "azure",  "openai"],
    TaskType.GENERAL:   ["azure",  "openai", "claude",  "gemini"],
}

# ---------------------------------------------------------------------------
# Per-provider telemetry
# ---------------------------------------------------------------------------

@dataclass
class ProviderStats:
    provider:            str
    call_count:          int   = 0
    fail_count:          int   = 0
    total_latency_ms:    float = 0.0
    consecutive_fails:   int   = 0
    circuit_opened_at:   float = 0.0   # epoch when circuit was tripped
    last_error:          str   = ""
    last_used_at:        float = 0.0
    last_success_at:     float = 0.0

    @property
    def avg_latency_ms(self) -> float:
        successes = self.call_count - self.fail_count
        return (self.total_latency_ms / successes) if successes > 0 else 0.0

    @property
    def error_rate(self) -> float:
        return (self.fail_count / self.call_count) if self.call_count > 0 else 0.0

    @property
    def circuit_open(self) -> bool:
        if self.consecutive_fails < CIRCUIT_FAIL_THRESHOLD:
            return False
        return (time.time() - self.circuit_opened_at) < CIRCUIT_OPEN_SECS

    def record_success(self, latency_ms: float) -> None:
        self.call_count       += 1
        self.total_latency_ms += latency_ms
        self.consecutive_fails = 0
        self.last_used_at      = time.time()
        self.last_success_at   = time.time()

    def record_failure(self, error: str) -> None:
        self.call_count       += 1
        self.fail_count       += 1
        self.consecutive_fails += 1
        self.last_error        = str(error)[:256]
        self.last_used_at      = time.time()
        if self.consecutive_fails == CIRCUIT_FAIL_THRESHOLD:
            self.circuit_opened_at = time.time()
            log.warning(
                "LLMRouter: circuit opened for provider=%s after %d consecutive failures",
                self.provider, self.consecutive_fails,
            )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "provider":          self.provider,
            "call_count":        self.call_count,
            "fail_count":        self.fail_count,
            "avg_latency_ms":    round(self.avg_latency_ms, 1),
            "error_rate":        round(self.error_rate, 4),
            "circuit_open":      self.circuit_open,
            "last_error":        self.last_error,
            "last_used_at":      self.last_used_at,
            "last_success_at":   self.last_success_at,
        }


# ---------------------------------------------------------------------------
# Router result
# ---------------------------------------------------------------------------

@dataclass
class RouterResult:
    success:          bool
    output:           str
    provider_used:    str
    model_used:       str
    task_type:        str
    latency_ms:       float
    fallback_count:   int
    tried_providers:  List[str] = field(default_factory=list)
    error:            str = ""
    request_id:       str = ""


# ---------------------------------------------------------------------------
# Individual provider call helpers
# ---------------------------------------------------------------------------

_DEFAULT_SYSTEM = (
    "You are CortexPrime, an autonomous AI assistant. "
    "Respond with intelligence, depth, and precision."
)


async def _call_azure(prompt: str, system: str, agent_type: str) -> str:
    """Call Azure OpenAI via the existing LLMGateway."""
    from backend.llm.llm_gateway import llm_gateway
    result = await llm_gateway.generate_azure(
        prompt=prompt,
        agent_type=agent_type,
        system_prompt=system,
    )
    if not result.get("success"):
        raise RuntimeError(result.get("error", "Azure call failed"))
    output = result.get("output", "")
    if not output:
        raise RuntimeError("Azure returned empty output")
    return output


async def _call_openai(prompt: str, system: str, model: str = "gpt-4o-mini") -> str:
    """Call OpenAI directly via the existing LLMGateway."""
    from backend.llm.llm_gateway import llm_gateway
    # Prefer gpt-5 on direct openai if available, fall back to gpt-4o
    result = await llm_gateway.generate_openai(prompt=prompt, model=model)
    if not result.get("success"):
        raise RuntimeError(result.get("error", "OpenAI call failed"))
    output = result.get("output", "")
    if not output:
        raise RuntimeError("OpenAI returned empty output")
    return output


async def _call_claude(prompt: str, system: str) -> str:
    """Call Anthropic Claude."""
    api_key = os.getenv("ANTHROPIC_API_KEY", "")
    if not api_key:
        raise RuntimeError("ANTHROPIC_API_KEY not configured")
    try:
        import anthropic
    except ImportError as exc:
        raise RuntimeError("anthropic package not installed") from exc

    model = os.getenv("MODEL_CLAUDE", "claude-opus-4-5")
    client = anthropic.AsyncAnthropic(api_key=api_key)
    response = await asyncio.wait_for(
        client.messages.create(
            model=model,
            max_tokens=4096,
            system=system,
            messages=[{"role": "user", "content": prompt}],
        ),
        timeout=CALL_TIMEOUT_SECS,
    )
    output = response.content[0].text if response.content else ""
    if not output:
        raise RuntimeError("Claude returned empty output")
    return output


async def _call_gemini(prompt: str, system: str) -> str:
    """Call Google Gemini."""
    api_key = os.getenv("GOOGLE_API_KEY", "")
    if not api_key:
        raise RuntimeError("GOOGLE_API_KEY not configured")
    try:
        import google.generativeai as genai
    except ImportError as exc:
        raise RuntimeError("google-generativeai package not installed") from exc

    model_name = os.getenv("MODEL_GEMINI", "gemini-2.0-flash-exp")
    genai.configure(api_key=api_key)
    model = genai.GenerativeModel(
        model_name=model_name,
        system_instruction=system,
    )
    resp = await asyncio.wait_for(
        model.generate_content_async(prompt),
        timeout=CALL_TIMEOUT_SECS,
    )
    output = resp.text if resp.text else ""
    if not output:
        raise RuntimeError("Gemini returned empty output")
    return output


async def _call_ollama(prompt: str, system: str) -> str:
    """Call local Ollama instance via HTTP."""
    import httpx

    base_url  = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
    model     = os.getenv("MODEL_OLLAMA", "llama3.2")
    full_prompt = f"{system}\n\nUser: {prompt}\nAssistant:"

    async with httpx.AsyncClient(timeout=CALL_TIMEOUT_SECS) as client:
        response = await client.post(
            f"{base_url}/api/generate",
            json={"model": model, "prompt": full_prompt, "stream": False},
        )
        response.raise_for_status()
        data   = response.json()
        output = data.get("response", "")
    if not output:
        raise RuntimeError("Ollama returned empty output")
    return output


# Map provider name → call function
_PROVIDER_CALL = {
    "azure":  lambda p, s, a: _call_azure(p, s, a),
    "openai": lambda p, s, _: _call_openai(p, s),
    "claude": lambda p, s, _: _call_claude(p, s),
    "gemini": lambda p, s, _: _call_gemini(p, s),
    "ollama": lambda p, s, _: _call_ollama(p, s),
}

_PROVIDER_DEFAULT_MODELS = {
    "azure":  "gpt-5 (Azure)",
    "openai": "gpt-4o-mini",
    "claude": os.getenv("MODEL_CLAUDE", "claude-opus-4-5"),
    "gemini": os.getenv("MODEL_GEMINI", "gemini-2.0-flash-exp"),
    "ollama": os.getenv("MODEL_OLLAMA", "llama3.2"),
}


# ---------------------------------------------------------------------------
# LLMRouter
# ---------------------------------------------------------------------------

class LLMRouter:
    """
    Multi-provider LLM router with automatic failover, circuit breaking,
    and per-provider telemetry.

    Usage
    -----
    result = await llm_router.route(
        prompt    = "...",
        system    = "You are ...",
        task_type = TaskType.CODING,   # optional; auto-detected if omitted
        agent_type = "planner",        # forwarded to Azure/gateway
    )
    if result.success:
        text = result.output
    """

    def __init__(self) -> None:
        self._stats: Dict[str, ProviderStats] = {
            name: ProviderStats(provider=name)
            for name in ("azure", "openai", "claude", "gemini", "ollama")
        }
        # rolling log of recent requests for aggregate error_rate
        self._recent: list[Dict[str, Any]] = []   # max 200 entries
        self._fallback_count_total: int = 0

    # ------------------------------------------------------------------
    # Public: route
    # ------------------------------------------------------------------

    async def route(
        self,
        prompt:     str,
        system:     str  = _DEFAULT_SYSTEM,
        task_type:  TaskType | str | None = None,
        agent_type: str  = "general",
    ) -> RouterResult:
        """
        Route a prompt to the best provider for the task type.
        Falls back automatically on provider failure or circuit-open.
        """
        if task_type is None:
            task_type = detect_task_type(prompt)
        elif isinstance(task_type, str):
            try:
                task_type = TaskType(task_type)
            except ValueError:
                task_type = TaskType.GENERAL

        chain          = _ROUTING.get(task_type, _ROUTING[TaskType.GENERAL])
        tried          = []
        fallback_count = 0

        for provider in chain:
            stats = self._stats[provider]

            if stats.circuit_open:
                log.info("LLMRouter: skipping %s (circuit open)", provider)
                tried.append(f"{provider}[circuit-open]")
                continue

            t0 = time.monotonic()
            try:
                call_fn = _PROVIDER_CALL[provider]
                output  = await asyncio.wait_for(
                    call_fn(prompt, system, agent_type),
                    timeout=CALL_TIMEOUT_SECS + 5,
                )
                latency_ms = (time.monotonic() - t0) * 1000
                stats.record_success(latency_ms)
                tried.append(provider)

                result = RouterResult(
                    success         = True,
                    output          = output,
                    provider_used   = provider,
                    model_used      = _PROVIDER_DEFAULT_MODELS.get(provider, "unknown"),
                    task_type       = task_type.value,
                    latency_ms      = round(latency_ms, 1),
                    fallback_count  = fallback_count,
                    tried_providers = tried,
                    request_id      = _get_request_id_safe(),
                )
                self._record_request(result)
                await self._persist_telemetry_async()
                return result

            except Exception as exc:
                latency_ms = (time.monotonic() - t0) * 1000
                stats.record_failure(str(exc))
                tried.append(f"{provider}[failed]")
                log.warning(
                    "LLMRouter: provider=%s failed (%.0f ms): %s — trying next",
                    provider, latency_ms, exc,
                )
                fallback_count += 1
                self._fallback_count_total += 1

        # All providers exhausted
        result = RouterResult(
            success         = False,
            output          = "",
            provider_used   = "none",
            model_used      = "none",
            task_type       = task_type.value,
            latency_ms      = 0.0,
            fallback_count  = fallback_count,
            tried_providers = tried,
            error           = "All providers in chain failed",
            request_id      = _get_request_id_safe(),
        )
        self._record_request(result)
        return result

    # ------------------------------------------------------------------
    # Public: health
    # ------------------------------------------------------------------

    def health(self) -> Dict[str, Any]:
        """
        Return a health snapshot for all providers.
        Consumed by GET /health/llm.
        """
        providers = {}
        for name, stats in self._stats.items():
            availability = "available"
            if stats.circuit_open:
                availability = "circuit_open"
            elif not self._provider_configured(name):
                availability = "not_configured"

            providers[name] = {
                **stats.to_dict(),
                "availability": availability,
            }

        # Aggregate
        total_calls    = sum(s.call_count for s in self._stats.values())
        total_fails    = sum(s.fail_count  for s in self._stats.values())
        global_err     = round(total_fails / total_calls, 4) if total_calls else 0.0
        has_available_provider = any(
            provider["availability"] == "available"
            for provider in providers.values()
        )
        has_circuit_open = any(
            provider["availability"] == "circuit_open"
            for provider in providers.values()
        )

        status = "degraded"
        if has_available_provider and not has_circuit_open and (total_calls == 0 or total_fails < total_calls):
            status = "healthy"

        return {
            "status":                status,
            "global_error_rate":     global_err,
            "global_fallback_count": self._fallback_count_total,
            "providers":             providers,
        }

    # ------------------------------------------------------------------
    # Public: telemetry snapshot
    # ------------------------------------------------------------------

    def telemetry(self) -> Dict[str, Any]:
        """Return full telemetry dict (mirrors health() + recent requests)."""
        return {
            **self.health(),
            "recent_requests": list(reversed(self._recent[-20:])),
        }

    # ------------------------------------------------------------------
    # Public: reset stats (useful in tests)
    # ------------------------------------------------------------------

    def reset_stats(self, provider: str | None = None) -> None:
        if provider:
            self._stats[provider] = ProviderStats(provider=provider)
        else:
            for name in self._stats:
                self._stats[name] = ProviderStats(provider=name)
            self._fallback_count_total = 0
            self._recent.clear()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _provider_configured(self, name: str) -> bool:
        checks = {
            "azure":  bool(os.getenv("AZURE_OPENAI_API_KEY")),
            "openai": bool(os.getenv("OPENAI_API_KEY")),
            "claude": bool(os.getenv("ANTHROPIC_API_KEY")),
            "gemini": bool(os.getenv("GOOGLE_API_KEY")),
            "ollama": True,   # always "configured" (local; may be offline)
        }
        return checks.get(name, False)

    def _record_request(self, result: RouterResult) -> None:
        self._recent.append({
            "provider":        result.provider_used,
            "task_type":       result.task_type,
            "latency_ms":      result.latency_ms,
            "fallback_count":  result.fallback_count,
            "success":         result.success,
            "tried":           result.tried_providers,
            "ts":              time.time(),
        })
        if len(self._recent) > 200:
            self._recent = self._recent[-200:]

    async def _persist_telemetry_async(self) -> None:
        """Fire-and-forget: push telemetry to Redis if available."""
        try:
            import json as _json
            from backend.infrastructure.redis.connection import redis_connection
            if not await redis_connection.ensure_connected():
                return
            redis = redis_connection.client
            snapshot = {
                name: stats.to_dict()
                for name, stats in self._stats.items()
            }
            await redis.set(
                "cx:llm:router:telemetry",
                _json.dumps(snapshot),
                ex=86400,   # 1 day TTL
            )
        except Exception:
            pass   # telemetry persistence is best-effort


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

llm_router = LLMRouter()

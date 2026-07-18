from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional


class ModelCapability(str, Enum):
    CHAT = "chat"
    STREAMING = "streaming"
    FUNCTION_CALLING = "function_calling"
    STRUCTURED_OUTPUT = "structured_output"
    VISION = "vision"
    EMBEDDINGS = "embeddings"
    TOOL_USE = "tool_use"


class FinishReason(str, Enum):
    STOP = "stop"
    LENGTH = "length"
    CONTENT_FILTER = "content_filter"
    FUNCTION_CALL = "function_call"
    TOOL_CALL = "tool_call"
    ERROR = "error"
    CANCELLED = "cancelled"
    TIMEOUT = "timeout"


@dataclass
class LLMModelInfo:
    name: str
    provider: str
    capabilities: set[ModelCapability] = field(default_factory=set)
    context_window: int = 4096
    max_output_tokens: int = 4096
    cost_per_1k_input: float = 0.0
    cost_per_1k_output: float = 0.0
    version: str = "1.0"
    is_default: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class LLMProviderInfo:
    name: str
    display_name: str
    version: str = "1.0"
    models: list[LLMModelInfo] = field(default_factory=list)
    priority: int = 100
    is_available: bool = False
    latency_ms: float = 0.0
    last_health_check: Optional[str] = None
    config: dict[str, Any] = field(default_factory=dict)


@dataclass
class LLMRequest:
    model: str = ""
    messages: list[dict[str, str]] = field(default_factory=list)
    system_prompt: Optional[str] = None
    temperature: float = 0.7
    max_tokens: Optional[int] = None
    stop: Optional[list[str]] = None
    functions: Optional[list[dict[str, Any]]] = None
    function_call: Optional[str] = None
    response_format: Optional[dict[str, Any]] = None
    stream: bool = False
    timeout_seconds: float = 60.0
    user: Optional[str] = None
    metadata: dict[str, Any] = field(default_factory=dict)
    request_id: str = field(default_factory=lambda: f"llm-{uuid.uuid4().hex[:12]}")

    def to_dict(self) -> dict[str, Any]:
        return {k: v for k, v in self.__dict__.items() if not k.startswith("_")}


@dataclass
class LLMResponse:
    content: str = ""
    model: str = ""
    provider: str = ""
    usage: Optional[dict[str, Any]] = None
    finish_reason: Optional[FinishReason] = None
    function_call: Optional[dict[str, Any]] = None
    latency_ms: float = 0.0
    cached: bool = False
    request_id: str = ""
    error: Optional[str] = None
    raw: Optional[dict[str, Any]] = None
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


@dataclass
class LLMContext:
    request_id: str = ""
    user_id: str = ""
    tenant_id: str = ""
    session_id: str = ""
    conversation_id: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


@dataclass
class StreamChunk:
    content: str = ""
    finish_reason: Optional[FinishReason] = None
    usage: Optional[dict[str, Any]] = None
    index: int = 0
    request_id: str = ""
    model: str = ""
    provider: str = ""
    done: bool = False


@dataclass
class EmbeddingRequest:
    texts: list[str] = field(default_factory=list)
    model: str = ""
    request_id: str = field(default_factory=lambda: f"emb-{uuid.uuid4().hex[:12]}")


@dataclass
class EmbeddingResult:
    embeddings: list[list[float]] = field(default_factory=list)
    model: str = ""
    provider: str = ""
    dimensions: int = 0
    latency_ms: float = 0.0
    request_id: str = ""
    error: Optional[str] = None


@dataclass
class ProviderHealth:
    provider: str = ""
    is_available: bool = False
    latency_ms: float = 0.0
    models_available: list[str] = field(default_factory=list)
    error: Optional[str] = None
    last_check: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

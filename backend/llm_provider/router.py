from __future__ import annotations

import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional

from backend.llm_provider.models import LLMModelInfo, LLMProviderInfo, LLMRequest
from backend.llm_provider.registry import ProviderRegistry

log = logging.getLogger(__name__)


class RoutingStrategy(str, Enum):
    PRIORITY = "priority"
    FALLBACK = "fallback"
    COST = "cost"
    CAPABILITY = "capability"
    ROUND_ROBIN = "round_robin"
    LATENCY = "latency"


class RoutingDimension(str, Enum):
    COST = "cost"
    LATENCY = "latency"
    CAPABILITIES = "capabilities"
    CONTEXT_WINDOW = "context_window"
    AVAILABILITY = "availability"


@dataclass
class RoutingRule:
    strategy: RoutingStrategy = RoutingStrategy.PRIORITY
    dimensions: list[RoutingDimension] = field(default_factory=list)
    fallback_order: list[str] = field(default_factory=list)
    preferred_provider: str = ""
    max_cost_per_1k: float = 0.0
    min_context_window: int = 0
    required_capabilities: set[str] = field(default_factory=set)


@dataclass
class RoutingStats:
    total_selections: int = 0
    by_strategy: dict[str, int] = field(default_factory=dict)
    by_provider: dict[str, int] = field(default_factory=dict)
    by_model: dict[str, int] = field(default_factory=dict)
    fallback_count: int = 0
    estimated_cost_saved: float = 0.0


class ModelRouter:
    def __init__(self, registry: Optional[ProviderRegistry] = None) -> None:
        self._registry = registry or __import__("backend.llm_provider.registry", fromlist=["registry"]).registry
        self._round_robin_index: dict[str, int] = {}
        self._stats = RoutingStats()

    def select_model(
        self,
        request: Optional[LLMRequest] = None,
        *,
        model: str = "",
        provider: str = "",
        strategy: RoutingStrategy = RoutingStrategy.PRIORITY,
        required_capabilities: Optional[set[str]] = None,
        min_context_window: int = 0,
        preferred_provider: str = "",
        fallback_order: Optional[list[str]] = None,
    ) -> tuple[Optional[str], Optional[str]]:
        was_fallback = False
        if model:
            prov = self._find_provider_for_model(model)
            if prov:
                self._track_selection(strategy, prov, model, was_fallback)
                return model, prov
            log.warning("Model %s not found in any provider, using fallback", model)
            was_fallback = True

        candidates = self._get_candidates(provider, required_capabilities or set())
        if not candidates:
            result = self._default_fallback()
            self._track_selection(strategy, result[1], result[0], True)
            return result

        if strategy == RoutingStrategy.PRIORITY:
            result = self._select_by_priority(candidates, min_context_window)
        elif strategy == RoutingStrategy.COST:
            result = self._select_by_cost(candidates, min_context_window)
        elif strategy == RoutingStrategy.LATENCY:
            result = self._select_by_latency(candidates, min_context_window)
        elif strategy == RoutingStrategy.ROUND_ROBIN:
            result = self._select_round_robin(candidates, min_context_window)
        elif strategy == RoutingStrategy.FALLBACK:
            result = self._select_by_fallback(fallback_order or [], candidates, min_context_window)
        elif strategy == RoutingStrategy.CAPABILITY:
            result = self._select_by_capability(candidates, required_capabilities or set(), min_context_window)
        else:
            result = self._select_by_priority(candidates, min_context_window)
        self._track_selection(strategy, result[1], result[0], was_fallback)
        return result

    def select_models(
        self,
        count: int = 3,
        required_capabilities: Optional[set[str]] = None,
    ) -> list[tuple[str, str]]:
        results: list[tuple[str, str]] = []
        seen: set[str] = set()
        for provider in self._registry.get_sorted():
            if not provider.provider_info.is_available:
                continue
            for model_info in provider.provider_info.models:
                if len(results) >= count:
                    return results
                key = (model_info.name, provider.name)
                if key in seen:
                    continue
                if required_capabilities:
                    model_caps = {c.value for c in model_info.capabilities}
                    if not required_capabilities.issubset(model_caps):
                        continue
                seen.add(key)
                results.append(key)
        return results

    def _track_selection(self, strategy: RoutingStrategy, provider: str, model: str, was_fallback: bool) -> None:
        self._stats.total_selections += 1
        strat_key = strategy.value if isinstance(strategy, RoutingStrategy) else str(strategy)
        self._stats.by_strategy[strat_key] = self._stats.by_strategy.get(strat_key, 0) + 1
        self._stats.by_provider[provider] = self._stats.by_provider.get(provider, 0) + 1
        self._stats.by_model[model] = self._stats.by_model.get(model, 0) + 1
        if was_fallback:
            self._stats.fallback_count += 1

    def get_routing_stats(self) -> dict[str, Any]:
        return {
            "total_selections": self._stats.total_selections,
            "by_strategy": dict(self._stats.by_strategy),
            "by_provider": dict(self._stats.by_provider),
            "by_model": dict(self._stats.by_model),
            "fallback_count": self._stats.fallback_count,
            "estimated_cost_saved": round(self._stats.estimated_cost_saved, 6),
        }

    def reset_routing_stats(self) -> None:
        self._stats = RoutingStats()

    def _get_candidates(self, provider_filter: str = "", required_caps: Optional[set[str]] = None) -> list[tuple[LLMProviderInfo, LLMModelInfo]]:
        candidates: list[tuple[LLMProviderInfo, LLMModelInfo]] = []
        for provider in self._registry.list_available() if not provider_filter else [self._registry.get(provider_filter)]:
            if not provider:
                continue
            info = provider.provider_info
            for model_info in info.models:
                if required_caps:
                    model_caps = {c.value for c in model_info.capabilities}
                    if not required_caps.issubset(model_caps):
                        continue
                candidates.append((info, model_info))
        return candidates

    def _select_by_priority(self, candidates: list[tuple[LLMProviderInfo, LLMModelInfo]], min_ctx: int) -> tuple[str, str]:
        candidates.sort(key=lambda c: (c[0].priority, c[1].cost_per_1k_input))
        for pinfo, minfo in candidates:
            if minfo.context_window >= min_ctx:
                return minfo.name, pinfo.name
        return candidates[0][1].name, candidates[0][0].name if candidates else self._default_fallback()

    def _select_by_cost(self, candidates: list[tuple[LLMProviderInfo, LLMModelInfo]], min_ctx: int) -> tuple[str, str]:
        candidates.sort(key=lambda c: c[1].cost_per_1k_input + c[1].cost_per_1k_output)
        for pinfo, minfo in candidates:
            if minfo.context_window >= min_ctx:
                return minfo.name, pinfo.name
        return candidates[0][1].name, candidates[0][0].name if candidates else self._default_fallback()

    def _select_by_latency(self, candidates: list[tuple[LLMProviderInfo, LLMModelInfo]], min_ctx: int) -> tuple[str, str]:
        candidates.sort(key=lambda c: c[0].latency_ms)
        for pinfo, minfo in candidates:
            if minfo.context_window >= min_ctx:
                return minfo.name, pinfo.name
        return candidates[0][1].name, candidates[0][0].name if candidates else self._default_fallback()

    def _select_round_robin(self, candidates: list[tuple[LLMProviderInfo, LLMModelInfo]], min_ctx: int) -> tuple[str, str]:
        valid = [(p, m) for p, m in candidates if m.context_window >= min_ctx]
        if not valid:
            return self._default_fallback()
        key = "default"
        idx = self._round_robin_index.get(key, 0) % len(valid)
        self._round_robin_index[key] = idx + 1
        pinfo, minfo = valid[idx]
        return minfo.name, pinfo.name

    def _select_by_fallback(self, fallback_order: list[str], candidates: list[tuple[LLMProviderInfo, LLMModelInfo]], min_ctx: int) -> tuple[str, str]:
        for prov_name in fallback_order:
            for pinfo, minfo in candidates:
                if pinfo.name == prov_name and minfo.context_window >= min_ctx:
                    return minfo.name, pinfo.name
        return self._select_by_priority(candidates, min_ctx)

    def _select_by_capability(self, candidates: list[tuple[LLMProviderInfo, LLMModelInfo]], caps: set[str], min_ctx: int) -> tuple[str, str]:
        for pinfo, minfo in candidates:
            model_caps = {c.value for c in minfo.capabilities}
            if caps.issubset(model_caps) and minfo.context_window >= min_ctx:
                return minfo.name, pinfo.name
        return self._select_by_priority(candidates, min_ctx)

    def _find_provider_for_model(self, model_name: str) -> Optional[str]:
        for provider in self._registry.list_providers():
            for minfo in provider.provider_info.models:
                if minfo.name == model_name:
                    return provider.name
        return None

    def _default_fallback(self) -> tuple[str, str]:
        for provider in self._registry.get_sorted():
            if provider.provider_info.models:
                return provider.provider_info.models[0].name, provider.name
        return "gpt-4o", "openai"


router = ModelRouter()

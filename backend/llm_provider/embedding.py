from __future__ import annotations

import logging
from typing import Optional

from backend.llm_provider.models import EmbeddingRequest, EmbeddingResult
from backend.llm_provider.registry import ProviderRegistry

log = logging.getLogger(__name__)


class EmbeddingProviderInterface:
    def __init__(self, registry: Optional[ProviderRegistry] = None) -> None:
        self._registry = registry or __import__("backend.llm_provider.registry", fromlist=["registry"]).registry

    async def embed(
        self,
        texts: list[str],
        model: str = "",
        provider: str = "",
        request_id: str = "",
    ) -> EmbeddingResult:
        request = EmbeddingRequest(
            texts=texts,
            model=model,
            request_id=request_id or f"emb-{__import__('uuid').uuid4().hex[:12]}",
        )

        if provider:
            prov = self._registry.get(provider)
            if prov:
                return await prov.embed(request)

        for prov in self._registry.get_sorted():
            if prov.provider_info.is_available:
                result = await prov.embed(request)
                if result.embeddings:
                    return result

        return EmbeddingResult(
            error="No available embedding provider found",
            request_id=request.request_id,
        )

    async def embed_batch(
        self,
        texts: list[str],
        batch_size: int = 10,
        model: str = "",
        provider: str = "",
    ) -> list[EmbeddingResult]:
        results: list[EmbeddingResult] = []
        for i in range(0, len(texts), batch_size):
            batch = texts[i:i + batch_size]
            result = await self.embed(batch, model=model, provider=provider)
            results.append(result)
        return results

    def get_embedding_providers(self) -> list[str]:
        return [
            p.name for p in self._registry.list_providers()
            if any("embeddings" in (c.value for c in m.capabilities) for m in p.provider_info.models)
        ]

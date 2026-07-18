from __future__ import annotations

import json
import logging
import os
from typing import Any, Optional

log = logging.getLogger(__name__)

try:
    from opensearchpy import AsyncOpenSearch, RequestsHttpConnection
    _OS_AVAILABLE = True
except ImportError:
    _OS_AVAILABLE = False

_INDEX_MAPPINGS: dict[str, dict[str, Any]] = {
    "cortex-logs": {
        "settings": {"number_of_shards": 1, "number_of_replicas": 0},
        "mappings": {
            "properties": {
                "timestamp": {"type": "date"},
                "service": {"type": "keyword"},
                "level": {"type": "keyword"},
                "message": {"type": "text"},
                "execution_id": {"type": "keyword"},
                "mission_id": {"type": "keyword"},
                "agent": {"type": "keyword"},
                "trace_id": {"type": "keyword"},
                "metadata": {"type": "object"},
            }
        },
    },
    "cortex-traces": {
        "settings": {"number_of_shards": 1, "number_of_replicas": 0},
        "mappings": {
            "properties": {
                "timestamp": {"type": "date"},
                "trace_id": {"type": "keyword"},
                "span_id": {"type": "keyword"},
                "parent_span_id": {"type": "keyword"},
                "service": {"type": "keyword"},
                "operation": {"type": "keyword"},
                "duration_ms": {"type": "float"},
                "status": {"type": "keyword"},
                "tags": {"type": "object"},
            }
        },
    },
    "cortex-audit": {
        "settings": {"number_of_shards": 1, "number_of_replicas": 0},
        "mappings": {
            "properties": {
                "timestamp": {"type": "date"},
                "action": {"type": "keyword"},
                "actor": {"type": "keyword"},
                "target": {"type": "keyword"},
                "outcome": {"type": "keyword"},
                "reason": {"type": "text"},
                "metadata": {"type": "object"},
            }
        },
    },
}


class OpenSearchClient:
    def __init__(self) -> None:
        self._client: Optional[AsyncOpenSearch] = None
        self._available: bool = False

    async def connect(self) -> bool:
        if not _OS_AVAILABLE:
            log.warning("opensearch-py not installed — OpenSearch disabled")
            return False
        host = os.getenv("OPENSEARCH_HOST", "localhost")
        port = int(os.getenv("OPENSEARCH_REST_PORT", "9200"))
        use_ssl = os.getenv("OPENSEARCH_USE_SSL", "false").lower() == "true"
        verify_certs = os.getenv("OPENSEARCH_VERIFY_CERTS", "true").lower() == "true"

        try:
            self._client = AsyncOpenSearch(
                hosts=[{"host": host, "port": port}],
                use_ssl=use_ssl,
                verify_certs=verify_certs,
                connection_class=RequestsHttpConnection,
                http_compress=True,
            )
            info = await self._client.info()
            log.info("OpenSearch connected (version=%s)", info.get("version", {}).get("number", "unknown"))
            await self._ensure_indices()
            self._available = True
            return True
        except Exception as exc:
            log.warning("OpenSearch connect failed: %s", exc)
            self._available = False
            return False

    async def _ensure_indices(self):
        for name, body in _INDEX_MAPPINGS.items():
            try:
                exists = await self._client.indices.exists(index=name)
                if not exists:
                    await self._client.indices.create(index=name, body=body)
                    log.info("Created OpenSearch index: %s", name)
            except Exception as exc:
                log.warning("Index %s creation failed: %s", name, exc)

    # ------------------------------------------------------------------
    # Log operations
    # ------------------------------------------------------------------

    async def index_log(self, log_entry: dict[str, Any], index: str = "cortex-logs") -> str:
        try:
            resp = await self._client.index(index=index, body=log_entry, refresh="wait_for")
            return resp["_id"]
        except Exception as exc:
            log.error("Log indexing failed: %s", exc)
            raise

    async def search_logs(
        self, query: str, index: str = "cortex-logs", size: int = 50, filters: Optional[dict[str, Any]] = None
    ) -> list[dict[str, Any]]:
        try:
            must: list[Any] = [{"match": {"message": query}}]
            if filters:
                for field, value in filters.items():
                    must.append({"term": {field: value}})
            resp = await self._client.search(
                index=index,
                body={"query": {"bool": {"must": must}}, "size": size, "sort": [{"timestamp": {"order": "desc"}}]},
            )
            return [h["_source"] for h in resp["hits"]["hits"]]
        except Exception as exc:
            log.error("Log search failed: %s", exc)
            return []

    # ------------------------------------------------------------------
    # Trace operations
    # ------------------------------------------------------------------

    async def index_trace(self, trace_entry: dict[str, Any]) -> str:
        return await self.index_log(trace_entry, index="cortex-traces")

    async def get_trace(self, trace_id: str) -> list[dict[str, Any]]:
        try:
            resp = await self._client.search(
                index="cortex-traces",
                body={"query": {"term": {"trace_id": trace_id}}, "size": 200, "sort": [{"timestamp": {"order": "asc"}}]},
            )
            return [h["_source"] for h in resp["hits"]["hits"]]
        except Exception:
            return []

    # ------------------------------------------------------------------
    # Health
    # ------------------------------------------------------------------

    async def ping(self) -> bool:
        if not self._available or self._client is None:
            return False
        try:
            return await self._client.ping()
        except Exception:
            self._available = False
            return False

    async def close(self) -> None:
        if self._client:
            try:
                await self._client.close()
            except Exception:
                pass
        self._available = False
        log.info("OpenSearch client closed")

    @property
    def is_available(self) -> bool:
        return self._available


opensearch_client = OpenSearchClient()

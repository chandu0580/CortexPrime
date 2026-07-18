from __future__ import annotations

import logging
from typing import Any, Optional

from backend.connector.adapter.interfaces import ConnectorAdapter
from backend.connector.models import Capability

log = logging.getLogger(__name__)


class ConnectorRegistry:
    def __init__(self) -> None:
        self._adapters: dict[str, ConnectorAdapter] = {}

    def register(self, adapter: ConnectorAdapter) -> None:
        ctype = adapter.connector_type
        if ctype in self._adapters:
            log.warning("Overwriting existing adapter: %s", ctype)
        self._adapters[ctype] = adapter
        log.info("Registered connector adapter: %s (%s)", adapter.connector_name, ctype)

    def unregister(self, connector_type: str) -> None:
        self._adapters.pop(connector_type, None)

    def get(self, connector_type: str) -> Optional[ConnectorAdapter]:
        return self._adapters.get(connector_type)

    def list(self) -> list[dict[str, Any]]:
        return [
            {
                "connector_type": a.connector_type,
                "connector_name": a.connector_name,
                "version": a.adapter_version,
            }
            for a in self._adapters.values()
        ]

    async def find_by_capability(self, capability: Capability) -> list[ConnectorAdapter]:
        result: list[ConnectorAdapter] = []
        for a in self._adapters.values():
            try:
                caps = await a.capabilities()
                if capability in caps:
                    result.append(a)
            except Exception:
                continue
        return result

    def count(self) -> int:
        return len(self._adapters)

    async def health_summary(self) -> dict[str, str]:
        result: dict[str, str] = {}
        for ctype, adapter in self._adapters.items():
            try:
                status = await adapter.health_check()
                result[ctype] = status.value
            except Exception as e:
                result[ctype] = f"error: {e}"
        return result


connector_registry = ConnectorRegistry()

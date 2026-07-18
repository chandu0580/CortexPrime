from __future__ import annotations

import logging

from backend.connector.adapters import ADAPTER_CLASSES
from backend.connector.capabilities import capability_catalog
from backend.connector.registry import connector_registry
from backend.connector.service import ConnectorService
from backend.core.dependency_container import container

log = logging.getLogger(__name__)


async def _register_default_adapters() -> None:
    for adapter_cls in ADAPTER_CLASSES:
        try:
            adapter = adapter_cls()
            initialized = await adapter.initialize()
            if initialized:
                connector_registry.register(adapter)
                log.info("Registered adapter: %s (%s)", adapter.connector_name, adapter.connector_type)
            else:
                log.warning("Adapter %s failed to initialize — skipping registration", adapter_cls.__name__)
        except Exception as exc:
            log.warning("Adapter %s registration error: %s", adapter_cls.__name__, exc)


async def _connector_startup() -> None:
    await _register_default_adapters()
    log.info("Connector Runtime: startup complete (%d adapters registered)", connector_registry.count())


async def _connector_shutdown() -> None:
    for entry in connector_registry.list():
        ctype = entry["connector_type"]
        adapter = connector_registry.get(ctype)
        if adapter:
            try:
                await adapter.shutdown()
            except Exception:
                log.warning("Connector %s shutdown error", ctype)
    capability_catalog.entries.clear()
    log.info("Connector Runtime: shutdown complete")


def register_connector_services() -> None:
    service = ConnectorService()
    container.register(
        "connector_service",
        service,
        startup=_connector_startup,
        shutdown=_connector_shutdown,
        startup_priority=50,
    )
    log.info("Connector Runtime services registered")

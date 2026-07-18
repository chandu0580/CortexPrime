from __future__ import annotations

import logging

from backend.cognitive_memory.service import cognitive_memory_service

log = logging.getLogger(__name__)


async def _startup() -> None:
    log.info("Cognitive Memory Runtime starting up")


async def _shutdown() -> None:
    log.info("Cognitive Memory Runtime shutting down")


try:
    from backend.core.dependency_container import container

    container.register(
        "cognitive_memory_service",
        cognitive_memory_service,
        startup=_startup,
        shutdown=_shutdown,
        startup_priority=80,
    )
    log.info("Cognitive Memory Service registered in DI container at priority 80")
except ImportError:
    log.warning("DI container not available — Cognitive Memory Service runs as singleton")

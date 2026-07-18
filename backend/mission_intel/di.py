from __future__ import annotations

import logging

from backend.mission_intel.service import mission_intel_service

log = logging.getLogger(__name__)


async def _startup() -> None:
    log.info("Mission Intelligence Service starting up")


async def _shutdown() -> None:
    log.info("Mission Intelligence Service shutting down")


try:
    from backend.core.dependency_container import container

    container.register(
        "mission_intel_service",
        mission_intel_service,
        startup=_startup,
        shutdown=_shutdown,
        startup_priority=85,
    )
    log.info("Mission Intelligence Service registered in DI container at priority 85")
except ImportError:
    log.warning("DI container not available — Mission Intelligence Service runs as singleton")

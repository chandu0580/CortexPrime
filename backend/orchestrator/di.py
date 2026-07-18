from __future__ import annotations

import logging

from backend.orchestrator.service import AutonomousMissionOrchestrator, orchestrator_service

log = logging.getLogger(__name__)


async def _startup() -> None:
    log.info("Autonomous Mission Orchestrator starting up")


async def _shutdown() -> None:
    log.info("Autonomous Mission Orchestrator shutting down")


try:
    from backend.core.dependency_container import container

    container.register(
        "orchestrator_service",
        orchestrator_service,
        startup=_startup,
        shutdown=_shutdown,
        startup_priority=75,
    )
    log.info("Autonomous Mission Orchestrator registered in DI container at priority 75")
except ImportError:
    log.warning("DI container not available — Autonomous Mission Orchestrator runs as singleton")

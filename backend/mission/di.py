from __future__ import annotations

import logging

from backend.core.dependency_container import container
from backend.mission.service import MissionService

log = logging.getLogger(__name__)


def register_mission_services() -> None:
    execution_service = None
    try:
        execution_service = container.resolve("execution_service")
    except Exception:
        log.warning("Execution service not available, step execution will use stub fallback")

    governance_service = None
    try:
        governance_service = container.resolve("governance_service")
    except Exception:
        log.warning("Governance service not available, mission execution will proceed without governance check")

    knowledge_service = None
    try:
        knowledge_service = container.resolve("knowledge_service")
    except Exception:
        log.warning("Knowledge service not available, mission auto-indexing will not run")

    service = MissionService(
        execution_service=execution_service,
        governance_service=governance_service,
        knowledge_service=knowledge_service,
    )
    container.register("mission_service", service)
    log.info("Mission Runtime services registered")

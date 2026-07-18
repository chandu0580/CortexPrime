from __future__ import annotations

import logging

from backend.core.dependency_container import container
from backend.execution.service import ExecutionService

log = logging.getLogger(__name__)


def register_execution_services() -> None:
    governance_service = None
    try:
        governance_service = container.resolve("governance_service")
    except Exception:
        log.warning("Governance service not available, execution will proceed without governance check")

    knowledge_service = None
    try:
        knowledge_service = container.resolve("knowledge_service")
    except Exception:
        log.warning("Knowledge service not available, execution auto-indexing will not run")

    service = ExecutionService(
        governance_service=governance_service,
        knowledge_service=knowledge_service,
    )
    container.register("execution_service", service)
    log.info("Execution Runtime services registered")

from __future__ import annotations

import logging

from backend.core.dependency_container import container
from backend.governance.service import GovernanceService

log = logging.getLogger(__name__)


def register_governance_services() -> None:
    service = GovernanceService()
    container.register("governance_service", service, startup_priority=40)
    log.info("Governance Runtime services registered")

from __future__ import annotations

import logging

from backend.core.dependency_container import container
from backend.knowledge.service import KnowledgeService

log = logging.getLogger(__name__)


def register_knowledge_services() -> None:
    service = KnowledgeService()
    container.register("knowledge_service", service, startup_priority=35)
    log.info("Knowledge Runtime services registered")

from __future__ import annotations

import logging

from backend.core.dependency_container import container
from backend.learning.service import LearningService

log = logging.getLogger(__name__)


def register_learning_services() -> None:
    service = LearningService()
    container.register("learning_service", service, startup_priority=30)
    log.info("Learning Runtime services registered")

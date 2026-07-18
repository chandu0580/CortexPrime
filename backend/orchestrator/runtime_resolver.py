from __future__ import annotations

import logging
from typing import Any

log = logging.getLogger(__name__)


def _resolve(name: str) -> Any:
    try:
        from backend.core.dependency_container import container
        return container.resolve(name)
    except Exception:
        return None


def get_mission_intel_service():
    return _resolve("mission_intel_service")


def get_knowledge_service():
    return _resolve("knowledge_service")


def get_learning_service():
    return _resolve("learning_service")


def get_governance_service():
    return _resolve("governance_service")


def get_execution_service():
    return _resolve("execution_service")


def get_connector_service():
    return _resolve("connector_service")


def get_cognitive_memory_service():
    return _resolve("cognitive_memory_service")


def get_mission_service():
    return _resolve("mission_service")


def get_ai_service():
    return _resolve("ai_service")


def resolve_runtime_status() -> dict[str, bool]:
    return {
        "mission_intel": get_mission_intel_service() is not None,
        "knowledge": get_knowledge_service() is not None,
        "learning": get_learning_service() is not None,
        "governance": get_governance_service() is not None,
        "execution": get_execution_service() is not None,
        "connector": get_connector_service() is not None,
        "cognitive_memory": get_cognitive_memory_service() is not None,
        "mission": get_mission_service() is not None,
        "ai": get_ai_service() is not None,
    }

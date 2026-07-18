from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional

from backend.connector.models import Capability

log = logging.getLogger(__name__)


class AdapterHealthStatus(str, Enum):
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    UNKNOWN = "unknown"


@dataclass
class AdapterResult:
    success: bool
    outputs: dict[str, Any] = field(default_factory=dict)
    error: Optional[str] = None
    duration_ms: Optional[float] = None
    metadata: dict[str, Any] = field(default_factory=dict)


class ConnectorAdapter(ABC):

    @property
    @abstractmethod
    def connector_type(self) -> str:
        ...

    @property
    @abstractmethod
    def connector_name(self) -> str:
        ...

    @property
    @abstractmethod
    def adapter_version(self) -> str:
        ...

    @abstractmethod
    async def initialize(self) -> bool:
        ...

    @abstractmethod
    async def health_check(self) -> AdapterHealthStatus:
        ...

    @abstractmethod
    async def capabilities(self) -> list[Capability]:
        ...

    @abstractmethod
    async def execute(self, capability: Capability, inputs: dict[str, Any],
                      timeout_seconds: Optional[int] = None) -> AdapterResult:
        ...

    @abstractmethod
    async def shutdown(self) -> None:
        ...

    async def metadata(self) -> dict[str, Any]:
        return {
            "connector_type": self.connector_type,
            "connector_name": self.connector_name,
            "version": self.adapter_version,
        }

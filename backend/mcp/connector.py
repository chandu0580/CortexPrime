from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional

from backend.mcp.models import MCPConnectorConfig, MCPRequest, MCPResponse, MCPToolDefinition

log = logging.getLogger(__name__)


class MCPConnector(ABC):
    def __init__(self, config: MCPConnectorConfig):
        self.config = config
        self._authenticated = False

    @abstractmethod
    async def authenticate(self) -> bool:
        ...

    @abstractmethod
    async def execute_tool(self, request: MCPRequest) -> MCPResponse:
        ...

    def get_tools(self) -> List[MCPToolDefinition]:
        return self.config.tools

    @property
    def name(self) -> str:
        return self.config.name

    @property
    def is_authenticated(self) -> bool:
        return self._authenticated

    async def health_check(self) -> bool:
        return self._authenticated

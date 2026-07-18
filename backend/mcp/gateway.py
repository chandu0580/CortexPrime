from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from backend.mcp.connector import MCPConnector
from backend.mcp.models import MCPRequest, MCPResponse, MCPToolDefinition
from backend.mcp.registry import mcp_registry

log = logging.getLogger(__name__)


class MCPGateway:
    def __init__(self):
        self._registry = mcp_registry

    def register_connector(self, connector: MCPConnector) -> None:
        self._registry.register(connector)

    def unregister_connector(self, name: str) -> None:
        self._registry.unregister(name)

    def get_connector(self, name: str) -> Optional[MCPConnector]:
        return self._registry.get_connector(name)

    def list_connectors(self) -> List[Dict[str, Any]]:
        return self._registry.list_connectors()

    def list_tools(self) -> List[MCPToolDefinition]:
        return self._registry.list_tools()

    async def execute_tool(self, request: MCPRequest) -> MCPResponse:
        return await self._registry.execute(request)

    async def health(self) -> Dict[str, Any]:
        connectors = self.list_connectors()
        return {
            "status": "healthy",
            "connector_count": len(connectors),
            "authenticated": sum(1 for c in connectors if c["authenticated"]),
            "tool_count": len(self.list_tools()),
        }


mcp_gateway = MCPGateway()

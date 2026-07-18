from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from backend.mcp.connector import MCPConnector
from backend.mcp.models import MCPRequest, MCPResponse, MCPToolDefinition

log = logging.getLogger(__name__)


class MCPRegistry:
    def __init__(self):
        self._connectors: Dict[str, MCPConnector] = {}

    def register(self, connector: MCPConnector) -> None:
        self._connectors[connector.name] = connector
        log.info("MCP connector registered: %s", connector.name)

    def unregister(self, name: str) -> None:
        self._connectors.pop(name, None)
        log.info("MCP connector unregistered: %s", name)

    def get_connector(self, name: str) -> Optional[MCPConnector]:
        return self._connectors.get(name)

    def list_connectors(self) -> List[Dict[str, Any]]:
        return [
            {
                "name": c.name,
                "version": c.config.version,
                "description": c.config.description,
                "authenticated": c.is_authenticated,
                "tools": [t.name for t in c.get_tools()],
            }
            for c in self._connectors.values()
        ]

    def list_tools(self) -> List[MCPToolDefinition]:
        tools = []
        for connector in self._connectors.values():
            tools.extend(connector.get_tools())
        return tools

    async def execute(self, request: MCPRequest) -> MCPResponse:
        for connector in self._connectors.values():
            for tool in connector.get_tools():
                if tool.name == request.tool:
                    if not connector.is_authenticated:
                        ok = await connector.authenticate()
                        if not ok:
                            return MCPResponse(
                                success=False,
                                error=f"Authentication failed for connector '{connector.name}'",
                                request_id=request.request_id,
                            )
                    return await connector.execute_tool(request)
        return MCPResponse(
            success=False,
            error=f"Tool '{request.tool}' not found in any registered connector",
            request_id=request.request_id,
        )


mcp_registry = MCPRegistry()

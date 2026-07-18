from __future__ import annotations

import logging
from typing import Any, Dict

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from backend.auth.dependencies import require_user
from backend.mcp.gateway import MCPRequest, MCPResponse, mcp_gateway
from backend.mcp.registry import mcp_registry

log = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v2/mcp", tags=["mcp"])


class ExecuteToolRequest(BaseModel):
    tool: str
    params: Dict[str, Any] = {}


class RegisterConnectorRequest(BaseModel):
    name: str
    version: str = "1.0.0"
    description: str = ""
    auth_type: str = "none"
    auth_config: Dict[str, Any] = {}
    tools: list[Dict[str, Any]] = []


@router.get("/tools")
async def list_tools(user: Dict = Depends(require_user)):
    return {"tools": [t.__dict__ for t in mcp_gateway.list_tools()]}


@router.get("/connectors")
async def list_connectors(user: Dict = Depends(require_user)):
    return {"connectors": mcp_gateway.list_connectors()}


@router.post("/execute")
async def execute_tool(
    req: ExecuteToolRequest,
    user: Dict = Depends(require_user),
):
    mcp_req = MCPRequest(tool=req.tool, params=req.params)
    response = await mcp_gateway.execute_tool(mcp_req)
    if not response.success:
        raise HTTPException(status_code=400, detail=response.error or "Tool execution failed")
    return {"result": response.data, "request_id": response.request_id}


@router.post("/connectors/register")
async def register_connector(
    req: RegisterConnectorRequest,
    user: Dict = Depends(require_user),
):
    from backend.mcp.connector import MCPConnector
    from backend.mcp.models import MCPConnectorConfig, MCPToolDefinition

    config = MCPConnectorConfig(
        name=req.name,
        version=req.version,
        description=req.description,
        auth_type=req.auth_type,
        auth_config=req.auth_config,
        tools=[MCPToolDefinition(**t) for t in req.tools],
    )

    class DynamicConnector(MCPConnector):
        async def authenticate(self) -> bool:
            return True

        async def execute_tool(self, request: MCPRequest) -> MCPResponse:
            return MCPResponse(success=False, error=f"Tool '{request.tool}' not implemented by dynamic connector")

    connector = DynamicConnector(config)
    mcp_registry.register(connector)
    return {"status": "registered", "name": req.name}


@router.get("/health")
async def mcp_health():
    return await mcp_gateway.health()

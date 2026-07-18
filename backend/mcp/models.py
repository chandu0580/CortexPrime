from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class MCPToolDefinition:
    name: str
    description: str
    input_schema: Dict[str, Any] = field(default_factory=dict)
    output_schema: Dict[str, Any] = field(default_factory=dict)


@dataclass
class MCPRequest:
    tool: str
    params: Dict[str, Any] = field(default_factory=dict)
    request_id: Optional[str] = None


@dataclass
class MCPResponse:
    success: bool
    data: Optional[Any] = None
    error: Optional[str] = None
    request_id: Optional[str] = None


@dataclass
class MCPConnectorConfig:
    name: str
    version: str
    description: str
    auth_type: str = "none"
    auth_config: Dict[str, Any] = field(default_factory=dict)
    tools: List[MCPToolDefinition] = field(default_factory=list)

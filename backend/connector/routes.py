from __future__ import annotations

import logging
from typing import Any, Optional

from fastapi import APIRouter, HTTPException, Query

log = logging.getLogger(__name__)

router = APIRouter(prefix="/api/connectors", tags=["connectors"])


_handlers: dict[str, Any] = {}


def register_connector_routes(service: Any, events: Any) -> None:
    _handlers["service"] = service
    _handlers["events"] = events


def _get_service():
    svc = _handlers.get("service")
    if not svc:
        from backend.connector.service import ConnectorService
        svc = ConnectorService()
        _handlers["service"] = svc
    return svc


def _entity_to_response(entity: Any) -> dict[str, Any]:
    return {
        "id": str(entity.id),
        "name": entity.name,
        "connector_type": entity.connector_type,
        "status": entity.status.value if hasattr(entity.status, "value") else str(entity.status),
        "version": entity.version,
        "description": entity.description,
        "endpoint": entity.endpoint,
        "capabilities": [c.value if hasattr(c, "value") else c for c in entity.capabilities],
        "health_status": entity.health_status,
        "error_message": entity.error_message,
        "last_health_check": entity.last_health_check.isoformat() if entity.last_health_check else None,
        "created_at": entity.created_at.isoformat() if entity.created_at else "",
    }


from pydantic import BaseModel


class RegisterConnectorRequest(BaseModel):
    connector_type: str
    name: str = ""
    description: Optional[str] = None
    version: str = "1.0"
    endpoint: Optional[str] = None
    auth_type: Optional[str] = None
    config: Optional[dict[str, Any]] = None


class ExecuteCapabilityRequest(BaseModel):
    capability: str
    inputs: dict[str, Any] = {}
    timeout_seconds: Optional[int] = None


@router.post("/register", response_model=dict[str, Any])
async def register_connector(req: RegisterConnectorRequest):
    from backend.connector.adapter.interfaces import ConnectorAdapter
    from backend.connector.models import ConnectorConfig

    class _InlineAdapter(ConnectorAdapter):
        @property
        def connector_type(self) -> str:
            return req.connector_type

        @property
        def connector_name(self) -> str:
            return req.name or req.connector_type

        @property
        def adapter_version(self) -> str:
            return req.version

        async def initialize(self) -> bool:
            return True

        async def health_check(self) -> Any:
            from backend.connector.adapter.interfaces import AdapterHealthStatus
            return AdapterHealthStatus.HEALTHY

        async def capabilities(self) -> list[Any]:
            from backend.connector.models import Capability
            return [Capability.EXECUTE]

        async def execute(self, capability: Any, inputs: dict[str, Any],
                          timeout_seconds: Optional[int] = None) -> Any:
            from backend.connector.adapter.interfaces import AdapterResult
            return AdapterResult(success=True, outputs={"message": f"Executed {capability.value}"})

        async def shutdown(self) -> None:
            pass

    svc = _get_service()
    config = ConnectorConfig(
        connector_type=req.connector_type,
        name=req.name,
        description=req.description,
        version=req.version,
        endpoint=req.endpoint,
        auth_type=req.auth_type,
        config=req.config,
    )
    entity = await svc.register_connector(_InlineAdapter(), config=config, actor="api")
    return _entity_to_response(entity)


@router.get("", response_model=list[dict[str, Any]])
async def list_connectors(
    capability: Optional[str] = Query(None),
):
    svc = _get_service()
    if capability:
        from backend.connector.models import Capability
        try:
            cap = Capability(capability)
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid capability: {capability}")
        entities = await svc.list_by_capability(cap)
    else:
        entities = await svc.list_connectors()
    return [_entity_to_response(e) for e in entities]


@router.get("/{connector_type}", response_model=dict[str, Any])
async def get_connector(connector_type: str):
    svc = _get_service()
    entity = await svc.get_connector(connector_type)
    if not entity:
        raise HTTPException(status_code=404, detail=f"Connector {connector_type} not found")
    return _entity_to_response(entity)


@router.post("/{connector_type}/enable", response_model=dict[str, Any])
async def enable_connector(connector_type: str):
    svc = _get_service()
    try:
        entity = await svc.enable_connector(connector_type, actor="api")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    if not entity:
        raise HTTPException(status_code=404, detail=f"Connector {connector_type} not found")
    return _entity_to_response(entity)


@router.post("/{connector_type}/disable", response_model=dict[str, Any])
async def disable_connector(connector_type: str):
    svc = _get_service()
    try:
        entity = await svc.disable_connector(connector_type, actor="api")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    if not entity:
        raise HTTPException(status_code=404, detail=f"Connector {connector_type} not found")
    return _entity_to_response(entity)


@router.delete("/{connector_type}", response_model=dict[str, Any])
async def delete_connector(connector_type: str):
    svc = _get_service()
    success = await svc.remove_connector(connector_type, actor="api")
    if not success:
        raise HTTPException(status_code=404, detail=f"Connector {connector_type} not found")
    return {"success": True, "connector_type": connector_type}


@router.get("/{connector_type}/health", response_model=dict[str, Any])
async def connector_health(connector_type: str):
    svc = _get_service()
    result = await svc.health_check(connector_type)
    if result.get("error") == "Not found":
        raise HTTPException(status_code=404, detail=f"Connector {connector_type} not found")
    return result


@router.get("/{connector_type}/capabilities", response_model=list[str])
async def connector_capabilities(connector_type: str):
    svc = _get_service()
    caps = await svc.capabilities(connector_type)
    if not caps and not await svc.get_connector(connector_type):
        raise HTTPException(status_code=404, detail=f"Connector {connector_type} not found")
    return [c.value if hasattr(c, "value") else c for c in caps]


@router.post("/{connector_type}/execute", response_model=dict[str, Any])
async def execute_capability(connector_type: str, req: ExecuteCapabilityRequest):
    from backend.connector.models import Capability
    try:
        cap = Capability(req.capability)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid capability: {req.capability}")

    svc = _get_service()
    try:
        result = await svc.execute_capability(
            connector_type=connector_type,
            capability=cap,
            inputs=req.inputs,
            timeout_seconds=req.timeout_seconds,
            actor="api",
        )
        return result
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

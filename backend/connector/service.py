from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Optional

try:
    from backend.database.repositories.factory import RepositoryFactory
    from backend.database.repositories.factory import repo_factory as _repo_factory
except ImportError:
    _repo_factory = None
from backend.connector.adapter.interfaces import AdapterHealthStatus, ConnectorAdapter
from backend.connector.capabilities import Capability, CapabilitySet, capability_catalog
from backend.connector.events import ConnectorEvent, ConnectorEventPublisher, connector_event_publisher
from backend.connector.models import ConnectorConfig, ConnectorEntity, ConnectorMetadata, ConnectorStatus
from backend.connector.registry import ConnectorRegistry, connector_registry
from backend.connector.state_machine import is_terminal, is_valid_transition, validate_transition
from backend.database.repositories.connectors import ConnectorConfigModel

log = logging.getLogger(__name__)


class ConnectorService:
    def __init__(
        self,
        registry: Optional[ConnectorRegistry] = None,
        events: Optional[ConnectorEventPublisher] = None,
        repo_factory: Optional[RepositoryFactory] = None,
    ) -> None:
        self._registry = registry or connector_registry
        self._events = events or connector_event_publisher
        self._repo_factory = repo_factory or _repo_factory or RepositoryFactory()
        self._capability_sets: dict[str, CapabilitySet] = {}

    # ------------------------------------------------------------------
    # Register
    # ------------------------------------------------------------------

    async def register_connector(
        self,
        adapter: ConnectorAdapter,
        config: Optional[ConnectorConfig] = None,
        actor: Optional[str] = None,
    ) -> ConnectorEntity:
        connector_id = uuid.uuid4()
        datetime.now(timezone.utc)

        cfg = config or ConnectorConfig(connector_type=adapter.connector_type)

        model = ConnectorConfigModel(
            id=connector_id,
            name=cfg.name or adapter.connector_name,
            connector_type=cfg.connector_type,
            description=cfg.description,
            version=cfg.version,
            endpoint=cfg.endpoint,
            auth_type=cfg.auth_type,
            config=cfg.config,
            metadata_=cfg.metadata,
            status=ConnectorStatus.REGISTERED.value,
        )
        repo = await self._repo_factory.connector_config_repo()
        model = await repo.create(model)

        self._registry.register(adapter)
        caps = await adapter.capabilities()
        capability_catalog.register(adapter.connector_type, caps)

        cs = CapabilitySet()
        cs.add_multiple(caps)
        self._capability_sets[adapter.connector_type] = cs

        entity = self._model_to_entity(model, caps, status=ConnectorStatus.REGISTERED)

        await self._publish_event(entity, "connector.registered",
                                   to_status="REGISTERED", actor=actor)
        return entity

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def initialize_connector(self, connector_type: str, actor: Optional[str] = None) -> Optional[ConnectorEntity]:
        entity = await self._get_entity(connector_type)
        if not entity:
            return None
        if not is_valid_transition(entity.status, ConnectorStatus.INITIALIZING):
            raise ValueError(f"Cannot initialize connector in status {entity.status.value}")

        await self._transition(entity, ConnectorStatus.INITIALIZING, actor)
        await self._publish_event(entity, "connector.initializing",
                                   to_status="INITIALIZING", actor=actor)

        adapter = self._registry.get(connector_type)
        if not adapter:
            entity = await self._transition(entity, ConnectorStatus.FAILED, actor)
            entity.error_message = f"No adapter for connector type {connector_type}"
            await self._publish_event(entity, "connector.failed",
                                       to_status="FAILED", actor=actor,
                                       payload={"error": entity.error_message})
            return entity

        try:
            success = await adapter.initialize()
            if success:
                entity = await self._transition(entity, ConnectorStatus.READY, actor)
                await self._publish_event(entity, "connector.ready",
                                           to_status="READY", actor=actor)
            else:
                entity = await self._transition(entity, ConnectorStatus.FAILED, actor)
                entity.error_message = f"Adapter {connector_type} initialize returned False"
                await self._publish_event(entity, "connector.failed",
                                           to_status="FAILED", actor=actor,
                                           payload={"error": entity.error_message})
        except Exception as exc:
            entity = await self._transition(entity, ConnectorStatus.FAILED, actor)
            entity.error_message = str(exc)
            await self._publish_event(entity, "connector.failed",
                                       to_status="FAILED", actor=actor,
                                       payload={"error": str(exc)})

        return entity

    async def disable_connector(self, connector_type: str, actor: Optional[str] = None) -> Optional[ConnectorEntity]:
        entity = await self._get_entity(connector_type)
        if not entity:
            return None
        if not is_valid_transition(entity.status, ConnectorStatus.DISABLED):
            raise ValueError(f"Cannot disable connector in status {entity.status.value}")

        await self._transition(entity, ConnectorStatus.DISABLED, actor)
        await self._publish_event(entity, "connector.disabled",
                                   to_status="DISABLED", actor=actor)
        return entity

    async def enable_connector(self, connector_type: str, actor: Optional[str] = None) -> Optional[ConnectorEntity]:
        entity = await self._get_entity(connector_type)
        if not entity:
            return None
        if not is_valid_transition(entity.status, ConnectorStatus.REGISTERED):
            raise ValueError(f"Cannot enable connector in status {entity.status.value}")

        await self._transition(entity, ConnectorStatus.REGISTERED, actor)
        await self._publish_event(entity, "connector.enabled",
                                   to_status="REGISTERED", actor=actor)
        return entity

    async def remove_connector(self, connector_type: str, actor: Optional[str] = None) -> bool:
        repo = await self._repo_factory.connector_config_repo()
        models = await repo.list_by_type(connector_type)
        for model in models:
            await repo.delete(model.id)

        self._registry.unregister(connector_type)
        capability_catalog.unregister(connector_type)
        self._capability_sets.pop(connector_type, None)

        await self._events.publish(ConnectorEvent(
            connector_type=connector_type,
            event_type="connector.removed",
            actor=actor,
            message=f"Connector {connector_type} removed",
        ))
        return True

    # ------------------------------------------------------------------
    # Read / Query
    # ------------------------------------------------------------------

    async def get_connector(self, connector_type: str) -> Optional[ConnectorEntity]:
        return await self._get_entity(connector_type)

    async def list_connectors(self) -> list[ConnectorEntity]:
        repo = await self._repo_factory.connector_config_repo()
        models = await repo.list()
        result: list[ConnectorEntity] = []
        for model in models:
            caps = self._capability_sets.get(model.connector_type, CapabilitySet()).list()
            status = ConnectorStatus(model.status) if model.status else ConnectorStatus.REGISTERED
            result.append(self._model_to_entity(model, caps, status=status))
        return result

    async def list_by_capability(self, capability: Capability) -> list[ConnectorEntity]:
        connector_types = capability_catalog.find_by_capability(capability)
        entities: list[ConnectorEntity] = []
        for ct in connector_types:
            entity = await self._get_entity(ct)
            if entity:
                entities.append(entity)
        return entities

    async def health_check(self, connector_type: str) -> dict[str, Any]:
        entity = await self._get_entity(connector_type)
        if not entity:
            return {"connector_type": connector_type, "status": "unknown", "error": "Not found"}

        adapter = self._registry.get(connector_type)
        if not adapter:
            return {"connector_type": connector_type, "status": entity.health_status, "error": "No adapter"}

        try:
            health = await adapter.health_check()
            entity.health_status = health.value
            entity.last_health_check = datetime.now(timezone.utc)

            if health == AdapterHealthStatus.UNHEALTHY and not is_terminal(entity.status):
                if is_valid_transition(entity.status, ConnectorStatus.UNAVAILABLE):
                    await self._transition(entity, ConnectorStatus.UNAVAILABLE, "system")
            elif health == AdapterHealthStatus.DEGRADED and not is_terminal(entity.status):
                if is_valid_transition(entity.status, ConnectorStatus.DEGRADED):
                    await self._transition(entity, ConnectorStatus.DEGRADED, "system")

            return {
                "connector_type": connector_type,
                "status": health.value,
                "connector_status": entity.status.value,
                "last_check": entity.last_health_check.isoformat(),
            }
        except Exception as exc:
            return {
                "connector_type": connector_type,
                "status": "error",
                "error": str(exc),
            }

    async def capabilities(self, connector_type: str) -> list[Capability]:
        cs = self._capability_sets.get(connector_type)
        if cs:
            return cs.list()
        entity = await self._get_entity(connector_type)
        if not entity:
            return []
        return entity.capabilities

    async def execute_capability(
        self,
        connector_type: str,
        capability: Capability,
        inputs: dict[str, Any],
        timeout_seconds: Optional[int] = None,
        actor: Optional[str] = None,
    ) -> dict[str, Any]:
        entity = await self._get_entity(connector_type)
        if not entity:
            raise ValueError(f"Connector {connector_type} not found")
        if entity.status in (ConnectorStatus.DISABLED, ConnectorStatus.FAILED):
            raise ValueError(f"Connector {connector_type} is {entity.status.value}")

        adapter = self._registry.get(connector_type)
        if not adapter:
            raise ValueError(f"No adapter for connector type {connector_type}")

        cs = self._capability_sets.get(connector_type, CapabilitySet())
        if not cs.has(capability):
            raise ValueError(f"Connector {connector_type} does not support capability {capability.value}")

        await self._publish_event(entity, "connector.capability_executing",
                                   to_status=entity.status.value, actor=actor,
                                   payload={"capability": capability.value, "inputs": inputs})

        try:
            result = await adapter.execute(capability, inputs, timeout_seconds=timeout_seconds)
            await self._publish_event(entity, "connector.capability_executed",
                                       to_status=entity.status.value, actor=actor,
                                       payload={
                                           "capability": capability.value,
                                           "success": result.success,
                                           "duration_ms": result.duration_ms,
                                       })
            return {
                "success": result.success,
                "outputs": result.outputs,
                "error": result.error,
                "duration_ms": result.duration_ms,
            }
        except Exception as exc:
            await self._publish_event(entity, "connector.capability_executed",
                                       to_status=entity.status.value, actor=actor,
                                       payload={"capability": capability.value, "success": False, "error": str(exc)})
            raise

    async def get_adapter(self, connector_type: str) -> Optional[ConnectorAdapter]:
        return self._registry.get(connector_type)

    async def run_health_checks(self) -> dict[str, Any]:
        results: dict[str, Any] = {}
        for ctype in list(self._registry._adapters.keys()):
            results[ctype] = await self.health_check(ctype)
        return results

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    async def _get_entity(self, connector_type: str) -> Optional[ConnectorEntity]:
        repo = await self._repo_factory.connector_config_repo()
        models = await repo.list_by_type(connector_type)
        if not models:
            return None
        model = models[0]
        caps = self._capability_sets.get(connector_type, CapabilitySet()).list()
        status = ConnectorStatus(model.status) if model.status else ConnectorStatus.REGISTERED
        return self._model_to_entity(model, caps, status=status)

    async def _transition(self, entity: ConnectorEntity, target: ConnectorStatus,
                           actor: Optional[str] = None) -> ConnectorEntity:
        validate_transition(entity.status, target)
        entity.status = target
        repo = await self._repo_factory.connector_config_repo()
        models = await repo.list_by_type(entity.connector_type)
        if models:
            model = models[0]
            model.status = target.value
            await repo.update(model)
        return entity

    async def _publish_event(self, entity: ConnectorEntity, event_type: str,
                              from_status: Optional[str] = None,
                              to_status: Optional[str] = None,
                              actor: Optional[str] = None,
                              payload: Optional[dict[str, Any]] = None) -> None:
        await self._events.publish(ConnectorEvent(
            connector_type=entity.connector_type,
            connector_name=entity.name,
            event_type=event_type,
            correlation_id=entity.metadata.correlation_id,
            from_status=from_status or entity.status.value,
            to_status=to_status or entity.status.value,
            actor=actor,
            payload=payload or {},
        ))

    def _model_to_entity(self, model: ConnectorConfigModel,
                          capabilities: list[Capability],
                          status: ConnectorStatus = ConnectorStatus.REGISTERED) -> ConnectorEntity:
        return ConnectorEntity(
            id=model.id,
            name=model.name,
            connector_type=model.connector_type,
            status=status,
            version=model.version or "1.0",
            description=model.description,
            endpoint=model.endpoint,
            capabilities=capabilities,
            metadata=ConnectorMetadata(
                tags=[],
                source="api",
            ),
            created_at=model.created_at,
        )

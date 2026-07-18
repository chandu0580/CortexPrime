from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional


class ConnectorStatus(str, Enum):
    REGISTERED = "REGISTERED"
    INITIALIZING = "INITIALIZING"
    READY = "READY"
    DEGRADED = "DEGRADED"
    UNAVAILABLE = "UNAVAILABLE"
    UPDATING = "UPDATING"
    DISABLED = "DISABLED"
    FAILED = "FAILED"


class Capability(str, Enum):
    DEPLOY = "deploy"
    ROLLBACK = "rollback"
    OBSERVE = "observe"
    SCALE = "scale"
    RESTART = "restart"
    BUILD = "build"
    TEST = "test"
    NOTIFY = "notify"
    PROVISION = "provision"
    DESTROY = "destroy"
    SEARCH = "search"
    EXECUTE = "execute"
    CONFIGURE = "configure"


@dataclass
class ConnectorConfig:
    connector_type: str
    name: str = ""
    description: Optional[str] = None
    version: str = "1.0"
    endpoint: Optional[str] = None
    auth_type: Optional[str] = None
    config: Optional[dict[str, Any]] = None
    tags: list[str] = field(default_factory=list)
    metadata: Optional[dict[str, Any]] = None


@dataclass
class ConnectorMetadata:
    correlation_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    source: str = "api"
    tags: list[str] = field(default_factory=list)
    custom: dict[str, Any] = field(default_factory=dict)


@dataclass
class ConnectorEntity:
    id: uuid.UUID
    name: str
    connector_type: str
    status: ConnectorStatus
    version: str = "1.0"
    description: Optional[str] = None
    endpoint: Optional[str] = None
    capabilities: list[Capability] = field(default_factory=list)
    metadata: ConnectorMetadata = field(default_factory=ConnectorMetadata)
    health_status: str = "unknown"
    error_message: Optional[str] = None
    last_health_check: Optional[datetime] = None
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

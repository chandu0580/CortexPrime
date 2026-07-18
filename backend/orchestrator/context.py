from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, List


def _id(prefix: str = "id") -> str:
    return f"{prefix}-{uuid.uuid4().hex[:12]}"


@dataclass
class OrchestratorContext:
    tenant_id: str = ""
    user_id: str = ""
    session_id: str = ""
    mission_id: str = ""
    execution_id: str = ""
    trace_id: str = ""
    correlation_id: str = ""
    permissions: List[str] = field(default_factory=list)
    source: str = "orchestrator"
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.trace_id:
            self.trace_id = _id("trace")
        if not self.correlation_id:
            self.correlation_id = _id("corr")

    def to_headers(self) -> Dict[str, str]:
        return {
            "X-Tenant-ID": self.tenant_id,
            "X-User-ID": self.user_id,
            "X-Session-ID": self.session_id,
            "X-Mission-ID": self.mission_id,
            "X-Execution-ID": self.execution_id,
            "X-Trace-ID": self.trace_id,
            "X-Correlation-ID": self.correlation_id,
            "X-Source": self.source,
        }

    def to_dict(self) -> Dict[str, Any]:
        return {
            "tenant_id": self.tenant_id,
            "user_id": self.user_id,
            "session_id": self.session_id,
            "mission_id": self.mission_id,
            "execution_id": self.execution_id,
            "trace_id": self.trace_id,
            "correlation_id": self.correlation_id,
            "permissions": list(self.permissions),
            "source": self.source,
        }

    def child(self, **overrides: Any) -> OrchestratorContext:
        kwargs: Dict[str, Any] = dict(
            tenant_id=self.tenant_id,
            user_id=self.user_id,
            session_id=self.session_id,
            mission_id=self.mission_id,
            execution_id=self.execution_id,
            trace_id=self.trace_id,
            correlation_id=self.correlation_id,
            permissions=list(self.permissions),
            source=self.source,
            metadata=dict(self.metadata),
        )
        kwargs.update(overrides)
        return OrchestratorContext(**kwargs)

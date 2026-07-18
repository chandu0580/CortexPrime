from __future__ import annotations

import uuid
from typing import Any, Optional

from backend.ai.models import AIContext, PlanStep, RuntimeTarget


class RuntimeContext:
    def __init__(
        self,
        tenant_id: str = "",
        user_id: str = "",
        session_id: str = "",
        mission_id: str = "",
        execution_id: str = "",
        trace_id: str = "",
        correlation_id: str = "",
        permissions: Optional[list[str]] = None,
        source: str = "ai_runtime",
        metadata: Optional[dict[str, Any]] = None,
    ) -> None:
        self.tenant_id = tenant_id
        self.user_id = user_id
        self.session_id = session_id
        self.mission_id = mission_id
        self.execution_id = execution_id
        self.trace_id = trace_id or _generate_id("trace")
        self.correlation_id = correlation_id or _generate_id("corr")
        self.permissions = permissions or []
        self.source = source
        self.metadata = metadata or {}

    def to_headers(self) -> dict[str, str]:
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

    def enrich_step_params(self, step: PlanStep) -> dict[str, Any]:
        params = dict(step.params)
        params.setdefault("_context", {})
        params["_context"].update({
            "tenant_id": self.tenant_id,
            "user_id": self.user_id,
            "mission_id": self.mission_id,
            "execution_id": self.execution_id,
            "trace_id": self.trace_id,
            "correlation_id": self.correlation_id,
            "permissions": self.permissions,
            "source": self.source,
        })
        return params

    def child_context(self, **overrides: Any) -> RuntimeContext:
        kwargs: dict[str, Any] = dict(
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
        return RuntimeContext(**kwargs)


class ContextPropagator:
    def build(self, ai_context: Optional[AIContext] = None) -> RuntimeContext:
        if not ai_context:
            return RuntimeContext()
        metadata = ai_context.metadata or {}
        return RuntimeContext(
            tenant_id=ai_context.tenant_id,
            user_id=ai_context.user_id,
            session_id=ai_context.session_id,
            mission_id=metadata.get("mission_id", ""),
            execution_id=metadata.get("execution_id", ""),
            permissions=metadata.get("permissions", []),
            source=ai_context.source,
            metadata=metadata,
        )

    def propagate(self, context: RuntimeContext, target: RuntimeTarget, step: PlanStep) -> dict[str, Any]:
        params = context.enrich_step_params(step)
        params["_runtime_target"] = target.value
        return params


def _generate_id(prefix: str = "id") -> str:
    return f"{prefix}-{uuid.uuid4().hex[:12]}"

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional

from backend.ai.models import RuntimeTarget


@dataclass
class RuntimeResult:
    runtime: RuntimeTarget
    step_id: str = ""
    status: str = "success"
    data: dict[str, Any] = field(default_factory=dict)
    error: Optional[str] = None
    duration_ms: float = 0.0
    correlation_id: str = ""
    trace: list[dict[str, Any]] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    @property
    def is_success(self) -> bool:
        return self.status == "success"

    @property
    def is_failure(self) -> bool:
        return self.status in ("failed", "cancelled")

    @property
    def is_partial(self) -> bool:
        return self.status == "partial"

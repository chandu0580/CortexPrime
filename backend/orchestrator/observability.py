from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

log = logging.getLogger(__name__)


@dataclass
class StageMetrics:
    stage: str = ""
    runtime_invoked: str = ""
    connector_invoked: str = ""
    duration_seconds: float = 0.0
    success: bool = False
    artifacts_produced: int = 0
    errors: List[str] = field(default_factory=list)
    decision_rationale: str = ""
    timestamp: str = ""


class MetricsCollector:
    def __init__(self) -> None:
        self._metrics: Dict[str, Dict[str, StageMetrics]] = {}

    def record(
        self,
        mission_id: str,
        stage: str,
        runtime_invoked: str = "",
        connector_invoked: str = "",
        duration_seconds: float = 0.0,
        success: bool = False,
        artifacts_produced: int = 0,
        error: str = "",
        decision_rationale: str = "",
    ) -> StageMetrics:
        m = StageMetrics(
            stage=stage,
            runtime_invoked=runtime_invoked,
            connector_invoked=connector_invoked,
            duration_seconds=duration_seconds,
            success=success,
            artifacts_produced=artifacts_produced,
            errors=[error] if error else [],
            decision_rationale=decision_rationale,
            timestamp=datetime.now(timezone.utc).isoformat(),
        )
        self._metrics.setdefault(mission_id, {})[stage] = m
        return m

    def get_metrics(self, mission_id: str) -> Dict[str, StageMetrics]:
        return self._metrics.get(mission_id, {})

    def get_stage_metric(self, mission_id: str, stage: str) -> Optional[StageMetrics]:
        return self._metrics.get(mission_id, {}).get(stage)

    def clear_mission(self, mission_id: str) -> None:
        self._metrics.pop(mission_id, None)


metrics_collector = MetricsCollector()

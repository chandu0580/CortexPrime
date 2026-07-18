from __future__ import annotations

import logging
from typing import Dict, List, Optional

from backend.fleet.models import AgentHealth, FleetMetricsSnapshot

log = logging.getLogger(__name__)


class FleetHealthMonitor:
    def __init__(self):
        self._snapshots: Dict[str, FleetMetricsSnapshot] = {}

    def compute_snapshot(
        self,
        fleet_id: str,
        agents: List[Dict],
        mission_count: int = 0,
        error_rate: float = 0.0,
        avg_latency_ms: float = 0.0,
    ) -> FleetMetricsSnapshot:
        snapshot = FleetMetricsSnapshot(fleet_id)
        snapshot.total_agents = len(agents)
        snapshot.mission_count = mission_count
        snapshot.error_rate = error_rate
        snapshot.avg_latency_ms = avg_latency_ms

        for agent in agents:
            status = agent.get("status", AgentHealth.UNKNOWN.value)
            if status == AgentHealth.HEALTHY.value:
                snapshot.healthy_agents += 1
            elif status == AgentHealth.DEGRADED.value:
                snapshot.degraded_agents += 1
            elif status == AgentHealth.UNHEALTHY.value:
                snapshot.unhealthy_agents += 1

        self._snapshots[fleet_id] = snapshot
        return snapshot

    def get_snapshot(self, fleet_id: str) -> Optional[FleetMetricsSnapshot]:
        return self._snapshots.get(fleet_id)

    def get_fleet_health_status(self, fleet_id: str) -> str:
        snapshot = self._snapshots.get(fleet_id)
        if not snapshot:
            return "unknown"
        if snapshot.unhealthy_agents > 0:
            return "degraded" if snapshot.unhealthy_agents < snapshot.total_agents / 2 else "unhealthy"
        if snapshot.degraded_agents > 0:
            return "degraded"
        return "healthy"


fleet_health_monitor = FleetHealthMonitor()

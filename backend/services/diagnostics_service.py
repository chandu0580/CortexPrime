from __future__ import annotations

import json
import logging
import os
import platform
import time
from datetime import datetime, timezone
from typing import Any, Dict, List
from uuid import uuid4

log = logging.getLogger(__name__)


class DiagnosticsService:
    async def generate_diagnostics(self) -> Dict[str, Any]:
        t0 = time.monotonic()

        diagnostics: Dict[str, Any] = {
            "diagnostics_id": str(uuid4()),
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "environment": self._get_environment_info(),
            "runtime_status": await self._get_runtime_status(),
            "connector_status": await self._get_connector_status(),
            "infrastructure": await self._get_infrastructure_status(),
            "configuration": self._get_configuration(),
            "mission_statistics": await self._get_mission_statistics(),
            "recent_failures": await self._get_recent_failures(),
            "performance_summary": await self._get_performance_summary(),
        }

        diagnostics["generation_time_ms"] = round((time.monotonic() - t0) * 1000, 1)
        return diagnostics

    def _get_environment_info(self) -> Dict[str, Any]:
        return {
            "python_version": platform.python_version(),
            "platform": platform.platform(),
            "hostname": platform.node(),
            "env": os.getenv("ENV", "development"),
            "version": os.getenv("BUILD_HASH", "1.0.0-rc.1"),
        }

    async def _get_runtime_status(self) -> Dict[str, Any]:
        status: Dict[str, Any] = {}
        try:
            from backend.runtime.runtime_state import runtime_state as rs
            state = rs.get_state() if hasattr(rs, "get_state") else {}
            status["active_executions"] = len(state.get("active_executions", {}))
            status["completed_executions"] = len(state.get("completed_executions", {}))
        except Exception as exc:
            status["error"] = str(exc)[:200]

        try:
            from backend.runtime.agent_registry import agent_registry
            agents = agent_registry.list_agents() if hasattr(agent_registry, "list_agents") else []
            status["registered_agents"] = agents
        except Exception as exc:
            status["agent_error"] = str(exc)[:200]

        try:
            from backend.events.event_bus import event_bus
            event_count = len(event_bus.get_events()) if hasattr(event_bus, "get_events") else 0
            status["event_bus_size"] = event_count
        except Exception as exc:
            status["event_bus_error"] = str(exc)[:200]

        return status

    async def _get_connector_status(self) -> Dict[str, Any]:
        try:
            from backend.connectors.registry import connector_registry
            count = connector_registry.count() if hasattr(connector_registry, "count") else 0
            return {"connector_count": count, "available": True}
        except Exception as exc:
            return {"error": str(exc)[:200], "available": False}

    async def _get_infrastructure_status(self) -> Dict[str, Any]:
        infra: Dict[str, Any] = {}
        for name in ("redis", "neo4j", "rabbitmq"):
            try:
                if name == "redis":
                    from backend.infrastructure.redis.connection import redis_connection
                    infra[name] = {"available": redis_connection.is_available}
                elif name == "neo4j":
                    from backend.infrastructure.neo4j.connection import neo4j_connection
                    infra[name] = {"available": neo4j_connection.is_available}
                elif name == "rabbitmq":
                    from backend.infrastructure.rabbitmq.connection import rabbitmq_connection
                    infra[name] = {"available": rabbitmq_connection.is_available}
            except Exception as exc:
                infra[name] = {"error": str(exc)[:200]}

        try:
            from backend.database.health import check_database_health
            db_health = await check_database_health()
            infra["postgresql"] = db_health
        except Exception as exc:
            infra["postgresql"] = {"status": "unavailable", "error": str(exc)[:200]}

        return infra

    def _get_configuration(self) -> Dict[str, Any]:
        safe_keys = {
            "ENV": "ENV",
            "LOG_LEVEL": "LOG_LEVEL",
            "CORS_ORIGINS": "CORS_ORIGINS",
            "BACKUP_DIR": "BACKUP_DIR",
            "RATE_LIMIT_ENABLED": "RATE_LIMIT_ENABLED",
        }
        config: Dict[str, Any] = {}
        for key, env_var in safe_keys.items():
            val = os.getenv(env_var)
            if val:
                config[key] = val
        return config

    async def _get_mission_statistics(self) -> Dict[str, Any]:
        try:
            from backend.runtime.runtime_metrics import runtime_metrics
            metrics = runtime_metrics.export_metrics() if hasattr(runtime_metrics, "export_metrics") else {}
            return {
                "total": metrics.get("total_executions", 0),
                "completed": metrics.get("completed_executions", 0),
                "failed": metrics.get("failed_executions", 0),
            }
        except Exception as exc:
            return {"error": str(exc)[:200]}

    async def _get_recent_failures(self) -> List[Dict[str, Any]]:
        try:
            from backend.safety.audit_logger import audit_logger
            entries = audit_logger.get_recent(limit=20) if hasattr(audit_logger, "get_recent") else []
            failures = [e for e in entries if isinstance(e, dict) and e.get("outcome") == "failed"]
            return failures[:10]
        except Exception as exc:
            return [{"error": str(exc)[:200]}]

    async def _get_performance_summary(self) -> Dict[str, Any]:
        try:
            from backend.runtime.runtime_metrics import runtime_metrics
            metrics = runtime_metrics.export_metrics() if hasattr(runtime_metrics, "export_metrics") else {}
            return {
                "total_executions": metrics.get("total_executions", 0),
                "total_tokens": metrics.get("total_tokens", 0),
            }
        except Exception as exc:
            return {"error": str(exc)[:200]}

    def serialize_diagnostics(self, diagnostics: Dict[str, Any]) -> str:
        return json.dumps(diagnostics, default=str, indent=2)


diagnostics_service = DiagnosticsService()

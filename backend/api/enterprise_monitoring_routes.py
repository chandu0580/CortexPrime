"""
Enterprise Monitoring Routes — REST API for Autonomous Enterprise Monitoring.

Endpoints
---------
  GET    /api/monitoring/watchers       — watcher list + health
  GET    /api/monitoring/rules          — list monitoring rules
  POST   /api/monitoring/rules          — create a new rule
  PUT    /api/monitoring/rules/{id}     — update a rule
  DELETE /api/monitoring/rules/{id}     — delete a rule
  GET    /api/monitoring/events         — detected event history
  GET    /api/monitoring/missions       — auto-generated missions
  GET    /api/monitoring/statistics     — aggregated statistics
  GET    /api/monitoring/health         — overall monitoring health
  POST   /api/monitoring/poll           — trigger manual poll
"""
from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from fastapi import APIRouter, HTTPException, Query

from backend.events.enterprise_event_types import EnterpriseEventTypes as EET
from backend.services.autonomous_mission_generator import auto_mission_generator
from backend.services.enterprise_event_hub import enterprise_hub
from backend.services.enterprise_watchers import watcher_manager
from backend.services.monitoring_rules_engine import monitoring_rules

log = logging.getLogger(__name__)

router = APIRouter(prefix="/api/monitoring", tags=["Enterprise Monitoring"])


# ------------------------------------------------------------------
# Watchers
# ------------------------------------------------------------------

@router.get("/watchers")
async def list_watchers() -> Dict[str, Any]:
    """List all watchers with their current health."""
    health = await watcher_manager.health_all()
    watcher_list = [
        {
            "connector": ct,
            "running": info.get("running", False),
            "poll_interval": info.get("poll_interval", 120),
            "available": info.get("available", False),
            "status": info.get("status", "unknown"),
        }
        for ct, info in health.items()
    ]
    return {"watchers": watcher_list, "total": len(watcher_list)}


# ------------------------------------------------------------------
# Rules CRUD
# ------------------------------------------------------------------

@router.get("/rules")
async def list_rules() -> Dict[str, Any]:
    """List all monitoring rules."""
    rules = monitoring_rules.get_rules()
    return {
        "rules": [r.to_dict() for r in rules],
        "total": len(rules),
    }


@router.post("/rules")
async def create_rule(rule_data: Dict[str, Any]) -> Dict[str, Any]:
    """Create a new monitoring rule."""
    try:
        rule = monitoring_rules.add_rule(rule_data)
        await enterprise_hub.emit_monitoring_rule_event(
            event_type=EET.MONITORING_RULE_CREATED,
            rule_id=rule.rule_id,
            rule_name=rule.name,
        )
        return {"rule": rule.to_dict(), "status": "created"}
    except Exception as exc:
        log.error("Failed to create rule: %s", exc)
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.put("/rules/{rule_id}")
async def update_rule(rule_id: str, rule_data: Dict[str, Any]) -> Dict[str, Any]:
    """Update an existing monitoring rule."""
    rule = monitoring_rules.update_rule(rule_id, rule_data)
    if not rule:
        raise HTTPException(status_code=404, detail=f"Rule {rule_id} not found")
    await enterprise_hub.emit_monitoring_rule_event(
        event_type=EET.MONITORING_RULE_UPDATED,
        rule_id=rule.rule_id,
        rule_name=rule.name,
    )
    return {"rule": rule.to_dict(), "status": "updated"}


@router.delete("/rules/{rule_id}")
async def delete_rule(rule_id: str) -> Dict[str, Any]:
    """Delete a monitoring rule."""
    deleted = monitoring_rules.delete_rule(rule_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Rule {rule_id} not found")
    return {"status": "deleted", "rule_id": rule_id}


# ------------------------------------------------------------------
# Events
# ------------------------------------------------------------------

@router.get("/events")
async def list_events(
    limit: int = Query(100, ge=1, le=500),
    connector: Optional[str] = None,
    severity: Optional[str] = None,
) -> Dict[str, Any]:
    """Get detected event history."""
    events = monitoring_rules.get_events(limit=limit, connector=connector, severity=severity)
    return {"events": events, "total": len(events)}


# ------------------------------------------------------------------
# Missions
# ------------------------------------------------------------------

@router.get("/missions")
async def list_auto_missions(
    limit: int = Query(50, ge=1, le=200),
    connector: Optional[str] = None,
) -> Dict[str, Any]:
    """Get auto-generated missions."""
    missions = auto_mission_generator.get_missions(limit=limit, connector=connector)
    return {"missions": missions, "total": len(missions)}


# ------------------------------------------------------------------
# Statistics
# ------------------------------------------------------------------

@router.get("/statistics")
async def get_monitoring_statistics() -> Dict[str, Any]:
    """Get aggregated monitoring statistics."""
    rule_stats = monitoring_rules.get_statistics()
    mission_stats = auto_mission_generator.get_mission_statistics()
    return {
        **rule_stats,
        **mission_stats,
    }


# ------------------------------------------------------------------
# Health
# ------------------------------------------------------------------

@router.get("/health")
async def get_monitoring_health() -> Dict[str, Any]:
    """Get overall monitoring subsystem health."""
    watcher_health = await watcher_manager.health_all()
    available_watchers = sum(
        1 for v in watcher_health.values() if v.get("available")
    )
    return {
        "status": "healthy" if available_watchers > 0 else "degraded",
        "watchers_available": available_watchers,
        "watchers_total": len(watcher_health),
        "rules_enabled": sum(1 for r in monitoring_rules.get_rules() if r.enabled),
        "rules_total": len(monitoring_rules.get_rules()),
        "auto_generated_missions": auto_mission_generator.get_mission_statistics().get("total_missions", 0),
        "watcher_health": watcher_health,
    }


# ------------------------------------------------------------------
# Manual poll trigger
# ------------------------------------------------------------------

@router.post("/poll")
async def trigger_poll(
    connector: Optional[str] = None,
) -> Dict[str, Any]:
    """Trigger a manual poll of watchers."""
    try:
        events = await watcher_manager.poll_once(connector_type=connector)
        # Evaluate each detected event against rules
        matched_count = 0
        mission_count = 0
        for event in events:
            monitoring_rules.record_event(event)
            matching_rules = await monitoring_rules.evaluate_event(event)
            for rule in matching_rules:
                matched_count += 1
                if rule.auto_create_mission:
                    result = await auto_mission_generator.create_mission(rule, event)
                    if result:
                        mission_count += 1

        return {
            "status": "completed",
            "events_detected": len(events),
            "rules_matched": matched_count,
            "missions_created": mission_count,
        }
    except Exception as exc:
        log.error("Manual poll failed: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc)) from exc

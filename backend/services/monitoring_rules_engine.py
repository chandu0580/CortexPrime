"""
Monitoring Rules Engine — evaluates watcher-detected events against configured rules.

Each rule specifies:
  - connector type to match
  - event type to match
  - severity threshold
  - optional conditions (dict of field → value)
  - whether to auto-create a mission
  - which mission template to use
  - notification targets

Rules are persisted as JSON on the filesystem (no new DB dependencies).
"""
from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

log = logging.getLogger(__name__)

# Default rules file location
_RULES_DIR = Path(__file__).resolve().parent.parent / "data"
_RULES_FILE = _RULES_DIR / "monitoring_rules.json"


# ---------------------------------------------------------------------------
# Rule model
# ---------------------------------------------------------------------------

class MonitoringRule:
    """A single monitoring rule configuration."""

    def __init__(
        self,
        rule_id: Optional[str] = None,
        name: str = "",
        description: str = "",
        connector: str = "",
        event_type: str = "",
        severity: str = "medium",
        conditions: Optional[Dict[str, Any]] = None,
        enabled: bool = True,
        business_hours: Optional[Dict[str, Any]] = None,
        cooldown_seconds: int = 300,
        retry_policy: Optional[Dict[str, Any]] = None,
        auto_create_mission: bool = True,
        mission_template: str = "incident_response",
        requires_approval: bool = False,
        notification_targets: Optional[List[str]] = None,
        created_at: Optional[str] = None,
        updated_at: Optional[str] = None,
    ) -> None:
        now = datetime.now(timezone.utc).isoformat()
        self.rule_id = rule_id or str(uuid.uuid4())
        self.name = name
        self.description = description
        self.connector = connector
        self.event_type = event_type
        self.severity = severity
        self.conditions = conditions or {}
        self.enabled = enabled
        self.business_hours = business_hours
        self.cooldown_seconds = cooldown_seconds
        self.retry_policy = retry_policy or {"max_retries": 3, "backoff": "linear"}
        self.auto_create_mission = auto_create_mission
        self.mission_template = mission_template
        self.requires_approval = requires_approval
        self.notification_targets = notification_targets or []
        self.created_at = created_at or now
        self.updated_at = updated_at or now

        # Track last matched timestamps per event signature for cooldown
        self._last_matched: Dict[str, str] = {}

    def matches(self, event: Dict[str, Any]) -> bool:
        """Check if a detected event matches this rule."""
        if not self.enabled:
            return False
        if self.connector and event.get("connector_type") != self.connector:
            return False
        if self.event_type and event.get("event_type") != self.event_type:
            return False
        if self.severity:
            severity_order = {"low": 0, "medium": 1, "high": 2, "critical": 3}
            event_sev = severity_order.get(event.get("severity", "low"), 0)
            rule_sev = severity_order.get(self.severity, 1)
            if event_sev < rule_sev:
                return False

        # Check custom conditions
        for key, expected in self.conditions.items():
            actual = event.get("metadata", {}).get(key) or event.get(key)
            if actual != expected:
                return False

        return True

    def is_on_cooldown(self, event: Dict[str, Any]) -> bool:
        """Check if this rule is in cooldown for a given event signature."""
        sig = self._event_signature(event)
        last = self._last_matched.get(sig)
        if not last:
            return False
        try:
            elapsed = (
                datetime.now(timezone.utc) - datetime.fromisoformat(last)
            ).total_seconds()
            return elapsed < self.cooldown_seconds
        except (ValueError, TypeError):
            return False

    def mark_matched(self, event: Dict[str, Any]) -> None:
        """Record the match timestamp for cooldown tracking."""
        sig = self._event_signature(event)
        self._last_matched[sig] = datetime.now(timezone.utc).isoformat()

    @staticmethod
    def _event_signature(event: Dict[str, Any]) -> str:
        """Create a stable signature for cooldown deduplication."""
        return f"{event.get('connector_type', '?')}:{event.get('event_type', '?')}:{event.get('title', '?')}"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "rule_id": self.rule_id,
            "name": self.name,
            "description": self.description,
            "connector": self.connector,
            "event_type": self.event_type,
            "severity": self.severity,
            "conditions": self.conditions,
            "enabled": self.enabled,
            "business_hours": self.business_hours,
            "cooldown_seconds": self.cooldown_seconds,
            "retry_policy": self.retry_policy,
            "auto_create_mission": self.auto_create_mission,
            "mission_template": self.mission_template,
            "requires_approval": self.requires_approval,
            "notification_targets": self.notification_targets,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "MonitoringRule":
        return cls(**{k: v for k, v in data.items() if k != "_last_matched"})


# ---------------------------------------------------------------------------
# Default rules
# ---------------------------------------------------------------------------

_DEFAULT_RULES: List[Dict[str, Any]] = [
    {
        "name": "GitHub Pipeline Failure",
        "description": "Auto-create incident when a GitHub pipeline fails",
        "connector": "github",
        "event_type": "pipeline_failure",
        "severity": "critical",
        "auto_create_mission": True,
        "mission_template": "incident_response",
    },
    {
        "name": "Jira Critical Issue",
        "description": "Auto-create bug triage when a critical Jira issue is detected",
        "connector": "jira",
        "event_type": "critical_issue",
        "severity": "critical",
        "auto_create_mission": True,
        "mission_template": "bug_triage",
    },
    {
        "name": "ServiceNow P1 Incident",
        "description": "Auto-create incident response for P1 ServiceNow incidents",
        "connector": "servicenow",
        "event_type": "p1_incident",
        "severity": "critical",
        "auto_create_mission": True,
        "mission_template": "incident_response",
    },
    {
        "name": "Azure Pipeline Failure",
        "description": "Auto-create incident when an Azure DevOps pipeline fails",
        "connector": "azure_devops",
        "event_type": "pipeline_failure",
        "severity": "critical",
        "auto_create_mission": True,
        "mission_template": "incident_response",
    },
    {
        "name": "Slack Alert Message",
        "description": "Alert when critical keywords appear in Slack",
        "connector": "slack",
        "event_type": "alert_message",
        "severity": "high",
        "auto_create_mission": True,
        "mission_template": "incident_response",
    },
    {
        "name": "Teams Alert Message",
        "description": "Alert when critical keywords appear in Teams",
        "connector": "teams",
        "event_type": "alert_message",
        "severity": "high",
        "auto_create_mission": True,
        "mission_template": "incident_response",
    },
    {
        "name": "ServiceNow P2 Incident",
        "description": "Track high-severity ServiceNow incidents",
        "connector": "servicenow",
        "event_type": "high_incident",
        "severity": "high",
        "auto_create_mission": True,
        "mission_template": "incident_response",
    },
    {
        "name": "Azure Critical Work Item",
        "description": "Track critical Azure DevOps work items",
        "connector": "azure_devops",
        "event_type": "critical_work_item",
        "severity": "high",
        "auto_create_mission": True,
        "mission_template": "bug_triage",
    },
]


# ---------------------------------------------------------------------------
# Rules Engine
# ---------------------------------------------------------------------------

class MonitoringRulesEngine:
    """Evaluates events against configured monitoring rules."""

    def __init__(self) -> None:
        self._rules: Dict[str, MonitoringRule] = {}
        self._initialized = False
        self._detected_events: List[Dict[str, Any]] = []

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def initialize(self) -> None:
        """Load rules from persistent storage."""
        if self._initialized:
            return
        self._load_rules()
        self._initialized = True
        log.info("MonitoringRulesEngine initialized — %d rule(s) loaded", len(self._rules))

    async def shutdown(self) -> None:
        """Persist rules and shut down."""
        self._save_rules()
        self._initialized = False
        log.info("MonitoringRulesEngine shutdown")

    # ------------------------------------------------------------------
    # Rule CRUD
    # ------------------------------------------------------------------

    def get_rules(self) -> List[MonitoringRule]:
        return list(self._rules.values())

    def get_rule(self, rule_id: str) -> Optional[MonitoringRule]:
        return self._rules.get(rule_id)

    def add_rule(self, rule_data: Dict[str, Any]) -> MonitoringRule:
        rule = MonitoringRule(**rule_data)
        self._rules[rule.rule_id] = rule
        self._save_rules()
        return rule

    def update_rule(self, rule_id: str, rule_data: Dict[str, Any]) -> Optional[MonitoringRule]:
        existing = self._rules.get(rule_id)
        if not existing:
            return None
        rule_data["rule_id"] = rule_id
        rule_data["updated_at"] = datetime.now(timezone.utc).isoformat()
        rule_data.setdefault("created_at", existing.created_at)
        rule = MonitoringRule(**rule_data)
        self._rules[rule_id] = rule
        self._save_rules()
        return rule

    def delete_rule(self, rule_id: str) -> bool:
        if rule_id in self._rules:
            del self._rules[rule_id]
            self._save_rules()
            return True
        return False

    # ------------------------------------------------------------------
    # Event evaluation
    # ------------------------------------------------------------------

    async def evaluate_event(self, event: Dict[str, Any]) -> List[MonitoringRule]:
        """Evaluate a detected event against all enabled rules. Returns matching rules."""
        matching: List[MonitoringRule] = []
        for rule in self._rules.values():
            if not rule.enabled:
                continue
            if not rule.matches(event):
                continue
            if rule.is_on_cooldown(event):
                log.debug("Rule '%s' in cooldown for event: %s", rule.name, event.get("title"))
                continue

            rule.mark_matched(event)
            matching.append(rule)

        if matching:
            log.info("Event matched %d rule(s): %s", len(matching), event.get("title"))

        return matching

    # ------------------------------------------------------------------
    # Event history
    # ------------------------------------------------------------------

    def record_event(self, event: Dict[str, Any]) -> None:
        """Record a detected event for history."""
        self._detected_events.append({
            **event,
            "recorded_at": datetime.now(timezone.utc).isoformat(),
        })
        if len(self._detected_events) > 1000:
            self._detected_events = self._detected_events[-1000:]

    def get_events(
        self,
        limit: int = 100,
        connector: Optional[str] = None,
        severity: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Get recorded events with optional filtering."""
        events = list(self._detected_events)
        if connector:
            events = [e for e in events if e.get("connector_type") == connector]
        if severity:
            events = [e for e in events if e.get("severity") == severity]
        events.reverse()
        return events[:limit]

    def clear_events(self) -> None:
        """Clear event history."""
        self._detected_events.clear()

    # ------------------------------------------------------------------
    # Statistics
    # ------------------------------------------------------------------

    def get_statistics(self) -> Dict[str, Any]:
        """Return aggregated statistics for the monitoring dashboard."""
        total_events = len(self._detected_events)
        by_severity: Dict[str, int] = {}
        by_connector: Dict[str, int] = {}
        for ev in self._detected_events:
            sev = ev.get("severity", "unknown")
            by_severity[sev] = by_severity.get(sev, 0) + 1
            conn = ev.get("connector_type", "unknown")
            by_connector[conn] = by_connector.get(conn, 0) + 1

        return {
            "total_events": total_events,
            "total_rules": len(self._rules),
            "enabled_rules": sum(1 for r in self._rules.values() if r.enabled),
            "auto_mission_rules": sum(1 for r in self._rules.values() if r.auto_create_mission),
            "events_by_severity": by_severity,
            "events_by_connector": by_connector,
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------

    def _load_rules(self) -> None:
        """Load rules from JSON file, falling back to defaults."""
        try:
            if _RULES_FILE.exists():
                data = json.loads(_RULES_FILE.read_text(encoding="utf-8"))
                rules_list = data if isinstance(data, list) else data.get("rules", [])
                for r_data in rules_list:
                    rule = MonitoringRule.from_dict(r_data)
                    self._rules[rule.rule_id] = rule
                log.info("Loaded %d rule(s) from %s", len(self._rules), _RULES_FILE)
                return
        except Exception as exc:
            log.warning("Failed to load rules from %s: %s", _RULES_FILE, exc)

        # Fall back to defaults
        for r_data in _DEFAULT_RULES:
            rule = MonitoringRule(**r_data)
            self._rules[rule.rule_id] = rule
        log.info("Loaded %d default rule(s)", len(self._rules))
        self._save_rules()

    def _save_rules(self) -> None:
        """Persist rules to JSON file."""
        try:
            _RULES_DIR.mkdir(parents=True, exist_ok=True)
            rules_list = [r.to_dict() for r in self._rules.values()]
            _RULES_FILE.write_text(
                json.dumps(rules_list, indent=2, default=str),
                encoding="utf-8",
            )
        except Exception as exc:
            log.warning("Failed to save rules: %s", exc)


# Singleton
monitoring_rules = MonitoringRulesEngine()

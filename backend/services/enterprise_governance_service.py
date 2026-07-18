"""
DEPRECATED — Enterprise Governance Center.

Replaced by ``backend/governance/`` (Governance Runtime).
This module still works but all new policy evaluation should use
the Governance Runtime (GovernanceService + DecisionPipeline).

Will be removed in a future release.
"""
from __future__ import annotations

import json
import logging
import uuid
import warnings
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

log = logging.getLogger(__name__)

warnings.warn(
    "DEPRECATED: 'backend.services.enterprise_governance_service' is replaced by "
    "'backend.governance.service.GovernanceService'. This module will be removed "
    "in a future release.",
    DeprecationWarning,
    stacklevel=2,
)

_DATA_DIR = Path(__file__).resolve().parent.parent / "data"
_POLICIES_FILE = _DATA_DIR / "policies.json"
_COMPLIANCE_FILE = _DATA_DIR / "compliance.json"
_AUDIT_FILE = _DATA_DIR / "governance_audit.json"

GOVERNANCE_EVENT_POLICY_CREATED    = "governance.policy_created"
GOVERNANCE_EVENT_POLICY_UPDATED    = "governance.policy_updated"
GOVERNANCE_EVENT_POLICY_DELETED    = "governance.policy_deleted"
GOVERNANCE_EVENT_COMPLIANCE_CHECK  = "governance.compliance_check"
GOVERNANCE_EVENT_VIOLATION         = "governance.violation"
GOVERNANCE_EVENT_AUDIT_RECORDED    = "governance.audit_recorded"

POLICY_SEVERITIES = ["critical", "high", "medium", "low"]
POLICY_SCOPES = ["patch", "deployment", "workspace", "build", "all"]
POLICY_ACTIONS = ["deny", "warn", "notify", "require_approval"]
COMPLIANCE_STATUSES = ["compliant", "non_compliant", "unknown"]


def _load_json(path: Path) -> List[Dict[str, Any]]:
    try:
        if path.exists():
            with open(path) as f:
                return json.load(f)
    except Exception as exc:
        log.error("Failed to load %s: %s", path.name, exc)
    return []


def _save_json(path: Path, data: List[Dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w") as f:
        json.dump(data, f, indent=2, default=str)


class GovernanceService:
    """Policy enforcement, compliance monitoring, and audit trail."""

    def __init__(self, event_bus=None) -> None:
        self._event_bus = event_bus

    # ── Policies ─────────────────────────────────────────────────────────

    async def create_policy(
        self,
        name: str,
        description: str = "",
        scope: str = "all",
        rule_type: str = "custom",
        condition: Optional[Dict[str, Any]] = None,
        action: str = "warn",
        severity: str = "medium",
        enabled: bool = True,
        tags: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        policies = _load_json(_POLICIES_FILE)
        now = datetime.now(timezone.utc).isoformat()
        policy = {
            "id": f"pol-{uuid.uuid4().hex[:12]}",
            "name": name,
            "description": description,
            "scope": scope,
            "rule_type": rule_type,
            "condition": condition or {},
            "action": action,
            "severity": severity,
            "enabled": enabled,
            "tags": tags or [],
            "violation_count": 0,
            "created_at": now,
            "updated_at": now,
        }
        policies.insert(0, policy)
        _save_json(_POLICIES_FILE, policies)
        await self._emit(GOVERNANCE_EVENT_POLICY_CREATED, policy)
        return policy

    async def get_policy(self, policy_id: str) -> Optional[Dict[str, Any]]:
        for p in _load_json(_POLICIES_FILE):
            if p["id"] == policy_id:
                return p
        return None

    async def list_policies(self, scope: str = "", severity: str = "", enabled: Optional[bool] = None) -> List[Dict[str, Any]]:
        policies = _load_json(_POLICIES_FILE)
        if scope:
            policies = [p for p in policies if p["scope"] == scope or p["scope"] == "all"]
        if severity:
            policies = [p for p in policies if p["severity"] == severity]
        if enabled is not None:
            policies = [p for p in policies if p["enabled"] == enabled]
        return policies

    async def update_policy(self, policy_id: str, updates: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        policies = _load_json(_POLICIES_FILE)
        for i, p in enumerate(policies):
            if p["id"] == policy_id:
                p.update(updates)
                p["updated_at"] = datetime.now(timezone.utc).isoformat()
                policies[i] = p
                _save_json(_POLICIES_FILE, policies)
                await self._emit(GOVERNANCE_EVENT_POLICY_UPDATED, p)
                return p
        return None

    async def delete_policy(self, policy_id: str) -> bool:
        policies = _load_json(_POLICIES_FILE)
        filtered = [p for p in policies if p["id"] != policy_id]
        if len(filtered) == len(policies):
            return False
        _save_json(_POLICIES_FILE, filtered)
        await self._emit(GOVERNANCE_EVENT_POLICY_DELETED, {"id": policy_id})
        return True

    # ── Compliance Checks ────────────────────────────────────────────────

    async def run_compliance_check(self, target_type: str, target_id: str,
                                    context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        policies = await self.list_policies(scope=target_type, enabled=True)
        violations = []
        for policy in policies:
            verdict = self._evaluate_policy(policy, context or {})
            if not verdict["compliant"]:
                violations.append({
                    "policy_id": policy["id"],
                    "policy_name": policy["name"],
                    "severity": policy["severity"],
                    "reason": verdict["reason"],
                    "action": policy["action"],
                })
        status = "compliant" if len(violations) == 0 else "non_compliant"
        result = {
            "id": f"cc-{uuid.uuid4().hex[:12]}",
            "target_type": target_type,
            "target_id": target_id,
            "status": status,
            "policies_evaluated": len(policies),
            "violations": violations,
            "violation_count": len(violations),
            "check_time": datetime.now(timezone.utc).isoformat(),
        }
        records = _load_json(_COMPLIANCE_FILE)
        records.insert(0, result)
        _save_json(_COMPLIANCE_FILE, records)
        if violations:
            await self._emit(GOVERNANCE_EVENT_VIOLATION, result)
        await self._emit(GOVERNANCE_EVENT_COMPLIANCE_CHECK, result)
        return result

    def _evaluate_policy(self, policy: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        condition = policy.get("condition", {})
        field = condition.get("field", "")
        operator = condition.get("operator", "exists")
        value = condition.get("value")
        actual = context.get(field)
        if operator == "exists":
            compliant = actual is not None
        elif operator == "equals":
            compliant = actual == value
        elif operator == "not_equals":
            compliant = actual != value
        elif operator == "contains":
            compliant = value in (actual or []) if isinstance(actual, list) else (value in str(actual or ""))
        elif operator == "greater_than":
            try:
                compliant = float(actual or 0) > float(value or 0)
            except (ValueError, TypeError):
                compliant = False
        elif operator == "less_than":
            try:
                compliant = float(actual or 0) < float(value or 0)
            except (ValueError, TypeError):
                compliant = False
        else:
            compliant = True
        if compliant:
            return {"compliant": True, "reason": ""}
        return {
            "compliant": False,
            "reason": f"Policy '{policy['name']}': {field} {operator} {value} — got {actual}",
        }

    async def get_compliance_history(self, target_type: str = "", target_id: str = "",
                                      limit: int = 50) -> List[Dict[str, Any]]:
        records = _load_json(_COMPLIANCE_FILE)
        if target_type:
            records = [r for r in records if r["target_type"] == target_type]
        if target_id:
            records = [r for r in records if r["target_id"] == target_id]
        return records[:limit]

    # ── Audit Trail ──────────────────────────────────────────────────────

    async def record_audit(self, action: str, actor: str, target_type: str,
                           target_id: str, details: Optional[Dict[str, Any]] = None,
                           result: str = "success") -> Dict[str, Any]:
        entry = {
            "id": f"aud-{uuid.uuid4().hex[:12]}",
            "action": action,
            "actor": actor,
            "target_type": target_type,
            "target_id": target_id,
            "details": details or {},
            "result": result,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        records = _load_json(_AUDIT_FILE)
        records.insert(0, entry)
        _save_json(_AUDIT_FILE, records)
        await self._emit(GOVERNANCE_EVENT_AUDIT_RECORDED, entry)
        return entry

    async def get_audit_log(self, target_type: str = "", actor: str = "",
                             action: str = "", limit: int = 100) -> List[Dict[str, Any]]:
        records = _load_json(_AUDIT_FILE)
        if target_type:
            records = [r for r in records if r["target_type"] == target_type]
        if actor:
            records = [r for r in records if r["actor"] == actor]
        if action:
            records = [r for r in records if r["action"] == action]
        return records[:limit]

    # ── Dashboard Stats ──────────────────────────────────────────────────

    async def get_dashboard_stats(self) -> Dict[str, Any]:
        policies = _load_json(_POLICIES_FILE)
        compliance = _load_json(_COMPLIANCE_FILE)
        audits = _load_json(_AUDIT_FILE)
        total_violations = sum(p.get("violation_count", 0) for p in policies)
        recent_checks = [c for c in compliance if c.get("status") == "non_compliant"]
        return {
            "total_policies": len(policies),
            "enabled_policies": sum(1 for p in policies if p.get("enabled")),
            "total_violations": total_violations,
            "non_compliant_checks": len(recent_checks),
            "total_audit_entries": len(audits),
            "policies_by_severity": {
                s: sum(1 for p in policies if p.get("severity") == s)
                for s in POLICY_SEVERITIES
            },
            "compliance_rate": round(
                (sum(1 for c in compliance if c.get("status") == "compliant") / max(len(compliance), 1)) * 100, 1
            ),
        }

    async def _emit(self, event_type: str, payload: Dict[str, Any]) -> None:
        if self._event_bus:
            try:
                from backend.events.event_models import CognitionEvent
                await self._event_bus.publish(CognitionEvent(event_type=event_type, data=payload))
            except Exception as exc:
                log.warning("Governance event emit failed: %s", exc)

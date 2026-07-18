from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from backend.mission_intel.models import (
    ComplianceCheck,
    GovernancePlan,
    LearningInsight,
    MissionAnalysis,
    RiskLevel,
)

log = logging.getLogger(__name__)

_RISK_GOVERNANCE_MAP: Dict[RiskLevel, str] = {
    RiskLevel.LOW: "none",
    RiskLevel.MEDIUM: "low",
    RiskLevel.HIGH: "medium",
    RiskLevel.CRITICAL: "high",
}

_REQUIRED_APPROVALS: Dict[str, int] = {
    "none": 0,
    "low": 1,
    "medium": 2,
    "high": 3,
}


class GovernancePlanner:

    async def plan(
        self,
        analysis: MissionAnalysis,
        learning_insight: LearningInsight,
        context: Optional[Dict[str, Any]] = None,
    ) -> GovernancePlan:
        governance_level = _RISK_GOVERNANCE_MAP.get(analysis.risk, "none")
        required_approvals = _REQUIRED_APPROVALS.get(governance_level, 0)

        compliance_checks: List[ComplianceCheck] = []
        approval_gates: List[Dict[str, Any]] = []

        if analysis.risk in (RiskLevel.HIGH, RiskLevel.CRITICAL):
            compliance_checks.append(ComplianceCheck(
                policy="high_risk_mission_approval",
                status="pending",
                reason="High or critical risk mission requires pre-approval",
                required_role="admin",
            ))
            approval_gates.append({
                "step_index": 0,
                "reason": "High-risk mission requires approval before execution",
                "timeout_seconds": 600,
                "required_role": "admin",
            })

        if analysis.category in ("compliance_audit", "security_investigation"):
            compliance_checks.append(ComplianceCheck(
                policy="regulated_workflow_policy",
                status="pending",
                reason=f"Mission category '{analysis.category}' requires compliance review",
                required_role="compliance_officer",
            ))
            approval_gates.append({
                "step_index": 1,
                "reason": "Compliance review required for regulated workflow",
                "timeout_seconds": 3600,
                "required_role": "compliance_officer",
            })

        if analysis.priority.value == "critical":
            approval_gates.append({
                "step_index": 0,
                "reason": "Critical priority mission requires immediate approval",
                "timeout_seconds": 300,
                "required_role": "admin",
            })

        for ri in learning_insight.risk_indicators:
            compliance_checks.append(ComplianceCheck(
                policy="learning_risk_indicator",
                status="review",
                reason=ri,
                required_role="operator",
            ))

        if analysis.risk == RiskLevel.CRITICAL and governance_level in ("high", "critical"):
            compliance_checks.append(ComplianceCheck(
                policy="emergency_override_policy",
                status="pending",
                reason="Critical risk requires emergency override authorization",
                required_role="super_admin",
            ))

        risk_assessment = analysis.risk
        approved = required_approvals == 0

        return GovernancePlan(
            compliance_checks=compliance_checks,
            required_approvals=required_approvals,
            approval_gates=approval_gates,
            risk_assessment=risk_assessment,
            approved=approved,
            governance_level=governance_level,
        )


governance_planner = GovernancePlanner()

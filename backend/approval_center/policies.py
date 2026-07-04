from __future__ import annotations

from typing import Dict, List, Optional

from backend.approval_center.models import (
    ApprovalPolicy,
    ApproverRole,
    RiskLevel,
)

# ---------------------------------------------------------------------------
# Approval Policies
# Each policy maps a risk level + mission scope to required approval roles,
# levels, escalation timing, and break-glass eligibility.
# ---------------------------------------------------------------------------

LOW_POLICY = ApprovalPolicy(
    policy_id="policy_low",
    name="Low Risk Auto-Approval",
    description="Low-risk missions are auto-approved with standard audit logging.",
    risk_level=RiskLevel.LOW,
    required_roles=[ApproverRole.MISSION_OWNER],
    required_levels=0,
    escalation_minutes=0,
    expiration_minutes=0,
    requires_break_glass=False,
    notify_roles=[ApproverRole.MANAGER],
)

MEDIUM_POLICY = ApprovalPolicy(
    policy_id="policy_medium",
    name="Medium Risk Single Approval",
    description="Medium-risk missions require manager-level approval.",
    risk_level=RiskLevel.MEDIUM,
    mission_ids=[
        "enterprise.change_management",
        "enterprise.customer_escalation",
    ],
    required_roles=[ApproverRole.MANAGER],
    required_levels=1,
    escalation_minutes=20,
    expiration_minutes=45,
    requires_break_glass=False,
    notify_roles=[ApproverRole.MANAGER, ApproverRole.PLATFORM_ADMIN],
)

HIGH_POLICY = ApprovalPolicy(
    policy_id="policy_high",
    name="High Risk Multi-Level Approval",
    description="High-risk missions require manager approval followed by executive approval.",
    risk_level=RiskLevel.HIGH,
    mission_ids=[
        "enterprise.software_release",
        "enterprise.incident_response",
        "enterprise.compliance_audit",
        "enterprise.infrastructure_deployment",
    ],
    required_roles=[ApproverRole.MANAGER, ApproverRole.EXECUTIVE],
    required_levels=2,
    escalation_minutes=15,
    expiration_minutes=30,
    requires_break_glass=True,
    break_glass_roles=[ApproverRole.PLATFORM_ADMIN, ApproverRole.EXECUTIVE],
    notify_roles=[
        ApproverRole.MANAGER, ApproverRole.EXECUTIVE,
        ApproverRole.PLATFORM_ADMIN,
    ],
)

CRITICAL_POLICY = ApprovalPolicy(
    policy_id="policy_critical",
    name="Critical Risk Three-Level + Security Approval",
    description="Critical-risk missions require manager, security officer, and executive approval.",
    risk_level=RiskLevel.CRITICAL,
    mission_ids=[
        "enterprise.security_investigation",
        "enterprise.disaster_recovery",
    ],
    required_roles=[
        ApproverRole.MANAGER,
        ApproverRole.SECURITY_OFFICER,
        ApproverRole.EXECUTIVE,
    ],
    required_levels=3,
    escalation_minutes=10,
    expiration_minutes=20,
    requires_break_glass=True,
    break_glass_roles=[
        ApproverRole.PLATFORM_ADMIN,
        ApproverRole.SECURITY_OFFICER,
    ],
    notify_roles=[
        ApproverRole.MANAGER, ApproverRole.SECURITY_OFFICER,
        ApproverRole.EXECUTIVE, ApproverRole.PLATFORM_ADMIN,
        ApproverRole.COMPLIANCE_OFFICER,
    ],
)

DEFAULT_POLICY = HIGH_POLICY

# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------

POLICY_REGISTRY: Dict[str, ApprovalPolicy] = {
    "policy_low": LOW_POLICY,
    "policy_medium": MEDIUM_POLICY,
    "policy_high": HIGH_POLICY,
    "policy_critical": CRITICAL_POLICY,
}

POLICY_BY_RISK: Dict[RiskLevel, ApprovalPolicy] = {
    RiskLevel.LOW: LOW_POLICY,
    RiskLevel.MEDIUM: MEDIUM_POLICY,
    RiskLevel.HIGH: HIGH_POLICY,
    RiskLevel.CRITICAL: CRITICAL_POLICY,
}


def get_policy(policy_id: str) -> Optional[ApprovalPolicy]:
    return POLICY_REGISTRY.get(policy_id)


def get_policy_for_risk(risk_level: RiskLevel) -> Optional[ApprovalPolicy]:
    return POLICY_BY_RISK.get(risk_level)


def get_policy_for_mission(mission_id: str, risk_level: RiskLevel) -> ApprovalPolicy:
    for policy in POLICY_REGISTRY.values():
        if mission_id in policy.mission_ids:
            return policy
    return get_policy_for_risk(risk_level) or DEFAULT_POLICY


def list_policies() -> List[dict]:
    return [p.to_dict() for p in POLICY_REGISTRY.values()]


# ---------------------------------------------------------------------------
# Risk assessor - determines risk level from mission + worker + target context
# ---------------------------------------------------------------------------

def assess_risk_from_context(
    risk_level: RiskLevel,
    mission_id: Optional[str] = None,
    needs_browser: bool = False,
    needs_voice: bool = False,
    target_environment: Optional[str] = None,
    affected_systems: Optional[List[str]] = None,
    requires_connectors: Optional[List[str]] = None,
) -> RiskLevel:
    final_risk = risk_level

    # Browser access to external sites increases risk
    if needs_browser and final_risk in (RiskLevel.LOW, RiskLevel.MEDIUM):
        final_risk = RiskLevel.MEDIUM

    # Production environment increases risk
    if target_environment and target_environment.lower() in (
        "production", "prod", "live", "critical"
    ):
        if final_risk == RiskLevel.LOW:
            final_risk = RiskLevel.MEDIUM
        elif final_risk == RiskLevel.MEDIUM:
            final_risk = RiskLevel.HIGH

    # Sensitive systems increase risk
    if affected_systems:
        sensitive_keywords = ["database", "auth", "payment", "pii", "security", "core"]
        if any(kw in " ".join(affected_systems).lower() for kw in sensitive_keywords):
            if final_risk == RiskLevel.MEDIUM:
                final_risk = RiskLevel.HIGH
            elif final_risk == RiskLevel.HIGH:
                final_risk = RiskLevel.CRITICAL

    return final_risk
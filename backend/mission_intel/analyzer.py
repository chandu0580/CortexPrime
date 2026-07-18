from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from backend.mission_intel.models import (
    MissionAnalysis,
    MissionPriority,
    RiskLevel,
)

log = logging.getLogger(__name__)

_RISK_KEYWORDS: Dict[RiskLevel, List[str]] = {
    RiskLevel.LOW: ["minor", "cosmetic", "documentation", "info", "low risk"],
    RiskLevel.MEDIUM: ["moderate", "change", "update", "medium"],
    RiskLevel.HIGH: ["critical", "production", "security", "outage", "data", "high"],
    RiskLevel.CRITICAL: ["p0", "p1", "severe", "emergency", "disaster", "breach", "compliance"],
}

_PRIORITY_KEYWORDS: Dict[MissionPriority, List[str]] = {
    MissionPriority.LOWEST: ["trivial", "nice to have", "backlog"],
    MissionPriority.LOW: ["minor", "low priority", "eventual"],
    MissionPriority.MEDIUM: ["standard", "normal", "medium", "default"],
    MissionPriority.HIGH: ["important", "urgent", "high priority", "asap"],
    MissionPriority.CRITICAL: ["critical", "blocking", "p0", "emergency", "severe"],
}

_CATEGORY_KEYWORDS: Dict[str, List[str]] = {
    "software_release": ["release", "deploy", "rollout", "version", "ship"],
    "incident_response": ["incident", "outage", "down", "degraded", "p1", "p0"],
    "executive_research": ["research", "briefing", "strategy", "analysis", "executive"],
    "compliance_audit": ["compliance", "audit", "regulatory", "sox", "hipaa", "gdpr"],
    "change_management": ["change", "migration", "upgrade", "cab", "change request"],
    "infrastructure_deployment": ["infrastructure", "deploy", "provision", "cluster", "terraform"],
    "security_investigation": ["security", "breach", "vulnerability", "forensic", "threat"],
    "knowledge_discovery": ["knowledge", "research", "learn", "document", "wiki"],
    "customer_escalation": ["escalation", "customer", "complaint", "support ticket"],
    "disaster_recovery": ["disaster", "recovery", "dr", "failover", "rto", "rpo"],
}

_CONNECTOR_CAPABILITY_MAP: Dict[str, List[str]] = {
    "github": ["build", "deploy", "search", "execute", "observe"],
    "jira": ["search", "execute", "notify"],
    "slack": ["notify", "search", "execute"],
    "kubernetes": ["observe", "deploy", "scale", "restart", "execute"],
    "docker": ["observe", "execute", "restart", "deploy"],
    "prometheus": ["observe", "search"],
    "grafana": ["observe", "search"],
}

_CAPABILITY_CONNECTOR_MAP: Dict[str, List[str]] = {}
for _conn, _caps in _CONNECTOR_CAPABILITY_MAP.items():
    for _cap in _caps:
        _CAPABILITY_CONNECTOR_MAP.setdefault(_cap, []).append(_conn)


class MissionAnalyzer:

    async def analyze(
        self,
        goal: str,
        context: Optional[Dict[str, Any]] = None,
    ) -> MissionAnalysis:
        ctx = context or {}
        goal_lower = goal.lower()

        category = self._detect_category(goal_lower, ctx.get("category", ""))
        risk = self._detect_risk(goal_lower, ctx.get("risk", ""))
        priority = self._detect_priority(goal_lower, ctx.get("priority", ""))
        constraints = self._extract_constraints(goal_lower, ctx.get("constraints", []))
        dependencies = self._extract_dependencies(goal_lower, ctx.get("dependencies", []))
        required_capabilities = self._detect_capabilities(goal_lower, ctx)
        suggested_connectors = self._suggest_connectors(required_capabilities)
        tags = self._extract_tags(goal_lower, category)
        estimated_duration = self._estimate_duration(category, risk, len(constraints))
        reasoning = self._build_reasoning(goal, category, risk, priority)

        return MissionAnalysis(
            goal=goal,
            category=category,
            constraints=constraints,
            risk=risk,
            priority=priority,
            dependencies=dependencies,
            required_capabilities=required_capabilities,
            suggested_connectors=suggested_connectors,
            estimated_duration_minutes=estimated_duration,
            tags=tags,
            confidence=0.85,
            reasoning=reasoning,
        )

    def _detect_category(self, text: str, hint: str = "") -> str:
        if hint and hint in _CATEGORY_KEYWORDS:
            return hint
        for cat, keywords in _CATEGORY_KEYWORDS.items():
            if any(kw in text for kw in keywords):
                return cat
        return "knowledge_discovery"

    def _detect_risk(self, text: str, hint: str = "") -> RiskLevel:
        if hint:
            try:
                return RiskLevel(hint.lower())
            except ValueError:
                pass
        for level, keywords in reversed(list(_RISK_KEYWORDS.items())):
            if any(kw in text for kw in keywords):
                return level
        return RiskLevel.LOW

    def _detect_priority(self, text: str, hint: str = "") -> MissionPriority:
        if hint:
            try:
                return MissionPriority(hint.lower())
            except ValueError:
                pass
        for level, keywords in _PRIORITY_KEYWORDS.items():
            if any(kw in text for kw in keywords):
                return level
        return MissionPriority.MEDIUM

    def _extract_constraints(self, text: str, hints: List[str]) -> List[str]:
        constraints: List[str] = list(hints)
        constraint_markers = [
            "within", "before", "after", "excluding", "must not",
            "cannot", "limited to", "restricted", "only",
        ]
        for marker in constraint_markers:
            if marker in text:
                idx = text.find(marker)
                snippet = text[idx:idx + 80].strip()
                if snippet not in constraints:
                    constraints.append(snippet)
        return constraints

    def _extract_dependencies(self, text: str, hints: List[str]) -> List[str]:
        return list(hints)

    def _detect_capabilities(self, text: str, ctx: Dict[str, Any]) -> List[str]:
        caps: List[str] = ctx.get("capabilities", [])
        for cap_name in _CAPABILITY_CONNECTOR_MAP:
            if cap_name in text:
                if cap_name not in caps:
                    caps.append(cap_name)
        return caps

    def _suggest_connectors(self, capabilities: List[str]) -> List[str]:
        connectors: List[str] = []
        for cap in capabilities:
            for conn in _CAPABILITY_CONNECTOR_MAP.get(cap, []):
                if conn not in connectors:
                    connectors.append(conn)
        return connectors

    def _extract_tags(self, text: str, category: str) -> List[str]:
        tags: List[str] = [category]
        for cap in _CAPABILITY_CONNECTOR_MAP:
            if cap in text and cap not in tags:
                tags.append(cap)
        return tags

    def _estimate_duration(self, category: str, risk: RiskLevel, constraint_count: int) -> int:
        base = {
            "incident_response": 15,
            "security_investigation": 45,
            "disaster_recovery": 60,
            "compliance_audit": 120,
            "executive_research": 60,
            "software_release": 30,
            "infrastructure_deployment": 60,
            "change_management": 30,
            "customer_escalation": 30,
            "knowledge_discovery": 45,
        }.get(category, 30)
        risk_mult = {RiskLevel.LOW: 1, RiskLevel.MEDIUM: 1.5, RiskLevel.HIGH: 2, RiskLevel.CRITICAL: 3}
        return int(base * risk_mult.get(risk, 1) + constraint_count * 5)

    def _build_reasoning(self, goal: str, category: str, risk: RiskLevel, priority: MissionPriority) -> str:
        return (
            f"Mission goal classified as '{category}' with {risk.value} risk "
            f"and {priority.value} priority."
        )


mission_analyzer = MissionAnalyzer()

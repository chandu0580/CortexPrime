from __future__ import annotations

import logging
from typing import Any

from backend.learning.models import Pattern, Recommendation, RecommendationCategory

log = logging.getLogger(__name__)


class RecommendationEngine:
    async def generate_all(self, patterns: list[Pattern]) -> list[Recommendation]:
        recs: list[Recommendation] = []
        for pattern in patterns:
            recs.extend(await self._generate_for_pattern(pattern))
        return recs

    async def generate_for_mission(self, mission_data: dict[str, Any]) -> list[Recommendation]:
        recs: list[Recommendation] = []
        status = mission_data.get("status", "")
        if status == "failed":
            recs.append(Recommendation(
                category=RecommendationCategory.PERFORMANCE.value,
                title="Review mission failure",
                description="The mission failed. Consider reviewing the plan and retrying with adjusted parameters.",
                reason=f"Mission '{mission_data.get('title', '')}' failed with status '{status}'",
                evidence=[f"Owner: {mission_data.get('owner', 'unknown')}"],
                confidence=0.7,
                priority="high",
                risk="medium",
                estimated_impact="May prevent future failures",
                actions=[{"action_type": "review", "label": "Review Mission", "description": "Analyze failure reasons"}],
                related_id=mission_data.get("mission_id"),
            ))
        if mission_data.get("retry_count", 0) > 2:
            recs.append(Recommendation(
                category=RecommendationCategory.RETRY.value,
                title="Consider retry strategy change",
                description=f"Mission was retried {mission_data.get('retry_count', 0)} times. Consider changing the retry strategy.",
                reason="High retry count indicates systemic issue",
                evidence=[f"Retries: {mission_data.get('retry_count', 0)}"],
                confidence=0.6,
                priority="medium",
                risk="low",
                estimated_impact="May reduce execution time",
                actions=[{"action_type": "configure", "label": "Adjust Retry Strategy", "description": "Update retry configuration"}],
                related_id=mission_data.get("mission_id"),
            ))
        return recs

    async def generate_for_execution(self, execution_data: dict[str, Any]) -> list[Recommendation]:
        recs: list[Recommendation] = []
        status = execution_data.get("status", "")
        error = execution_data.get("error", "")
        if status == "failed":
            recs.append(Recommendation(
                category=RecommendationCategory.RETRY.value,
                title="Retry failed execution",
                description=f"Execution failed: {error}. A retry may succeed with adjusted parameters.",
                reason=f"Execution failed with error: {error}",
                evidence=[f"Agent: {execution_data.get('agent', 'unknown')}", f"Trigger: {execution_data.get('trigger', 'manual')}"],
                confidence=0.5,
                priority="medium",
                risk="low",
                estimated_impact="May resolve transient failure",
                actions=[{"action_type": "retry", "label": "Retry Execution", "description": "Retry with same parameters"}],
                related_id=execution_data.get("execution_id"),
            ))
        return recs

    async def generate_for_connector(self, connector_data: dict[str, Any]) -> list[Recommendation]:
        recs: list[Recommendation] = []
        failure_rate = connector_data.get("failure_rate", 0)
        if failure_rate > 0.3:
            recs.append(Recommendation(
                category=RecommendationCategory.CONNECTOR.value,
                title=f"Investigate {connector_data.get('name', 'connector')} reliability",
                description=f"Connector has {failure_rate:.0%} failure rate. Consider reviewing configuration or escalating.",
                reason=f"High failure rate ({failure_rate:.0%}) detected",
                evidence=[f"Type: {connector_data.get('connector_type', 'unknown')}", f"Failures: {connector_data.get('failed', 0)}/{connector_data.get('total', 0)}"],
                confidence=min(failure_rate * 1.5, 1.0),
                priority="high",
                risk="high",
                estimated_impact="May block mission execution",
                actions=[{"action_type": "review", "label": "Review Connector", "description": "Check connector configuration and health"}],
                related_id=connector_data.get("connector_id"),
            ))
        return recs

    async def generate_for_governance(self, governance_data: dict[str, Any]) -> list[Recommendation]:
        recs: list[Recommendation] = []
        decision = governance_data.get("decision", "")
        if decision == "DENY":
            recs.append(Recommendation(
                category=RecommendationCategory.GOVERNANCE.value,
                title="Review denied governance decision",
                description=f"Action was denied by governance. Review policy '{governance_data.get('policy_name', 'unknown')}'.",
                reason=f"Governance denied: {governance_data.get('reason', '')}",
                evidence=[f"Resource: {governance_data.get('resource_type', 'unknown')}/{governance_data.get('resource_id', '')}", f"Action: {governance_data.get('action', '')}"],
                confidence=0.8,
                priority="high",
                risk="medium",
                estimated_impact="Unblocks workflow",
                actions=[{"action_type": "review", "label": "Review Policy", "description": "Review and potentially adjust policy"}],
                related_id=governance_data.get("decision_id"),
            ))
        return recs

    async def _generate_for_pattern(self, pattern: Pattern) -> list[Recommendation]:
        recs: list[Recommendation] = []
        data = pattern.pattern_data or {}
        ptype = data.get("type", "")

        if ptype == "repeated_failure":
            owner = data.get("owner", "unknown")
            recs.append(Recommendation(
                category=RecommendationCategory.PERFORMANCE.value,
                title=f"Review {owner}'s failed missions",
                description=f"Mission owner '{owner}' has {pattern.occurrences} failed missions. Consider reviewing their approach or providing additional guidance.",
                reason="Repeated failures indicate a systemic issue",
                evidence=[f"Owner: {owner}", f"Failures: {pattern.occurrences}"],
                confidence=pattern.confidence,
                priority="high",
                risk="high",
                estimated_impact="May reduce failure rate",
                actions=[{"action_type": "review", "label": "Review Missions", "description": f"Analyze {owner}'s failed missions"}],
            ))
        elif ptype == "connector_reliability":
            ctype = data.get("connector_type", "unknown")
            recs.append(Recommendation(
                category=RecommendationCategory.CONNECTOR.value,
                title=f"Review {ctype} connector health",
                description=f"Connector type '{ctype}' has {data.get('failure_rate', 0):.0%} failure rate ({data.get('failed', 0)}/{data.get('total', 0)}).",
                reason="Low connector reliability impacts mission execution",
                evidence=[f"Type: {ctype}", f"Failures: {data.get('failed', 0)}/{data.get('total', 0)}"],
                confidence=pattern.confidence,
                priority="high",
                risk="high",
                estimated_impact="May unblock connector-dependent missions",
                actions=[{"action_type": "review", "label": "Review Connector", "description": f"Investigate {ctype} reliability"}],
            ))
        elif ptype == "approval_bottleneck":
            recs.append(Recommendation(
                category=RecommendationCategory.APPROVAL.value,
                title="Approval bottleneck detected",
                description=f"{pattern.occurrences} pending approvals. Consider adding reviewers or streamlining approval workflow.",
                reason="Backlog of pending approvals delays execution",
                evidence=[f"Pending: {pattern.occurrences}", f"Total: {data.get('total', 0)}"],
                confidence=pattern.confidence,
                priority="medium",
                risk="medium",
                estimated_impact="May reduce approval wait time",
                actions=[{"action_type": "configure", "label": "Review Approvals", "description": "Streamline approval workflow"}],
            ))
        elif ptype == "retry_frequency":
            recs.append(Recommendation(
                category=RecommendationCategory.RETRY.value,
                title="High execution retry rate",
                description=f"{pattern.occurrences} executions had errors. Consider increasing timeouts or reviewing execution parameters.",
                reason="Frequent errors indicate configuration or infrastructure issues",
                evidence=[f"Errors: {pattern.occurrences}", f"Total: {data.get('total', 0)}"],
                confidence=pattern.confidence,
                priority="medium",
                risk="medium",
                estimated_impact="May reduce execution failures",
                actions=[{"action_type": "configure", "label": "Review Timeouts", "description": "Adjust execution timeout and retry configuration"}],
            ))
        elif ptype == "completion_trend":
            if pattern.name == "high_mission_failure_rate":
                recs.append(Recommendation(
                    category=RecommendationCategory.PERFORMANCE.value,
                    title="High mission failure rate",
                    description=f"Mission failure rate is {data.get('failure_rate', 0):.0%}. Review mission planning and execution.",
                    reason="Systemic failures indicate planning or execution issues",
                    evidence=[f"Failed: {data.get('failed', 0)}/{data.get('total', 0)}"],
                    confidence=pattern.confidence,
                    priority="critical",
                    risk="high",
                    estimated_impact="Critical for platform reliability",
                    actions=[{"action_type": "review", "label": "Analyze Failures", "description": "Deep-dive into failure patterns"}],
                ))
        elif ptype == "policy_violation":
            recs.append(Recommendation(
                category=RecommendationCategory.GOVERNANCE.value,
                title="Review policy violations",
                description=f"{pattern.occurrences} policy violations detected. Review policies and user permissions.",
                reason="Frequent violations suggest policy misconfiguration",
                evidence=[f"Violations: {pattern.occurrences}"],
                confidence=pattern.confidence,
                priority="medium",
                risk="medium",
                estimated_impact="May reduce unnecessary blocks",
                actions=[{"action_type": "review", "label": "Review Policies", "description": "Audit governance policies"}],
            ))
        return recs

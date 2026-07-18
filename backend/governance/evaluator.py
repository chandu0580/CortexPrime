from __future__ import annotations

import logging
from typing import Any, Optional

from backend.governance.models import (
    DecisionReasonCode,
    DecisionRequest,
    GovernanceDecision,
    PolicyResult,
)

log = logging.getLogger(__name__)


class PolicyEvaluationEngine:
    """
    Rule-based policy evaluation engine.

    Evaluates policies against a DecisionRequest using:
    - User / Role matching
    - Mission type matching
    - Execution type matching
    - Connector capability matching
    - Resource scope matching
    - Time constraints
    - Risk level thresholds
    """

    @staticmethod
    async def evaluate(
        policy: dict[str, Any],
        request: DecisionRequest,
    ) -> PolicyResult:
        conditions = policy.get("conditions", {})
        if not conditions:
            return PolicyResult(
                policy_name=policy.get("name", ""),
                policy_id=str(policy.get("id", "")),
                category=policy.get("category", ""),
                severity=policy.get("severity", "medium"),
                matched=False,
                message="No conditions defined",
            )

        actions = policy.get("actions", {})
        action_type = actions.get("action", "allow")
        action_map = {
            "allow": GovernanceDecision.ALLOW,
            "deny": GovernanceDecision.DENY,
            "require_approval": GovernanceDecision.REQUIRE_APPROVAL,
            "require_review": GovernanceDecision.REQUIRE_REVIEW,
            "escalate": GovernanceDecision.ESCALATE,
        }
        default_decision = action_map.get(action_type, GovernanceDecision.ALLOW)

        matched = False
        evaluated: list[dict[str, Any]] = []
        match_reason: Optional[str] = None

        condition_blocks = conditions if isinstance(conditions, list) else [conditions]

        for block in condition_blocks:
            block_type = block.get("type", "all")
            block_rules = block.get("rules", block.get("conditions", [block]))
            block_result = await PolicyEvaluationEngine._evaluate_block(
                block_type, block_rules, request
            )
            evaluated.append({
                "type": block_type,
                "rules": block_rules,
                "matched": block_result,
            })
            if block_result:
                matched = True
                match_reason = f"Matched {block_type} block"

        if not matched:
            return PolicyResult(
                policy_name=policy.get("name", ""),
                policy_id=str(policy.get("id", "")),
                category=policy.get("category", ""),
                severity=policy.get("severity", "medium"),
                matched=False,
                decision=GovernanceDecision.ALLOW,
                reason_code=DecisionReasonCode.NO_POLICY_MATCH,
                message="No conditions matched",
                conditions_evaluated=evaluated,
            )

        reason_code = PolicyEvaluationEngine._decision_to_reason(
            default_decision, match_reason or "Policy matched"
        )

        return PolicyResult(
            policy_name=policy.get("name", ""),
            policy_id=str(policy.get("id", "")),
            category=policy.get("category", ""),
            severity=policy.get("severity", "medium"),
            matched=True,
            decision=default_decision,
            reason_code=reason_code,
            message=match_reason or "Policy matched",
            conditions_evaluated=evaluated,
        )

    @staticmethod
    async def _evaluate_block(
        block_type: str,
        rules: list[dict[str, Any]],
        request: DecisionRequest,
    ) -> bool:
        results = []
        for rule in rules:
            result = await PolicyEvaluationEngine._evaluate_rule(rule, request)
            results.append(result)

        if block_type == "all":
            return all(results)
        elif block_type == "any":
            return any(results)
        elif block_type == "none":
            return not any(results)
        return all(results)

    @staticmethod
    async def _evaluate_rule(
        rule: dict[str, Any],
        request: DecisionRequest,
    ) -> bool:
        field = rule.get("field", "")
        operator = rule.get("operator", "equals")
        value = rule.get("value")

        actual = PolicyEvaluationEngine._resolve_field(field, request)

        if operator == "equals":
            return actual == value
        elif operator == "not_equals":
            return actual != value
        elif operator == "contains":
            return value in (actual or "")
        elif operator == "in":
            return actual in (value or [])
        elif operator == "not_in":
            return actual not in (value or [])
        elif operator == "exists":
            return actual is not None
        elif operator == "not_exists":
            return actual is None
        elif operator == "greater_than":
            try:
                return float(actual or 0) > float(value or 0)
            except (ValueError, TypeError):
                return False
        elif operator == "less_than":
            try:
                return float(actual or 0) < float(value or 0)
            except (ValueError, TypeError):
                return False
        elif operator == "matches":
            import re
            if actual and value:
                return bool(re.match(str(value), str(actual)))
            return False

        return False

    @staticmethod
    def _resolve_field(field: str, request: DecisionRequest) -> Any:
        field_map = {
            "user": request.user,
            "role": request.role,
            "tenant": request.tenant,
            "requester": request.requester,
            "resource_type": request.resource_type,
            "resource_id": request.resource_id,
            "action": request.action,
            "scope": request.scope,
            "risk_level": request.risk_level,
            "mission_id": request.mission_id,
            "mission_type": request.mission_type,
            "execution_id": request.execution_id,
            "execution_type": request.execution_type,
            "connector_type": request.connector_type,
            "connector_capability": request.connector_capability,
        }
        if field in field_map:
            return field_map[field]
        return request.context.get(field)

    @staticmethod
    def _decision_to_reason(
        decision: GovernanceDecision,
        message: str,
    ) -> DecisionReasonCode:
        mapping = {
            GovernanceDecision.ALLOW: DecisionReasonCode.POLICY_ALLOWED,
            GovernanceDecision.DENY: DecisionReasonCode.POLICY_DENIED,
            GovernanceDecision.REQUIRE_APPROVAL: DecisionReasonCode.APPROVAL_REQUIRED,
            GovernanceDecision.REQUIRE_REVIEW: DecisionReasonCode.APPROVAL_REQUIRED,
            GovernanceDecision.ESCALATE: DecisionReasonCode.ESCALATED,
        }
        return mapping.get(decision, DecisionReasonCode.NO_POLICY_MATCH)

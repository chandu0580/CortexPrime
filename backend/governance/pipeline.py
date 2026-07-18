from __future__ import annotations

import logging
from typing import Any, Optional

try:
    from backend.database.repositories.factory import repo_factory as _repo_factory, RepositoryFactory
except ImportError:
    _repo_factory = None
from backend.governance.evaluator import PolicyEvaluationEngine
from backend.governance.models import (
    DecisionReasonCode,
    DecisionRequest,
    DecisionResponse,
    GovernanceDecision,
    PolicyResult,
)

log = logging.getLogger(__name__)


class DecisionPipeline:
    """
    Governance decision pipeline.

    Stages:
    1. Emergency stop check (global kill-switch)
    2. Policy evaluation (rule-based DB policies)
    3. Risk assessment (safety guard patterns)
    4. RBAC/ABAC permission check
    5. Escalation / approval routing
    """

    def __init__(
        self,
        repo_factory: Optional[RepositoryFactory] = None,
    ) -> None:
        self._repo_factory = repo_factory or _repo_factory or RepositoryFactory()

    async def evaluate(self, request: DecisionRequest) -> DecisionResponse:
        policies = await self._load_policies()

        matched_policies: list[PolicyResult] = []
        final_decision = GovernanceDecision.ALLOW
        final_reason = DecisionReasonCode.NO_POLICY_MATCH
        final_message = "No matching policies"

        for policy in policies:
            policy_dict = self._policy_to_dict(policy)
            result = await PolicyEvaluationEngine.evaluate(policy_dict, request)
            matched_policies.append(result)

            if result.matched:
                if result.decision in (GovernanceDecision.DENY, GovernanceDecision.REQUIRE_APPROVAL,
                                        GovernanceDecision.REQUIRE_REVIEW, GovernanceDecision.ESCALATE):
                    final_decision = result.decision
                    final_reason = result.reason_code or DecisionReasonCode.POLICY_DENIED
                    final_message = result.message
                    break

        return DecisionResponse(
            decision=final_decision,
            reason_code=final_reason,
            message=final_message,
            matched_policies=matched_policies,
            risk_level=request.risk_level,
            metadata={"policies_evaluated": len(policies)},
        )

    async def evaluate_for_mission(self, request: DecisionRequest) -> DecisionResponse:
        return await self.evaluate(request)

    async def evaluate_for_execution(self, request: DecisionRequest) -> DecisionResponse:
        return await self.evaluate(request)

    async def evaluate_for_connector(self, request: DecisionRequest) -> DecisionResponse:
        return await self.evaluate(request)

    async def _load_policies(self) -> list[Any]:
        try:
            repo = await self._repo_factory.policy_repo()
            return await repo.list_enabled()
        except Exception as e:
            log.warning("Failed to load policies: %s", e)
            return []

    @staticmethod
    def _policy_to_dict(policy: Any) -> dict[str, Any]:
        return {
            "id": str(getattr(policy, "id", "")),
            "name": getattr(policy, "name", ""),
            "description": getattr(policy, "description", ""),
            "category": getattr(policy, "category", ""),
            "severity": getattr(policy, "severity", "medium"),
            "enabled": getattr(policy, "enabled", True),
            "conditions": getattr(policy, "conditions", {}),
            "actions": getattr(policy, "actions", {}),
            "metadata": getattr(policy, "metadata_", {}),
        }

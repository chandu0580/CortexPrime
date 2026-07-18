from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from backend.governance.evaluator import PolicyEvaluationEngine
from backend.governance.models import DecisionReasonCode, DecisionRequest, GovernanceDecision
from backend.governance.pipeline import DecisionPipeline


def _make_request(**kwargs) -> DecisionRequest:
    return DecisionRequest(
        requester=kwargs.get("requester", "tester"),
        user=kwargs.get("user", "tester"),
        role=kwargs.get("role", "user"),
        tenant=kwargs.get("tenant", ""),
        action=kwargs.get("action", "execute"),
        resource_type=kwargs.get("resource_type", "mission"),
        resource_id=kwargs.get("resource_id", "res-001"),
        risk_level=kwargs.get("risk_level", "low"),
        scope=kwargs.get("scope", ""),
        mission_type=kwargs.get("mission_type", "standard"),
        mission_id=kwargs.get("mission_id", "mis-001"),
        context=kwargs.get("context", {}),
    )


def _policy_model(**kwargs):
    model = MagicMock()
    model.id = kwargs.get("id", "p-1")
    model.name = kwargs.get("name", "test-policy")
    model.description = kwargs.get("description", "")
    model.category = kwargs.get("category", "general")
    model.severity = kwargs.get("severity", "medium")
    model.enabled = kwargs.get("enabled", True)
    model.conditions = kwargs.get("conditions", {})
    model.actions = kwargs.get("actions", {"action": "allow"})
    model.metadata_ = kwargs.get("metadata_", {})
    return model


@pytest.fixture
def mock_policy_repo():
    repo = AsyncMock()
    repo.list_enabled = AsyncMock(return_value=[])
    return repo


@pytest.fixture
def mock_repo_factory(mock_policy_repo):
    factory = MagicMock()
    factory.policy_repo = AsyncMock(return_value=mock_policy_repo)
    return factory


@pytest.fixture
def pipeline(mock_repo_factory):
    return DecisionPipeline(repo_factory=mock_repo_factory)


# ---------------------------------------------------------------------------
# Pipeline: no policies
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_pipeline_no_policies_allows(pipeline, mock_policy_repo):
    mock_policy_repo.list_enabled.return_value = []
    request = _make_request()
    response = await pipeline.evaluate(request)
    assert response.allowed
    assert response.reason_code == DecisionReasonCode.NO_POLICY_MATCH
    assert response.message == "No matching policies"


# ---------------------------------------------------------------------------
# Pipeline: single allow policy
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_pipeline_single_allow(pipeline, mock_policy_repo):
    mock_policy_repo.list_enabled.return_value = [
        _policy_model(
            name="allow-standard",
            conditions=[{"type": "all", "rules": [{"field": "action", "operator": "equals", "value": "execute"}]}],
            actions={"action": "allow"},
        ),
    ]
    request = _make_request(action="execute")
    response = await pipeline.evaluate(request)
    assert response.allowed
    assert len(response.matched_policies) == 1
    assert response.matched_policies[0].matched


# ---------------------------------------------------------------------------
# Pipeline: deny wins over allow
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_pipeline_deny_wins(pipeline, mock_policy_repo):
    mock_policy_repo.list_enabled.return_value = [
        _policy_model(
            name="allow-general",
            conditions=[{"type": "all", "rules": [{"field": "resource_type", "operator": "equals", "value": "mission"}]}],
            actions={"action": "allow"},
        ),
        _policy_model(
            name="deny-specific",
            conditions=[{"type": "all", "rules": [{"field": "resource_id", "operator": "equals", "value": "res-001"}]}],
            actions={"action": "deny"},
        ),
    ]
    request = _make_request(resource_id="res-001")
    response = await pipeline.evaluate(request)
    assert response.denied
    assert response.reason_code == DecisionReasonCode.POLICY_DENIED


# ---------------------------------------------------------------------------
# Pipeline: deny stops evaluation (first deny wins)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_pipeline_first_deny_stops(pipeline, mock_policy_repo):
    mock_policy_repo.list_enabled.return_value = [
        _policy_model(
            name="deny-early",
            conditions=[{"type": "all", "rules": [{"field": "action", "operator": "equals", "value": "execute"}]}],
            actions={"action": "deny"},
        ),
        _policy_model(
            name="allow-late",
            conditions=[{"type": "all", "rules": [{"field": "resource_type", "operator": "equals", "value": "mission"}]}],
            actions={"action": "allow"},
        ),
    ]
    request = _make_request(action="execute")
    response = await pipeline.evaluate(request)
    assert response.denied
    # Only the first policy should be matched due to early stop
    assert response.matched_policies[0].policy_name == "deny-early"
    assert response.matched_policies[0].matched


# ---------------------------------------------------------------------------
# Pipeline: require_approval evaluated before stop
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_pipeline_require_approval(pipeline, mock_policy_repo):
    mock_policy_repo.list_enabled.return_value = [
        _policy_model(
            name="approval-needed",
            conditions=[{"type": "all", "rules": [{"field": "risk_level", "operator": "equals", "value": "high"}]}],
            actions={"action": "require_approval"},
        ),
    ]
    request = _make_request(risk_level="high")
    response = await pipeline.evaluate(request)
    assert response.requires_approval


# ---------------------------------------------------------------------------
# Pipeline: escalate
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_pipeline_escalate(pipeline, mock_policy_repo):
    mock_policy_repo.list_enabled.return_value = [
        _policy_model(
            name="escalate-critical",
            conditions=[{"type": "all", "rules": [{"field": "risk_level", "operator": "equals", "value": "critical"}]}],
            actions={"action": "escalate"},
        ),
    ]
    request = _make_request(risk_level="critical")
    response = await pipeline.evaluate(request)
    assert response.decision == GovernanceDecision.ESCALATE


# ---------------------------------------------------------------------------
# Pipeline: require_review
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_pipeline_require_review(pipeline, mock_policy_repo):
    mock_policy_repo.list_enabled.return_value = [
        _policy_model(
            name="review-needed",
            conditions=[{"type": "all", "rules": [{"field": "action", "operator": "equals", "value": "deploy"}]}],
            actions={"action": "require_review"},
        ),
    ]
    request = _make_request(action="deploy")
    response = await pipeline.evaluate(request)
    assert response.decision == GovernanceDecision.REQUIRE_REVIEW


# ---------------------------------------------------------------------------
# Pipeline: no matching policy defaults to allow
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_pipeline_no_policy_match_allows(pipeline, mock_policy_repo):
    mock_policy_repo.list_enabled.return_value = [
        _policy_model(
            name="irrelevant",
            conditions=[{"type": "all", "rules": [{"field": "action", "operator": "equals", "value": "deploy"}]}],
            actions={"action": "deny"},
        ),
    ]
    request = _make_request(action="execute")
    response = await pipeline.evaluate(request)
    assert response.allowed


# ---------------------------------------------------------------------------
# Pipeline: repo failure degrades to allow
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_pipeline_repo_failure_allows(pipeline, mock_repo_factory):
    mock_repo_factory.policy_repo = AsyncMock(side_effect=Exception("DB down"))
    pipeline._repo_factory = mock_repo_factory
    request = _make_request()
    response = await pipeline.evaluate(request)
    assert response.allowed
    assert response.message == "No matching policies"


# ---------------------------------------------------------------------------
# Pipeline: multi-policy with same conditions
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_pipeline_multi_policy_same_conditions(pipeline, mock_policy_repo):
    mock_policy_repo.list_enabled.return_value = [
        _policy_model(
            name="policy-a",
            conditions=[{"type": "all", "rules": [{"field": "action", "operator": "equals", "value": "execute"}]}],
            actions={"action": "allow"},
        ),
        _policy_model(
            name="policy-b",
            conditions=[{"type": "all", "rules": [{"field": "action", "operator": "equals", "value": "execute"}]}],
            actions={"action": "allow"},
        ),
    ]
    request = _make_request(action="execute")
    response = await pipeline.evaluate(request)
    assert response.allowed
    assert len(response.matched_policies) == 2


# ---------------------------------------------------------------------------
# Pipeline: evaluate_for_mission / evaluate_for_execution / evaluate_for_connector
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_pipeline_evaluate_for_mission(pipeline, mock_policy_repo):
    mock_policy_repo.list_enabled.return_value = []
    response = await pipeline.evaluate_for_mission(_make_request())
    assert response.allowed


@pytest.mark.asyncio
async def test_pipeline_evaluate_for_execution(pipeline, mock_policy_repo):
    mock_policy_repo.list_enabled.return_value = []
    response = await pipeline.evaluate_for_execution(_make_request())
    assert response.allowed


@pytest.mark.asyncio
async def test_pipeline_evaluate_for_connector(pipeline, mock_policy_repo):
    mock_policy_repo.list_enabled.return_value = []
    response = await pipeline.evaluate_for_connector(_make_request())
    assert response.allowed


# ---------------------------------------------------------------------------
# Policy evaluation engine: condition blocks
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_evaluator_all_block_all_match(pipeline, mock_policy_repo):
    mock_policy_repo.list_enabled.return_value = [
        _policy_model(
            name="all-block",
            conditions=[{
                "type": "all",
                "rules": [
                    {"field": "action", "operator": "equals", "value": "execute"},
                    {"field": "role", "operator": "equals", "value": "user"},
                ],
            }],
            actions={"action": "allow"},
        ),
    ]
    response = await pipeline.evaluate(_make_request(action="execute", role="user"))
    assert response.allowed


@pytest.mark.asyncio
async def test_evaluator_all_block_one_fails(pipeline, mock_policy_repo):
    mock_policy_repo.list_enabled.return_value = [
        _policy_model(
            name="all-block-fail",
            conditions=[{
                "type": "all",
                "rules": [
                    {"field": "action", "operator": "equals", "value": "execute"},
                    {"field": "role", "operator": "equals", "value": "admin"},
                ],
            }],
            actions={"action": "deny"},
        ),
    ]
    response = await pipeline.evaluate(_make_request(action="execute", role="user"))
    assert response.allowed  # policy didn't match


@pytest.mark.asyncio
async def test_evaluator_any_block(pipeline, mock_policy_repo):
    mock_policy_repo.list_enabled.return_value = [
        _policy_model(
            name="any-block",
            conditions=[{
                "type": "any",
                "rules": [
                    {"field": "role", "operator": "equals", "value": "admin"},
                    {"field": "role", "operator": "equals", "value": "user"},
                ],
            }],
            actions={"action": "allow"},
        ),
    ]
    response = await pipeline.evaluate(_make_request(role="user"))
    assert response.allowed


@pytest.mark.asyncio
async def test_evaluator_none_block(pipeline, mock_policy_repo):
    mock_policy_repo.list_enabled.return_value = [
        _policy_model(
            name="none-block",
            conditions=[{
                "type": "none",
                "rules": [
                    {"field": "role", "operator": "equals", "value": "admin"},
                    {"field": "role", "operator": "equals", "value": "superadmin"},
                ],
            }],
            actions={"action": "allow"},
        ),
    ]
    response = await pipeline.evaluate(_make_request(role="user"))
    assert response.allowed


# ---------------------------------------------------------------------------
# Policy evaluation engine: operators
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_evaluator_operator_contains(pipeline, mock_policy_repo):
    mock_policy_repo.list_enabled.return_value = [
        _policy_model(
            name="contains-op",
            conditions=[{"type": "all", "rules": [{"field": "resource_id", "operator": "contains", "value": "res"}]}],
            actions={"action": "allow"},
        ),
    ]
    response = await pipeline.evaluate(_make_request(resource_id="res-001"))
    assert response.allowed


@pytest.mark.asyncio
async def test_evaluator_operator_not_contains(pipeline, mock_policy_repo):
    mock_policy_repo.list_enabled.return_value = [
        _policy_model(
            name="not-contains",
            conditions=[{"type": "all", "rules": [{"field": "resource_id", "operator": "contains", "value": "prod"}]}],
            actions={"action": "deny"},
        ),
    ]
    response = await pipeline.evaluate(_make_request(resource_id="res-001"))
    assert response.allowed  # not matched -> allow


@pytest.mark.asyncio
async def test_evaluator_operator_in(pipeline, mock_policy_repo):
    mock_policy_repo.list_enabled.return_value = [
        _policy_model(
            name="in-op",
            conditions=[{"type": "all", "rules": [{"field": "action", "operator": "in", "value": ["execute", "deploy"]}]}],
            actions={"action": "allow"},
        ),
    ]
    response = await pipeline.evaluate(_make_request(action="execute"))
    assert response.allowed


@pytest.mark.asyncio
async def test_evaluator_operator_not_in(pipeline, mock_policy_repo):
    mock_policy_repo.list_enabled.return_value = [
        _policy_model(
            name="not-in-op",
            conditions=[{"type": "all", "rules": [{"field": "action", "operator": "not_in", "value": ["delete", "purge"]}]}],
            actions={"action": "allow"},
        ),
    ]
    response = await pipeline.evaluate(_make_request(action="execute"))
    assert response.allowed


@pytest.mark.asyncio
async def test_evaluator_operator_greater_than(pipeline, mock_policy_repo):
    mock_policy_repo.list_enabled.return_value = [
        _policy_model(
            name="risk-above",
            conditions=[{"type": "all", "rules": [{"field": "risk_level", "operator": "greater_than", "value": "3"}]}],
            actions={"action": "deny"},
        ),
    ]
    request = _make_request(risk_level="5")
    response = await pipeline.evaluate(request)
    assert response.denied


@pytest.mark.asyncio
async def test_evaluator_operator_less_than(pipeline, mock_policy_repo):
    mock_policy_repo.list_enabled.return_value = [
        _policy_model(
            name="risk-below",
            conditions=[{"type": "all", "rules": [{"field": "risk_level", "operator": "less_than", "value": "5"}]}],
            actions={"action": "allow"},
        ),
    ]
    request = _make_request(risk_level="medium")
    response = await pipeline.evaluate(request)
    assert response.allowed


@pytest.mark.asyncio
async def test_evaluator_operator_exists(pipeline, mock_policy_repo):
    mock_policy_repo.list_enabled.return_value = [
        _policy_model(
            name="exists-op",
            conditions=[{"type": "all", "rules": [{"field": "mission_id", "operator": "exists", "value": ""}]}],
            actions={"action": "allow"},
        ),
    ]
    response = await pipeline.evaluate(_make_request(mission_id="mis-001"))
    assert response.allowed


@pytest.mark.asyncio
async def test_evaluator_operator_not_exists(pipeline, mock_policy_repo):
    mock_policy_repo.list_enabled.return_value = [
        _policy_model(
            name="not-exists-op",
            conditions=[{"type": "all", "rules": [{"field": "execution_id", "operator": "not_exists", "value": ""}]}],
            actions={"action": "allow"},
        ),
    ]
    response = await pipeline.evaluate(_make_request())
    assert response.allowed


@pytest.mark.asyncio
async def test_evaluator_operator_matches(pipeline, mock_policy_repo):
    mock_policy_repo.list_enabled.return_value = [
        _policy_model(
            name="matches-op",
            conditions=[{"type": "all", "rules": [{"field": "resource_id", "operator": "matches", "value": "res-\\d+"}]}],
            actions={"action": "allow"},
        ),
    ]
    response = await pipeline.evaluate(_make_request(resource_id="res-001"))
    assert response.allowed


@pytest.mark.asyncio
async def test_evaluator_context_field(pipeline, mock_policy_repo):
    mock_policy_repo.list_enabled.return_value = [
        _policy_model(
            name="context-op",
            conditions=[{"type": "all", "rules": [{"field": "env", "operator": "equals", "value": "production"}]}],
            actions={"action": "deny"},
        ),
    ]
    request = _make_request(context={"env": "production"})
    response = await pipeline.evaluate(request)
    assert response.denied

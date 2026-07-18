from __future__ import annotations

import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest

from backend.governance.models import DecisionReasonCode, DecisionRequest, GovernanceDecision
from backend.governance.service import GovernanceService


@pytest.fixture
def mock_policy_repo():
    repo = AsyncMock()
    repo.list = AsyncMock(return_value=[])
    repo.list_enabled = AsyncMock(return_value=[])
    repo.list_by_category = AsyncMock(return_value=[])
    repo.get = AsyncMock(return_value=None)
    repo.create = AsyncMock()
    repo.update = AsyncMock()
    repo.delete = AsyncMock(return_value=True)
    repo.count = AsyncMock(return_value=0)
    return repo


@pytest.fixture
def mock_approval_repo():
    repo = AsyncMock()
    repo.create = AsyncMock()
    repo.get_by_request_id = AsyncMock(return_value=None)
    repo.list = AsyncMock(return_value=[])
    repo.list_by_status = AsyncMock(return_value=[])
    repo.update = AsyncMock()
    return repo


@pytest.fixture
def mock_repo_factory(mock_policy_repo, mock_approval_repo):
    factory = MagicMock()
    factory.policy_repo = AsyncMock(return_value=mock_policy_repo)
    factory.approval_request_repo = AsyncMock(return_value=mock_approval_repo)
    return factory


@pytest.fixture
def mock_pipeline():
    pipeline = AsyncMock()
    pipeline.evaluate = AsyncMock()
    return pipeline


@pytest.fixture
def mock_events():
    events = AsyncMock()
    events.publish = AsyncMock()
    return events


@pytest.fixture
def service(mock_pipeline, mock_events, mock_repo_factory):
    return GovernanceService(
        pipeline=mock_pipeline,
        events=mock_events,
        repo_factory=mock_repo_factory,
    )


def _make_request(**kwargs) -> DecisionRequest:
    return DecisionRequest(
        requester=kwargs.get("requester", "test-user"),
        user=kwargs.get("user", "test-user"),
        role=kwargs.get("role", "admin"),
        tenant=kwargs.get("tenant", ""),
        action=kwargs.get("action", "execute"),
        resource_type=kwargs.get("resource_type", "mission"),
        resource_id=kwargs.get("resource_id", "res-123"),
        risk_level=kwargs.get("risk_level", "low"),
        scope=kwargs.get("scope", ""),
        mission_type=kwargs.get("mission_type", "standard"),
        mission_id=kwargs.get("mission_id", "mis-123"),
        execution_id=kwargs.get("execution_id"),
        execution_type=kwargs.get("execution_type"),
        connector_type=kwargs.get("connector_type"),
        connector_capability=kwargs.get("connector_capability"),
        context=kwargs.get("context", {}),
    )


# ---------------------------------------------------------------------------
# Policy evaluation
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_evaluate_allowed(service, mock_pipeline, mock_events):
    from backend.governance.models import DecisionResponse
    mock_pipeline.evaluate.return_value = DecisionResponse(
        decision=GovernanceDecision.ALLOW,
        reason_code=DecisionReasonCode.POLICY_ALLOWED,
        message="Policy allowed",
        risk_level="low",
    )
    request = _make_request()
    response = await service.evaluate(request)
    assert response.allowed
    assert not response.denied
    assert response.message == "Policy allowed"
    assert mock_events.publish.called


@pytest.mark.asyncio
async def test_evaluate_denied(service, mock_pipeline, mock_events):
    from backend.governance.models import DecisionResponse
    mock_pipeline.evaluate.return_value = DecisionResponse(
        decision=GovernanceDecision.DENY,
        reason_code=DecisionReasonCode.POLICY_DENIED,
        message="Access denied by policy",
        risk_level="high",
    )
    request = _make_request()
    response = await service.evaluate(request)
    assert response.denied
    assert not response.allowed


@pytest.mark.asyncio
async def test_evaluate_require_approval(service, mock_pipeline, mock_events):
    from backend.governance.models import DecisionResponse
    mock_pipeline.evaluate.return_value = DecisionResponse(
        decision=GovernanceDecision.REQUIRE_APPROVAL,
        reason_code=DecisionReasonCode.APPROVAL_REQUIRED,
        message="Approval required",
        risk_level="medium",
    )
    request = _make_request()
    response = await service.evaluate(request)
    assert response.requires_approval
    assert not response.allowed
    assert not response.denied


@pytest.mark.asyncio
async def test_evaluate_require_review(service, mock_pipeline, mock_events):
    from backend.governance.models import DecisionResponse
    mock_pipeline.evaluate.return_value = DecisionResponse(
        decision=GovernanceDecision.REQUIRE_REVIEW,
        reason_code=DecisionReasonCode.APPROVAL_REQUIRED,
        message="Review required",
        risk_level="high",
    )
    request = _make_request()
    response = await service.evaluate(request)
    assert response.decision == GovernanceDecision.REQUIRE_REVIEW


@pytest.mark.asyncio
async def test_evaluate_escalated(service, mock_pipeline, mock_events):
    from backend.governance.models import DecisionResponse
    mock_pipeline.evaluate.return_value = DecisionResponse(
        decision=GovernanceDecision.ESCALATE,
        reason_code=DecisionReasonCode.ESCALATED,
        message="Escalated to human reviewer",
        risk_level="critical",
    )
    request = _make_request()
    response = await service.evaluate(request)
    assert response.decision == GovernanceDecision.ESCALATE


@pytest.mark.asyncio
async def test_evaluate_mission_delegates_to_evaluate(service, mock_pipeline):
    from backend.governance.models import DecisionResponse
    mock_pipeline.evaluate.return_value = DecisionResponse(
        decision=GovernanceDecision.ALLOW, reason_code=DecisionReasonCode.POLICY_ALLOWED, message="ok", risk_level="low"
    )
    request = _make_request(mission_id="mis-999")
    response = await service.evaluate_mission(request)
    assert response.allowed
    mock_pipeline.evaluate.assert_called_with(request)


@pytest.mark.asyncio
async def test_evaluate_execution_delegates_to_evaluate(service, mock_pipeline):
    from backend.governance.models import DecisionResponse
    mock_pipeline.evaluate.return_value = DecisionResponse(
        decision=GovernanceDecision.ALLOW, reason_code=DecisionReasonCode.POLICY_ALLOWED, message="ok", risk_level="low"
    )
    request = _make_request(execution_id="exec-999")
    response = await service.evaluate_execution(request)
    assert response.allowed
    mock_pipeline.evaluate.assert_called_with(request)


@pytest.mark.asyncio
async def test_evaluate_connector_delegates_to_evaluate(service, mock_pipeline):
    from backend.governance.models import DecisionResponse
    mock_pipeline.evaluate.return_value = DecisionResponse(
        decision=GovernanceDecision.ALLOW, reason_code=DecisionReasonCode.POLICY_ALLOWED, message="ok", risk_level="low"
    )
    request = _make_request(connector_type="github", connector_capability="read")
    response = await service.evaluate_connector(request)
    assert response.allowed
    mock_pipeline.evaluate.assert_called_with(request)


# ---------------------------------------------------------------------------
# Policy CRUD
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_list_policies(service, mock_policy_repo):
    mock_policy_repo.list.return_value = []
    result = await service.list_policies()
    assert result == []


@pytest.mark.asyncio
async def test_list_policies_enabled_only(service, mock_policy_repo):
    mock_policy_repo.list_enabled.return_value = []
    result = await service.list_policies(enabled_only=True)
    assert result == []
    mock_policy_repo.list_enabled.assert_called_once()


@pytest.mark.asyncio
async def test_list_policies_by_category(service, mock_policy_repo):
    mock_policy_repo.list_by_category.return_value = []
    result = await service.list_policies(category="security")
    assert result == []
    mock_policy_repo.list_by_category.assert_called_once_with("security")


@pytest.mark.asyncio
async def test_get_policy_not_found(service, mock_policy_repo):
    mock_policy_repo.get.return_value = None
    result = await service.get_policy(str(uuid.uuid4()))
    assert result is None


@pytest.mark.asyncio
async def test_get_policy_found(service, mock_policy_repo):
    pid = uuid.uuid4()
    from datetime import datetime, timezone
    model = MagicMock()
    model.id = pid
    model.name = "test-policy"
    model.description = "desc"
    model.category = "security"
    model.severity = "high"
    model.enabled = True
    model.conditions = {}
    model.actions = {"action": "deny"}
    model.created_at = datetime.now(timezone.utc)
    model.metadata_ = {}
    mock_policy_repo.get.return_value = model
    result = await service.get_policy(str(pid))
    assert result is not None
    assert result["name"] == "test-policy"
    assert result["category"] == "security"


@pytest.mark.asyncio
async def test_create_policy(service, mock_policy_repo):
    pid = uuid.uuid4()
    model = MagicMock()
    model.id = pid
    model.name = "new-policy"
    model.category = "general"
    model.severity = "medium"
    model.enabled = True
    model.conditions = {}
    model.actions = {"action": "allow"}
    model.description = ""
    model.created_at = datetime.now(timezone.utc)
    model.metadata_ = {}
    mock_policy_repo.create.return_value = model
    result = await service.create_policy(name="new-policy")
    assert result["name"] == "new-policy"
    assert result["category"] == "general"
    mock_policy_repo.create.assert_called_once()


@pytest.mark.asyncio
async def test_update_policy(service, mock_policy_repo):
    pid = uuid.uuid4()
    mock_policy_repo.get.return_value = MagicMock(
        id=pid, name="old-name", description="", category="general",
        severity="medium", enabled=True, conditions={}, actions={},
    )
    mock_policy_repo.update.return_value = MagicMock(
        id=pid, name="updated-name", description="", category="general",
        severity="medium", enabled=True, conditions={}, actions={},
    )
    result = await service.update_policy(str(pid), {"name": "updated-name"})
    assert result["updated"] is True


@pytest.mark.asyncio
async def test_update_policy_not_found(service, mock_policy_repo):
    mock_policy_repo.get.return_value = None
    result = await service.update_policy(str(uuid.uuid4()), {"name": "x"})
    assert result is None


@pytest.mark.asyncio
async def test_delete_policy(service, mock_policy_repo):
    mock_policy_repo.delete.return_value = True
    result = await service.delete_policy(str(uuid.uuid4()))
    assert result is True


@pytest.mark.asyncio
async def test_delete_policy_not_found(service, mock_policy_repo):
    mock_policy_repo.delete.side_effect = Exception("not found")
    result = await service.delete_policy(str(uuid.uuid4()))
    assert result is False


# ---------------------------------------------------------------------------
# Approval management
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_request_approval(service, mock_approval_repo):
    mock_approval_repo.create.return_value = MagicMock(
        id=uuid.uuid4(), request_id="gov-abc123",
        requester="test-user", resource_type="mission", resource_id="res-123",
        action="deploy", reason="Need approval", status="pending",
        reviewers=["reviewer1"], approved_by=None, approved_at=None,
        created_at=datetime.now(timezone.utc),
    )
    request = _make_request(action="deploy", context={"reason": "Need approval"})
    result = await service.request_approval(request, reviewers=["reviewer1"])
    assert result is not None
    assert result["status"] == "pending"
    assert result["requester"] == "test-user"


@pytest.mark.asyncio
async def test_approve(service, mock_approval_repo):
    mock_approval_repo.get_by_request_id.return_value = MagicMock(
        id=uuid.uuid4(), request_id="gov-abc", requester="user1",
        resource_type="mission", resource_id="res-1", action="deploy",
        reason="", status="pending", reviewers=[], approved_by=None, approved_at=None,
    )
    mock_approval_repo.update.return_value = MagicMock(
        request_id="gov-abc", status="approved", approved_by="approver1", approved_at="now",
    )
    result = await service.approve("gov-abc", "approver1")
    assert result is not None
    assert result["status"] == "approved"


@pytest.mark.asyncio
async def test_approve_not_pending(service, mock_approval_repo):
    mock_approval_repo.get_by_request_id.return_value = MagicMock(status="approved")
    result = await service.approve("gov-abc", "approver1")
    assert result is None


@pytest.mark.asyncio
async def test_reject(service, mock_approval_repo):
    mock_approval_repo.get_by_request_id.return_value = MagicMock(
        id=uuid.uuid4(), request_id="gov-abc", requester="user1",
        resource_type="mission", resource_id="res-1", action="deploy",
        reason="", status="pending", reviewers=[], approved_by=None, approved_at=None,
    )
    mock_approval_repo.update.return_value = MagicMock(
        request_id="gov-abc", status="rejected", approved_by="reviewer1", approved_at="now",
    )
    result = await service.reject("gov-abc", "reviewer1")
    assert result is not None
    assert result["status"] == "rejected"


@pytest.mark.asyncio
async def test_reject_not_found(service, mock_approval_repo):
    mock_approval_repo.get_by_request_id.return_value = None
    result = await service.reject("gov-xxx", "reviewer1")
    assert result is None


@pytest.mark.asyncio
async def test_list_approval_requests(service, mock_approval_repo):
    mock_approval_repo.list.return_value = []
    result = await service.list_approval_requests()
    assert result == []


@pytest.mark.asyncio
async def test_list_approval_requests_by_status(service, mock_approval_repo):
    mock_approval_repo.list_by_status.return_value = []
    result = await service.list_approval_requests(status="pending")
    assert result == []
    mock_approval_repo.list_by_status.assert_called_once_with("pending", limit=50, offset=0)


# ---------------------------------------------------------------------------
# Health
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_health(service, mock_policy_repo, mock_approval_repo):
    mock_policy_repo.count.return_value = 5
    mock_approval_repo.list_by_status.return_value = [MagicMock()]
    result = await service.health()
    assert result["status"] == "healthy"
    assert result["policy_count"] == 5

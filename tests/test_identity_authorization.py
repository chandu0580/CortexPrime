from __future__ import annotations

import pytest

from backend.identity.interfaces.authorization import AuthorizationRequest, AuthorizationResult
from backend.identity.authorization.rbac import RBACProvider, BUILTIN_ROLES
from backend.identity.authorization.abac import ABACEvaluator, ABACRule, AttributeContext, EqualsCondition, InCondition
from backend.identity.authorization.permission_evaluator import DefaultPermissionEvaluator


class TestRBACProvider:
    @pytest.fixture
    def rbac(self):
        return RBACProvider()

    @pytest.mark.asyncio
    async def test_admin_can_admin_users(self, rbac):
        result = await rbac.authorize(
            AuthorizationRequest(user_id="admin-1", role="admin", action="admin", resource="users")
        )
        assert result.allowed is True

    @pytest.mark.asyncio
    async def test_viewer_cannot_write(self, rbac):
        result = await rbac.authorize(
            AuthorizationRequest(user_id="viewer-1", role="viewer", action="write", resource="missions")
        )
        assert result.allowed is False

    @pytest.mark.asyncio
    async def test_owner_can_do_anything(self, rbac):
        for action in ("read", "write", "admin"):
            result = await rbac.authorize(
                AuthorizationRequest(user_id="owner-1", role="owner", action=action, resource="*")
            )
            assert result.allowed is True

    @pytest.mark.asyncio
    async def test_member_can_write_projects(self, rbac):
        result = await rbac.authorize(
            AuthorizationRequest(user_id="member-1", role="member", action="write", resource="projects")
        )
        assert result.allowed is True

    @pytest.mark.asyncio
    async def test_member_cannot_write_connectors(self, rbac):
        result = await rbac.authorize(
            AuthorizationRequest(user_id="member-1", role="member", action="write", resource="connectors")
        )
        assert result.allowed is False

    @pytest.mark.asyncio
    async def test_unknown_role_is_rejected(self, rbac):
        result = await rbac.authorize(
            AuthorizationRequest(user_id="x", role="superuser", action="read", resource="*")
        )
        assert result.allowed is False

    @pytest.mark.asyncio
    async def test_get_permissions_returns_list(self, rbac):
        perms = await rbac.get_permissions("admin")
        assert len(perms) > 0
        assert "admin:users" in perms
        assert "read:*" in perms


class TestABACEvaluator:
    @pytest.fixture
    def abac(self):
        return ABACEvaluator()

    @pytest.mark.asyncio
    async def test_allow_when_condition_met(self, abac):
        abac.add_rule(ABACRule(
            name="allow-prod-deploy",
            effect="allow",
            conditions=[
                EqualsCondition("environment", "production"),
                InCondition("role", ["admin", "operator"]),
            ],
        ))
        result = await abac.evaluate(AttributeContext(
            user_attributes={"role": "admin"},
            resource_attributes={"environment": "production"},
        ))
        assert result == "allow"

    @pytest.mark.asyncio
    async def test_deny_when_condition_not_met(self, abac):
        abac.add_rule(ABACRule(
            name="deny-dev-deploy",
            effect="deny",
            conditions=[
                EqualsCondition("environment", "development"),
            ],
        ))
        result = await abac.evaluate(AttributeContext(
            user_attributes={"role": "admin"},
            resource_attributes={"environment": "production"},
        ))
        assert result is None

    @pytest.mark.asyncio
    async def test_remove_rule(self, abac):
        abac.add_rule(ABACRule(name="test-rule", effect="allow", conditions=[]))
        assert len(abac._rules) == 1
        abac.remove_rule("test-rule")
        assert len(abac._rules) == 0


class TestPermissionEvaluator:
    @pytest.fixture
    def evaluator(self):
        return DefaultPermissionEvaluator(RBACProvider())

    @pytest.mark.asyncio
    async def test_has_permission(self, evaluator):
        assert await evaluator.has_permission("user-1", "read", "projects") is True
        assert await evaluator.has_permission("user-1", "write", "billing") is False

    @pytest.mark.asyncio
    async def test_has_all_permissions(self, evaluator):
        assert await evaluator.has_all_permissions("user-1", ["read", "write"], "projects") is True
        assert await evaluator.has_all_permissions("user-1", ["read", "admin"], "users") is False

    @pytest.mark.asyncio
    async def test_filter_by_permission(self, evaluator):
        allowed = await evaluator.filter_by_permission("user-1", "write", ["projects", "billing", "missions"])
        assert "projects" in allowed
        assert "billing" not in allowed
        assert "missions" in allowed

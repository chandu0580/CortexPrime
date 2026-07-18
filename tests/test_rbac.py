from __future__ import annotations

import os
import sys
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from backend.auth.rbac import PERMISSIONS, check_permission


class TestPermissionsStructure:
    def test_has_expected_roles(self):
        assert set(PERMISSIONS.keys()) == {"member", "admin", "owner"}

    def test_member_permissions(self):
        member = PERMISSIONS["member"]
        assert "read" in member
        assert "write" in member
        assert "admin" in member
        assert "projects" in member["read"]
        assert "missions" in member["read"]
        assert "projects" in member["write"]
        assert member["admin"] == []

    def test_admin_permissions(self):
        admin = PERMISSIONS["admin"]
        assert admin["read"] == ["*"]
        assert "users" in admin["admin"]

    def test_owner_permissions(self):
        owner = PERMISSIONS["owner"]
        assert owner["read"] == ["*"]
        assert owner["write"] == ["*"]
        assert owner["admin"] == ["*"]


class TestCheckPermission:
    def test_member_can_read_projects(self):
        assert check_permission("member", "read", "projects") is True

    def test_member_can_read_missions(self):
        assert check_permission("member", "read", "missions") is True

    def test_member_cannot_read_settings(self):
        assert check_permission("member", "read", "settings") is False

    def test_member_can_write_projects(self):
        assert check_permission("member", "write", "projects") is True

    def test_member_cannot_write_missions(self):
        assert check_permission("member", "write", "missions") is False

    def test_member_cannot_admin_users(self):
        assert check_permission("member", "admin", "users") is False

    def test_admin_can_read_anything(self):
        assert check_permission("admin", "read", "anything_at_all") is True

    def test_admin_can_write_settings(self):
        assert check_permission("admin", "write", "settings") is True

    def test_admin_can_admin_users(self):
        assert check_permission("admin", "admin", "users") is True

    def test_admin_cannot_admin_billing(self):
        assert check_permission("admin", "admin", "billing") is False

    def test_owner_can_do_anything(self):
        assert check_permission("owner", "read", "anything") is True
        assert check_permission("owner", "write", "anything") is True
        assert check_permission("owner", "admin", "anything") is True

    def test_unknown_role_returns_false(self):
        assert check_permission("superadmin", "read", "projects") is False

    def test_empty_role_returns_false(self):
        assert check_permission("", "read", "projects") is False

    def test_unknown_action_returns_false(self):
        assert check_permission("admin", "delete", "projects") is False

    def test_member_analytics_read(self):
        assert check_permission("member", "read", "analytics") is True

    def test_member_executions_read(self):
        assert check_permission("member", "read", "executions") is True

    def test_admin_connectors_write(self):
        assert check_permission("admin", "write", "connectors") is True

from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from backend.auth.tenant import Tenant, TenantManager, TenantUser


@pytest.fixture
def temp_storage():
    with tempfile.TemporaryDirectory() as tmp:
        yield str(tmp)


@pytest.fixture
def manager(temp_storage):
    return TenantManager(storage_path=temp_storage)


class TestTenantDataclass:
    def test_create_tenant_dataclass(self):
        t = Tenant(tenant_id="t1", name="Acme", slug="acme")
        assert t.tenant_id == "t1"
        assert t.name == "Acme"
        assert t.slug == "acme"
        assert t.domain is None
        assert t.plan == "free"
        assert t.is_active is True
        assert t.settings == {}
        assert isinstance(t.created_at, str)

    def test_tenant_with_all_fields(self):
        t = Tenant(
            tenant_id="t2", name="Corp", slug="corp",
            domain="corp.com", plan="enterprise",
            is_active=False, settings={"theme": "dark"},
        )
        assert t.domain == "corp.com"
        assert t.plan == "enterprise"
        assert t.is_active is False
        assert t.settings == {"theme": "dark"}


class TestTenantUserDataclass:
    def test_create_tenant_user_dataclass(self):
        u = TenantUser(user_id="u1", tenant_id="t1", email="a@b.com")
        assert u.user_id == "u1"
        assert u.tenant_id == "t1"
        assert u.email == "a@b.com"
        assert u.role == "member"
        assert u.is_active is True
        assert u.permissions == []
        assert isinstance(u.created_at, str)

    def test_tenant_user_with_all_fields(self):
        u = TenantUser(
            user_id="u2", tenant_id="t2", email="b@b.com",
            role="admin", is_active=False, permissions=["read"],
        )
        assert u.role == "admin"
        assert u.is_active is False
        assert u.permissions == ["read"]


class TestTenantManager:
    def test_create_tenant(self, manager):
        t = manager.create_tenant(name="Test", slug="test")
        assert t.name == "Test"
        assert t.slug == "test"
        assert t.tenant_id.startswith("tenant-")
        assert t.is_active is True
        assert t.plan == "free"

    def test_get_tenant(self, manager):
        created = manager.create_tenant(name="Foo", slug="foo")
        fetched = manager.get_tenant(created.tenant_id)
        assert fetched is not None
        assert fetched.name == "Foo"

    def test_get_tenant_nonexistent(self, manager):
        assert manager.get_tenant("nonexistent") is None

    def test_get_tenant_by_slug(self, manager):
        manager.create_tenant(name="Bar", slug="bar")
        fetched = manager.get_tenant_by_slug("bar")
        assert fetched is not None
        assert fetched.name == "Bar"

    def test_get_tenant_by_slug_nonexistent(self, manager):
        assert manager.get_tenant_by_slug("nope") is None

    def test_list_tenants(self, manager):
        manager.create_tenant(name="A", slug="a")
        manager.create_tenant(name="B", slug="b")
        assert len(manager.list_tenants()) == 2

    def test_list_tenants_empty(self, manager):
        assert manager.list_tenants() == []

    def test_add_user(self, manager):
        t = manager.create_tenant(name="T", slug="t")
        u = manager.add_user(t.tenant_id, "user@test.com", role="admin")
        assert u is not None
        assert u.email == "user@test.com"
        assert u.role == "admin"
        assert u.tenant_id == t.tenant_id
        assert u.user_id.startswith("user-")

    def test_add_user_nonexistent_tenant(self, manager):
        u = manager.add_user("no-such-tenant", "test@test.com")
        assert u is None

    def test_get_users(self, manager):
        t = manager.create_tenant(name="T", slug="t")
        manager.add_user(t.tenant_id, "a@test.com")
        manager.add_user(t.tenant_id, "b@test.com")
        users = manager.get_users(t.tenant_id)
        assert len(users) == 2

    def test_get_users_empty(self, manager):
        assert manager.get_users("nonexistent") == []

    def test_get_user_by_email(self, manager):
        t = manager.create_tenant(name="T", slug="t")
        manager.add_user(t.tenant_id, "find@test.com")
        u = manager.get_user_by_email("find@test.com")
        assert u is not None
        assert u.email == "find@test.com"

    def test_get_user_by_email_nonexistent(self, manager):
        assert manager.get_user_by_email("nobody@test.com") is None

    def test_update_user_role(self, manager):
        t = manager.create_tenant(name="T", slug="t")
        u = manager.add_user(t.tenant_id, "u@test.com", role="member")
        result = manager.update_user_role(t.tenant_id, u.user_id, "admin")
        assert result is True
        updated = manager.get_user_by_email("u@test.com")
        assert updated is not None
        assert updated.role == "admin"

    def test_update_user_role_nonexistent_user(self, manager):
        t = manager.create_tenant(name="T", slug="t")
        result = manager.update_user_role(t.tenant_id, "no-such-user", "admin")
        assert result is False

    def test_update_user_role_nonexistent_tenant(self, manager):
        result = manager.update_user_role("no-tenant", "user1", "admin")
        assert result is False

    def test_deactivate_tenant(self, manager):
        t = manager.create_tenant(name="T", slug="t")
        result = manager.deactivate_tenant(t.tenant_id)
        assert result is True
        fetched = manager.get_tenant(t.tenant_id)
        assert fetched is not None
        assert fetched.is_active is False

    def test_deactivate_nonexistent_tenant(self, manager):
        result = manager.deactivate_tenant("no-such-tenant")
        assert result is False

    def test_save_load_round_trip(self, temp_storage):
        m1 = TenantManager(storage_path=temp_storage)
        t = m1.create_tenant(name="Persist", slug="persist")
        m1.add_user(t.tenant_id, "p@test.com")

        m2 = TenantManager(storage_path=temp_storage)
        assert len(m2.list_tenants()) == 1
        loaded = m2.get_tenant(t.tenant_id)
        assert loaded is not None
        assert loaded.name == "Persist"
        users = m2.get_users(t.tenant_id)
        assert len(users) == 1
        assert users[0].email == "p@test.com"

    def test_create_tenant_with_domain_and_plan(self, manager):
        t = manager.create_tenant(name="Biz", slug="biz", domain="biz.com", plan="enterprise")
        assert t.domain == "biz.com"
        assert t.plan == "enterprise"

    def test_add_user_default_role(self, manager):
        t = manager.create_tenant(name="T", slug="t")
        u = manager.add_user(t.tenant_id, "default@test.com")
        assert u.role == "member"

    def test_get_tenant_by_slug_multiple(self, manager):
        manager.create_tenant(name="A", slug="same")
        manager.create_tenant(name="B", slug="same")
        fetched = manager.get_tenant_by_slug("same")
        assert fetched is not None
        assert fetched.name == "A"

    def test_get_user_by_email_multiple_tenants(self, manager):
        t1 = manager.create_tenant(name="T1", slug="t1")
        t2 = manager.create_tenant(name="T2", slug="t2")
        manager.add_user(t1.tenant_id, "shared@test.com")
        manager.add_user(t2.tenant_id, "shared@test.com")
        u = manager.get_user_by_email("shared@test.com")
        assert u is not None
        assert u.tenant_id == t1.tenant_id

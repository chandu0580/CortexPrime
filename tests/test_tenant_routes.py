from __future__ import annotations

import os
import sys
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from backend.api.tenant_routes import router
from backend.auth.dependencies import require_admin
from backend.auth.tenant import Tenant, TenantUser


def _make_tenant(**kwargs) -> Tenant:
    defaults = dict(tenant_id="t-1", name="Test", slug="test", domain=None, plan="free", is_active=True, settings={}, created_at="2025-01-01T00:00:00")
    defaults.update(kwargs)
    return Tenant(**defaults)


def _make_user(**kwargs) -> TenantUser:
    defaults = dict(user_id="u-1", tenant_id="t-1", email="user@test.com", role="member", is_active=True, permissions=[], created_at="2025-01-01T00:00:00")
    defaults.update(kwargs)
    return TenantUser(**defaults)


@pytest.fixture
def mock_tenant_manager():
    with patch("backend.api.tenant_routes.get_tenant_manager") as mock_get:
        tm = MagicMock()
        tm.create_tenant.return_value = _make_tenant()
        tm.get_tenant.return_value = _make_tenant()
        tm.get_tenant_by_slug.return_value = None
        tm.list_tenants.return_value = [_make_tenant()]
        tm.add_user.return_value = _make_user()
        tm.get_users.return_value = [_make_user()]
        tm.get_user_by_email.return_value = None
        tm.update_user_role.return_value = True
        tm.deactivate_tenant.return_value = True
        mock_get.return_value = tm
        yield tm


@pytest.fixture
def client(mock_tenant_manager):
    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[require_admin] = lambda: {"sub": "admin", "role": "admin"}
    yield TestClient(app, raise_server_exceptions=False)
    app.dependency_overrides.clear()


class TestTenantRoutesCreate:
    def test_create_tenant(self, client, mock_tenant_manager):
        res = client.post("/api/tenants", json={"name": "Acme", "slug": "acme"})
        assert res.status_code == 201
        data = res.json()
        assert data["name"] == "Test"
        assert data["slug"] == "test"
        assert "tenant_id" in data

    def test_create_tenant_calls_manager(self, client, mock_tenant_manager):
        client.post("/api/tenants", json={"name": "Acme", "slug": "acme"})
        mock_tenant_manager.create_tenant.assert_called_once_with(name="Acme", slug="acme", domain=None, plan="free")

    def test_create_tenant_with_domain_and_plan(self, client, mock_tenant_manager):
        client.post("/api/tenants", json={"name": "Biz", "slug": "biz", "domain": "biz.com", "plan": "enterprise"})
        mock_tenant_manager.create_tenant.assert_called_once_with(name="Biz", slug="biz", domain="biz.com", plan="enterprise")

    def test_create_tenant_duplicate_slug(self, client, mock_tenant_manager):
        mock_tenant_manager.get_tenant_by_slug.return_value = _make_tenant()
        res = client.post("/api/tenants", json={"name": "Dup", "slug": "test"})
        assert res.status_code == 409
        assert "already exists" in res.json()["detail"]

    def test_create_tenant_invalid_slug(self, client):
        res = client.post("/api/tenants", json={"name": "Bad", "slug": "INVALID SLUG!"})
        assert res.status_code == 422

    def test_create_tenant_empty_name(self, client):
        res = client.post("/api/tenants", json={"name": "", "slug": "empty"})
        assert res.status_code == 422


class TestTenantRoutesList:
    def test_list_tenants(self, client, mock_tenant_manager):
        res = client.get("/api/tenants")
        assert res.status_code == 200
        data = res.json()
        assert isinstance(data, list)
        assert len(data) == 1

    def test_list_tenants_calls_manager(self, client, mock_tenant_manager):
        client.get("/api/tenants")
        mock_tenant_manager.list_tenants.assert_called_once()


class TestTenantRoutesGet:
    def test_get_tenant(self, client, mock_tenant_manager):
        res = client.get("/api/tenants/t-1")
        assert res.status_code == 200
        data = res.json()
        assert data["tenant_id"] == "t-1"

    def test_get_tenant_calls_manager(self, client, mock_tenant_manager):
        client.get("/api/tenants/t-1")
        mock_tenant_manager.get_tenant.assert_called_once_with("t-1")

    def test_get_tenant_not_found(self, client, mock_tenant_manager):
        mock_tenant_manager.get_tenant.return_value = None
        res = client.get("/api/tenants/nonexistent")
        assert res.status_code == 404


class TestTenantRoutesUsers:
    def test_add_user(self, client, mock_tenant_manager):
        res = client.post("/api/tenants/t-1/users", json={"email": "new@test.com"})
        assert res.status_code == 201
        data = res.json()
        assert data["email"] == "user@test.com"

    def test_add_user_calls_manager(self, client, mock_tenant_manager):
        client.post("/api/tenants/t-1/users", json={"email": "new@test.com", "role": "admin"})
        mock_tenant_manager.add_user.assert_called_once_with("t-1", "new@test.com", "admin")

    def test_add_user_tenant_not_found(self, client, mock_tenant_manager):
        mock_tenant_manager.get_tenant.return_value = None
        res = client.post("/api/tenants/nonexistent/users", json={"email": "u@test.com"})
        assert res.status_code == 404

    def test_add_user_duplicate_email(self, client, mock_tenant_manager):
        mock_tenant_manager.get_user_by_email.return_value = _make_user()
        res = client.post("/api/tenants/t-1/users", json={"email": "user@test.com"})
        assert res.status_code == 409
        assert "already exists" in res.json()["detail"]

    def test_add_user_fails(self, client, mock_tenant_manager):
        mock_tenant_manager.add_user.return_value = None
        res = client.post("/api/tenants/t-1/users", json={"email": "fail@test.com"})
        assert res.status_code == 400

    def test_list_users(self, client, mock_tenant_manager):
        res = client.get("/api/tenants/t-1/users")
        assert res.status_code == 200
        data = res.json()
        assert isinstance(data, list)
        assert len(data) == 1

    def test_list_users_tenant_not_found(self, client, mock_tenant_manager):
        mock_tenant_manager.get_tenant.return_value = None
        res = client.get("/api/tenants/nonexistent/users")
        assert res.status_code == 404

    def test_update_user_role(self, client, mock_tenant_manager):
        res = client.patch("/api/tenants/t-1/users/u-1", json={"role": "admin"})
        assert res.status_code == 200
        data = res.json()
        assert data["user_id"] == "u-1"

    def test_update_user_role_not_found(self, client, mock_tenant_manager):
        mock_tenant_manager.get_tenant.return_value = None
        res = client.patch("/api/tenants/nonexistent/users/u-1", json={"role": "admin"})
        assert res.status_code == 404

    def test_update_user_role_user_not_found(self, client, mock_tenant_manager):
        mock_tenant_manager.update_user_role.return_value = False
        res = client.patch("/api/tenants/t-1/users/nonexistent", json={"role": "admin"})
        assert res.status_code == 404


class TestTenantRoutesDeactivate:
    def test_deactivate_tenant(self, client, mock_tenant_manager):
        res = client.post("/api/tenants/t-1/deactivate")
        assert res.status_code == 200
        data = res.json()
        assert data["tenant_id"] == "t-1"

    def test_deactivate_tenant_not_found(self, client, mock_tenant_manager):
        mock_tenant_manager.get_tenant.return_value = None
        res = client.post("/api/tenants/nonexistent/deactivate")
        assert res.status_code == 404

    def test_deactivate_already_inactive(self, client, mock_tenant_manager):
        mock_tenant_manager.get_tenant.return_value = _make_tenant(is_active=False)
        res = client.post("/api/tenants/t-1/deactivate")
        assert res.status_code == 400
        assert "already inactive" in res.json()["detail"]

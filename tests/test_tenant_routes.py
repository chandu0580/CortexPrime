"""The V1 tenant routes after retirement — Phase 10.11 (ADR-104).

What changed
------------
This module used to test these routes as a working tenant and membership API:
create a tenant, add a user, change a role, deactivate. Phases 10.10 and 10.11
refused all four, for two different reasons that are worth keeping straight:

* **tenant** mutation is refused because tenant administration is out-of-band —
  the authority grammar is capability+environment scoped and a tenant is
  neither, so there is no way to express "may create a tenant" without
  inventing an authority;
* **membership** mutation is refused because it had become a *silent no-op*:
  it wrote ``tenant_users.json``, which stopped being authoritative in Phase
  10.9, so an operator received 201 and the person got nothing at all.

The reads were repointed at the durable stores rather than removed, because a
V1 client asking "who is in my tenant" deserves the real answer.

So the tests for the removed behaviour are gone, and what remains guards the
refusals, the scoping, and that the reads no longer touch a file.
"""

from __future__ import annotations

import ast
import inspect

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.api import tenant_routes


@pytest.fixture
def client(monkeypatch):
    """The router with authentication stubbed to a tenant-A admin.

    Authentication is not what these tests are about; the guard being exercised
    is the tenant scoping *after* a caller is admitted.
    """
    app = FastAPI()
    app.dependency_overrides = {}
    app.include_router(tenant_routes.router)

    from backend.auth import dependencies

    async def _admin():
        return {"sub": "admin@example.test", "role": "admin",
                "tenant_id": "tenant-aaa", "user_role": "admin"}

    app.dependency_overrides[dependencies.require_admin] = _admin
    return TestClient(app, raise_server_exceptions=False)


class TestTenantMutationIsRefused:
    """Out-of-band by design. Never repointed at the durable store."""

    def test_create_is_refused(self, client):
        r = client.post("/api/tenants",
                        json={"name": "X", "slug": "x"})
        assert r.status_code == 403
        assert "out-of-band" in r.json()["detail"]

    def test_deactivate_is_refused(self, client):
        r = client.post("/api/tenants/tenant-aaa/deactivate")
        assert r.status_code == 403
        assert "out-of-band" in r.json()["detail"]


class TestMembershipMutationIsRefused:
    """These returned 201 and granted nothing. Refusing is the honest answer."""

    def test_add_user_is_refused_and_names_the_governed_route(self, client):
        r = client.post("/api/tenants/tenant-aaa/users",
                        json={"email": "n@example.test", "role": "member"})
        assert r.status_code == 403
        detail = r.json()["detail"]
        assert "/api/v1/tenants/members" in detail
        assert "granted nothing" in detail

    def test_update_role_is_refused(self, client):
        r = client.patch("/api/tenants/tenant-aaa/users/user-1",
                         json={"role": "owner"})
        assert r.status_code == 403
        assert "/api/v1/tenants/members" in r.json()["detail"]


class TestCrossTenantStaysRefused:
    """Phase 10.9's guard, still holding after the rewrite.

    404 rather than 403 deliberately: a tenant may not learn another exists.
    """

    @pytest.mark.parametrize("call", [
        lambda c: c.get("/api/tenants/tenant-other"),
        lambda c: c.post("/api/tenants/tenant-other/users",
                         json={"email": "x@y.test", "role": "member"}),
        lambda c: c.get("/api/tenants/tenant-other/users"),
        lambda c: c.patch("/api/tenants/tenant-other/users/u",
                          json={"role": "owner"}),
        lambda c: c.post("/api/tenants/tenant-other/deactivate"),
    ])
    def test_a_foreign_tenant_is_not_found(self, client, call):
        assert call(client).status_code == 404


class TestReadsUseTheDurableStore:
    def test_no_route_reads_the_legacy_json(self):
        """AST, not a substring search.

        This module's own docstrings name ``tenant_users.json`` while
        explaining why nothing reads it — a text search would match its own
        explanation.
        """
        tree = ast.parse(inspect.getsource(tenant_routes))
        names = {
            node.attr for node in ast.walk(tree)
            if isinstance(node, ast.Attribute)
        } | {
            node.id for node in ast.walk(tree) if isinstance(node, ast.Name)
        }
        assert "get_tenant_manager" not in names
        imported = {
            alias.name for node in ast.walk(tree)
            if isinstance(node, (ast.Import, ast.ImportFrom))
            for alias in node.names
        }
        assert "get_tenant_manager" not in imported
        assert "TenantManager" not in imported

    def test_listing_without_a_composed_engine_is_empty_not_a_crash(self, client):
        """No engine means no authoritative store, so there is nothing to say.

        Empty rather than a 500, and empty rather than falling back to a file:
        a missing store is not permission to consult one nobody governs.
        """
        r = client.get("/api/tenants")
        assert r.status_code == 200
        assert r.json() == []

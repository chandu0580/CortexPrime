"""The legacy tenant JSON importer — Phase 10.11 (ADR-104).

What changed
------------
This module used to test ``TenantManager`` as a *store*: creating tenants,
adding users, updating roles, deactivating. Phase 10.11 deleted every one of
those methods, because they were the only code in the repository that wrote
``tenants.json`` or ``tenant_users.json`` and, after Phases 10.9 and 10.10, a
write there changed nothing any governed path reads.

So the tests for them are gone too. That is not a correct test being bent to
pass — it is a test of a mechanism that no longer exists.

What remains here guards the retirement itself:

* the dataclasses, which the importer still yields;
* the read path, which the two migrations depend on;
* **that the mutators stay gone** — a regression guard, because reintroducing
  one would silently re-add a file store to a frozen inventory that may only
  shrink;
* that a missing directory is an empty import rather than a crash, which is
  what a fresh installation looks like.
"""

from __future__ import annotations

import ast
import inspect
import json
import pathlib

import pytest

from backend.auth.tenant import Tenant, TenantManager, TenantUser


@pytest.fixture
def legacy_store(tmp_path):
    """A legacy JSON store, written directly.

    Written by the test rather than through the class, because the class can no
    longer write anything — which is the point of this phase.
    """
    tenants = [
        {"tenant_id": "tenant-aaa", "name": "Alpha", "slug": "alpha",
         "domain": None, "plan": "free", "is_active": True, "settings": {},
         "created_at": "2026-01-01T00:00:00+00:00"},
        {"tenant_id": "tenant-bbb", "name": "Beta", "slug": "beta",
         "domain": None, "plan": "free", "is_active": False, "settings": {},
         "created_at": "2026-01-01T00:00:00+00:00"},
    ]
    users = {
        "tenant-aaa": [
            {"user_id": "user-1", "tenant_id": "tenant-aaa",
             "email": "a@example.test", "role": "owner", "is_active": True,
             "permissions": [], "created_at": "2026-01-01T00:00:00+00:00"},
        ],
    }
    (tmp_path / "tenants.json").write_text(json.dumps(tenants), encoding="utf-8")
    (tmp_path / "tenant_users.json").write_text(json.dumps(users), encoding="utf-8")
    return TenantManager(storage_path=str(tmp_path))


class TestDataclasses:
    def test_tenant_defaults(self):
        tenant = Tenant(tenant_id="t", name="N", slug="s")
        assert tenant.is_active is True
        assert tenant.plan == "free"

    def test_tenant_user_defaults(self):
        user = TenantUser(user_id="u", tenant_id="t", email="e@x.test")
        assert user.role == "member"
        assert user.is_active is True
        assert user.permissions == []


class TestReadPath:
    """The migrations read through these. Nothing else does."""

    def test_reads_tenants(self, legacy_store):
        assert {t.slug for t in legacy_store.list_tenants()} == {"alpha", "beta"}

    def test_reads_one_tenant(self, legacy_store):
        assert legacy_store.get_tenant("tenant-aaa").name == "Alpha"

    def test_unknown_tenant_is_none(self, legacy_store):
        assert legacy_store.get_tenant("tenant-nope") is None

    def test_reads_by_slug(self, legacy_store):
        assert legacy_store.get_tenant_by_slug("beta").tenant_id == "tenant-bbb"

    def test_preserves_inactive_state(self, legacy_store):
        """The migration must import inactive tenants AS inactive."""
        assert legacy_store.get_tenant("tenant-bbb").is_active is False

    def test_reads_users(self, legacy_store):
        users = legacy_store.get_users("tenant-aaa")
        assert [u.email for u in users] == ["a@example.test"]

    def test_reads_user_by_email(self, legacy_store):
        assert legacy_store.get_user_by_email("a@example.test").role == "owner"

    def test_unknown_email_is_none(self, legacy_store):
        assert legacy_store.get_user_by_email("nobody@example.test") is None

    def test_absent_directory_is_an_empty_import(self, tmp_path):
        """A fresh installation has no legacy data. That is not an error."""
        empty = TenantManager(storage_path=str(tmp_path / "does-not-exist"))
        assert empty.list_tenants() == []
        assert empty.get_tenant("anything") is None


class TestTheMutatorsStayGone:
    """A regression guard, not a formality.

    Reintroducing any of these would put a write back into a module named in
    ``GRANDFATHERED_STORES`` -- an inventory that may only shrink -- and would
    silently re-create the trap Phase 10.11 removed: a write that returns
    success and changes nothing a governed path reads.
    """

    RETIRED = ("create_tenant", "add_user", "update_user_role",
               "deactivate_tenant", "grant_permission", "revoke_permission",
               "_save")

    @pytest.mark.parametrize("name", RETIRED)
    def test_mutator_is_absent(self, name):
        assert not hasattr(TenantManager, name), (
            f"{name} was retired in Phase 10.11; re-adding it re-adds a file "
            "store to a frozen inventory")

    def test_no_file_write_call_survives(self):
        """AST, not a substring search.

        The docstrings in this module legitimately *name* the removed methods,
        so a text search would match its own explanation -- the exact false
        positive this codebase has hit repeatedly.
        """
        source = inspect.getsource(
            __import__("backend.auth.tenant", fromlist=["tenant"]))
        tree = ast.parse(source)
        writes = [
            node.func.attr for node in ast.walk(tree)
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr in ("write_text", "write", "dump", "mkdir")
        ]
        assert writes == [], f"a write path survived: {writes}"


class TestNotAnAuthority:
    def test_the_module_decides_nothing(self):
        """It must not import an authority resolver or a durable store.

        An importer that started consulting authority would be a second place
        answering questions Phases 10.8-10.10 gave exactly one home each.
        """
        source = inspect.getsource(
            __import__("backend.auth.tenant", fromlist=["tenant"]))
        tree = ast.parse(source)
        imported = {
            alias.name for node in ast.walk(tree)
            if isinstance(node, ast.ImportFrom) for alias in node.names
        } | {
            node.module or "" for node in ast.walk(tree)
            if isinstance(node, ast.ImportFrom)
        }
        forbidden = [name for name in imported
                     if "approver" in name or "grants" in name
                     or "sql_" in name or "durable" in name]
        assert forbidden == [], f"the importer reached for authority: {forbidden}"

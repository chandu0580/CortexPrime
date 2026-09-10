"""Phase 11.2: ``require_user`` resolves the tenant store from the governed
runtime when no product engine is composed (``backend.main``), and still
refuses when neither exists. No JSON fallback anywhere."""
from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import patch

from backend.auth import dependencies as deps


class _Store:  # a DurableStore stand-in for the repository constructor
    pass


def test_product_engine_store_wins_when_present():
    engine = SimpleNamespace(tenants="engine-tenants")
    with patch("backend.api.product.app.current_engine", return_value=engine):
        assert deps._tenant_store() == "engine-tenants"


def test_governed_runtime_store_is_used_when_no_engine():
    runtime = SimpleNamespace(persistence=SimpleNamespace(store=_Store()))
    with patch("backend.api.product.app.current_engine", return_value=None), \
         patch("backend.core.dependency_container.container.resolve", return_value=runtime), \
         patch("backend.contexts.connectivity.infrastructure.sql_tenant.SqlTenantRepository",
               side_effect=lambda store: ("repo", store)) as repo:
        result = deps._tenant_store()
    assert result[0] == "repo" and isinstance(result[1], _Store)
    repo.assert_called_once()


def test_neither_store_refuses_rather_than_falls_back():
    with patch("backend.api.product.app.current_engine", return_value=None), \
         patch("backend.core.dependency_container.container.resolve", side_effect=KeyError("none")):
        assert deps._tenant_store() is None

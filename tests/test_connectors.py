"""
Sprint 53.2 — Phase 3: Enterprise Connectors
=============================================
Tests for all 8 enterprise connectors, their registry, and base class.

Covers:
  - ConnectorRegistry CRUD and lifecycle
  - BaseConnector capability introspection
  - CredentialService load/store/remove
  - Connector health and initialization patterns
  - Operation validation via registry

Usage:
    pytest tests/test_connectors.py -v
"""
from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

pytestmark = pytest.mark.asyncio


# =============================================================
# 1. CONNECTOR REGISTRY
# =============================================================

class TestConnectorRegistry:
    """Test registry CRUD and lifecycle management."""

    def test_register_and_get(self):
        from backend.connectors.registry import ConnectorRegistry

        registry = ConnectorRegistry()
        connector = MagicMock()
        connector.connector_type = "test_type"
        connector.connector_name = "Test Connector"

        registry.register(connector)
        assert registry.get("test_type") is connector
        assert registry.count() == 1
        assert "test_type" in registry.list_types()

    def test_register_overwrites_existing(self):
        from backend.connectors.registry import ConnectorRegistry

        registry = ConnectorRegistry()
        c1 = MagicMock(connector_type="dup", connector_name="C1")
        c2 = MagicMock(connector_type="dup", connector_name="C2")

        registry.register(c1)
        registry.register(c2)
        assert registry.get("dup").connector_name == "C2"

    def test_get_returns_none_for_unregistered(self):
        from backend.connectors.registry import ConnectorRegistry

        registry = ConnectorRegistry()
        assert registry.get("nonexistent") is None

    def test_list_all_returns_all_connectors(self):
        from backend.connectors.registry import ConnectorRegistry

        registry = ConnectorRegistry()
        for t in ("a", "b", "c"):
            registry.register(MagicMock(connector_type=t, connector_name=t.upper()))
        assert len(registry.list_all()) == 3

    async def test_initialize_all(self):
        from backend.connectors.registry import ConnectorRegistry

        registry = ConnectorRegistry()
        c1 = MagicMock(connector_type="t1", connector_name="T1")
        c1.initialize = AsyncMock(return_value=True)
        c2 = MagicMock(connector_type="t2", connector_name="T2")
        c2.initialize = AsyncMock(return_value=False)

        registry.register(c1)
        registry.register(c2)

        results = await registry.initialize_all()
        assert results["t1"] is True
        assert results["t2"] is False

    async def test_health_all(self):
        from backend.connectors.registry import ConnectorRegistry

        registry = ConnectorRegistry()
        c1 = MagicMock(connector_type="t1", connector_name="T1")
        c1.health = AsyncMock(return_value={"status": "available"})
        registry.register(c1)

        results = await registry.health_all()
        assert results["t1"]["status"] == "available"

    async def test_shutdown_all(self):
        from backend.connectors.registry import ConnectorRegistry

        registry = ConnectorRegistry()
        c1 = MagicMock(connector_type="t1", connector_name="T1")
        c1.shutdown = AsyncMock()
        registry.register(c1)

        await registry.shutdown_all()
        c1.shutdown.assert_called_once()

    async def test_initialize_connector(self):
        from backend.connectors.registry import ConnectorRegistry

        registry = ConnectorRegistry()
        c = MagicMock(connector_type="t1", connector_name="T1")
        c.initialize = AsyncMock(return_value=True)
        registry.register(c)

        assert await registry.initialize_connector("t1") is True
        assert await registry.initialize_connector("nonexistent") is False

    async def test_shutdown_connector(self):
        from backend.connectors.registry import ConnectorRegistry

        registry = ConnectorRegistry()
        c = MagicMock(connector_type="t1", connector_name="T1")
        c.shutdown = AsyncMock()
        registry.register(c)

        assert await registry.shutdown_connector("t1") is True
        assert await registry.shutdown_connector("nonexistent") is False


# =============================================================
# 2. CAPABILITY INTROSPECTION
# =============================================================

class TestCapabilityIntrospection:
    """Test get_all_operations, get_connector_operations, validate_operation."""

    def test_get_all_operations(self):
        from backend.connectors.registry import ConnectorRegistry

        registry = ConnectorRegistry()
        c = MagicMock(connector_type="test_c", connector_name="Test")
        c.get_operations.return_value = {
            "do_stuff": {"description": "Does stuff", "required_params": ["x"], "optional_params": {}},
        }
        registry.register(c)

        ops = registry.get_all_operations()
        assert "test_c" in ops
        assert "do_stuff" in ops["test_c"]

    def test_get_connector_operations_returns_none_for_missing(self):
        from backend.connectors.registry import ConnectorRegistry

        registry = ConnectorRegistry()
        assert registry.get_connector_operations("nonexistent") is None

    def test_validate_operation_missing_connector(self):
        from backend.connectors.registry import ConnectorRegistry

        registry = ConnectorRegistry()
        valid, errors = registry.validate_operation("unknown", "op", {})
        assert valid is False
        assert "not registered" in errors[0]

    def test_validate_operation_missing_operation(self):
        from backend.connectors.registry import ConnectorRegistry

        registry = ConnectorRegistry()
        c = MagicMock(connector_type="test_c", connector_name="Test")
        c.get_operations.return_value = {
            "existing_op": {"description": "", "required_params": [], "optional_params": {}},
        }
        registry.register(c)

        valid, errors = registry.validate_operation("test_c", "nonexistent_op", {})
        assert valid is False
        assert "not found" in errors[0]

    def test_validate_operation_missing_required_param(self):
        from backend.connectors.registry import ConnectorRegistry

        registry = ConnectorRegistry()
        c = MagicMock(connector_type="test_c", connector_name="Test")
        c.get_operations.return_value = {
            "create_something": {
                "description": "Creates something",
                "required_params": ["name", "owner"],
                "optional_params": {},
            },
        }
        registry.register(c)

        valid, errors = registry.validate_operation("test_c", "create_something", {"name": "test"})
        assert valid is False
        assert any("owner" in e for e in errors)

    def test_validate_operation_passes(self):
        from backend.connectors.registry import ConnectorRegistry

        registry = ConnectorRegistry()
        c = MagicMock(connector_type="test_c", connector_name="Test")
        c.get_operations.return_value = {
            "create_something": {
                "description": "Creates something",
                "required_params": ["name", "owner"],
                "optional_params": {},
            },
        }
        registry.register(c)

        valid, errors = registry.validate_operation("test_c", "create_something", {"name": "test", "owner": "me"})
        assert valid is True
        assert errors == []


# =============================================================
# 3. CAPABILITIES PROMPT BUILDING
# =============================================================

class TestCapabilitiesPrompt:
    """Test get_capabilities_prompt output."""

    def test_prompt_contains_registered_connectors(self):
        from backend.connectors.registry import ConnectorRegistry

        registry = ConnectorRegistry()
        c = MagicMock(connector_type="test_c", connector_name="Test")
        c.get_operations.return_value = {
            "op1": {"description": "First operation", "required_params": ["x"], "optional_params": {}},
        }
        registry.register(c)

        prompt = registry.get_capabilities_prompt(include_examples=True)
        assert "test_c" in prompt
        assert "op1" in prompt
        assert "First operation" in prompt
        assert "Connector" in prompt or "connector" in prompt

    def test_prompt_with_no_connectors(self):
        from backend.connectors.registry import ConnectorRegistry

        registry = ConnectorRegistry()
        prompt = registry.get_capabilities_prompt()
        assert "No enterprise connectors" in prompt


# =============================================================
# 4. CREDENTIAL SERVICE
# =============================================================

class TestCredentialService:
    """Test CredentialService store/load/remove/exists."""

    def _reset(self):
        from backend.services import credential_service
        credential_service._CREDENTIAL_STORE.clear()

    def test_store_and_load(self):
        self._reset()
        from backend.services.credential_service import CredentialService

        CredentialService.store("github", {"token": "ghp_test"})
        creds = CredentialService.load("github")
        assert creds["token"] == "ghp_test"

    def test_load_returns_copy(self):
        self._reset()
        from backend.services.credential_service import CredentialService

        CredentialService.store("jira", {"email": "test@test.com"})
        creds = CredentialService.load("jira")
        creds["email"] = "modified"
        # Verify original is unchanged
        reloaded = CredentialService.load("jira")
        assert reloaded["email"] == "test@test.com"

    def test_remove_credentials(self, monkeypatch):
        # backend/.env ships a non-empty placeholder SLACK_BOT_TOKEN;
        # CredentialService.exists() falls back to checking the env var,
        # so without clearing it this test sees the placeholder as a
        # real credential even after explicitly removing it from the
        # in-memory store.
        monkeypatch.delenv("SLACK_BOT_TOKEN", raising=False)
        self._reset()
        from backend.services.credential_service import CredentialService

        CredentialService.store("slack", {"bot_token": "xoxb-test"})
        assert CredentialService.exists("slack") is True
        CredentialService.remove("slack")
        assert CredentialService.exists("slack") is False

    def test_no_environment_fallback(self, monkeypatch):
        """Contract change (Phase 5.15, ADR-058): the store never falls back
        to the environment. A credential in the process environment is
        invisible until the composition root explicitly bootstraps it —
        which is what stopped a bare application boot consuming `.env`
        provider tokens and contacting real providers (found in 5.14)."""
        self._reset()
        from backend.services.credential_service import CredentialService

        monkeypatch.setenv("GITHUB_TOKEN", "env-token")
        assert CredentialService.load("github") == {}
        assert CredentialService.exists("github") is False

    def test_bootstrap_is_the_one_road_in(self, monkeypatch):
        """The sanctioned path: the composition act carries environment
        configuration into the store, once, explicitly (ADR-058)."""
        self._reset()
        from backend.api.connector_credential_composition import (
            bootstrap_connector_credentials,
        )
        from backend.services.credential_service import CredentialService

        monkeypatch.setenv("GITHUB_TOKEN", "env-token")
        outcome = bootstrap_connector_credentials(["github"])
        assert outcome == {"github": True}
        assert CredentialService.load("github") == {"token": "env-token"}

    def test_exists_returns_false_for_unknown(self):
        self._reset()
        from backend.services.credential_service import CredentialService

        assert CredentialService.exists("unknown") is False

    def test_env_mapping_for_all_connectors(self):
        """The env mapping lives in the composition module now (ADR-058) —
        the credential store itself knows nothing about the environment."""
        from backend.api.connector_credential_composition import (
            CONNECTOR_ENVIRONMENT,
        )

        connectors = ["github", "jira", "slack", "teams", "azure_devops",
                      "servicenow", "confluence", "notion", "gitlab_ci",
                      "jenkins", "circleci"]
        for ctype in connectors:
            assert isinstance(CONNECTOR_ENVIRONMENT.get(ctype), dict), ctype


# =============================================================
# 5. BASE CONNECTOR
# =============================================================

class TestBaseConnector:
    """Test BaseConnector activity recording and operation discovery."""

    def test_get_operations_excludes_lifecycle_and_private(self):
        from backend.connectors.base import BaseConnector

        class TestConnector(BaseConnector):
            connector_name = "Test"
            connector_type = "test"

            async def initialize(self) -> bool:
                return True

            async def shutdown(self) -> bool:
                return True

            async def health(self) -> dict:
                return {"status": "ok"}

            async def do_public_thing(self, x: int) -> dict:
                return {"result": x}

            async def _private_method(self) -> None:
                pass

        ops = TestConnector.get_operations()
        assert "do_public_thing" in ops
        assert "initialize" not in ops
        assert "shutdown" not in ops
        assert "health" not in ops
        assert "_private_method" not in ops

    def test_configure_stores_credentials(self, monkeypatch):
        from backend.connectors.base import BaseConnector
        from backend.services import credential_service

        store_called = []

        def _fake_store(ctype, creds):
            store_called.append((ctype, creds))

        monkeypatch.setattr(credential_service.CredentialService, "store", _fake_store)

        class TestConnector(BaseConnector):
            connector_name = "Test"
            connector_type = "test_conn"

            async def initialize(self) -> bool:
                return True

            async def shutdown(self) -> bool:
                return True

            async def health(self) -> dict:
                return {"status": "ok"}

        c = TestConnector()
        c.configure({"token": "abc"})
        assert len(store_called) == 1
        assert store_called[0][0] == "test_conn"
        assert store_called[0][1]["token"] == "abc"


# =============================================================
# 6. EXISTING CONNECTOR NAMES LIST
# =============================================================

class TestKnownConnectorNames:
    """Verify all 8 enterprise connectors exist as modules and have expected metadata."""

    CONNECTOR_SPECS = {
        "github": {"name": "GitHub", "file": "github.py"},
        "jira": {"name": "Jira", "file": "jira.py"},
        "slack": {"name": "Slack", "file": "slack.py"},
        "teams": {"name": "Teams", "file": "teams.py"},
        "azure_devops": {"name": "AzureDevOps", "file": "azure_devops.py"},
        "servicenow": {"name": "ServiceNow", "file": "servicenow.py"},
        "confluence": {"name": "Confluence", "file": "confluence.py"},
        "notion": {"name": "Notion", "file": "notion.py"},
    }

    def test_connector_files_exist(self):
        import os
        for ctype, spec in self.CONNECTOR_SPECS.items():
            path = os.path.join(os.path.dirname(__file__), "..", "backend", "connectors", spec["file"])
            assert os.path.exists(path), f"Missing connector file: {path}"

    def test_known_connector_type_list(self):
        # `_KNOWN_CONNECTOR_TYPES` never actually existed in backend.services.mission_runtime
        # (which has nothing to do with connectors) — this was pointed at the wrong module.
        # The real known-connector-type roster lives as `connector_type` on each watcher
        # class in enterprise_watchers.py, which is what this test actually meant to check.
        from backend.services.enterprise_watchers import _WATCHER_CLASSES
        expected = {"github", "jira", "slack", "teams", "azure_devops", "servicenow", "confluence", "notion", "docker"}
        actual = {cls.connector_type for cls in _WATCHER_CLASSES}
        assert actual == expected

"""
Enterprise operations validation — diagnostics.

Originally (Sprint 55.0 / Phase 6) this module covered Health Center,
Backup & Restore, Maintenance Mode, Diagnostics and Operational Reports.
Phase 10.29 (ADR-119) retired the health-center, backup, maintenance and
operational-reports API/model surface; the tests that covered only that
surface were removed with it. Diagnostics is retained and still tested here.

Usage:
    pytest tests/test_enterprise_operations.py -v
"""
from __future__ import annotations

import json

import pytest


# =============================================================
# 4. DIAGNOSTICS SERVICE
# =============================================================

class TestDiagnosticsService:
    pytestmark = pytest.mark.asyncio
    async def test_generate_diagnostics_has_all_sections(self):
        from backend.services.diagnostics_service import diagnostics_service
        result = await diagnostics_service.generate_diagnostics()
        assert "diagnostics_id" in result
        assert "generated_at" in result
        assert "environment" in result
        assert "runtime_status" in result
        assert "connector_status" in result
        assert "infrastructure" in result
        assert "configuration" in result
        assert "mission_statistics" in result
        assert "recent_failures" in result
        assert "performance_summary" in result
        assert "generation_time_ms" in result

    async def test_environment_info(self):
        from backend.services.diagnostics_service import diagnostics_service
        result = await diagnostics_service.generate_diagnostics()
        env = result["environment"]
        assert "python_version" in env
        assert "platform" in env
        assert "env" in env

    async def test_infrastructure_status(self):
        from backend.services.diagnostics_service import diagnostics_service
        result = await diagnostics_service.generate_diagnostics()
        infra = result["infrastructure"]
        assert "redis" in infra
        assert "neo4j" in infra
        assert "rabbitmq" in infra
        assert "postgresql" in infra

    async def test_serialize_diagnostics(self):
        from backend.services.diagnostics_service import diagnostics_service
        data = {"test": "value", "number": 42}
        serialized = diagnostics_service.serialize_diagnostics(data)
        parsed = json.loads(serialized)
        assert parsed["test"] == "value"
        assert parsed["number"] == 42


# 6. REGRESSION — HEALTH ROUTES IMPORT
# =============================================================

class TestRoutesImport:
    def test_diagnostics_routes_import(self):
        from backend.api.diagnostics_routes import router
        assert router is not None
        assert router.prefix == "/api/operations/diagnostics"

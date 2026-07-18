"""
Sprint 55.0 — Phase 6: Enterprise Operations Validation
========================================================
Tests for Health Center, Backup & Restore, Maintenance Mode,
Diagnostics, and Operational Reports services.

Usage:
    pytest tests/test_enterprise_operations.py -v
"""
from __future__ import annotations

import json
import os
import tempfile
from unittest.mock import AsyncMock, MagicMock, patch

import pytest




# =============================================================
# 1. HEALTH CENTER SERVICE
# =============================================================

class TestHealthCenterService:
    pytestmark = pytest.mark.asyncio
    async def test_health_dashboard_returns_all_components(self):
        from backend.services.health_center_service import health_center_service, COMPONENTS
        result = await health_center_service.get_health_dashboard()
        assert result["overall_status"] in ("healthy", "warning", "critical")
        assert result["total_components"] == len(COMPONENTS)
        assert result["healthy_count"] + result["warning_count"] + result["critical_count"] == result["total_components"]
        assert "components" in result
        for comp in COMPONENTS:
            assert comp["name"] in result["components"]

    async def test_health_dashboard_component_structure(self):
        from backend.services.health_center_service import health_center_service
        result = await health_center_service.get_health_dashboard()
        for name, comp in result["components"].items():
            assert "status" in comp
            assert "latency_ms" in comp
            assert "detail" in comp
            assert comp["status"] in ("healthy", "warning", "critical", "unavailable")

    async def test_save_and_get_snapshot_history(self):
        from unittest.mock import AsyncMock
        mock_db = AsyncMock()
        mock_db.execute.return_value = MagicMock()
        mock_db.execute.return_value.scalars.return_value.all.return_value = []

        from backend.services.health_center_service import health_center_service
        history = await health_center_service.get_snapshot_history(mock_db, limit=10)
        assert isinstance(history, list)

    async def test_cached_status(self):
        from backend.services.health_center_service import health_center_service
        cached = health_center_service.get_cached_status()
        assert cached is None or isinstance(cached, dict)


# =============================================================
# 2. BACKUP & RESTORE SERVICE
# =============================================================

class TestBackupService:
    pytestmark = pytest.mark.asyncio
    async def test_create_backup_returns_backup_id(self, monkeypatch):
        from backend.services.backup_service import backup_service

        with tempfile.TemporaryDirectory() as tmpdir:
            monkeypatch.setattr("backend.services.backup_service.BACKUP_DIR", tmpdir)
            result = await backup_service.create_backup(
                entities=["workflow_definitions", "connector_configurations"],
                triggered_by="test-user",
            )
            assert result["status"] == "completed"
            assert "backup_id" in result
            assert result["integrity_hash"] is not None
            assert result["file_path"] is not None

    async def test_create_backup_invalid_entity(self, monkeypatch):
        from backend.services.backup_service import backup_service

        with tempfile.TemporaryDirectory() as tmpdir:
            monkeypatch.setattr("backend.services.backup_service.BACKUP_DIR", tmpdir)
            result = await backup_service.create_backup(
                entities=["invalid_entity"],
                triggered_by="test-user",
            )
            assert result["status"] == "completed_with_errors"

    async def test_verify_backup_valid(self, monkeypatch):
        from backend.services.backup_service import backup_service

        with tempfile.TemporaryDirectory() as tmpdir:
            monkeypatch.setattr("backend.services.backup_service.BACKUP_DIR", tmpdir)
            result = await backup_service.create_backup(
                entities=["workflow_definitions"],
                triggered_by="test-user",
            )
            verify = await backup_service.verify_backup(result["backup_id"])
            assert verify["status"] == "verified"
            assert verify["integrity_hash"] == result["integrity_hash"]

    async def test_verify_backup_not_found(self):
        from backend.services.backup_service import backup_service
        verify = await backup_service.verify_backup("nonexistent-backup-id")
        assert verify["status"] == "not_found"

    async def test_restore_backup_not_found(self):
        from backend.services.backup_service import backup_service
        result = await backup_service.restore_backup(backup_id="nonexistent")
        assert result["status"] == "failed"

    async def test_restore_backup_valid(self, monkeypatch):
        from backend.services.backup_service import backup_service

        with tempfile.TemporaryDirectory() as tmpdir:
            monkeypatch.setattr("backend.services.backup_service.BACKUP_DIR", tmpdir)
            created = await backup_service.create_backup(
                entities=["workflow_definitions"],
                triggered_by="test-user",
            )
            result = await backup_service.restore_backup(backup_id=created["backup_id"])
            assert result["status"] == "completed"

    async def test_list_backups_empty(self, monkeypatch):
        from backend.services.backup_service import backup_service

        with tempfile.TemporaryDirectory() as tmpdir:
            monkeypatch.setattr("backend.services.backup_service.BACKUP_DIR", tmpdir)
            backups = await backup_service.list_backups(limit=10)
            assert isinstance(backups, list)
            assert len(backups) == 0

    async def test_supported_entities(self):
        from backend.services.backup_service import SUPPORTED_ENTITIES
        assert "workflow_definitions" in SUPPORTED_ENTITIES
        assert "connector_configurations" in SUPPORTED_ENTITIES
        assert "mission_history" in SUPPORTED_ENTITIES
        assert "replay_history" in SUPPORTED_ENTITIES
        assert "audit_logs" in SUPPORTED_ENTITIES
        assert "analytics_metadata" in SUPPORTED_ENTITIES


# =============================================================
# 3. MAINTENANCE MODE SERVICE
# =============================================================

class TestMaintenanceService:
    pytestmark = pytest.mark.asyncio
    async def test_initial_state_is_disabled(self):
        from backend.services.maintenance_service import maintenance_service
        status = await maintenance_service.get_status()
        assert status["enabled"] is False

    async def test_enable_maintenance(self, monkeypatch):
        from backend.services.maintenance_service import maintenance_service
        monkeypatch.setattr(maintenance_service, "_state", type(maintenance_service._state)())

        state = await maintenance_service.enable(
            banner_message="Test maintenance",
            allow_existing_missions=True,
            block_new_missions=True,
            triggered_by="test-admin",
        )
        assert state.enabled is True
        assert state.banner_message == "Test maintenance"
        assert state.allow_existing_missions is True
        assert state.block_new_missions is True
        assert state.triggered_by == "test-admin"

    async def test_disable_maintenance(self, monkeypatch):
        from backend.services.maintenance_service import maintenance_service
        monkeypatch.setattr(maintenance_service, "_state", type(maintenance_service._state)())

        await maintenance_service.enable(triggered_by="test")
        state = await maintenance_service.disable(triggered_by="test-admin")
        assert state.enabled is False

    async def test_should_block_new_mission(self, monkeypatch):
        from backend.services.maintenance_service import maintenance_service
        monkeypatch.setattr(maintenance_service, "_state", type(maintenance_service._state)())

        assert maintenance_service.should_block_new_mission() is False
        await maintenance_service.enable(block_new_missions=True, triggered_by="test")
        assert maintenance_service.should_block_new_mission() is True

    async def test_maintenance_banner(self, monkeypatch):
        from backend.services.maintenance_service import maintenance_service
        monkeypatch.setattr(maintenance_service, "_state", type(maintenance_service._state)())

        assert maintenance_service.get_banner() is None
        await maintenance_service.enable(banner_message="Down for maintenance", triggered_by="test")
        assert maintenance_service.get_banner() == "Down for maintenance"

    async def test_is_maintenance_active(self, monkeypatch):
        from backend.services.maintenance_service import maintenance_service
        monkeypatch.setattr(maintenance_service, "_state", type(maintenance_service._state)())

        assert maintenance_service.is_maintenance_active() is False
        await maintenance_service.enable(triggered_by="test")
        assert maintenance_service.is_maintenance_active() is True

    async def test_get_maintenance_events(self):
        from unittest.mock import AsyncMock
        mock_db = AsyncMock()
        mock_db.execute.return_value = MagicMock()
        mock_db.execute.return_value.scalars.return_value.all.return_value = []

        from backend.services.maintenance_service import maintenance_service
        events = await maintenance_service.get_event_history(mock_db, limit=10)
        assert isinstance(events, list)


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


# =============================================================
# 5. OPERATIONAL REPORTS SERVICE
# =============================================================

class TestOperationalReportsService:
    pytestmark = pytest.mark.asyncio
    async def test_generate_daily_report(self):
        from unittest.mock import AsyncMock
        mock_db = AsyncMock()
        mock_db.add.return_value = None
        mock_db.flush.return_value = None
        mock_db.refresh.return_value = None
        mock_db.refresh.side_effect = lambda obj: setattr(obj, "id", "00000000-0000-0000-0000-000000000001")

        from backend.services.operational_reports_service import operational_reports_service
        result = await operational_reports_service.generate_daily_report(
            db=mock_db,
            generated_by="test-user",
        )
        assert result["report_type"] == "daily"
        assert result["status"] == "generated"

    async def test_generate_weekly_report(self):
        from unittest.mock import AsyncMock, MagicMock
        mock_db = AsyncMock()
        mock_db.add.return_value = None
        mock_db.flush.return_value = None
        mock_db.refresh.return_value = None
        mock_db.refresh.side_effect = lambda obj: setattr(obj, "id", "00000000-0000-0000-0000-000000000002")

        from backend.services.operational_reports_service import operational_reports_service
        result = await operational_reports_service.generate_weekly_report(
            db=mock_db,
            generated_by="test-user",
        )
        assert result["report_type"] == "weekly"
        assert result["status"] == "generated"

    async def test_generate_monthly_report(self):
        from unittest.mock import AsyncMock
        mock_db = AsyncMock()
        mock_db.add.return_value = None
        mock_db.flush.return_value = None
        mock_db.refresh.return_value = None
        mock_db.refresh.side_effect = lambda obj: setattr(obj, "id", "00000000-0000-0000-0000-000000000003")

        from backend.services.operational_reports_service import operational_reports_service
        result = await operational_reports_service.generate_monthly_report(
            db=mock_db,
            generated_by="test-user",
        )
        assert result["report_type"] == "monthly"
        assert result["status"] == "generated"

    async def test_generate_report_invalid_type(self):
        from unittest.mock import AsyncMock
        mock_db = AsyncMock()

        from backend.services.operational_reports_service import operational_reports_service
        with pytest.raises(ValueError, match="Unknown report type"):
            await operational_reports_service.generate_report(
                report_type="invalid",
                db=mock_db,
            )

    async def test_list_reports(self):
        from unittest.mock import AsyncMock, MagicMock
        mock_db = AsyncMock()
        mock_db.execute.return_value = MagicMock()
        mock_db.execute.return_value.scalars.return_value.all.return_value = []

        from backend.services.operational_reports_service import operational_reports_service
        reports = await operational_reports_service.list_reports(mock_db, limit=10)
        assert isinstance(reports, list)


# =============================================================
# 6. REGRESSION — HEALTH ROUTES IMPORT
# =============================================================

class TestRoutesImport:
    def test_health_center_routes_import(self):
        from backend.api.health_center_routes import router
        assert router is not None
        assert router.prefix == "/api/operations/health-center"

    def test_backup_routes_import(self):
        from backend.api.backup_routes import router
        assert router is not None
        assert router.prefix == "/api/operations/backup"

    def test_maintenance_routes_import(self):
        from backend.api.maintenance_routes import router
        assert router is not None
        assert router.prefix == "/api/operations/maintenance"

    def test_diagnostics_routes_import(self):
        from backend.api.diagnostics_routes import router
        assert router is not None
        assert router.prefix == "/api/operations/diagnostics"

    def test_operational_reports_routes_import(self):
        from backend.api.operational_reports_routes import router
        assert router is not None
        assert router.prefix == "/api/operations/reports"


# =============================================================
# 7. REGRESSION — MODEL IMPORTS
# =============================================================

class TestModelImports:
    def test_health_status_model(self):
        from backend.database.models.health_status import HealthStatusSnapshot
        assert HealthStatusSnapshot.__tablename__ == "health_status_snapshots"

    def test_backup_record_model(self):
        from backend.database.models.backup_record import BackupRecord
        assert BackupRecord.__tablename__ == "backup_records"

    def test_maintenance_event_model(self):
        from backend.database.models.maintenance_event import MaintenanceEvent
        assert MaintenanceEvent.__tablename__ == "maintenance_events"

    def test_operational_report_model(self):
        from backend.database.models.operational_report import OperationalReport
        assert OperationalReport.__tablename__ == "operational_reports"

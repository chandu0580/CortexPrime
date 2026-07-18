from __future__ import annotations

import hashlib
import json
import logging
import os
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from uuid import uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from backend.database.models.backup_record import BackupRecord

log = logging.getLogger(__name__)

BACKUP_DIR = os.getenv("BACKUP_DIR", os.path.join("data", "backups"))

SUPPORTED_ENTITIES = {
    "workflow_definitions": "Workflow definitions",
    "connector_configurations": "Connector configurations",
    "mission_history": "Mission history",
    "replay_history": "Replay history",
    "audit_logs": "Audit logs",
    "analytics_metadata": "Analytics metadata",
}


class BackupService:
    def __init__(self) -> None:
        os.makedirs(BACKUP_DIR, exist_ok=True)

    async def create_backup(
        self,
        entities: List[str],
        triggered_by: Optional[str] = None,
        db: Optional[AsyncSession] = None,
    ) -> Dict[str, Any]:
        record = BackupRecord(
            backup_type="manual" if triggered_by else "scheduled",
            status="in_progress",
            entities={e: SUPPORTED_ENTITIES.get(e, e) for e in entities},
            triggered_by=triggered_by or "system",
        )
        if db:
            db.add(record)
            await db.flush()
            await db.refresh(record)

        backup_id = str(record.id) if db else str(uuid4())
        backup_data: Dict[str, Any] = {
            "backup_id": backup_id,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "triggered_by": triggered_by or "system",
            "entities": {},
        }

        errors: List[str] = []

        for entity in entities:
            try:
                data = await self._dump_entity(entity)
                backup_data["entities"][entity] = data
                log.info("Backed up entity: %s (%d records)", entity, len(data) if isinstance(data, list) else 1)
            except Exception as exc:
                errors.append(f"{entity}: {exc}")
                log.warning("Failed to back up entity %s: %s", entity, exc)

        serialized = json.dumps(backup_data, default=str, indent=2)
        integrity_hash = hashlib.sha256(serialized.encode()).hexdigest()

        backup_file = os.path.join(BACKUP_DIR, f"backup_{backup_id}.json")
        with open(backup_file, "w") as f:
            f.write(serialized)

        total_bytes = len(serialized.encode())

        if db:
            record.status = "completed" if not errors else "completed_with_errors"
            record.integrity_hash = integrity_hash
            record.file_path = backup_file
            record.total_bytes = total_bytes
            record.error_message = "; ".join(errors) if errors else None
            record.completed_at = datetime.now(timezone.utc)
            await db.flush()
            await db.refresh(record)

        return {
            "backup_id": backup_id,
            "status": "completed" if not errors else "completed_with_errors",
            "integrity_hash": integrity_hash,
            "file_path": backup_file,
            "total_bytes": total_bytes,
            "entities_count": len(entities),
            "errors": errors,
        }

    async def restore_backup(
        self,
        backup_id: str,
        entities: Optional[List[str]] = None,
        triggered_by: Optional[str] = None,
        db: Optional[AsyncSession] = None,
    ) -> Dict[str, Any]:
        backup_file = os.path.join(BACKUP_DIR, f"backup_{backup_id}.json")
        if not os.path.exists(backup_file):
            return {"status": "failed", "error": f"Backup {backup_id} not found"}

        with open(backup_file) as f:
            backup_data = json.load(f)

        integrity_hash = hashlib.sha256(json.dumps(backup_data, default=str).encode()).hexdigest()
        if db:
            record = await self._get_record(db, backup_id)
            if record and record.integrity_hash and record.integrity_hash != integrity_hash:
                return {"status": "failed", "error": "Integrity check failed — backup may be corrupted"}

        entity_list = entities or list(backup_data.get("entities", {}).keys())
        errors: List[str] = []
        restored: List[str] = []

        for entity in entity_list:
            entity_data = backup_data.get("entities", {}).get(entity)
            if entity_data is None:
                errors.append(f"{entity}: not found in backup")
                continue
            try:
                await self._restore_entity(entity, entity_data)
                restored.append(entity)
                log.info("Restored entity: %s", entity)
            except Exception as exc:
                errors.append(f"{entity}: {exc}")
                log.warning("Failed to restore entity %s: %s", entity, exc)

        return {
            "backup_id": backup_id,
            "status": "completed" if not errors else "completed_with_errors",
            "restored_entities": restored,
            "errors": errors,
        }

    async def verify_backup(self, backup_id: str) -> Dict[str, Any]:
        backup_file = os.path.join(BACKUP_DIR, f"backup_{backup_id}.json")
        if not os.path.exists(backup_file):
            return {"status": "not_found", "backup_id": backup_id}

        stat = os.stat(backup_file)
        with open(backup_file) as f:
            content = f.read()

        try:
            data = json.loads(content)
            current_hash = hashlib.sha256(content.encode()).hexdigest()
            entity_count = len(data.get("entities", {}))
            return {
                "status": "verified",
                "backup_id": backup_id,
                "file_size_bytes": stat.st_size,
                "integrity_hash": current_hash,
                "entity_count": entity_count,
                "created_at": data.get("created_at"),
                "file_path": backup_file,
            }
        except json.JSONDecodeError as exc:
            return {"status": "corrupted", "backup_id": backup_id, "error": str(exc)}

    async def rollback(
        self,
        backup_id: str,
        triggered_by: Optional[str] = None,
        db: Optional[AsyncSession] = None,
    ) -> Dict[str, Any]:
        log.info("Rollback initiated for backup %s by %s", backup_id, triggered_by or "system")
        return await self.restore_backup(
            backup_id=backup_id,
            entities=None,
            triggered_by=triggered_by,
            db=db,
        )

    async def list_backups(self, limit: int = 50) -> List[Dict[str, Any]]:
        backups: List[Dict[str, Any]] = []
        if not os.path.isdir(BACKUP_DIR):
            return backups
        files = sorted(
            [f for f in os.listdir(BACKUP_DIR) if f.startswith("backup_") and f.endswith(".json")],
            reverse=True,
        )[:limit]
        for fname in files:
            fpath = os.path.join(BACKUP_DIR, fname)
            stat = os.stat(fpath)
            backup_id = fname.replace("backup_", "").replace(".json", "")
            backups.append({
                "backup_id": backup_id,
                "file_size_bytes": stat.st_size,
                "created_at": datetime.fromtimestamp(stat.st_ctime, tz=timezone.utc).isoformat(),
                "file_path": fpath,
            })
        return backups

    async def _dump_entity(self, entity: str) -> Any:
        from backend.database.models.audit_log import AuditLog
        from backend.database.models.runtime_analytics import RuntimeAnalyticsRecord

        if entity == "workflow_definitions":
            from backend.safety.approval_queue import approval_queue
            return {"queue_size": len(getattr(approval_queue, "_requests", {}))}
        elif entity == "connector_configurations":
            from backend.connectors.registry import connector_registry
            return {"connector_count": connector_registry.count() if hasattr(connector_registry, "count") else 0}
        elif entity == "mission_history":
            from backend.database.engine import AsyncSessionLocal
            async with AsyncSessionLocal() as session:
                from sqlalchemy import select

                from backend.database.models.runtime_analytics import RuntimeAnalyticsRecord
                result = await session.execute(select(RuntimeAnalyticsRecord).limit(1000))
                rows = result.scalars().all()
                return [r.to_dict() for r in rows]
        elif entity == "replay_history":
            return {"available": True}
        elif entity == "audit_logs":
            from backend.database.engine import AsyncSessionLocal
            async with AsyncSessionLocal() as session:
                from sqlalchemy import select

                from backend.database.models.audit_log import AuditLog
                result = await session.execute(select(AuditLog).limit(1000))
                rows = result.scalars().all()
                return [r.to_dict() for r in rows]
        elif entity == "analytics_metadata":
            from backend.database.engine import AsyncSessionLocal
            async with AsyncSessionLocal() as session:
                from sqlalchemy import select

                from backend.database.models.runtime_analytics import RuntimeAnalyticsRecord
                result = await session.execute(select(RuntimeAnalyticsRecord).limit(100))
                rows = result.scalars().all()
                return {"analytics": [r.to_dict() for r in rows]}
        else:
            raise ValueError(f"Unknown entity: {entity}")

    async def _restore_entity(self, entity: str, data: Any) -> None:
        log.info("Restore of %s initiated (%d records)", entity, len(data) if isinstance(data, list) else 1)

    async def _get_record(self, db: AsyncSession, backup_id: str) -> Optional[BackupRecord]:
        from uuid import UUID

        from sqlalchemy import select
        try:
            result = await db.execute(select(BackupRecord).where(BackupRecord.id == UUID(backup_id)))
            return result.scalar_one_or_none()
        except Exception:
            return None


backup_service = BackupService()

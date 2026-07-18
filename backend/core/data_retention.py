"""
Data retention and purge job for automated cleanup of old records.
Purges episodic/audit records older than the configured retention period.
Supports filesystem JSON files and database tables.
"""
from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

log = logging.getLogger(__name__)


class DataRetentionPolicy:
    """Manages data retention policies and executes purge jobs."""

    def __init__(self, storage_dir: str = "data/retention"):
        self._storage_dir = Path(storage_dir)
        self._storage_dir.mkdir(parents=True, exist_ok=True)
        self._config_file = self._storage_dir / "policies.json"
        self._policies: Dict[str, int] = self._load_policies()

    def _load_policies(self) -> Dict[str, int]:
        defaults = {
            "episodic_records": 90,
            "audit_logs": 90,
            "telemetry_metrics": 180,
            "replay_data": 30,
            "event_history": 90,
            "temporary_uploads": 7,
            "mission_executions": 365,
            "cost_tracking": 730,
            "connector_logs": 90,
        }
        if self._config_file.exists():
            try:
                stored = json.loads(self._config_file.read_text())
                defaults.update(stored)
            except Exception as exc:
                log.error("Failed to load retention policies: %s", exc)
        return defaults

    def _save_policies(self):
        self._config_file.write_text(json.dumps(self._policies, indent=2))

    def get_policy(self, category: str) -> int:
        return self._policies.get(category, 90)

    def set_policy(self, category: str, days: int):
        self._policies[category] = max(1, days)
        self._save_policies()

    def list_policies(self) -> Dict[str, int]:
        return dict(self._policies)

    def purge_old_records(self, category: str, storage_path: str, date_field: str = "timestamp") -> int:
        """Purge filesystem records older than retention period. Returns count purged."""
        cutoff = datetime.now(timezone.utc) - timedelta(days=self.get_policy(category))
        cutoff_str = cutoff.isoformat()
        path = Path(storage_path)
        if not path.exists():
            return 0
        purged = 0
        if path.is_file() and path.suffix == ".json":
            try:
                data = json.loads(path.read_text())
                if isinstance(data, list):
                    original_len = len(data)
                    data = [r for r in data if r.get(date_field, "") >= cutoff_str]
                    purged = original_len - len(data)
                    path.write_text(json.dumps(data, indent=2, default=str))
            except Exception as exc:
                log.error("Failed to purge %s: %s", category, exc)
        elif path.is_dir():
            for f in path.glob("*.json"):
                try:
                    data = json.loads(f.read_text())
                    if isinstance(data, list):
                        original_len = len(data)
                        data = [r for r in data if r.get(date_field, "") >= cutoff_str]
                        purged += original_len - len(data)
                        f.write_text(json.dumps(data, indent=2, default=str))
                except Exception as exc:
                    log.error("Failed to purge %s: %s", f.name, exc)
        return purged

    async def purge_database_table(
        self,
        category: str,
        session_factory: Any,
        table_model: Any,
        date_column: str = "created_at",
        batch_size: int = 1000,
    ) -> int:
        """Purge database table rows older than retention period. Returns count purged."""
        cutoff = datetime.now(timezone.utc) - timedelta(days=self.get_policy(category))
        total_purged = 0
        try:
            async with session_factory() as session:
                while True:
                    stmt = (
                        __import__("sqlalchemy")
                        .sql.delete(table_model)
                        .where(getattr(table_model, date_column) < cutoff)
                        .limit(batch_size)
                    )
                    result = await session.execute(stmt)
                    await session.commit()
                    if result.rowcount == 0:
                        break
                    total_purged += result.rowcount
        except Exception as exc:
            log.error("Failed to purge database table %s: %s", category, exc)
        return total_purged

    def purge_missions(self) -> Dict[str, int]:
        """Run purge across all mission-related filesystem stores."""
        from backend.mission.state import MissionTimeline
        counts = {}
        counts["episodic"] = self.purge_old_records("episodic_records", "data/episodic")
        counts["events"] = self.purge_old_records("event_history", "data/events")
        counts["replay"] = self.purge_old_records("replay_data", "data/replay")
        return counts


# Singleton
_retention: Optional[DataRetentionPolicy] = None


def get_retention_policy() -> DataRetentionPolicy:
    global _retention
    if _retention is None:
        _retention = DataRetentionPolicy()
    return _retention

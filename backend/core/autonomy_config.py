"""
Runtime-configurable autonomy thresholds.
Allows admin to tune autonomous behavior without code changes.
"""
from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Dict, Optional

log = logging.getLogger(__name__)

DEFAULT_THRESHOLDS: Dict[str, Any] = {
    "max_concurrent_missions": 5,
    "auto_approve_threshold": 0.85,
    "max_retries_per_stage": 3,
    "cooldown_seconds": 60,
    "require_human_approval": True,
    "confidence_threshold": 0.7,
    "max_iterations_per_mission": 10,
    "auto_resolve_conflicts": False,
    "max_parallel_workers": 4,
    "staging_auto_deploy": False,
}


class AutonomyConfig:
    """Runtime-configurable autonomy thresholds with file persistence."""

    def __init__(self, storage_path: str = "data/config/autonomy.json"):
        self._path = Path(storage_path)
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._config: Dict[str, Any] = {}
        self._load()

    def _load(self):
        if self._path.exists():
            try:
                self._config = json.loads(self._path.read_text())
            except Exception as exc:
                log.error("Failed to load autonomy config: %s", exc)
                self._config = {}
        for key, val in DEFAULT_THRESHOLDS.items():
            self._config.setdefault(key, val)
        self._save()

    def _save(self):
        self._path.write_text(json.dumps(self._config, indent=2))

    def get(self, key: str, default=None):
        return self._config.get(key, default)

    def set(self, key: str, value: Any) -> bool:
        if key not in DEFAULT_THRESHOLDS:
            return False
        self._config[key] = value
        self._save()
        return True

    def get_all(self) -> Dict[str, Any]:
        return dict(self._config)

    def reset(self, key: str) -> bool:
        if key in DEFAULT_THRESHOLDS:
            self._config[key] = DEFAULT_THRESHOLDS[key]
            self._save()
            return True
        return False

    def reset_all(self):
        self._config = dict(DEFAULT_THRESHOLDS)
        self._save()


# Singleton
_autonomy_config: Optional[AutonomyConfig] = None


def get_autonomy_config() -> AutonomyConfig:
    global _autonomy_config
    if _autonomy_config is None:
        _autonomy_config = AutonomyConfig()
    return _autonomy_config

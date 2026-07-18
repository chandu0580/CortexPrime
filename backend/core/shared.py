from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

log = logging.getLogger(__name__)


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def load_json(path: Path) -> List[Dict[str, Any]]:
    try:
        if path.exists():
            with open(path) as f:
                return json.load(f)
    except Exception as exc:
        log.error("Failed to load %s: %s", path.name, exc)
    return []


def save_json(path: Path, data: List[Dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w") as f:
        json.dump(data, f, indent=2, default=str)


# ── Pipeline state machine ──────────────────────────────────────────────────

PIPELINE_VALID_TRANSITIONS: dict[str, list[str]] = {
    "pending":   ["running", "cancelled"],
    "running":   ["paused", "completed", "failed", "cancelled"],
    "paused":    ["running", "cancelled"],
    "completed": [],
    "failed":    [],
    "cancelled": [],
}


def pipeline_can_transition(current: str, target: str) -> bool:
    return target in PIPELINE_VALID_TRANSITIONS.get(current, [])


def pipeline_is_terminal(state: str) -> bool:
    return state in ("completed", "failed", "cancelled")

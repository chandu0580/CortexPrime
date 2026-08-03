"""
Enterprise Docker Container Health Monitor
=============================================

Detects real container-health problems on the real, already-connected
Docker daemon (backend.connectors.docker.DockerConnector) — the classic,
common operational finding: a container stuck restarting in a crash-loop,
a container killed by the OOM killer, or a container that died and has no
restart policy to bring it back.

Confirmed genuinely greenfield before building this: DockerConnector
already exposed list_containers()/get_container() (added for dashboard
intelligence in enterprise_infrastructure_intelligence.py), but grepping
backend/services/*.py found no aggregation logic anywhere that reasons
over container state *changes* between observations — every existing
consumer just tracks the latest snapshot, none of them compute a
restart-count delta or flag a repeating crash-loop pattern.

Same shape as every other detector this session: check_all_containers()
records every currently-detected gap set to history (dashboard
visibility), and only a genuinely NEW gap signature for a container files
a ticket via the alert correlator. The "actually fix it" half —
enterprise_docker_health_fix_executor.restart_crashlooping_container — is
gated through the real Approval Center, same as every other detector that
touches live infrastructure state.

Unlike branch-protection/vulnerability/credential-expiry (one-shot config
facts, checked at startup + on-demand), a crash-looping container is
actively bad *right now* — this is wired as a genuine continuous
EnterpriseWatcher (backend.services.enterprise_watchers), reusing
WatcherManager's existing generic poll-loop machinery rather than a
one-shot startup check.
"""
from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

log = logging.getLogger(__name__)

_DATA_DIR = Path(__file__).resolve().parent.parent / "data"
_DOCKER_HEALTH_HISTORY_FILE = _DATA_DIR / "docker_health_history.json"
MAX_DOCKER_HEALTH_HISTORY = 500

# Number of restarts within one poll interval that counts as a crash-loop.
CRASH_LOOP_RESTART_THRESHOLD = int(os.getenv("DOCKER_HEALTH_CRASH_LOOP_THRESHOLD", "3"))

# This repo's own data-plane containers — restarting one of these affects
# live running state (dropped connections, brief unavailability), unlike a
# disposable/dev container, so the fix executor escalates risk for these.
CRITICAL_CONTAINER_NAME_HINTS = ("postgres", "redis", "rabbitmq", "neo4j")

_SEVERITY_RANK = {"low": 0, "medium": 1, "high": 2, "critical": 3}
_SEVERITY_THRESHOLD_RANK = _SEVERITY_RANK["medium"]


def _load_json(path: Path) -> List[Dict[str, Any]]:
    try:
        if path.exists():
            with open(path) as f:
                return json.load(f)
    except Exception as exc:
        log.warning("Failed to load %s: %s", path.name, exc)
    return []


def _save_json(path: Path, data: List[Dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with open(path, "w") as f:
            json.dump(data, f, indent=2)
    except Exception as exc:
        log.warning("Failed to save %s: %s", path.name, exc)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def is_critical_container(name: str) -> bool:
    lowered = name.lower()
    return any(hint in lowered for hint in CRITICAL_CONTAINER_NAME_HINTS)


def assess_container_health(
    prev: Optional[Dict[str, Any]],
    curr: Dict[str, Any],
) -> List[Dict[str, str]]:
    """Turn a container's previous and current snapshot into a list of
    concrete, factual gaps — no LLM needed, this is a structural state
    comparison, not causal reasoning.

    prev/curr are dicts shaped like DockerConnector.list_containers()
    entries (name, status, restart_count, oom_killed, exit_code,
    started_at, host_config.restart_policy). prev is None the first time a
    container is observed — no delta can be computed yet, so no crash-loop
    gap is raised on that first check (avoids a false positive on startup).
    """
    gaps: List[Dict[str, str]] = []

    if prev is not None:
        restart_delta = curr.get("restart_count", 0) - prev.get("restart_count", 0)
        if restart_delta >= CRASH_LOOP_RESTART_THRESHOLD:
            gaps.append({
                "gap": "crash_loop",
                "severity": "critical",
                "description": (
                    f"Container restarted {restart_delta} times since the last check "
                    f"(restart_count {prev.get('restart_count', 0)} -> {curr.get('restart_count', 0)})."
                ),
            })

    # OOMKilled reflects the *current* State — only a genuinely new
    # incarnation's OOM kill (started_at changed, or this is the first
    # observation) counts as a fresh finding, not a stale flag we already
    # reported for the same container run.
    if curr.get("oom_killed") and (prev is None or prev.get("started_at") != curr.get("started_at")):
        gaps.append({
            "gap": "oom_killed",
            "severity": "critical",
            "description": (
                f"Container was killed by the OOM killer (exit_code={curr.get('exit_code', 0)}) — "
                "it ran out of available memory."
            ),
        })

    status = (curr.get("status") or "").lower()
    restart_policy = (curr.get("host_config", {}) or {}).get("restart_policy", "")
    if status in ("exited", "dead") and restart_policy in ("", "no"):
        gaps.append({
            "gap": "not_running_no_recovery",
            "severity": "high",
            "description": (
                f"Container is {status} with no restart policy configured — "
                "nothing will bring it back automatically."
            ),
        })

    return gaps


def _overall_severity(gaps: List[Dict[str, str]]) -> str:
    if not gaps:
        return "low"
    return max((g["severity"] for g in gaps), key=lambda s: _SEVERITY_RANK.get(s, 0))


def _gap_signature(gaps: List[Dict[str, str]]) -> str:
    return "+".join(sorted(g["gap"] for g in gaps))


class DockerHealthHistoryStore:
    """Durable record of container-health checks — every currently-detected
    gap set is recorded on every check (not just ticket-worthy ones) so the
    dashboard can show current container health, and the raw snapshot
    fields needed to compute the next check's restart-count delta."""

    def __init__(self, file_path: Optional[Path] = None) -> None:
        self._file_path = file_path or _DOCKER_HEALTH_HISTORY_FILE
        self._history: List[Dict[str, Any]] = _load_json(self._file_path)

    def last_signature(self, container_name: str) -> Optional[str]:
        for entry in self._history:
            if entry.get("container") == container_name:
                return entry.get("gap_signature")
        return None

    def last_snapshot(self, container_name: str) -> Optional[Dict[str, Any]]:
        for entry in self._history:
            if entry.get("container") == container_name:
                return entry.get("snapshot")
        return None

    def record(
        self,
        container: str,
        container_id: str,
        snapshot: Dict[str, Any],
        gaps: List[Dict[str, str]],
        severity: str,
        ticket_key: Optional[str] = None,
        fix_applied: bool = False,
    ) -> Dict[str, Any]:
        entry = {
            "container": container,
            "container_id": container_id,
            "snapshot": snapshot,
            "gaps": gaps,
            "gap_signature": _gap_signature(gaps),
            "severity": severity,
            "ticket_key": ticket_key,
            "fix_applied": fix_applied,
            "checked_at": _now(),
        }
        self._history = [e for e in self._history if e.get("container") != container]
        self._history.insert(0, entry)
        self._history = self._history[:MAX_DOCKER_HEALTH_HISTORY]
        _save_json(self._file_path, self._history)
        return entry

    def list_recent(self, limit: int = 20) -> List[Dict[str, Any]]:
        return self._history[:limit]

    def clear(self) -> None:
        self._history = []
        _save_json(self._file_path, [])


docker_health_history_store = DockerHealthHistoryStore()


async def check_all_containers(
    history_store: Optional[DockerHealthHistoryStore] = None,
) -> List[Dict[str, Any]]:
    """Check every real, currently-visible container's health once.
    Returns the recorded history entry for each container checked (skips
    entirely if the docker connector isn't registered — nothing to check,
    not an error)."""
    from backend.connectors.registry import connector_registry
    from backend.services.enterprise_alert_correlator import correlate_and_report
    from backend.services.enterprise_docker_health_incident_reporter import report_docker_health_incident

    hstore = history_store or docker_health_history_store
    results: List[Dict[str, Any]] = []

    docker = connector_registry.get("docker")
    if docker is None:
        return results

    try:
        containers = await docker.list_containers(all=True)
    except Exception as exc:
        log.warning("Docker health check failed to list containers: %s", exc)
        return results

    for curr in containers:
        name = curr.get("name", "unknown")
        container_id = curr.get("container_id", "")
        prev = hstore.last_snapshot(name)

        try:
            gaps = assess_container_health(prev, curr)
        except Exception as exc:
            log.warning("Docker health check raised for %s: %s", name, exc)
            continue

        severity = _overall_severity(gaps)
        signature = _gap_signature(gaps)

        ticket_key: Optional[str] = None
        if gaps and signature != hstore.last_signature(name) and _SEVERITY_RANK.get(severity, 0) >= _SEVERITY_THRESHOLD_RANK:
            summary = "; ".join(g["description"] for g in gaps)
            issue = await correlate_and_report(
                source="docker_health",
                service=name,
                summary=summary,
                reporter=lambda n=name, cid=container_id, g=gaps, s=severity: report_docker_health_incident(n, cid, g, s),
                severity="critical" if severity == "critical" else "warning",
            )
            ticket_key = (issue.get("key") or issue.get("ticket_key")) if issue else None

        entry = hstore.record(
            container=name,
            container_id=container_id,
            snapshot={
                "restart_count": curr.get("restart_count", 0),
                "started_at": curr.get("started_at", ""),
                "oom_killed": curr.get("oom_killed", False),
                "exit_code": curr.get("exit_code", 0),
                "status": curr.get("status", ""),
                "host_config": curr.get("host_config", {}),
            },
            gaps=gaps,
            severity=severity,
            ticket_key=ticket_key,
        )
        results.append(entry)

    return results

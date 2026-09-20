"""The connector health contract, reusable by every connector (Phase 11.1-K).

"Healthy" used to mean the process started. A connector's health now means
what an operator actually needs to know, derived from evidence each time:

    DISABLED                -- no connection is configured for this connector
    MISCONFIGURED           -- configured, but it cannot work as declared
                               (a capability contract conflicts, a required
                               permission is missing on every capability, the
                               composition failed)
    AUTHENTICATION_REQUIRED -- the credential could not be obtained or was rejected
    RATE_LIMITED            -- the platform or the provider is throttling it
    UNAVAILABLE             -- the provider could not be reached
    DEGRADED                -- reachable and authenticated, but some capabilities
                               are unavailable (named, with the reason)
    CONNECTED               -- every commissioned capability's requirements hold

The worst state wins. Every check is recorded with its evidence so the product
API can explain the state, and nothing in a check carries a credential.
"""

from __future__ import annotations

import logging
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Callable, Optional

__all__ = ["ConnectorHealthState", "HealthCheck", "ConnectorHealth", "ConnectorHealthMonitor",
           "worst"]

log = logging.getLogger(__name__)


class ConnectorHealthState(str, Enum):
    CONNECTED = "CONNECTED"
    DEGRADED = "DEGRADED"
    RATE_LIMITED = "RATE_LIMITED"
    UNAVAILABLE = "UNAVAILABLE"
    AUTHENTICATION_REQUIRED = "AUTHENTICATION_REQUIRED"
    MISCONFIGURED = "MISCONFIGURED"
    DISABLED = "DISABLED"


_SEVERITY = {
    ConnectorHealthState.CONNECTED: 0, ConnectorHealthState.DEGRADED: 1,
    ConnectorHealthState.RATE_LIMITED: 2, ConnectorHealthState.UNAVAILABLE: 3,
    ConnectorHealthState.AUTHENTICATION_REQUIRED: 4, ConnectorHealthState.MISCONFIGURED: 5,
    ConnectorHealthState.DISABLED: 6,
}


def worst(*states: ConnectorHealthState) -> ConnectorHealthState:
    return max(states, key=lambda s: _SEVERITY[s]) if states else ConnectorHealthState.CONNECTED


@dataclass(frozen=True)
class HealthCheck:
    name: str
    ok: bool
    state_if_failed: ConnectorHealthState
    detail: str = ""
    error_class: Optional[str] = None

    def to_dict(self) -> dict:
        return {"name": self.name, "ok": self.ok, "detail": self.detail[:300],
                "error_class": self.error_class,
                "state_if_failed": self.state_if_failed.value}


@dataclass(frozen=True)
class ConnectorHealth:
    connector_id: str
    tenant_id: Optional[str]
    state: ConnectorHealthState
    summary: str
    checks: tuple = ()
    available_capabilities: tuple = ()
    unavailable_capabilities: dict = field(default_factory=dict)
    checked_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    duration_seconds: float = 0.0

    @classmethod
    def from_checks(cls, connector_id: str, tenant_id: Optional[str], checks: list, *,
                    available: tuple = (), unavailable: Optional[dict] = None,
                    duration_seconds: float = 0.0) -> "ConnectorHealth":
        failed = [c for c in checks if not c.ok]
        unavailable = dict(unavailable or {})
        if not failed and not unavailable:
            state = ConnectorHealthState.CONNECTED
            summary = f"connected; {len(available)} capabilities available"
        else:
            state = worst(*[c.state_if_failed for c in failed]) if failed else \
                ConnectorHealthState.DEGRADED
            if unavailable and state is ConnectorHealthState.CONNECTED:
                state = ConnectorHealthState.DEGRADED
            first = failed[0] if failed else None
            summary = (f"{state.value.lower()}: {first.name}: {first.detail}" if first
                       else f"degraded: {len(unavailable)} capabilities unavailable")
        return cls(connector_id=connector_id, tenant_id=tenant_id, state=state,
                   summary=summary[:300], checks=tuple(checks),
                   available_capabilities=tuple(available), unavailable_capabilities=unavailable,
                   duration_seconds=round(duration_seconds, 3))

    @classmethod
    def disabled(cls, connector_id: str, reason: str) -> "ConnectorHealth":
        return cls(connector_id=connector_id, tenant_id=None, state=ConnectorHealthState.DISABLED,
                   summary=reason)

    def to_dict(self) -> dict:
        return {"connector": self.connector_id, "tenant_id": self.tenant_id,
                "state": self.state.value, "summary": self.summary, "checked_at": self.checked_at,
                "duration_seconds": self.duration_seconds,
                "available_capabilities": list(self.available_capabilities),
                "unavailable_capabilities": dict(self.unavailable_capabilities),
                "checks": [c.to_dict() for c in self.checks]}


class ConnectorHealthMonitor:
    """Runs each connector's probe at start and then every ``interval_seconds``.

    Probes are registered as callables returning ``ConnectorHealth``; a probe
    that raises yields MISCONFIGURED with the exception type (never its text,
    which could carry provider detail). The latest result per connector is kept
    and exported as a gauge per state, so health is visible on ``/metrics``.
    """

    def __init__(self, *, interval_seconds: float = 600.0, metrics: Optional[Any] = None) -> None:
        self._interval = max(30.0, float(interval_seconds))
        self._metrics = metrics
        self._probes: dict = {}
        self._latest: dict = {}
        self._lock = threading.Lock()
        self._stop = threading.Event()
        self._thread: Optional[threading.Thread] = None

    def register(self, connector_id: str, probe: Callable[[], ConnectorHealth]) -> None:
        self._probes[connector_id] = probe

    def set_static(self, health: ConnectorHealth) -> None:
        with self._lock:
            self._latest[health.connector_id] = health
        self._export(health)

    def check(self, connector_id: str) -> ConnectorHealth:
        probe = self._probes.get(connector_id)
        if probe is None:
            health = self._latest.get(connector_id) or ConnectorHealth.disabled(
                connector_id, "no connection is configured for this connector")
            return health
        started = time.monotonic()
        try:
            health = probe()
        except Exception as exc:  # noqa: BLE001 - a probe that fails is a finding
            log.warning("connector %s health probe raised %s", connector_id, type(exc).__name__)
            health = ConnectorHealth.from_checks(connector_id, None, [HealthCheck(
                "probe", False, ConnectorHealthState.MISCONFIGURED,
                f"the health probe could not run ({type(exc).__name__})")],
                duration_seconds=time.monotonic() - started)
        with self._lock:
            self._latest[connector_id] = health
        self._export(health)
        return health

    def check_all(self) -> dict:
        return {cid: self.check(cid) for cid in list(self._probes)}

    def latest(self) -> dict:
        with self._lock:
            return dict(self._latest)

    def start(self) -> None:
        if self._thread is not None:
            return

        def loop() -> None:
            while not self._stop.is_set():
                self.check_all()
                self._stop.wait(self._interval)

        self._thread = threading.Thread(target=loop, name="connector-health", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()

    def _export(self, health: ConnectorHealth) -> None:
        if self._metrics is None:
            return
        for state in ConnectorHealthState:
            self._metrics.gauge("connector.health", 1.0 if state is health.state else 0.0,
                                labels={"connector": health.connector_id, "state": state.value})

"""The seam Phase 3.4's Evidence Plane will observe execution through.

Why a port and not OpenTelemetry
----------------------------------
Wiring a tracer into the execution domain would make the domain depend on a
telemetry vendor, and the domain would then be untestable without one. It would
also put a decision that belongs to deployment -- which backend, what sampling,
what retention -- inside the rules about when a production change may run twice.

So execution announces facts to an observer it knows nothing about. Phase 3.4
implements the observer. Nothing in this module changes when it does.

Why the observer cannot influence anything
--------------------------------------------
Every method returns ``None`` and the runtime ignores exceptions from them
(``SafeObserver``). Observation must not be able to change what the runtime
decides, and a telemetry backend having a bad afternoon must not stop a
production run or, worse, cause one to be retried.

This is the opposite of the event stream, which is authoritative. Events are
facts the runtime stands behind; observations are a convenience for whoever is
watching. Losing an observation is survivable. Losing an event is not.
"""

from __future__ import annotations

import logging
from typing import Any, Mapping, Optional, Protocol, Sequence, runtime_checkable

__all__ = [
    "ExecutionObserver",
    "NullObserver",
    "SafeObserver",
    "CompositeObserver",
    "RecordingObserver",
]

log = logging.getLogger(__name__)


@runtime_checkable
class ExecutionObserver(Protocol):
    """What a watcher of the execution runtime may be told.

    Deliberately a flat set of named lifecycle moments rather than a generic
    ``emit(name, payload)``. A generic hook would let any caller invent a
    vocabulary, and the point of the seam is that Phase 3.4 can rely on these
    meaning the same thing every time.
    """

    def execution_started(self, execution_id: str, detail: Mapping[str, Any]) -> None: ...

    def execution_state_changed(
        self, execution_id: str, from_state: str, to_state: str, reason: Optional[str]
    ) -> None: ...

    def node_assigned(
        self, execution_id: str, node_id: str, worker_id: str, attempt: int
    ) -> None: ...

    def node_finished(
        self, execution_id: str, node_id: str, outcome: str, detail: Mapping[str, Any]
    ) -> None: ...

    def attempt_failed(
        self, execution_id: str, node_id: str, failure: Mapping[str, Any]
    ) -> None: ...

    def retry_decided(self, execution_id: str, decision: Mapping[str, Any]) -> None: ...

    def checkpoint_recorded(
        self, execution_id: str, checkpoint_id: str, label: str
    ) -> None: ...

    def lease_expired(self, execution_id: str, node_id: str, worker_id: str) -> None: ...

    def outcome_unknown(
        self, execution_id: str, node_id: str, detail: Mapping[str, Any]
    ) -> None: ...

    def recovery_decided(self, execution_id: str, decision: Mapping[str, Any]) -> None: ...

    def compensation_changed(
        self, execution_id: str, node_id: str, state: str, detail: Mapping[str, Any]
    ) -> None: ...


class NullObserver:
    """Observes nothing. The default, so the runtime never checks for None."""

    def execution_started(self, execution_id, detail) -> None: ...
    def execution_state_changed(self, execution_id, from_state, to_state, reason) -> None: ...
    def node_assigned(self, execution_id, node_id, worker_id, attempt) -> None: ...
    def node_finished(self, execution_id, node_id, outcome, detail) -> None: ...
    def attempt_failed(self, execution_id, node_id, failure) -> None: ...
    def retry_decided(self, execution_id, decision) -> None: ...
    def checkpoint_recorded(self, execution_id, checkpoint_id, label) -> None: ...
    def lease_expired(self, execution_id, node_id, worker_id) -> None: ...
    def outcome_unknown(self, execution_id, node_id, detail) -> None: ...
    def recovery_decided(self, execution_id, decision) -> None: ...
    def compensation_changed(self, execution_id, node_id, state, detail) -> None: ...


class SafeObserver:
    """Wraps an observer so watching cannot break running.

    A telemetry exporter that throws must not fail a production deployment, and
    it must certainly not cause one to be retried. Failures are logged and
    dropped.
    """

    def __init__(self, inner: Any) -> None:
        self._inner = inner

    def __getattr__(self, name: str):
        target = getattr(self._inner, name, None)
        if target is None:
            return lambda *args, **kwargs: None

        def guarded(*args, **kwargs):
            try:
                target(*args, **kwargs)
            except Exception:  # noqa: BLE001 - observation must never propagate
                log.warning("execution observer %s failed; continuing", name, exc_info=True)
            return None

        return guarded


class CompositeObserver:
    """Fans one lifecycle moment out to several observers."""

    def __init__(self, observers: Sequence[Any]) -> None:
        self._observers = tuple(SafeObserver(o) for o in observers)

    def __getattr__(self, name: str):
        def fan_out(*args, **kwargs):
            for observer in self._observers:
                getattr(observer, name)(*args, **kwargs)
            return None

        return fan_out


class RecordingObserver:
    """Keeps what it was told, in order. For tests and local inspection.

    Not the Evidence Plane and not a substitute for one -- it holds everything
    in memory forever, which is fine for a test and wrong for a platform.
    """

    def __init__(self) -> None:
        self.calls: list = []

    def __getattr__(self, name: str):
        if name.startswith("_"):
            raise AttributeError(name)

        def record(*args, **kwargs):
            self.calls.append((name, args, kwargs))
            return None

        return record

    def names(self) -> tuple:
        return tuple(name for name, _, _ in self.calls)

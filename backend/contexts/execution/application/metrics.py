"""The metrics seam. A Protocol and three implementations, no telemetry platform.

Why a seam and not a library
------------------------------
No Prometheus, no OpenTelemetry, no StatsD, and no exporter. This context does
for measurement what it already does for workers: names what it needs and lets
the composition root decide what provides it. A runtime that imported a metrics
client would couple every deployment to that client's version, its transport,
and its failure modes.

Why metrics rather than events for these
------------------------------------------
"Most nodes are not dispatchable yet" is the ordinary state of a healthy run.
Emitting a domain event for each would bury the facts an operator reads during an
incident under a stream of things merely being normal. Counters answer "how
often" without competing with the log for attention.

Measurement never changes an outcome
--------------------------------------
``SafeMetrics`` contains every exception a recorder raises, for the same reason
``SafeObserver`` does: a monitoring backend being down must never be able to fail
an execution, and a metrics call sitting in an error path is exactly where that
would happen. It and ``NullMetrics`` now live in
``backend.platform.observability`` and are re-exported here — Connectivity needs
the same guarantee, and a second copy of it would be one place to fix and
another to leave broken.
"""

from __future__ import annotations

import logging
import threading
from typing import Any, Mapping, Optional

from backend.platform.observability.metrics import (
    MetricsRecorder,
    NullMetrics,
    SafeMetrics,
)

__all__ = [
    "ExecutionMetrics",
    "NullMetrics",
    "SafeMetrics",
    "RecordingMetrics",
    "METRIC_NAMES",
]

log = logging.getLogger(__name__)

#: The vocabulary this phase records. Named as constants so a typo is an
#: ``AttributeError`` at import rather than a counter nobody ever sees increment.
METRIC_NAMES = (
    "execution.dispatch.cycles",
    "execution.dispatch.candidates",
    "execution.dispatch.refused",
    "execution.lease.acquired",
    "execution.lease.conflict",
    "execution.lease.expired",
    "execution.invocation.admitted",
    "execution.invocation.refused",
    "execution.outcome.success",
    "execution.outcome.failure",
    "execution.outcome.unknown",
    "execution.result.late",
    "execution.result.duplicate",
    "execution.retry.decided",
    "execution.retry.refused",
    "execution.recovery.planned",
    "execution.compensation.started",
    "execution.compensation.concluded",
    "execution.compensation.unresolved",
    "execution.completed",
    "execution.failed",
)


#: ``NullMetrics`` and ``SafeMetrics`` live in ``backend.platform.observability``
#: because Connectivity needs them too, and a context importing another
#: context's helper is the boundary violation the fitness functions refuse.
#: ``ExecutionMetrics`` stays here: it is an alias for the platform Protocol
#: under the name this context has always used, so existing type annotations and
#: ``isinstance`` checks keep working.
ExecutionMetrics = MetricsRecorder


class RecordingMetrics:
    """Keeps counts in memory. For reasoning about a lifecycle, not for production."""

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self.counters: dict = {}
        self.observations: dict = {}
        self.gauges: dict = {}

    @staticmethod
    def _key(name: str, labels: Optional[Mapping[str, str]]) -> tuple:
        return (name, tuple(sorted((labels or {}).items())))

    def increment(
        self, name: str, *, value: int = 1, labels: Optional[Mapping[str, str]] = None
    ) -> None:
        with self._lock:
            key = self._key(name, labels)
            self.counters[key] = self.counters.get(key, 0) + value

    def observe(
        self, name: str, seconds: float, *, labels: Optional[Mapping[str, str]] = None
    ) -> None:
        with self._lock:
            self.observations.setdefault(self._key(name, labels), []).append(seconds)

    def gauge(
        self, name: str, value: float, *, labels: Optional[Mapping[str, str]] = None
    ) -> None:
        with self._lock:
            self.gauges[self._key(name, labels)] = value

    def count(self, name: str, **labels: str) -> int:
        with self._lock:
            return self.counters.get(self._key(name, labels or None), 0)

    def total(self, name: str) -> int:
        """Every count for a metric, across all label sets."""
        with self._lock:
            return sum(v for (n, _), v in self.counters.items() if n == name)

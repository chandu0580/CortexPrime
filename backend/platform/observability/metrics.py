"""The metrics seam: a Protocol and two implementations, no telemetry platform.

No Prometheus, no OpenTelemetry, no StatsD, and no exporter. The platform names
what it needs and lets the composition root decide what provides it; importing a
metrics client here would couple every deployment to that client's version, its
transport and its failure modes.

Measurement never changes an outcome
--------------------------------------
``SafeMetrics`` contains every exception a recorder raises. A monitoring backend
being down must never be able to fail an execution — and a metrics call sitting
in an error path is exactly where an unguarded raise would replace the real
error with a reporting error.
"""

from __future__ import annotations

import logging
from typing import Any, Mapping, Optional, Protocol, runtime_checkable

__all__ = ["MetricsRecorder", "NullMetrics", "SafeMetrics"]

log = logging.getLogger(__name__)


@runtime_checkable
class MetricsRecorder(Protocol):
    """What a recorder must offer. Three verbs, deliberately.

    ``labels`` carries dimensions an operator groups by — a tenant, a reason —
    and never a principal id, a payload, or anything else that would turn a
    metrics backend into a place customer data ends up.
    """

    def increment(
        self, name: str, *, value: int = 1, labels: Optional[Mapping[str, str]] = None
    ) -> None: ...

    def observe(
        self, name: str, seconds: float, *, labels: Optional[Mapping[str, str]] = None
    ) -> None: ...

    def gauge(
        self, name: str, value: float, *, labels: Optional[Mapping[str, str]] = None
    ) -> None: ...


class NullMetrics:
    """Records nothing. The default, so nothing is required to be wired."""

    def increment(
        self, name: str, *, value: int = 1, labels: Optional[Mapping[str, str]] = None
    ) -> None:
        return None

    def observe(
        self, name: str, seconds: float, *, labels: Optional[Mapping[str, str]] = None
    ) -> None:
        return None

    def gauge(
        self, name: str, value: float, *, labels: Optional[Mapping[str, str]] = None
    ) -> None:
        return None


class SafeMetrics:
    """Wraps a recorder so it cannot affect the work being measured."""

    def __init__(self, inner: Optional[Any] = None) -> None:
        self._inner = inner or NullMetrics()

    def increment(
        self, name: str, *, value: int = 1, labels: Optional[Mapping[str, str]] = None
    ) -> None:
        self._guarded("increment", name, value=value, labels=labels)

    def observe(
        self, name: str, seconds: float, *, labels: Optional[Mapping[str, str]] = None
    ) -> None:
        self._guarded("observe", name, seconds, labels=labels)

    def gauge(
        self, name: str, value: float, *, labels: Optional[Mapping[str, str]] = None
    ) -> None:
        self._guarded("gauge", name, value, labels=labels)

    def _guarded(self, method: str, *args: Any, **kwargs: Any) -> None:
        try:
            getattr(self._inner, method)(*args, **kwargs)
        except Exception:  # noqa: BLE001 - measurement never changes an outcome
            log.debug("metrics %s failed", method, exc_info=True)

"""A ``MetricsRecorder`` over ``prometheus_client`` -- the fabric's metrics, emitted.

The metrics seam (``backend.platform.observability.metrics``) names what the
fabric measures and deliberately imports no telemetry client. Until Phase
11.1-K no composition supplied a recorder, so every ``increment`` in the
credential broker, the transport broker, the adapters and the gateway went to
``None`` (connector reality audit, section 11). This is the recorder the
governed runtime now composes.

Name mapping
--------------
Fabric names are dotted (``credential.expired``). Prometheus names are
``cortex_<dotted_with_underscores>`` plus ``_total`` for counters and
``_seconds`` for observations. A name keeps the label set it was first used
with; a later call with other labels is normalised to that set (missing labels
become ``""``, extra labels are dropped) rather than raising, because a metrics
call must never change an outcome.

What never becomes a label
----------------------------
The seam's contract already forbids principals and payloads. This recorder adds
a mechanical backstop: label values are truncated to 64 characters and label
*names* on a deny list (anything that smells of a secret, a token or a
principal) are dropped.
"""

from __future__ import annotations

import logging
import re
import threading
from typing import Any, Mapping, Optional

__all__ = ["PrometheusMetricsRecorder", "prometheus_name"]

log = logging.getLogger(__name__)

_DENIED_LABEL_PARTS = ("token", "secret", "password", "credential_value", "principal",
                       "authorization", "api_key", "cookie")
_MAX_VALUE = 64
_BUCKETS = (0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0, 30.0, 60.0)


def prometheus_name(name: str) -> str:
    cleaned = re.sub(r"[^a-zA-Z0-9_]", "_", str(name)).strip("_").lower()
    return f"cortex_{cleaned}"


class PrometheusMetricsRecorder:
    """Lazily creates one Prometheus family per fabric name."""

    def __init__(self, registry: Optional[Any] = None) -> None:
        from prometheus_client import REGISTRY

        self._registry = registry if registry is not None else REGISTRY
        self._families: dict = {}
        self._labels: dict = {}
        self._lock = threading.Lock()

    # -- MetricsRecorder -----------------------------------------------------

    def increment(self, name: str, *, value: int = 1,
                  labels: Optional[Mapping[str, str]] = None) -> None:
        family, values = self._family("counter", name, labels)
        (family.labels(*values) if values is not None else family).inc(max(0, value))

    def observe(self, name: str, seconds: float, *,
                labels: Optional[Mapping[str, str]] = None) -> None:
        family, values = self._family("histogram", name, labels)
        (family.labels(*values) if values is not None else family).observe(max(0.0, float(seconds)))

    def gauge(self, name: str, value: float, *,
              labels: Optional[Mapping[str, str]] = None) -> None:
        family, values = self._family("gauge", name, labels)
        (family.labels(*values) if values is not None else family).set(float(value))

    # -- internals -------------------------------------------------------------

    def _family(self, kind: str, name: str, labels: Optional[Mapping[str, str]]):
        from prometheus_client import Counter, Gauge, Histogram

        clean = {str(k): str(v)[:_MAX_VALUE] for k, v in dict(labels or {}).items()
                 if re.fullmatch(r"[a-zA-Z_][a-zA-Z0-9_]*", str(k))
                 and not any(part in str(k).lower() for part in _DENIED_LABEL_PARTS)}
        key = (kind, name)
        with self._lock:
            family = self._families.get(key)
            if family is None:
                label_names = tuple(sorted(clean))
                base = prometheus_name(name)
                doc = f"CortexPrime fabric metric {name}"
                try:
                    if kind == "counter":
                        family = Counter(base, doc, label_names, registry=self._registry)
                    elif kind == "histogram":
                        family = Histogram(base + "_seconds", doc, label_names,
                                           registry=self._registry, buckets=_BUCKETS)
                    else:
                        family = Gauge(base, doc, label_names, registry=self._registry)
                except ValueError:
                    # The name is already registered by another module (or as
                    # another kind). Measurement never changes an outcome: this
                    # name becomes a no-op, said once.
                    log.warning("metric %s could not be registered; recording it is disabled", base)
                    family, label_names = _Noop(), ()
                self._families[key] = family
                self._labels[key] = label_names
            label_names = self._labels[key]
        if not label_names:
            return family, None
        return family, tuple(clean.get(n, "") for n in label_names)


class _Noop:
    def labels(self, *_args: Any) -> "_Noop":
        return self

    def inc(self, *_args: Any) -> None:
        return None

    def observe(self, *_args: Any) -> None:
        return None

    def set(self, *_args: Any) -> None:
        return None

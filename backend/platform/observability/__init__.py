"""Measurement infrastructure. Shared, because more than one context measures.

This exists because Phase 5.3 needed a metrics seam in Connectivity and one
already existed in Execution. Two choices were available: import across a
bounded-context boundary, or duplicate fifteen lines of "a metrics backend must
never fail an execution". The first is a boundary violation the fitness
functions correctly refuse; the second is the same rule written twice, which is
one place for it to be fixed and another for it to stay broken.

So the generic part moved here — ``platform`` is what every context may depend
on — and Execution's ``application/metrics.py`` re-exports it alongside the
vocabulary that is genuinely Execution's own.
"""

from backend.platform.observability.metrics import (
    MetricsRecorder,
    NullMetrics,
    SafeMetrics,
)

__all__ = ["MetricsRecorder", "NullMetrics", "SafeMetrics"]
